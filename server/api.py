#!/usr/bin/env python3
"""
Firecracker API Server - REST API for managing coding environments
"""

import os
import subprocess
import hashlib
import secrets
from typing import Optional
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import jwt

from vm_manager import VMManager

# === Configuration ===
SECRET_KEY = os.getenv("SECRET_KEY", secrets.token_hex(32))
S3_BUCKET = os.getenv("S3_BUCKET")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
KERNEL_PATH = os.getenv("KERNEL_PATH", "/opt/firecracker/vmlinux")
BASE_ROOTFS_PATH = os.getenv("BASE_ROOTFS_PATH", "/opt/firecracker/rootfs.ext4")

# === App Setup ===
app = FastAPI(title="DELTA3 Firecracker API", version="2.0.0")
security = HTTPBearer()

vm_manager = VMManager(
    kernel_path=KERNEL_PATH,
    base_rootfs_path=BASE_ROOTFS_PATH,
    s3_bucket=S3_BUCKET,
    aws_region=AWS_REGION
)

# Simple in-memory user store (replace with database in production)
users_db = {}
api_keys_db = {}


# === Models ===
class UserCreate(BaseModel):
    username: str
    password: str


class UserLogin(BaseModel):
    username: str
    password: str


class CodeExecution(BaseModel):
    code: str


class FileOperation(BaseModel):
    path: str
    content: Optional[str] = None


class CommandExecution(BaseModel):
    command: str


# === Auth Helpers ===
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


def create_token(user_id: str) -> str:
    payload = {
        "user_id": user_id,
        "exp": datetime.utcnow() + timedelta(days=30)
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        return payload["user_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")


def verify_api_key(x_api_key: str = Header(...)) -> str:
    if x_api_key not in api_keys_db:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_keys_db[x_api_key]


# === User Endpoints ===
@app.post("/auth/register")
async def register(user: UserCreate):
    if user.username in users_db:
        raise HTTPException(status_code=400, detail="User already exists")
    
    users_db[user.username] = {
        "password_hash": hash_password(user.password),
        "created_at": datetime.utcnow().isoformat()
    }
    
    return {"message": "User created", "username": user.username}


@app.post("/auth/login")
async def login(user: UserLogin):
    if user.username not in users_db:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    if users_db[user.username]["password_hash"] != hash_password(user.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    token = create_token(user.username)
    return {"token": token, "user_id": user.username}


@app.post("/auth/api-key")
async def create_api_key(user_id: str = Depends(verify_token)):
    api_key = f"delta3_{secrets.token_hex(24)}"
    api_keys_db[api_key] = user_id
    return {"api_key": api_key}


# === VM Endpoints ===
@app.post("/vm/start")
async def start_vm(user_id: str = Depends(verify_api_key)):
    """Start or restore user's VM."""
    try:
        vm = vm_manager.create_vm(user_id)
        return {
            "status": "running",
            "vm_id": vm.vm_id,
            "message": "VM started successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/vm/stop")
async def stop_vm(save: bool = True, user_id: str = Depends(verify_api_key)):
    """Stop user's VM, optionally saving state to S3."""
    vm_manager.stop_vm(user_id, save=save)
    return {"status": "stopped", "saved": save}


@app.get("/vm/status")
async def vm_status(user_id: str = Depends(verify_api_key)):
    """Get VM status."""
    vm = vm_manager.get_vm(user_id)
    if vm and vm.is_running():
        return {"status": "running", "vm_id": vm.vm_id}
    return {"status": "stopped"}


# === Code Execution Endpoints ===
def _execute_in_vm(user_id: str, command: str) -> dict:
    """Execute command in user's VM via chroot (mounting rootfs)."""
    vm = vm_manager.get_vm(user_id)
    if not vm or not vm.is_running():
        raise HTTPException(status_code=400, detail="VM not running. Call /vm/start first")
    
    # Get user's rootfs path
    rootfs_path = vm_manager._get_user_rootfs_path(user_id)
    if not rootfs_path.exists():
        return {"stdout": "", "stderr": "User rootfs not found", "exit_code": -1}
    
    # Mount point for chroot
    mount_point = f"/tmp/firecracker-chroot-{user_id}"
    
    try:
        # Create mount point
        Path(mount_point).mkdir(parents=True, exist_ok=True)
        
        # Mount rootfs (if not already mounted)
        if not os.path.ismount(mount_point):
            subprocess.run(["sudo", "mount", str(rootfs_path), mount_point], 
                         check=False, capture_output=True)
        
        # Execute command in chroot
        # Use bash -c to handle complex commands
        result = subprocess.run(
            ["sudo", "chroot", mount_point, "/bin/bash", "-c", 
             f"cd /home/user && {command}"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        return {
            "stdout": result.stdout,
            "stderr": result.stderr,
            "exit_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {"stdout": "", "stderr": "Command timed out", "exit_code": -1}
    except Exception as e:
        return {"stdout": "", "stderr": str(e), "exit_code": -1}


@app.post("/execute/code")
async def execute_code(req: CodeExecution, user_id: str = Depends(verify_api_key)):
    """Execute Python code in user's VM."""
    # Write code to temp file and execute
    escaped_code = req.code.replace("'", "'\"'\"'")
    command = f"python3 -c '{escaped_code}'"
    return _execute_in_vm(user_id, command)


@app.post("/execute/command")
async def execute_command(req: CommandExecution, user_id: str = Depends(verify_api_key)):
    """Execute shell command in user's VM."""
    return _execute_in_vm(user_id, req.command)


# === File Endpoints ===
@app.post("/files/write")
async def write_file(req: FileOperation, user_id: str = Depends(verify_api_key)):
    """Write file in user's VM."""
    if not req.content:
        raise HTTPException(status_code=400, detail="Content required")
    
    escaped_content = req.content.replace("'", "'\"'\"'")
    command = f"echo '{escaped_content}' > {req.path}"
    result = _execute_in_vm(user_id, command)
    
    if result["exit_code"] == 0:
        return {"status": "success", "path": req.path}
    return {"status": "error", "error": result["stderr"]}


@app.post("/files/read")
async def read_file(req: FileOperation, user_id: str = Depends(verify_api_key)):
    """Read file from user's VM."""
    result = _execute_in_vm(user_id, f"cat {req.path}")
    
    if result["exit_code"] == 0:
        return {"content": result["stdout"]}
    raise HTTPException(status_code=404, detail=f"File not found: {req.path}")


@app.get("/files/list")
async def list_files(path: str = "/home/user", user_id: str = Depends(verify_api_key)):
    """List files in directory."""
    result = _execute_in_vm(user_id, f"ls -la {path}")
    return {"files": result["stdout"], "path": path}


# === Health Check ===
@app.get("/health")
async def health():
    return {"status": "healthy", "version": "2.0.0"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
