"""
Gemini AI integration for code execution with S3 persistence.
"""

import json
import subprocess
import tempfile
import os
import shutil
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types
import boto3
from botocore.exceptions import ClientError

# S3 client
s3 = boto3.client("s3", region_name=os.environ.get("AWS_REGION", "us-east-1"))
FILES_BUCKET = os.environ.get("FILES_BUCKET", "delta3-files")

# Tool definitions for Gemini
TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="execute_python",
                description="Execute Python code. Returns stdout, stderr, and exit code.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "code": types.Schema(
                            type=types.Type.STRING,
                            description="Python code to execute"
                        )
                    },
                    required=["code"]
                )
            ),
            types.FunctionDeclaration(
                name="execute_shell",
                description="Execute a shell command. Returns stdout, stderr, and exit code.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "command": types.Schema(
                            type=types.Type.STRING,
                            description="Shell command to run"
                        )
                    },
                    required=["command"]
                )
            ),
            types.FunctionDeclaration(
                name="write_file",
                description="Write content to a file. Creates parent directories if needed. Files persist across sessions.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "path": types.Schema(
                            type=types.Type.STRING,
                            description="File path (e.g., 'project/main.py')"
                        ),
                        "content": types.Schema(
                            type=types.Type.STRING,
                            description="Content to write"
                        )
                    },
                    required=["path", "content"]
                )
            ),
            types.FunctionDeclaration(
                name="read_file",
                description="Read content from a file.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "path": types.Schema(
                            type=types.Type.STRING,
                            description="File path to read"
                        )
                    },
                    required=["path"]
                )
            ),
            types.FunctionDeclaration(
                name="list_files",
                description="List files in a directory.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "path": types.Schema(
                            type=types.Type.STRING,
                            description="Directory path (default: current directory)"
                        )
                    },
                    required=[]
                )
            ),
            types.FunctionDeclaration(
                name="delete_file",
                description="Delete a file.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "path": types.Schema(
                            type=types.Type.STRING,
                            description="File path to delete"
                        )
                    },
                    required=["path"]
                )
            )
        ]
    )
]

SYSTEM_PROMPT = """You are an AI coding assistant with a persistent workspace. You can execute Python code, run shell commands, and manage files.

IMPORTANT:
1. Your workspace persists between sessions - files you create will be there next time
2. Use write_file to save code, then execute_python or execute_shell to run it
3. Use list_files to see what files already exist in your workspace
4. Working directory is your personal workspace

When asked to write code:
1. First check if relevant files already exist with list_files
2. Write the file with write_file
3. Execute it with execute_python or execute_shell
4. Report the results

Always verify your work by checking outputs."""


