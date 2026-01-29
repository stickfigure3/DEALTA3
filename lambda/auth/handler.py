"""
Authentication Lambda handler.
Handles user registration, login, and session management.
"""

import json
import os
import sys

# Add shared module to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from shared import storage


def response(status_code: int, body: dict, headers: dict = None) -> dict:
    """Create API Gateway response."""
    default_headers = {
        "Content-Type": "application/json",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,Authorization,X-Session-Token",
        "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,OPTIONS"
    }
    if headers:
        default_headers.update(headers)
    
    return {
        "statusCode": status_code,
        "headers": default_headers,
        "body": json.dumps(body)
    }


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
    if path == "/auth/register" and method == "POST":
        return register(body)
    
    elif path == "/auth/login" and method == "POST":
        return login(body)
    
    elif path == "/auth/logout" and method == "POST":
        return logout(event)
    
    elif path == "/auth/me" and method == "GET":
        return get_me(event)
    
    elif path == "/auth/gemini-key" and method == "POST":
        return update_gemini_key(event, body)
    
    return response(404, {"error": "Not found"})


def register(body: dict):
    """Register new user."""
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    
    if not email or not password:
        return response(400, {"error": "Email and password required"})
    
    if "@" not in email:
        return response(400, {"error": "Invalid email format"})
    
    if len(password) < 6:
        return response(400, {"error": "Password must be at least 6 characters"})
    
    try:
        result = storage.create_user(email, password)
        return response(201, {
            "message": "Account created",
            "user_id": result["user_id"],
            "api_key": result["api_key"]
        })
    except ValueError as e:
        return response(400, {"error": str(e)})
    except Exception as e:
        return response(500, {"error": f"Registration failed: {str(e)}"})


def login(body: dict):
    """Login user and create session."""
    email = body.get("email", "").strip().lower()
    password = body.get("password", "")
    
    if not email or not password:
        return response(400, {"error": "Email and password required"})
    
    result = storage.verify_login(email, password)
    
    if not result:
        return response(401, {"error": "Invalid credentials"})
    
    return response(200, {
        "message": "Login successful",
        "session_token": result["session_token"],
        "user_id": result["user_id"],
        "api_key": result["api_key"],
        "gemini_key_set": result["gemini_key"] is not None,
        "expires": result["expires"]
    })


def logout(event: dict):
    """Logout user (invalidate session)."""
    # For now, just return success - sessions expire naturally
    return response(200, {"message": "Logged out"})


def get_me(event: dict):
    """Get current user info."""
    session_token = event.get("headers", {}).get("X-Session-Token") or \
                    event.get("headers", {}).get("x-session-token")
    
    if not session_token:
        return response(401, {"error": "Session token required"})
    
    user_id = storage.verify_session(session_token)
    
    if not user_id:
        return response(401, {"error": "Invalid or expired session"})
    
    user = storage.get_user(user_id)
    
    if not user:
        return response(404, {"error": "User not found"})
    
    return response(200, {
        "user_id": user["user_id"],
        "email": user["email"],
        "api_key": user["api_key"],
        "gemini_key_set": user.get("gemini_key") is not None,
        "created_at": user["created_at"]
    })


def update_gemini_key(event: dict, body: dict):
    """Update user's Gemini API key."""
    session_token = event.get("headers", {}).get("X-Session-Token") or \
                    event.get("headers", {}).get("x-session-token")
    
    if not session_token:
        return response(401, {"error": "Session token required"})
    
    user_id = storage.verify_session(session_token)
    
    if not user_id:
        return response(401, {"error": "Invalid or expired session"})
    
    gemini_key = body.get("gemini_key", "").strip()
    
    if not gemini_key:
        return response(400, {"error": "Gemini API key required"})
    
    if not gemini_key.startswith("AIza"):
        return response(400, {"error": "Invalid Gemini API key format"})
    
    if storage.update_gemini_key(user_id, gemini_key):
        return response(200, {"message": "Gemini API key updated"})
    
    return response(500, {"error": "Failed to update API key"})
