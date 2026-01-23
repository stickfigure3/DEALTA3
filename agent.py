#!/usr/bin/env python3
"""
DELTA3 - AI Coding Agent with Firecracker VMs and Gemini LLM
Client CLI that connects to DELTA3 API server
"""

import os
import json
import sys
import httpx
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# === CONFIGURATION ===
API_SERVER_URL = os.getenv("DELTA3_API_URL", "http://localhost:8000")
API_KEY = os.getenv("DELTA3_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# === TOOL DEFINITIONS FOR GEMINI ===
TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="execute_code",
                description="Execute Python code in the VM environment. Use this to run any Python code, install packages, or perform computations.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "code": types.Schema(
                            type=types.Type.STRING,
                            description="The Python code to execute"
                        )
                    },
                    required=["code"]
                )
            ),
            types.FunctionDeclaration(
                name="read_file",
                description="Read the contents of a file from the VM filesystem.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "path": types.Schema(
                            type=types.Type.STRING,
                            description="The path to the file to read"
                        )
                    },
                    required=["path"]
                )
            ),
            types.FunctionDeclaration(
                name="write_file",
                description="Write content to a file in the VM filesystem.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "path": types.Schema(
                            type=types.Type.STRING,
                            description="The path to the file to write"
                        ),
                        "content": types.Schema(
                            type=types.Type.STRING,
                            description="The content to write to the file"
                        )
                    },
                    required=["path", "content"]
                )
            ),
            types.FunctionDeclaration(
                name="run_terminal",
                description="Run a shell command in the VM terminal.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "command": types.Schema(
                            type=types.Type.STRING,
                            description="The shell command to run"
                        )
                    },
                    required=["command"]
                )
            ),
            types.FunctionDeclaration(
                name="list_files",
                description="List files in a directory in the VM.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "path": types.Schema(
                            type=types.Type.STRING,
                            description="The directory path to list (default: /home/user)"
                        )
                    },
                    required=[]
                )
            )
        ]
    )
]

SYSTEM_PROMPT = """You are an AI coding assistant with access to a Firecracker microVM coding environment. 
You can execute Python code, read/write files, and run terminal commands.

IMPORTANT WORKFLOW FOR CREATING REUSABLE CODE:
1. Use write_file to save Python code to /home/user/filename.py
2. Use run_terminal with "python /home/user/filename.py" to execute the file
3. Files persist in the VM and are saved to S3 when you disconnect!

Example workflow to create and use a module:
1. write_file(path="/home/user/utils.py", content="def greet(name): return f'Hello {name}'")
2. run_terminal(command="python -c 'from utils import greet; print(greet(\"World\"))'")

Available tools:
- execute_code: Run Python code directly (good for quick calculations)
- write_file: Save code/files to /home/user/ (PERSISTENT via S3)
- read_file: Read file contents
- run_terminal: Run shell commands including "python filename.py"
- list_files: List directory contents (default: /home/user)

The working directory is /home/user. Files you create persist to S3 and survive restarts.
Always verify your work by checking outputs."""


class Delta3Client:
    """HTTP client for DELTA3 API server."""
    
    def __init__(self, api_url: str, api_key: str):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.headers = {"X-API-Key": api_key}
        self.client = httpx.Client(timeout=60.0)
    
    def _request(self, method: str, endpoint: str, json_data: dict = None) -> dict:
        """Make HTTP request to API server."""
        url = f"{self.api_url}{endpoint}"
        response = self.client.request(method, url, headers=self.headers, json=json_data)
        
        if response.status_code >= 400:
            raise Exception(f"API Error {response.status_code}: {response.text}")
        
        return response.json()
    
    def start_vm(self) -> dict:
        return self._request("POST", "/vm/start")
    
    def stop_vm(self, save: bool = True) -> dict:
        return self._request("POST", f"/vm/stop?save={str(save).lower()}")
    
    def vm_status(self) -> dict:
        return self._request("GET", "/vm/status")
    
    def execute_code(self, code: str) -> dict:
        return self._request("POST", "/execute/code", {"code": code})
    
    def execute_command(self, command: str) -> dict:
        return self._request("POST", "/execute/command", {"command": command})
    
    def write_file(self, path: str, content: str) -> dict:
        return self._request("POST", "/files/write", {"path": path, "content": content})
    
    def read_file(self, path: str) -> dict:
        return self._request("POST", "/files/read", {"path": path})
    
    def list_files(self, path: str = "/home/user") -> dict:
        return self._request("GET", f"/files/list?path={path}")


