#!/usr/bin/env python3
"""Test script for DELTA3 components"""

import os
import sys
from dotenv import load_dotenv

load_dotenv()

# Set E2B API key in environment
os.environ["E2B_API_KEY"] = os.getenv("E2B_API_KEY") or ""

results = {
    "step2_cli": False,
    "step3_tools": False,
    "step4_loop": False,
    "step5_persist": False,
}

# Test Step 2: E2B Sandbox + Gemini Connection
print("\n" + "="*50)
print("STEP 2: Testing CLI Components")
print("="*50)

try:
    from e2b_code_interpreter import Sandbox
    from google import genai
    
    # Test E2B
    print("Testing E2B sandbox...")
    sandbox = Sandbox.create(timeout=60)
    print(f"  ✅ Sandbox created: {sandbox.sandbox_id}")
    
    # Test code execution
    result = sandbox.run_code("print('Hello from E2B!')")
    stdout = str(result.logs.stdout)
    assert "Hello from E2B!" in stdout
    print(f"  ✅ Code execution works")
    
    # Kill test sandbox
    sandbox.kill()
    
    # Test Gemini
    print("Testing Gemini API...")
    import time
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
    
    # Try multiple models in case of quota issues
    models_to_try = ["gemini-2.0-flash", "gemini-2.5-flash", "gemini-2.0-flash-lite"]
    gemini_ok = False
    
    for model_name in models_to_try:
        try:
            print(f"  Trying {model_name}...")
            response = client.models.generate_content(
                model=model_name,
                contents="Say 'test successful' and nothing else."
            )
            if response.text:
                print(f"  ✅ Gemini API works ({model_name})")
                gemini_ok = True
                break
        except Exception as e:
            if "429" in str(e):
                print(f"  Rate limited on {model_name}, trying next...")
                time.sleep(2)
            else:
                raise e
    
    if not gemini_ok:
        raise Exception("All Gemini models rate limited")
    
    results["step2_cli"] = True
    print("STEP 2: ✅ PASSED")
    
    # Keep sandbox for later tests
    test_sandbox = sandbox
    test_sandbox_id = sandbox.sandbox_id
    
except Exception as e:
    print(f"STEP 2: ❌ FAILED - {e}")
    test_sandbox = None
    test_sandbox_id = None

# Test Step 3: Tool Schema Definitions
print("\n" + "="*50)
print("STEP 3: Testing Tool Schema")
print("="*50)

try:
    from agent import TOOLS, Delta3Agent
    
    # Verify tools are defined
    tool_declarations = TOOLS[0].function_declarations
    tool_names = [f.name for f in tool_declarations]
    required_tools = ["execute_code", "read_file", "write_file", "run_terminal", "list_files"]
    
    for tool in required_tools:
        assert tool in tool_names, f"Missing tool: {tool}"
        print(f"  ✅ Tool defined: {tool}")
    
    results["step3_tools"] = True
    print("STEP 3: ✅ PASSED")
    
except Exception as e:
    print(f"STEP 3: ❌ FAILED - {e}")

# Test Step 4: Agentic Loop
print("\n" + "="*50)
print("STEP 4: Testing Agentic Loop")
print("="*50)

try:
    agent = Delta3Agent()
    
    # Test a simple request that requires tool use
    response = agent.process_request("Use the execute_code tool to calculate 2+2 and tell me the result.")
    
    # Verify response contains the answer
    assert "4" in response, f"Expected '4' in response, got: {response}"
    print(f"  ✅ Agentic loop executed successfully")
    print(f"  ✅ Response received: {response[:100]}...")
    
    results["step4_loop"] = True
    print("STEP 4: ✅ PASSED")
    
except Exception as e:
    print(f"STEP 4: ❌ FAILED - {e}")
    import traceback
    traceback.print_exc()
    agent = None

# Test Step 5: Persistence
print("\n" + "="*50)
print("STEP 5: Testing Persistence")
print("="*50)

try:
    if agent is None:
        raise Exception("Agent not created in step 4")
    
    # First, write a file in the sandbox
    agent.sandbox.files.write("/home/user/test_persist.txt", "persistence test data")
    print("  ✅ File written to sandbox")
    
    # Get sandbox ID
    sid = agent.get_sandbox_id()
    print(f"  ✅ Sandbox ID: {sid}")
    
    # Keep alive for reconnection
    agent.sandbox.set_timeout(120)
    
    # Reconnect to same sandbox
    from e2b_code_interpreter import Sandbox
    sandbox2 = Sandbox.connect(sid)
    
    # Verify file persists
    content = sandbox2.files.read("/home/user/test_persist.txt")
    assert content == "persistence test data", f"Got: {content}"
    print("  ✅ File persisted across reconnection")
    
    # Cleanup
    sandbox2.kill()
    
    results["step5_persist"] = True
    print("STEP 5: ✅ PASSED")
    
except Exception as e:
    print(f"STEP 5: ❌ FAILED - {e}")
    import traceback
    traceback.print_exc()

# Final Summary
print("\n" + "="*50)
print("FINAL RESULTS")
print("="*50)

for step, passed in results.items():
    status = "✅" if passed else "❌"
    print(f"{status} {step}")

all_passed = all(results.values())
print("\n" + ("🎉 ALL TESTS PASSED!" if all_passed else "⚠️  SOME TESTS FAILED"))

sys.exit(0 if all_passed else 1)
