"""
DELTA3 Storage Module

Handles persistence to DynamoDB (users, memories) and S3 (files, chat history).
"""

from .users import (
    create_user,
    verify_login,
    verify_session,
    verify_api_key,
    get_user,
    update_gemini_key,
    hash_password,
    generate_api_key,
    generate_session_token
)

from .files import (
    write_file,
    read_file,
    list_files,
    delete_file,
    get_user_prefix
)

from .chat import (
    save_chat_message,
    get_chat_history,
    clear_chat_history
)

from .memories import (
    save_memory,
    get_memories,
    search_memories,
    update_memory,
    delete_memory
)

__all__ = [
    # Users
    "create_user", "verify_login", "verify_session", "verify_api_key",
    "get_user", "update_gemini_key", "hash_password", "generate_api_key",
    "generate_session_token",
    # Files
    "write_file", "read_file", "list_files", "delete_file", "get_user_prefix",
    # Chat
    "save_chat_message", "get_chat_history", "clear_chat_history",
    # Memories
    "save_memory", "get_memories", "search_memories", "update_memory", "delete_memory"
]
