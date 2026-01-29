"""
Chat Lambda handler.
Handles chat messages and code execution via Gemini.
"""

import json
import os

import storage
from gemini import GeminiAgent


def response(status_code: int, body: dict) -> dict:
    """Create API Gateway response."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Session-Token,X-API-Key",
            "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"
        },
        "body": json.dumps(body)
    }


def get_user_from_request(event: dict) -> tuple:
    """Extract and verify user from request. Returns (user_id, gemini_key, error_response)."""
    headers = event.get("headers", {})
    
    # Try session token first
    session_token = headers.get("X-Session-Token") or headers.get("x-session-token")
    if session_token:
        user_id = storage.verify_session(session_token)
        if user_id:
            user = storage.get_user(user_id)
            if user and user.get("gemini_key"):
                return user_id, user["gemini_key"], None
            return None, None, response(400, {"error": "Gemini API key not set. Please add it in settings."})
    
    # Try API key
    api_key = headers.get("X-API-Key") or headers.get("x-api-key")
    if api_key:
        user_id = storage.verify_api_key(api_key)
        if user_id:
            user = storage.get_user(user_id)
            if user and user.get("gemini_key"):
                return user_id, user["gemini_key"], None
            return None, None, response(400, {"error": "Gemini API key not set"})
    
    return None, None, response(401, {"error": "Authentication required"})


def handler(event, context):
    """Main Lambda handler."""
    
    # Handle CORS preflight
    if event.get("httpMethod") == "OPTIONS":
        return response(200, {"message": "OK"})
    
    path = event.get("path", "")
    method = event.get("httpMethod", "GET")
    
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return response(400, {"error": "Invalid JSON body"})
    
    # Route requests
    if path == "/chat/send" and method == "POST":
        return send_message(event, body)
    
    elif path == "/chat/history" and method == "GET":
        return get_history(event)
    
    elif path == "/chat/clear" and method == "POST":
        return clear_history(event)
    
    elif path == "/files/list" and method == "GET":
        return list_files(event)
    
    elif path == "/files/read" and method == "POST":
        return read_file(event, body)
    
    elif path == "/files/write" and method == "POST":
        return write_file(event, body)
    
    elif path == "/files/delete" and method == "POST":
        return delete_file(event, body)
    
    return response(404, {"error": "Not found"})


def send_message(event: dict, body: dict):
    """Send message to Gemini and get response."""
    user_id, gemini_key, error = get_user_from_request(event)
    if error:
        return error
    
    message = body.get("message", "").strip()
    if not message:
        return response(400, {"error": "Message required"})
    
    try:
        # Load chat history for context continuity
        chat_history = storage.get_chat_history(user_id, limit=20)
        
        # Create agent with user's Gemini key, user_id, and history
        # This will:
        # 1. Restore user's files from S3 to /tmp workspace
        # 2. Load previous chat context into Gemini
        agent = GeminiAgent(
            api_key=gemini_key,
            user_id=user_id,
            chat_history=chat_history
        )
        
        # Process message (files created will auto-sync to S3)
        result = agent.process_message(message)
        
        # Save to history for next session
        storage.save_chat_message(user_id, "user", message)
        storage.save_chat_message(
            user_id, 
            "assistant", 
            result["response"],
            tool_calls=result.get("tool_calls")
        )
        
        return response(200, {
            "response": result["response"],
            "tool_calls": result.get("tool_calls", [])
        })
    
    except Exception as e:
        import traceback
        return response(500, {"error": f"Chat error: {str(e)}", "trace": traceback.format_exc()})


def get_history(event: dict):
    """Get chat history."""
    user_id, _, error = get_user_from_request(event)
    if error:
        return error
    
    # Get limit from query params
    params = event.get("queryStringParameters") or {}
    limit = int(params.get("limit", 50))
    
    history = storage.get_chat_history(user_id, limit=limit)
    
    return response(200, {"history": history})


def clear_history(event: dict):
    """Clear chat history."""
    user_id, _, error = get_user_from_request(event)
    if error:
        return error
    
    storage.clear_chat_history(user_id)
    
    return response(200, {"message": "History cleared"})


def list_files(event: dict):
    """List user's files."""
    user_id, _, error = get_user_from_request(event)
    if error:
        return error
    
    params = event.get("queryStringParameters") or {}
    path = params.get("path", "")
    
    files = storage.list_files(user_id, path)
    
    return response(200, {"files": files, "path": path})


def read_file(event: dict, body: dict):
    """Read a file."""
    user_id, _, error = get_user_from_request(event)
    if error:
        return error
    
    path = body.get("path", "")
    if not path:
        return response(400, {"error": "Path required"})
    
    content = storage.read_file(user_id, path)
    
    if content is None:
        return response(404, {"error": "File not found"})
    
    return response(200, {"content": content, "path": path})


def write_file(event: dict, body: dict):
    """Write a file."""
    user_id, _, error = get_user_from_request(event)
    if error:
        return error
    
    path = body.get("path", "")
    content = body.get("content", "")
    
    if not path:
        return response(400, {"error": "Path required"})
    
    if storage.write_file(user_id, path, content):
        return response(200, {"message": "File saved", "path": path})
    
    return response(500, {"error": "Failed to save file"})


def delete_file(event: dict, body: dict):
    """Delete a file."""
    user_id, _, error = get_user_from_request(event)
    if error:
        return error
    
    path = body.get("path", "")
    if not path:
        return response(400, {"error": "Path required"})
    
    if storage.delete_file(user_id, path):
        return response(200, {"message": "File deleted", "path": path})
    
    return response(500, {"error": "Failed to delete file"})
