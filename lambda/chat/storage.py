"""
Storage utilities for DynamoDB and S3 operations.
"""

import os
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import boto3
from botocore.exceptions import ClientError

# Configuration
USERS_TABLE = os.environ.get("USERS_TABLE", "delta3-users")
FILES_BUCKET = os.environ.get("FILES_BUCKET", "delta3-files")
MEMORIES_TABLE = os.environ.get("MEMORIES_TABLE", "delta3-memories")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Clients
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
s3 = boto3.client("s3", region_name=AWS_REGION)
users_table = dynamodb.Table(USERS_TABLE)
memories_table = dynamodb.Table(MEMORIES_TABLE)


def hash_password(password: str) -> str:
    """Hash password with SHA256."""
    return hashlib.sha256(password.encode()).hexdigest()


def generate_api_key() -> str:
    """Generate a unique API key."""
    return f"delta3_{secrets.token_hex(24)}"


def generate_session_token() -> str:
    """Generate a session token."""
    return secrets.token_hex(32)


# === User Operations ===

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
    # Scan for session (in production, use GSI)
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


# === File Operations ===

def get_user_prefix(user_id: str) -> str:
    """Get S3 prefix for user's files."""
    return f"users/{user_id}/"


def write_file(user_id: str, path: str, content: str) -> bool:
    """Write file to S3."""
    # Normalize path
    if path.startswith("/"):
        path = path[1:]
    
    key = f"{get_user_prefix(user_id)}{path}"
    
    try:
        s3.put_object(
            Bucket=FILES_BUCKET,
            Key=key,
            Body=content.encode("utf-8"),
            ContentType="text/plain"
        )
        return True
    except ClientError:
        return False


def read_file(user_id: str, path: str) -> Optional[str]:
    """Read file from S3."""
    if path.startswith("/"):
        path = path[1:]
    
    key = f"{get_user_prefix(user_id)}{path}"
    
    try:
        response = s3.get_object(Bucket=FILES_BUCKET, Key=key)
        return response["Body"].read().decode("utf-8")
    except ClientError:
        return None


def list_files(user_id: str, path: str = "") -> list:
    """List files in user's directory."""
    if path.startswith("/"):
        path = path[1:]
    
    prefix = f"{get_user_prefix(user_id)}{path}"
    
    try:
        response = s3.list_objects_v2(
            Bucket=FILES_BUCKET,
            Prefix=prefix,
            Delimiter="/"
        )
        
        files = []
        
        # Files
        for obj in response.get("Contents", []):
            name = obj["Key"].replace(prefix, "")
            if name:
                files.append({
                    "name": name,
                    "type": "file",
                    "size": obj["Size"],
                    "modified": obj["LastModified"].isoformat()
                })
        
        # Directories
        for prefix_obj in response.get("CommonPrefixes", []):
            name = prefix_obj["Prefix"].replace(prefix, "").rstrip("/")
            if name:
                files.append({
                    "name": name,
                    "type": "directory"
                })
        
        return files
    except ClientError:
        return []


def delete_file(user_id: str, path: str) -> bool:
    """Delete file from S3."""
    if path.startswith("/"):
        path = path[1:]
    
    key = f"{get_user_prefix(user_id)}{path}"
    
    try:
        s3.delete_object(Bucket=FILES_BUCKET, Key=key)
        return True
    except ClientError:
        return False


# === Chat History ===

def save_chat_message(user_id: str, role: str, content: str, tool_calls: list = None):
    """Save chat message to history."""
    key = f"{get_user_prefix(user_id)}chat_history.json"
    
    # Load existing
    try:
        response = s3.get_object(Bucket=FILES_BUCKET, Key=key)
        history = json.loads(response["Body"].read().decode("utf-8"))
    except ClientError:
        history = []
    
    # Append message
    message = {
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat()
    }
    if tool_calls:
        message["tool_calls"] = tool_calls
    
    history.append(message)
    
    # Keep last 100 messages
    if len(history) > 100:
        history = history[-100:]
    
    # Save
    s3.put_object(
        Bucket=FILES_BUCKET,
        Key=key,
        Body=json.dumps(history).encode("utf-8"),
        ContentType="application/json"
    )


def get_chat_history(user_id: str, limit: int = 20) -> list:
    """Get recent chat history."""
    key = f"{get_user_prefix(user_id)}chat_history.json"
    
    try:
        response = s3.get_object(Bucket=FILES_BUCKET, Key=key)
        history = json.loads(response["Body"].read().decode("utf-8"))
        return history[-limit:]
    except ClientError:
        return []


