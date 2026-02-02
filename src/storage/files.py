"""
S3 file storage operations.
"""

import os
from typing import Optional, List, Dict, Any

import boto3
from botocore.exceptions import ClientError

# Configuration
FILES_BUCKET = os.environ.get("FILES_BUCKET", "delta3-files")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")

# Client
s3 = boto3.client("s3", region_name=AWS_REGION)


def get_user_prefix(user_id: str) -> str:
    """Get S3 prefix for user's files."""
    return f"users/{user_id}/"


def write_file(user_id: str, path: str, content: str) -> bool:
    """Write file to S3."""
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


def list_files(user_id: str, path: str = "") -> List[Dict[str, Any]]:
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
