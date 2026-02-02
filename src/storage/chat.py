"""
Chat history storage in S3.
"""

import os
import json
from datetime import datetime
from typing import List, Dict, Any

import boto3
from botocore.exceptions import ClientError

from .files import get_user_prefix

# Configuration
FILES_BUCKET = os.environ.get("FILES_BUCKET", "delta3-files")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Client
s3 = boto3.client("s3", region_name=AWS_REGION)


def save_chat_message(user_id: str, role: str, content: str, tool_calls: List = None):
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


def get_chat_history(user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
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