def clear_chat_history(user_id: str) -> bool:
    """Clear chat history."""
    key = f"{get_user_prefix(user_id)}chat_history.json"

    try:
        s3.delete_object(Bucket=FILES_BUCKET, Key=key)
        return True
    except ClientError:
        return False


# === Memory Management ===

def save_memory(
    user_id: str,
    content: str,
    category: str,
    importance: int,
    tags: list = None,
    source_context: str = None
) -> dict:
    """Save a new memory."""
    import uuid

    timestamp = datetime.utcnow().isoformat() + 'Z'
    memory_id = f"{timestamp}#{uuid.uuid4().hex[:8]}"

    item = {
        "user_id": user_id,
        "memory_id": memory_id,
        "content": content,
        "category": category,
        "importance": importance,
        "tags": tags or [],
        "created_at": timestamp,
        "last_accessed": timestamp,
        "access_count": 0,
    }

    if source_context:
        item["source_context"] = source_context

    try:
        memories_table.put_item(Item=item)
        return {"success": True, "memory_id": memory_id}
    except ClientError as e:
        return {"success": False, "error": str(e)}


def get_memories(
    user_id: str,
    category: str = None,
    min_importance: int = None,
    tags: list = None,
    limit: int = 20
) -> list:
    """Get memories with optional filters."""
    try:
        if category:
            # Use CategoryIndex GSI
            response = memories_table.query(
                IndexName="CategoryIndex",
                KeyConditionExpression="user_id = :uid AND category = :cat",
                ExpressionAttributeValues={
                    ":uid": user_id,
                    ":cat": category
                },
                ScanIndexForward=False,
                Limit=limit
            )
        else:
            # Query main table
            response = memories_table.query(
                KeyConditionExpression="user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
                ScanIndexForward=False,
                Limit=limit
            )

        memories = response.get("Items", [])

        # Apply post-filters
        if min_importance:
            memories = [m for m in memories if m.get("importance", 0) >= min_importance]

        if tags:
            memories = [m for m in memories if any(t in m.get("tags", []) for t in tags)]

        # Update access stats for top 10 memories
        for memory in memories[:10]:
            _increment_access_count(user_id, memory["memory_id"])

        return memories

    except ClientError as e:
        print(f"Error getting memories: {e}")
        return []


def search_memories(user_id: str, query: str, limit: int = 5) -> list:
    """Search memories by keyword (simple text matching)."""
    all_memories = get_memories(user_id, limit=100)

    # Simple keyword search (case-insensitive)
    query_lower = query.lower()
    matches = []

    for memory in all_memories:
        content_lower = memory.get("content", "").lower()
        if query_lower in content_lower:
            matches.append(memory)

    # Sort by importance, then recency
    matches.sort(key=lambda m: (m.get("importance", 0), m.get("created_at", "")), reverse=True)

    return matches[:limit]


def update_memory(user_id: str, memory_id: str, new_content: str = None, importance: int = None) -> dict:
    """Update an existing memory."""
    try:
        update_expr = "SET last_accessed = :now"
        expr_values = {":now": datetime.utcnow().isoformat() + 'Z'}

        if new_content:
            update_expr += ", content = :content"
            expr_values[":content"] = new_content

        if importance is not None:
            update_expr += ", importance = :imp"
            expr_values[":imp"] = importance

        memories_table.update_item(
            Key={"user_id": user_id, "memory_id": memory_id},
            UpdateExpression=update_expr,
            ExpressionAttributeValues=expr_values
        )

        return {"success": True}
    except ClientError as e:
        return {"success": False, "error": str(e)}


def delete_memory(user_id: str, memory_id: str) -> bool:
    """Delete a memory."""
    try:
        memories_table.delete_item(
            Key={"user_id": user_id, "memory_id": memory_id}
        )
        return True
    except ClientError:
        return False


def _increment_access_count(user_id: str, memory_id: str):
    """Increment access count for a memory."""
    try:
        memories_table.update_item(
            Key={"user_id": user_id, "memory_id": memory_id},
            UpdateExpression="SET access_count = access_count + :inc, last_accessed = :now",
            ExpressionAttributeValues={
                ":inc": 1,
                ":now": datetime.utcnow().isoformat() + 'Z'
            }
        )
    except ClientError:
        pass  # Non-critical, fail silently