class Delta3Agent:
    def __init__(self):
        """Initialize the agent with API client and Gemini."""
        if not API_KEY:
            raise ValueError("DELTA3_API_KEY not set in environment")
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in environment")
        
        # Configure Gemini client
        self.gemini = genai.Client(api_key=GEMINI_API_KEY)
        
        # Initialize API client
        self.client = Delta3Client(API_SERVER_URL, API_KEY)
        
        # Start VM
        print("🔄 Starting VM...")
        result = self.client.start_vm()
        print(f"✅ VM ready: {result.get('vm_id', 'unknown')}")
        
        # Chat history for context
        self.history = []
    
    def execute_tool(self, tool_name: str, args: dict) -> str:
        """Execute a tool call and return the result."""
        try:
            if tool_name == "execute_code":
                result = self.client.execute_code(args["code"])
                output = ""
                if result.get("stdout"):
                    output += f"stdout:\n{result['stdout']}\n"
                if result.get("stderr"):
                    output += f"stderr:\n{result['stderr']}\n"
                return output if output else "Code executed successfully (no output)"
            
            elif tool_name == "read_file":
                result = self.client.read_file(args["path"])
                return result.get("content", "")
            
            elif tool_name == "write_file":
                result = self.client.write_file(args["path"], args["content"])
                return f"File written: {args['path']}"
            
            elif tool_name == "run_terminal":
                result = self.client.execute_command(args['command'])
                output = ""
                if result.get("stdout"):
                    output += result["stdout"]
                if result.get("stderr"):
                    output += f"\nstderr: {result['stderr']}"
                return output if output else "Command completed (no output)"
            
            elif tool_name == "list_files":
                path = args.get("path", "/home/user")
                result = self.client.list_files(path)
                return result.get("files", "")
            
            else:
                return f"Unknown tool: {tool_name}"
                
        except Exception as e:
            return f"Tool error: {str(e)}"
    
    def process_request(self, user_input: str) -> str:
        """Process a user request through the agentic loop."""
        print(f"\n💬 User: {user_input}")
        print("🤖 Thinking...")
        
        # Add user message to history
        self.history.append(types.Content(
            role="user",
            parts=[types.Part.from_text(text=user_input)]
        ))
        
        # Agentic loop - keep processing until no more tool calls
        max_iterations = 10
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            
            # Generate response with retry for rate limits
            import time
            for attempt in range(3):
                try:
                    response = self.gemini.models.generate_content(
                        model="gemini-2.0-flash",
                        contents=self.history,
                        config=types.GenerateContentConfig(
                            tools=TOOLS,
                            system_instruction=SYSTEM_PROMPT,
                        )
                    )
                    break
                except Exception as e:
                    if "429" in str(e) and attempt < 2:
                        print(f"  ⏳ Rate limited, waiting... (attempt {attempt + 1})")
                        time.sleep(5 * (attempt + 1))
                    else:
                        raise e
            
            # Check if we have a response
            if not response.candidates or not response.candidates[0].content.parts:
                return "No response generated"
            
            # Add assistant response to history
            self.history.append(response.candidates[0].content)
            
            # Process parts
            has_tool_calls = False
            tool_response_parts = []
            final_text = ""
            
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    has_tool_calls = True
                    fc = part.function_call
                    tool_name = fc.name
                    args = dict(fc.args) if fc.args else {}
                    
                    print(f"  🔧 {tool_name}({json.dumps(args)[:100]}...)")
                    
                    result = self.execute_tool(tool_name, args)
                    result_preview = result[:200] + "..." if len(result) > 200 else result
                    print(f"  📤 Result: {result_preview}")
                    
                    tool_response_parts.append(types.Part.from_function_response(
                        name=tool_name,
                        response={"result": result}
                    ))
                
                elif part.text:
                    final_text += part.text
            
            if not has_tool_calls:
                return final_text
            
            # Send tool results back
            self.history.append(types.Content(
                role="user",
                parts=tool_response_parts
            ))
        
        return final_text if final_text else "Max iterations reached"
    
    def save_and_stop(self):
        """Save environment to S3 and stop VM."""
        print("💾 Saving environment to S3...")
        self.client.stop_vm(save=True)
        print("✅ Environment saved!")


def main():
    """Main CLI entry point."""
    print("=" * 50)
    print("  DELTA3 - AI Coding Agent (Firecracker)")
    print("=" * 50)
    
    try:
        agent = Delta3Agent()
    except Exception as e:
        print(f"❌ Failed to start: {e}")
        print("\nMake sure you have:")
        print("  1. DELTA3_API_URL set (default: http://localhost:8000)")
        print("  2. DELTA3_API_KEY set (get from /auth/api-key)")
        print("  3. GEMINI_API_KEY set")
        sys.exit(1)
    
    print("\nCommands:")
    print("  quit/exit - Save to S3 and exit")
    print("  save      - Save current state to S3")
    print("  nosave    - Exit without saving")
    print()
    
    while True:
        try:
            user_input = input("\n🎯 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit']:
                agent.save_and_stop()
                print("👋 Goodbye!")
                break
            
            if user_input.lower() == 'save':
                agent.client.stop_vm(save=True)
                print("💾 Saved to S3!")
                agent.client.start_vm()
                print("✅ VM restarted")
                continue
            
            if user_input.lower() == 'nosave':
                agent.client.stop_vm(save=False)
                print("👋 Goodbye! (not saved)")
                break
            
            response = agent.process_request(user_input)
            print(f"\n🤖 Assistant: {response}")
            
        except KeyboardInterrupt:
            print("\n💾 Saving and exiting...")
            agent.save_and_stop()
            print("👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
