#!/usr/bin/env python3
"""
DELTA3 - AI Coding Agent with E2B Sandbox and Gemini LLM
"""

import os
import json
import sys
from typing import Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types
from e2b_code_interpreter import Sandbox

load_dotenv()

# === CONFIGURATION ===
E2B_API_KEY = os.getenv("E2B_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Set E2B API key in environment (SDK reads from env)
os.environ["E2B_API_KEY"] = E2B_API_KEY or ""

# === TOOL DEFINITIONS FOR GEMINI ===
TOOLS = [
    types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="execute_code",
                description="Execute Python code in the sandbox environment. Use this to run any Python code, install packages, or perform computations.",
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
                description="Read the contents of a file from the sandbox filesystem.",
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
                description="Write content to a file in the sandbox filesystem.",
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
                description="Run a shell command in the sandbox terminal.",
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
                description="List files in a directory in the sandbox.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "path": types.Schema(
                            type=types.Type.STRING,
                            description="The directory path to list (default: current directory)"
                        )
                    },
                    required=[]
                )
            )
        ]
    )
]

SYSTEM_PROMPT = """You are an AI coding assistant with access to a sandboxed coding environment. 
You can execute Python code, read/write files, and run terminal commands.

IMPORTANT WORKFLOW FOR CREATING REUSABLE CODE:
1. Use write_file to save Python code to /home/user/filename.py
2. Use run_terminal with "python /home/user/filename.py" to execute the file
3. Files persist in the sandbox - you can import them later!

Example workflow to create and use a module:
1. write_file(path="/home/user/utils.py", content="def greet(name): return f'Hello {name}'")
2. run_terminal(command="python -c 'from utils import greet; print(greet(\"World\"))'")

Or run a script:
1. write_file(path="/home/user/script.py", content="print('Hello!')")
2. run_terminal(command="python /home/user/script.py")

Available tools:
- execute_code: Run Python code directly (good for quick calculations)
- write_file: Save code/files to /home/user/ (PERSISTENT)
- read_file: Read file contents
- run_terminal: Run shell commands including "python filename.py"
- list_files: List directory contents (default: /home/user)

The working directory is /home/user. Files you create there persist across requests.
Always verify your work by checking outputs."""


class Delta3Agent:
    def __init__(self, sandbox_id: Optional[str] = None):
        """Initialize the agent with E2B sandbox and Gemini."""
        if not E2B_API_KEY:
            raise ValueError("E2B_API_KEY not set in environment")
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY not set in environment")
        
        # Configure Gemini client
        self.client = genai.Client(api_key=GEMINI_API_KEY)
        
        # Initialize or resume sandbox
        print("🔄 Starting sandbox...")
        if sandbox_id:
            self.sandbox = Sandbox.connect(sandbox_id)
            print(f"✅ Reconnected to sandbox: {sandbox_id}")
        else:
            self.sandbox = Sandbox.create(timeout=300)
            print(f"✅ Sandbox ready: {self.sandbox.sandbox_id}")
        
        # Chat history for context
        self.history = []
    
    def execute_tool(self, tool_name: str, args: dict) -> str:
        """Execute a tool call and return the result."""
        try:
            if tool_name == "execute_code":
                result = self.sandbox.run_code(args["code"])
                output = ""
                if result.logs.stdout:
                    output += f"stdout:\n{result.logs.stdout}\n"
                if result.logs.stderr:
                    output += f"stderr:\n{result.logs.stderr}\n"
                if result.error:
                    output += f"error:\n{result.error.name}: {result.error.value}\n"
                if result.results:
                    for r in result.results:
                        if hasattr(r, 'text') and r.text:
                            output += f"result: {r.text}\n"
                return output if output else "Code executed successfully (no output)"
            
            elif tool_name == "read_file":
                content = self.sandbox.files.read(args["path"])
                return content
            
            elif tool_name == "write_file":
                self.sandbox.files.write(args["path"], args["content"])
                return f"File written: {args['path']}"
            
            elif tool_name == "run_terminal":
                # Run from /home/user directory so relative paths work
                cmd = f"cd /home/user && {args['command']}"
                result = self.sandbox.commands.run(cmd)
                output = ""
                if result.stdout:
                    output += result.stdout
                if result.stderr:
                    output += f"\nstderr: {result.stderr}"
                return output if output else "Command completed (no output)"
            
            elif tool_name == "list_files":
                path = args.get("path", "/home/user")
                files = self.sandbox.files.list(path)
                return "\n".join([f.name for f in files])
            
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
                    response = self.client.models.generate_content(
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
    
    def get_sandbox_id(self) -> str:
        """Get the current sandbox ID for persistence."""
        return self.sandbox.sandbox_id
    
    def close(self):
        """Close the sandbox (optional - keeps it alive for persistence)."""
        pass


def main():
    """Main CLI entry point."""
    print("=" * 50)
    print("  DELTA3 - AI Coding Agent")
    print("=" * 50)
    
    # Check for sandbox ID for persistence
    sandbox_id = None
    sandbox_file = ".sandbox_id"
    
    if os.path.exists(sandbox_file):
        with open(sandbox_file, "r") as f:
            sandbox_id = f.read().strip()
        print(f"📁 Found existing sandbox: {sandbox_id}")
        try:
            agent = Delta3Agent(sandbox_id=sandbox_id)
        except Exception as e:
            print(f"⚠️  Could not reconnect, starting new sandbox: {e}")
            agent = Delta3Agent()
    else:
        agent = Delta3Agent()
    
    # Save sandbox ID for persistence
    with open(sandbox_file, "w") as f:
        f.write(agent.get_sandbox_id())
    
    print(f"\n💾 Sandbox ID saved to {sandbox_file}")
    print("Type 'quit' or 'exit' to stop. Type 'new' for fresh sandbox.\n")
    
    while True:
        try:
            user_input = input("\n🎯 You: ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() in ['quit', 'exit']:
                print("👋 Goodbye! Sandbox will remain available for reconnection.")
                break
            
            if user_input.lower() == 'new':
                agent.sandbox.kill()
                os.remove(sandbox_file)
                agent = Delta3Agent()
                with open(sandbox_file, "w") as f:
                    f.write(agent.get_sandbox_id())
                print("🆕 New sandbox created!")
                continue
            
            response = agent.process_request(user_input)
            print(f"\n🤖 Assistant: {response}")
            
        except KeyboardInterrupt:
            print("\n👋 Interrupted. Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")


if __name__ == "__main__":
    main()
