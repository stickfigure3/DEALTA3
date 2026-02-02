"""
Long-term memory storage in DynamoDB.
"""

import os
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

import boto3
from botocore.exceptions import ClientError

# Configuration
MEMORIES_TABLE = os.environ.get("MEMORIES_TABLE", "delta3-memories")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Client
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)
memories_table = dynamodb.Table(MEMORIES_TABLE)


def save_memory(
    user_id: str,
    content: str,
    category: str,
    importance: int,
    tags: List[str] = None,
    source_context: str = None
) -> Dict[str, Any]:
    """Save a new memory."""
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
    tags: List[str] = None,
    limit: int = 20
) -> List[Dict[str, Any]]:
    """Get memories with optional filters."""
    try:
        if category:
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
            response = memories_table.query(
                KeyConditionExpression="user_id = :uid",
                ExpressionAttributeValues={":uid": user_id},
                ScanIndexForward=False,
                Limit=limit
            )

        memories = response.get("Items", [])

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


def search_memories(user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Search memories by keyword (simple text matching)."""
    all_memories = get_memories(user_id, limit=100)

    query_lower = query.lower()
    matches = []

    for memory in all_memories:
        content_lower = memory.get("content", "").lower()
        if query_lower in content_lower:
            matches.append(memory)

    matches.sort(key=lambda m: (m.get("importance", 0), m.get("created_at", "")), reverse=True)

    return matches[:limit]


def update_memory(
    user_id: str,
    memory_id: str,
    new_content: str = None,
    importance: int = None
) -> Dict[str, Any]:
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
