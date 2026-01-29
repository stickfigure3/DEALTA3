"""
Gemini AI integration for code execution.
"""

import json
import subprocess
import tempfile
import os
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

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
                description="Write content to a file. Creates parent directories if needed.",
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
            )
        ]
    )
]

SYSTEM_PROMPT = """You are an AI coding assistant. You can execute Python code, run shell commands, and manage files.

IMPORTANT:
1. Use write_file to save code before running it
2. Use execute_python for Python code execution
3. Use execute_shell for system commands
4. Files persist between sessions
5. Working directory is /tmp/workspace

When asked to write code:
1. First write the file with write_file
2. Then execute it with execute_python or execute_shell
3. Report the results

Always verify your work by checking outputs."""


class CodeExecutor:
    """Executes code in Lambda's /tmp directory."""
    
    def __init__(self, workspace: str = "/tmp/workspace"):
        self.workspace = workspace
        os.makedirs(workspace, exist_ok=True)
    
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
                cwd=self.workspace
            )
            
            # Cleanup
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
        """Write file to workspace."""
        try:
            full_path = os.path.join(self.workspace, path.lstrip("/"))
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            
            with open(full_path, "w") as f:
                f.write(content)
            
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def read_file(self, path: str) -> Dict[str, Any]:
        """Read file from workspace."""
        try:
            full_path = os.path.join(self.workspace, path.lstrip("/"))
            
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
            full_path = os.path.join(self.workspace, path.lstrip("/"))
            
            if not os.path.exists(full_path):
                return {"success": True, "files": []}
            
            files = []
            for name in os.listdir(full_path):
                item_path = os.path.join(full_path, name)
                files.append({
                    "name": name,
                    "type": "directory" if os.path.isdir(item_path) else "file",
                    "size": os.path.getsize(item_path) if os.path.isfile(item_path) else None
                })
            
            return {"success": True, "files": files}
        except Exception as e:
            return {"success": False, "error": str(e)}


class GeminiAgent:
    """Gemini-powered coding agent."""
    
    def __init__(self, api_key: str):
        self.client = genai.Client(api_key=api_key)
        self.executor = CodeExecutor()
        self.history: List[types.Content] = []
    
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
                return f"File written: {args['path']}"
            return f"Error: {result['error']}"
        
        elif name == "read_file":
            result = self.executor.read_file(args["path"])
            if result["success"]:
                return result["content"]
            return f"Error: {result['error']}"
        
        elif name == "list_files":
            result = self.executor.list_files(args.get("path", ""))
            if result["success"]:
                if not result["files"]:
                    return "Directory is empty"
                return "\n".join(
                    f"{'📁' if f['type'] == 'directory' else '📄'} {f['name']}"
                    for f in result["files"]
                )
            return f"Error: {result['error']}"
        
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
                    "response": "No response generated",
                    "tool_calls": tool_calls
                }
            
            # Add to history
            self.history.append(response.candidates[0].content)
            
            # Process parts
            has_tool_calls = False
            tool_response_parts = []
            final_text = ""
            
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
                    final_text += part.text
            
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
            "response": final_text if final_text else "Max iterations reached",
            "tool_calls": tool_calls
        }
    
    def clear_history(self):
        """Clear conversation history."""
        self.history = []
