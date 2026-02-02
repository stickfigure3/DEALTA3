"""
User management and authentication.
"""

import os
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

import boto3
from botocore.exceptions import ClientError

# Configuration
USERS_TABLE = os.environ.get("USERS_TABLE", "delta3-users")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Clients
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
users_table = dynamodb.Table(USERS_TABLE)


def hash_password(password: str) -> str:
    """Hash password with SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a unique API key."""
    return f"delta3_{secrets.token_hex(24)}"


def generate_session_token() -> str:
    """Generate a session token."""
    return secrets.token_hex(32)


def create_user(email: str, password: str) -> Dict[str, Any]:
    """Create a new user account."""
    user_id = email.lower()
    
    # Check if exists
    try:
        response = users_table.get_item(Key={"user_id": user_id})
        if "Item" in response:
            raise ValueError("User already exists")
    except ClientError:
        pass
    
    api_key = generate_api_key()
    
    user = {
        "user_id": user_id,
        "email": email,
        "password_hash": hash_password(password),
        "api_key": api_key,
        "gemini_key": None,
        "created_at": datetime.utcnow().isoformat(),
        "last_login": None,
        "sessions": {}
    }
    
    users_table.put_item(Item=user)
    return {"user_id": user_id, "api_key": api_key}


def verify_login(email: str, password: str) -> Optional[Dict[str, Any]]:
    """Verify login credentials and create session."""
    user_id = email.lower()
    
    try:
        response = users_table.get_item(Key={"user_id": user_id})
        if "Item" not in response:
            return None
        
        user = response["Item"]
        if user["password_hash"] != hash_password(password):
            return None
        
        # Create session
        session_token = generate_session_token()
        expires = (datetime.utcnow() + timedelta(days=7)).isoformat()
        
        # Update user with new session
        users_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET last_login = :now, sessions.#token = :expires",
            ExpressionAttributeNames={"#token": session_token},
            ExpressionAttributeValues={
                ":now": datetime.utcnow().isoformat(),
                ":expires": expires
            }
        )
        
        return {
            "user_id": user_id,
            "session_token": session_token,
            "api_key": user.get("api_key"),
            "gemini_key": user.get("gemini_key"),
            "expires": expires
        }
    except ClientError:
        return None


def verify_session(session_token: str) -> Optional[str]:
    """Verify session token and return user_id."""
    try:
        response = users_table.scan(
            FilterExpression="attribute_exists(sessions.#token)",
            ExpressionAttributeNames={"#token": session_token}
        )
        
        if not response.get("Items"):
            return None
        
        user = response["Items"][0]
        expires = user.get("sessions", {}).get(session_token)
        
        if expires and datetime.fromisoformat(expires) > datetime.utcnow():
            return user["user_id"]
        
        return None
    except (ClientError, ValueError):
        return None


def verify_api_key(api_key: str) -> Optional[str]:
    """Verify API key and return user_id."""
    try:
        response = users_table.scan(
            FilterExpression="api_key = :key",
            ExpressionAttributeValues={":key": api_key}
        )
        
        if response.get("Items"):
            return response["Items"][0]["user_id"]
        return None
    except ClientError:
        return None


def get_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    try:
        response = users_table.get_item(Key={"user_id": user_id})
        return response.get("Item")
    except ClientError:
        return None


def update_gemini_key(user_id: str, gemini_key: str) -> bool:
    """Update user's Gemini API key."""
    try:
        users_table.update_item(
            Key={"user_id": user_id},
            UpdateExpression="SET gemini_key = :key",
            ExpressionAttributeValues={":key": gemini_key}
        )
        return True
    except ClientError:
        return False
