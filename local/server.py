#!/usr/bin/env python3
"""
DELTA3 Local Development Server

A FastAPI server that mimics the AWS Lambda + API Gateway setup
for local development and testing.

Usage:
    python local/server.py

The server will start at http://localhost:8000
"""

import os
import sys
import json
import hashlib
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi import FastAPI, Request, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# Local storage (file-based instead of AWS)
DATA_DIR = Path(__file__).parent / "data"
USERS_FILE = DATA_DIR / "users.json"
MEMORIES_FILE = DATA_DIR / "memories.json"
CHAT_DIR = DATA_DIR / "chat"
FILES_DIR = DATA_DIR / "files"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
CHAT_DIR.mkdir(exist_ok=True)
FILES_DIR.mkdir(exist_ok=True)

app = FastAPI(title="DELTA3 Local Dev Server", version="3.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ Local Storage ============

def load_users() -> Dict:
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return {}

def save_users(users: Dict):
    USERS_FILE.write_text(json.dumps(users, indent=2))

def load_memories() -> Dict:
    if MEMORIES_FILE.exists():
        return json.loads(MEMORIES_FILE.read_text())
    return {}

def save_memories(memories: Dict):
    MEMORIES_FILE.write_text(json.dumps(memories, indent=2))


# ============ Auth Helpers ============

def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def generate_api_key() -> str:
    return f"delta3_{secrets.token_hex(24)}"

def generate_session_token() -> str:
    return secrets.token_hex(32)

def get_current_user(session_token: Optional[str] = None, api_key: Optional[str] = None) -> Optional[Dict]:
    """Verify credentials and return user."""
    users = load_users()
    
    if session_token:
        for user_id, user in users.items():
            sessions = user.get("sessions", {})
            if session_token in sessions:
                expires = sessions[session_token]
                if datetime.fromisoformat(expires) > datetime.utcnow():
                    return user
    
    if api_key:
        for user_id, user in users.items():
            if user.get("api_key") == api_key:
                return user
    
    return None


# ============ Request Models ============

class RegisterRequest(BaseModel):
    email: str
    password: str

class LoginRequest(BaseModel):
    email: str
    password: str

class GeminiKeyRequest(BaseModel):
    gemini_key: str

class ChatRequest(BaseModel):
    message: str

class FileWriteRequest(BaseModel):
    path: str
    content: str

class FileReadRequest(BaseModel):
    path: str

class MemoryDeleteRequest(BaseModel):
    memory_id: str


# ============ Auth Endpoints ============

@app.post("/auth/register")
async def register(req: RegisterRequest):
    users = load_users()
    user_id = req.email.lower()
    
    if user_id in users:
        raise HTTPException(400, "User already exists")
    
    if "@" not in req.email:
        raise HTTPException(400, "Invalid email format")
    
    if len(req.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")
    
    api_key = generate_api_key()
    
    users[user_id] = {
        "user_id": user_id,
        "email": req.email,
        "password_hash": hash_password(req.password),
        "api_key": api_key,
        "gemini_key": None,
        "created_at": datetime.utcnow().isoformat(),
        "sessions": {}
    }
    
    save_users(users)
    
    return {"message": "Account created", "user_id": user_id, "api_key": api_key}


@app.post("/auth/login")
async def login(req: LoginRequest):
    users = load_users()
    user_id = req.email.lower()
    
    user = users.get(user_id)
    if not user or user["password_hash"] != hash_password(req.password):
        raise HTTPException(401, "Invalid credentials")
    
    session_token = generate_session_token()
    expires = (datetime.utcnow() + timedelta(days=7)).isoformat()
    
    user["sessions"][session_token] = expires
    user["last_login"] = datetime.utcnow().isoformat()
    save_users(users)
    
    return {
        "message": "Login successful",
        "session_token": session_token,
        "user_id": user_id,
        "api_key": user["api_key"],
        "gemini_key_set": user.get("gemini_key") is not None,
        "expires": expires
    }


@app.get("/auth/me")
async def get_me(x_session_token: Optional[str] = Header(None)):
    user = get_current_user(session_token=x_session_token)
    if not user:
        raise HTTPException(401, "Invalid or expired session")
    
    return {
        "user_id": user["user_id"],
        "email": user["email"],
        "api_key": user["api_key"],
        "gemini_key_set": user.get("gemini_key") is not None,
        "created_at": user["created_at"]
    }


@app.post("/auth/gemini-key")
async def set_gemini_key(req: GeminiKeyRequest, x_session_token: Optional[str] = Header(None)):
    users = load_users()
    user = get_current_user(session_token=x_session_token)
    if not user:
        raise HTTPException(401, "Invalid or expired session")
    
    if not req.gemini_key.startswith("AIza"):
        raise HTTPException(400, "Invalid Gemini API key format")
    
    users[user["user_id"]]["gemini_key"] = req.gemini_key
    save_users(users)
    
    return {"message": "Gemini API key updated"}


@app.post("/auth/logout")
async def logout():
    return {"message": "Logged out"}


# ============ Chat Endpoints ============

@app.post("/chat/send")
async def send_message(
    req: ChatRequest,
    x_session_token: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    user = get_current_user(session_token=x_session_token, api_key=x_api_key)
    if not user:
        raise HTTPException(401, "Authentication required")
    
    if not user.get("gemini_key"):
        raise HTTPException(400, "Gemini API key not set")
    
    user_id = user["user_id"]
    
    # Load chat history
    chat_file = CHAT_DIR / f"{user_id.replace('@', '_').replace('.', '_')}.json"
    chat_history = []
    if chat_file.exists():
        chat_history = json.loads(chat_file.read_text())
    
    # Create agent
    from agent import GeminiAgent
    
    # Create a local storage module
    class LocalStorage:
        def save_memory(self, user_id, content, category, importance, tags=None, source_context=None):
            memories = load_memories()
            if user_id not in memories:
                memories[user_id] = []
            
            import uuid
            memory_id = f"{datetime.utcnow().isoformat()}#{uuid.uuid4().hex[:8]}"
            
            memories[user_id].append({
                "memory_id": memory_id,
                "content": content,
                "category": category,
                "importance": importance,
                "tags": tags or [],
                "created_at": datetime.utcnow().isoformat()
            })
            
            save_memories(memories)
            return {"success": True, "memory_id": memory_id}
        
        def get_memories(self, user_id, category=None, min_importance=None, limit=20):
            memories = load_memories().get(user_id, [])
            
            if category:
                memories = [m for m in memories if m.get("category") == category]
            if min_importance:
                memories = [m for m in memories if m.get("importance", 0) >= min_importance]
            
            return memories[:limit]
        
        def search_memories(self, user_id, query, limit=5):
            memories = self.get_memories(user_id, limit=100)
            query_lower = query.lower()
            matches = [m for m in memories if query_lower in m.get("content", "").lower()]
            return matches[:limit]
        
        def update_memory(self, user_id, memory_id, new_content=None, importance=None):
            memories = load_memories()
            user_memories = memories.get(user_id, [])
            
            for m in user_memories:
                if m["memory_id"] == memory_id:
                    if new_content:
                        m["content"] = new_content
                    if importance is not None:
                        m["importance"] = importance
                    save_memories(memories)
                    return {"success": True}
            
            return {"success": False, "error": "Memory not found"}
        
        def delete_memory(self, user_id, memory_id):
            memories = load_memories()
            user_memories = memories.get(user_id, [])
            memories[user_id] = [m for m in user_memories if m["memory_id"] != memory_id]
            save_memories(memories)
            return True
    
    # Workspace directory will be created by the executor with "workspace_" prefix

    agent = GeminiAgent(
        api_key=user["gemini_key"],
        user_id=user_id,
        chat_history=chat_history[-20:],
        local_mode=True,
        workspace_base=str(FILES_DIR),
        storage_module=LocalStorage()
    )
    
    try:
        result = agent.process_message(req.message)
        
        # Save to history
        chat_history.append({
            "role": "user",
            "content": req.message,
            "timestamp": datetime.utcnow().isoformat()
        })
        chat_history.append({
            "role": "assistant",
            "content": result["response"],
            "tool_calls": result.get("tool_calls"),
            "timestamp": datetime.utcnow().isoformat()
        })
        
        # Keep last 100
        if len(chat_history) > 100:
            chat_history = chat_history[-100:]
        
        chat_file.write_text(json.dumps(chat_history, indent=2))
        
        return {
            "response": result["response"],
            "tool_calls": result.get("tool_calls", [])
        }
    
    except Exception as e:
        import traceback
        raise HTTPException(500, f"Chat error: {str(e)}\n{traceback.format_exc()}")


@app.get("/chat/history")
async def get_history(
    limit: int = 50,
    x_session_token: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    user = get_current_user(session_token=x_session_token, api_key=x_api_key)
    if not user:
        raise HTTPException(401, "Authentication required")
    
    user_id = user["user_id"]
    chat_file = CHAT_DIR / f"{user_id.replace('@', '_').replace('.', '_')}.json"
    
    if not chat_file.exists():
        return {"history": []}
    
    history = json.loads(chat_file.read_text())
    return {"history": history[-limit:]}


@app.post("/chat/clear")
async def clear_history(
    x_session_token: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    user = get_current_user(session_token=x_session_token, api_key=x_api_key)
    if not user:
        raise HTTPException(401, "Authentication required")
    
    user_id = user["user_id"]
    chat_file = CHAT_DIR / f"{user_id.replace('@', '_').replace('.', '_')}.json"
    
    if chat_file.exists():
        chat_file.unlink()
    
    return {"message": "History cleared"}


# ============ File Endpoints ============

@app.get("/files/list")
async def list_files(
    path: str = "",
    x_session_token: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    user = get_current_user(session_token=x_session_token, api_key=x_api_key)
    if not user:
        raise HTTPException(401, "Authentication required")
    
    user_id = user["user_id"]
    safe_user_id = user_id.replace('@', '_').replace('.', '_')
    user_dir = FILES_DIR / f"workspace_{safe_user_id}"
    
    if path:
        user_dir = user_dir / path.lstrip("/")
    
    if not user_dir.exists():
        return {"files": [], "path": path}
    
    files = []
    for item in user_dir.iterdir():
        files.append({
            "name": item.name,
            "type": "directory" if item.is_dir() else "file",
            "size": item.stat().st_size if item.is_file() else None
        })
    
    return {"files": files, "path": path}


@app.post("/files/read")
async def read_file(
    req: FileReadRequest,
    x_session_token: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    user = get_current_user(session_token=x_session_token, api_key=x_api_key)
    if not user:
        raise HTTPException(401, "Authentication required")
    
    user_id = user["user_id"]
    safe_user_id = user_id.replace('@', '_').replace('.', '_')
    file_path = FILES_DIR / f"workspace_{safe_user_id}" / req.path.lstrip("/")
    
    if not file_path.exists():
        raise HTTPException(404, "File not found")
    
    return {"content": file_path.read_text(), "path": req.path}


@app.post("/files/write")
async def write_file(
    req: FileWriteRequest,
    x_session_token: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    user = get_current_user(session_token=x_session_token, api_key=x_api_key)
    if not user:
        raise HTTPException(401, "Authentication required")
    
    user_id = user["user_id"]
    safe_user_id = user_id.replace('@', '_').replace('.', '_')
    file_path = FILES_DIR / f"workspace_{safe_user_id}" / req.path.lstrip("/")
    
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(req.content)
    
    return {"message": "File saved", "path": req.path}


@app.post("/files/delete")
async def delete_file(
    req: FileReadRequest,
    x_session_token: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    user = get_current_user(session_token=x_session_token, api_key=x_api_key)
    if not user:
        raise HTTPException(401, "Authentication required")
    
    user_id = user["user_id"]
    safe_user_id = user_id.replace('@', '_').replace('.', '_')
    file_path = FILES_DIR / f"workspace_{safe_user_id}" / req.path.lstrip("/")
    
    if file_path.exists():
        file_path.unlink()
    
    return {"message": "File deleted", "path": req.path}


# ============ Memory Endpoints ============

@app.get("/memories")
async def get_memories(
    category: Optional[str] = None,
    limit: int = 50,
    x_session_token: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    user = get_current_user(session_token=x_session_token, api_key=x_api_key)
    if not user:
        raise HTTPException(401, "Authentication required")
    
    user_id = user["user_id"]
    memories = load_memories().get(user_id, [])
    
    if category:
        memories = [m for m in memories if m.get("category") == category]
    
    return {"memories": memories[:limit]}


@app.delete("/memories")
async def delete_memory(
    req: MemoryDeleteRequest,
    x_session_token: Optional[str] = Header(None),
    x_api_key: Optional[str] = Header(None)
):
    user = get_current_user(session_token=x_session_token, api_key=x_api_key)
    if not user:
        raise HTTPException(401, "Authentication required")
    
    user_id = user["user_id"]
    memories = load_memories()
    user_memories = memories.get(user_id, [])
    
    memories[user_id] = [m for m in user_memories if m.get("memory_id") != req.memory_id]
    save_memories(memories)
    
    return {"success": True}


# ============ Startup ============

def create_root_user():
    """Create root user with preset Gemini key on startup."""
    users = load_users()
    
    user_id = "root"  # Simple user ID for local dev
    
    # Get Gemini key from environment variable (required for local dev)
    gemini_key = os.environ.get("GEMINI_API_KEY")
    
    if user_id not in users:
        users[user_id] = {
            "user_id": user_id,
            "email": user_id,  # Use same as user_id for simplicity
            "password_hash": hash_password("root"),
            "api_key": generate_api_key(),
            "gemini_key": gemini_key,  # Will be None if not set
            "created_at": datetime.utcnow().isoformat(),
            "sessions": {}
        }
        
        save_users(users)
        if gemini_key:
            print("✅ Created root user (email: root, password: root, Gemini key: set)")
        else:
            print("✅ Created root user (email: root, password: root)")
            print("⚠️  GEMINI_API_KEY not set - set it in .env or environment")
    else:
        # Ensure Gemini key is updated from env if provided
        if gemini_key and not users[user_id].get("gemini_key"):
            users[user_id]["gemini_key"] = gemini_key
            save_users(users)
        print("ℹ️  Root user already exists")


@app.on_event("startup")
async def startup():
    create_root_user()
    print("""
╔═══════════════════════════════════════════════════════════════╗
║                    DELTA3 Local Dev Server                     ║
╠═══════════════════════════════════════════════════════════════╣
║  API:      http://localhost:8000                               ║
║  Docs:     http://localhost:8000/docs                          ║
║                                                                 ║
║  Root User:                                                     ║
║    Email:    root                                               ║
║    Password: root                                               ║
║    (Gemini key pre-configured)                                  ║
╚═══════════════════════════════════════════════════════════════╝
""")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