class PersistentCodeExecutor:
    """Executes code with S3-backed persistent storage."""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.workspace = f"/tmp/workspace_{user_id.replace('@', '_').replace('.', '_')}"
        self.s3_prefix = f"users/{user_id}/workspace/"
        self._setup_workspace()
    
    def _setup_workspace(self):
        """Setup workspace by restoring files from S3."""
        # Clean and create workspace
        if os.path.exists(self.workspace):
            shutil.rmtree(self.workspace)
        os.makedirs(self.workspace, exist_ok=True)
        
        # Restore files from S3
        try:
            paginator = s3.get_paginator('list_objects_v2')
            for page in paginator.paginate(Bucket=FILES_BUCKET, Prefix=self.s3_prefix):
                for obj in page.get('Contents', []):
                    key = obj['Key']
                    relative_path = key.replace(self.s3_prefix, '')
                    if relative_path:
                        local_path = os.path.join(self.workspace, relative_path)
                        os.makedirs(os.path.dirname(local_path), exist_ok=True)
                        s3.download_file(FILES_BUCKET, key, local_path)
        except ClientError:
            pass  # No files yet, that's okay
    
    def _sync_to_s3(self, path: str, content: str = None):
        """Sync a file to S3."""
        # Normalize path
        if path.startswith("/"):
            path = path[1:]
        if path.startswith("tmp/workspace"):
            path = path.split("/", 3)[-1] if len(path.split("/")) > 3 else ""
        
        s3_key = f"{self.s3_prefix}{path}"
        
        try:
            if content is not None:
                s3.put_object(
                    Bucket=FILES_BUCKET,
                    Key=s3_key,
                    Body=content.encode('utf-8'),
                    ContentType='text/plain'
                )
            else:
                # Read from local file
                local_path = os.path.join(self.workspace, path)
                if os.path.exists(local_path):
                    s3.upload_file(local_path, FILES_BUCKET, s3_key)
        except ClientError as e:
            print(f"S3 sync error: {e}")
    
    def _delete_from_s3(self, path: str):
        """Delete a file from S3."""
        if path.startswith("/"):
            path = path[1:]
        
        s3_key = f"{self.s3_prefix}{path}"
        
        try:
            s3.delete_object(Bucket=FILES_BUCKET, Key=s3_key)
        except ClientError:
            pass
    
    def execute_python(self, code: str) -> Dict[str, Any]:
        """Execute Python code."""
        try:
            # Write to temp file
            with tempfile.NamedTemporaryFile(
                mode="w", 
                suffix=".py", 
                dir=self.workspace,
                delete=False
            ) as f:
                f.write(code)
                script_path = f.name
            
            # Execute
            result = subprocess.run(
                ["python3", script_path],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.workspace,
                env={**os.environ, "PYTHONPATH": self.workspace}
            )
            
            # Cleanup temp script
            os.unlink(script_path)
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Execution timed out (60s limit)", "exit_code": -1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "exit_code": -1}
    
    def execute_shell(self, command: str) -> Dict[str, Any]:
        """Execute shell command."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=self.workspace
            )
            
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"stdout": "", "stderr": "Command timed out (60s limit)", "exit_code": -1}
        except Exception as e:
            return {"stdout": "", "stderr": str(e), "exit_code": -1}
    
    def write_file(self, path: str, content: str) -> Dict[str, Any]:
        """Write file to workspace and sync to S3."""
        try:
            # Normalize path
            clean_path = path.lstrip("/")
            full_path = os.path.join(self.workspace, clean_path)
            os.makedirs(os.path.dirname(full_path) if os.path.dirname(full_path) else self.workspace, exist_ok=True)
            
            with open(full_path, "w") as f:
                f.write(content)
            
            # Sync to S3 for persistence
            self._sync_to_s3(clean_path, content)
            
            return {"success": True, "path": clean_path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """Read file from workspace."""
        try:
            clean_path = path.lstrip("/")
            full_path = os.path.join(self.workspace, clean_path)
            
            with open(full_path, "r") as f:
                content = f.read()
            
            return {"success": True, "content": content}
        except FileNotFoundError:
            return {"success": False, "error": f"File not found: {path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def list_files(self, path: str = "") -> Dict[str, Any]:
        """List files in directory."""
        try:
            clean_path = path.lstrip("/") if path else ""
            full_path = os.path.join(self.workspace, clean_path) if clean_path else self.workspace
            
            if not os.path.exists(full_path):
                return {"success": True, "files": []}
            
            files = []
            for name in os.listdir(full_path):
                item_path = os.path.join(full_path, name)
                # Skip temp files
                if name.startswith("tmp") and name.endswith(".py"):
                    continue
                files.append({
                    "name": name,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None
                })
            
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def delete_file(self, path: str) -> Dict[str, Any]:
        """Delete file from workspace and S3."""
        try:
            clean_path = path.lstrip("/")
            full_path = os.path.join(self.workspace, clean_path)
            
            if os.path.exists(full_path):
                if os.path.isdir(full_path):
                    shutil.rmtree(full_path)
                else:
                    os.unlink(full_path)
            
            # Delete from S3
            self._delete_from_s3(clean_path)
            
            return {"success": True, "path": clean_path}
        except Exception as e:
            return {"success": False, "error": str(e)}


class GeminiAgent:
    """Gemini-powered coding agent with persistent environment."""
    
    def __init__(self, api_key: str, user_id: str, chat_history: List[Dict] = None):
        self.client = genai.Client(api_key=api_key)
        self.user_id = user_id
        self.executor = PersistentCodeExecutor(user_id)
        self.history: List[types.Content] = []
        
        # Load chat history into context
        if chat_history:
            self._load_history(chat_history)
    
    def _load_history(self, chat_history: List[Dict]):
        """Load previous chat history into Gemini context."""
        # Only load recent messages to stay within context limits
        recent = chat_history[-10:] if len(chat_history) > 10 else chat_history
        
        for msg in recent:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            
            if role == "user":
                self.history.append(types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=content)]
                ))
            elif role == "assistant":
                self.history.append(types.Content(
                    role="model",
                    parts=[types.Part.from_text(text=content)]
                ))
    
    def execute_tool(self, name: str, args: Dict) -> str:
        """Execute a tool and return result as string."""
        if name == "execute_python":
            result = self.executor.execute_python(args["code"])
            output = ""
            if result["stdout"]:
                output += f"Output:\n{result['stdout']}"
            if result["stderr"]:
                output += f"\nErrors:\n{result['stderr']}"
            if not output:
                output = f"Code executed (exit code: {result['exit_code']})"
            return output
        
        elif name == "execute_shell":
            result = self.executor.execute_shell(args["command"])
            output = ""
            if result["stdout"]:
                output += result["stdout"]
            if result["stderr"]:
                output += f"\nErrors:\n{result['stderr']}"
            if not output:
                output = f"Command completed (exit code: {result['exit_code']})"
            return output
        
        elif name == "write_file":
            result = self.executor.write_file(args["path"], args["content"])
            if result["success"]:
                return f"✅ File saved: {result['path']} (persisted to storage)"
            return f"❌ Error: {result['error']}"
        
        elif name == "read_file":
            result = self.executor.read_file(args["path"])
            if result["success"]:
                return result["content"]
            return f"❌ Error: {result['error']}"
        
        elif name == "list_files":
            result = self.executor.list_files(args.get("path", ""))
            if result["success"]:
                if not result["files"]:
                    return "📁 Directory is empty (no files yet)"
                return "Files in workspace:\n" + "\n".join(
                    f"{'📁' if f['type'] == 'directory' else '📄'} {f['name']}"
                    + (f" ({f['size']} bytes)" if f.get('size') else "")
                    for f in result["files"]
                )
            return f"❌ Error: {result['error']}"
        
        elif name == "delete_file":
            result = self.executor.delete_file(args["path"])
            if result["success"]:
                return f"🗑️ Deleted: {result['path']}"
            return f"❌ Error: {result['error']}"
        
        return f"Unknown tool: {name}"
    
    def process_message(self, user_message: str) -> Dict[str, Any]:
        """Process user message and return response with tool calls."""
        # Add user message to history
        self.history.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_message)]
        ))
        
        tool_calls = []
        max_iterations = 10
        final_text = ""
        
        for _ in range(max_iterations):
            # Generate response
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=self.history,
                    config=types.GenerateContentConfig(
                        tools=TOOLS,
                        system_instruction=SYSTEM_PROMPT
                    )
                )
            except Exception as e:
                return {
                    "response": f"Error calling Gemini: {str(e)}",
                    "tool_calls": tool_calls
                }
            
            if not response.candidates or not response.candidates[0].content.parts:
                return {
                    "response": final_text if final_text else "No response generated",
                    "tool_calls": tool_calls
                }
            
            # Add to history
            self.history.append(response.candidates[0].content)
            
            # Process parts
            has_tool_calls = False
            tool_response_parts = []
            
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    has_tool_calls = True
                    fc = part.function_call
                    args = dict(fc.args) if fc.args else {}
                    
                    # Execute tool
                    result = self.execute_tool(fc.name, args)
                    
                    tool_calls.append({
                        "tool": fc.name,
                        "args": args,
                        "result": result[:500]  # Truncate for response
                    })
                    
                    tool_response_parts.append(types.Part.from_function_response(
                        name=fc.name,
                        response={"result": result}
                    ))
                
                elif part.text:
                    final_text = part.text
            
            if not has_tool_calls:
                return {
                    "response": final_text,
                    "tool_calls": tool_calls
                }
            
            # Send tool results back
            self.history.append(types.Content(
                role="user",
                parts=tool_response_parts
            ))
        
        return {
            "response": final_text if final_text else "Completed with tool calls",
            "tool_calls": tool_calls
        }
    
    def clear_history(self):
        """Clear conversation history."""
        self.history = []
