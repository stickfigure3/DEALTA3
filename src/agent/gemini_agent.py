"""
Gemini AI Agent for code generation and execution.
"""

from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

from .executor import PersistentCodeExecutor
from .tools import TOOLS, SYSTEM_PROMPT


class GeminiAgent:
    """Gemini-powered coding agent with persistent environment."""
    
    def __init__(
        self, 
        api_key: str, 
        user_id: str, 
        chat_history: List[Dict] = None,
        local_mode: bool = False,
        workspace_base: str = "/tmp",
        storage_module = None
    ):
        """
        Initialize the Gemini agent.
        
        Args:
            api_key: Gemini API key
            user_id: User identifier
            chat_history: Previous chat history to load
            local_mode: If True, use local storage instead of AWS
            workspace_base: Base directory for workspace
            storage_module: Storage module for memories (optional)
        """
        self.client = genai.Client(api_key=api_key)
        self.user_id = user_id
        self.local_mode = local_mode
        self.storage = storage_module
        
        self.executor = PersistentCodeExecutor(
            user_id=user_id,
            workspace_base=workspace_base,
            local_mode=local_mode
        )
        
        self.history: List[types.Content] = []
        
        if chat_history:
            self._load_history(chat_history)
    
    def _load_history(self, chat_history: List[Dict]):
        """Load previous chat history into Gemini context."""
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

    def _load_memories(self) -> str:
        """Load relevant memories and format for context injection."""
        if not self.storage:
            return ""
        
        from datetime import datetime, timedelta

        memories = []

        try:
            # Load critical memories (importance >= 9)
            critical = self.storage.get_memories(
                self.user_id,
                min_importance=9,
                limit=5
            )
            memories.extend(critical)

            # Load recent important memories (last 7 days, importance >= 6)
            recent = self.storage.get_memories(
                self.user_id,
                min_importance=6,
                limit=10
            )
            week_ago = (datetime.utcnow() - timedelta(days=7)).isoformat()
            recent = [m for m in recent if m.get("created_at", "") >= week_ago]
            memories.extend(recent)
        except Exception:
            return ""

        # Deduplicate by memory_id
        seen = set()
        unique_memories = []
        for mem in memories:
            if mem["memory_id"] not in seen:
                seen.add(mem["memory_id"])
                unique_memories.append(mem)

        if not unique_memories:
            return ""

        # Format memories by category
        by_category = {}
        for mem in unique_memories:
            cat = mem.get("category", "other")
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(mem)

        context_parts = [
            "=== LONG-TERM MEMORY ===",
            "You have the following information about this user:\n"
        ]

        for category, mems in sorted(by_category.items()):
            context_parts.append(f"[{category.upper()}]")
            for mem in sorted(mems, key=lambda m: m.get("importance", 0), reverse=True):
                context_parts.append(f"- {mem['content']} (Importance: {mem['importance']})")
            context_parts.append("")

        context_parts.append("=== END MEMORY ===")

        return "\n".join(context_parts)
    
    def execute_tool(self, name: str, args: Dict) -> str:
        """Execute a tool and return result as string."""
        
        # Code execution tools
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
        
        # File tools
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

        # Memory tools
        elif name == "store_memory":
            if not self.storage:
                return "Memory storage not available"
            result = self.storage.save_memory(
                self.user_id,
                args["content"],
                args["category"],
                args["importance"],
                args.get("tags", []),
                source_context="Stored during conversation"
            )
            if result.get("success"):
                return f"✓ Memory stored (ID: {result['memory_id']})"
            return f"Failed to store memory: {result.get('error', 'Unknown error')}"

        elif name == "search_memories":
            if not self.storage:
                return "Memory storage not available"
            query = args["query"]
            limit = args.get("limit", 5)

            memories = self.storage.search_memories(self.user_id, query, limit)

            if not memories:
                return "No matching memories found."

            result = f"Found {len(memories)} memories:\n\n"
            for mem in memories:
                result += f"- [{mem['category']}] {mem['content']} (Importance: {mem['importance']}, ID: {mem['memory_id']})\n"

            return result

        elif name == "list_memories":
            if not self.storage:
                return "Memory storage not available"
            category = args.get("category")
            limit = args.get("limit", 20)

            memories = self.storage.get_memories(self.user_id, category=category, limit=limit)

            if not memories:
                return "No memories found."

            result = f"Your memories ({len(memories)} total):\n\n"

            by_category = {}
            for mem in memories:
                cat = mem.get("category", "other")
                if cat not in by_category:
                    by_category[cat] = []
                by_category[cat].append(mem)

            for cat, mems in sorted(by_category.items()):
                result += f"\n[{cat.upper()}]\n"
                for mem in mems:
                    result += f"  - {mem['content']} (Importance: {mem['importance']}, ID: {mem['memory_id']})\n"

            return result

        elif name == "update_memory":
            if not self.storage:
                return "Memory storage not available"
            result = self.storage.update_memory(
                self.user_id,
                args["memory_id"],
                args.get("new_content"),
                args.get("importance")
            )
            if result.get("success"):
                return "✓ Memory updated"
            return f"Failed to update memory: {result.get('error', 'Unknown error')}"

        elif name == "delete_memory":
            if not self.storage:
                return "Memory storage not available"
            success = self.storage.delete_memory(self.user_id, args["memory_id"])
            if success:
                return "✓ Memory deleted"
            return "Failed to delete memory"

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

        # Load memories and create enhanced system prompt
        memory_context = self._load_memories()
        enhanced_prompt = SYSTEM_PROMPT
        if memory_context:
            enhanced_prompt += f"\n\n{memory_context}"

        for _ in range(max_iterations):
            try:
                response = self.client.models.generate_content(
                    model="gemini-2.0-flash",
                    contents=self.history,
                    config=types.GenerateContentConfig(
                        tools=TOOLS,
                        system_instruction=enhanced_prompt
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
            
            self.history.append(response.candidates[0].content)
            
            has_tool_calls = False
            tool_response_parts = []
            
            for part in response.candidates[0].content.parts:
                if part.function_call:
                    has_tool_calls = True
                    fc = part.function_call
                    args = dict(fc.args) if fc.args else {}
                    
                    result = self.execute_tool(fc.name, args)
                    
                    tool_calls.append({
                        "tool": fc.name,
                        "args": args,
                        "result": result[:500]
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
