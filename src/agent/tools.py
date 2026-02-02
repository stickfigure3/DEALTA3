"""
Tool definitions for the Gemini AI agent.
"""

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
            ),
            types.FunctionDeclaration(
                name="store_memory",
                description="Store important information to long-term memory. Use when the user shares preferences, facts, project context, or skills.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "content": types.Schema(
                            type=types.Type.STRING,
                            description="The information to remember"
                        ),
                        "category": types.Schema(
                            type=types.Type.STRING,
                            description="Memory category: preference, fact, context, skill, or project"
                        ),
                        "importance": types.Schema(
                            type=types.Type.INTEGER,
                            description="Importance level 1-10"
                        ),
                        "tags": types.Schema(
                            type=types.Type.ARRAY,
                            description="Optional tags for categorization",
                            items=types.Schema(type=types.Type.STRING)
                        )
                    },
                    required=["content", "category", "importance"]
                )
            ),
            types.FunctionDeclaration(
                name="search_memories",
                description="Search long-term memory for relevant information.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "query": types.Schema(
                            type=types.Type.STRING,
                            description="What to search for"
                        ),
                        "category": types.Schema(
                            type=types.Type.STRING,
                            description="Optional: filter by category"
                        ),
                        "limit": types.Schema(
                            type=types.Type.INTEGER,
                            description="Maximum results to return (default: 5)"
                        )
                    },
                    required=["query"]
                )
            ),
            types.FunctionDeclaration(
                name="list_memories",
                description="List all memories, optionally filtered by category.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "category": types.Schema(
                            type=types.Type.STRING,
                            description="Optional category filter"
                        ),
                        "limit": types.Schema(
                            type=types.Type.INTEGER,
                            description="Maximum results (default: 20)"
                        )
                    },
                    required=[]
                )
            ),
            types.FunctionDeclaration(
                name="update_memory",
                description="Update an existing memory when information changes.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "memory_id": types.Schema(
                            type=types.Type.STRING,
                            description="ID of memory to update"
                        ),
                        "new_content": types.Schema(
                            type=types.Type.STRING,
                            description="Updated content"
                        ),
                        "importance": types.Schema(
                            type=types.Type.INTEGER,
                            description="Updated importance (optional)"
                        )
                    },
                    required=["memory_id", "new_content"]
                )
            ),
            types.FunctionDeclaration(
                name="delete_memory",
                description="Delete a memory.",
                parameters=types.Schema(
                    type=types.Type.OBJECT,
                    properties={
                        "memory_id": types.Schema(
                            type=types.Type.STRING,
                            description="ID of memory to delete"
                        )
                    },
                    required=["memory_id"]
                )
            )
        ]
    )
]

SYSTEM_PROMPT = """You are an AI coding assistant with a persistent workspace and long-term memory.

CAPABILITIES:
1. Persistent workspace - files you create will be there next time
2. Long-term memory - you can remember user preferences, facts, and context across sessions
3. Code execution - run Python code and shell commands

MEMORY USAGE:
- Proactively store important information using store_memory (preferences, facts, context, skills, projects)
- Be selective - only store genuinely useful information (importance 6+)
- When users share preferences like "I prefer X" or "I use Y framework", store it immediately
- Search memories when context would be helpful
- Update memories when information changes

WHEN TO STORE MEMORIES:
✓ User preferences (coding style, tools, communication style)
✓ User background (role, company, expertise level)
✓ Project context (goals, constraints, architecture decisions)
✓ User skills and knowledge level
✗ Transient information (current task details, temporary notes)
✗ Information already in conversation history

CODING WORKFLOW:
1. Check for relevant memories that might inform your approach
2. First check if relevant files already exist with list_files
3. Write the file with write_file
4. Execute it with execute_python or execute_shell
5. Report the results

Always verify your work by checking outputs."""
