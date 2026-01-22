# DELTA3 - AI Coding Agent with Firecracker MicroVMs

A self-hosted AI coding environment using AWS Firecracker microVMs for secure, isolated code execution with S3-backed persistence.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Your Infrastructure                       │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │   Client     │     │  API Server  │     │  Firecracker │     │
│  │   (CLI)      │────▶│  (FastAPI)   │────▶│   MicroVM    │     │
│  │              │◀────│              │◀────│              │     │
│  └──────────────┘     └──────────────┘     └──────────────┘     │
│         │                    │                                    │
│         │                    ▼                                    │
│         │             ┌──────────────┐                           │
│         └────────────▶│  Google      │                           │
│                       │  Gemini API  │                           │
│                       └──────────────┘                           │
│                              │                                    │
│                              ▼                                    │
│                       ┌──────────────┐                           │
│                       │     S3       │                           │
│                       │ (Persistence)│                           │
│                       └──────────────┘                           │
└─────────────────────────────────────────────────────────────────┘
```

## Features

- 🔥 **Firecracker MicroVMs** - Secure, lightweight VM isolation
- 🤖 **Gemini AI Integration** - Natural language → code execution
- 💾 **S3 Persistence** - Environments saved per-user to S3
- 🔐 **User Authentication** - API keys and JWT tokens
- 🚀 **Fast Boot** - VMs start in ~125ms

## Components

| Component | Description |
|-----------|-------------|
| `agent.py` | CLI client - connects to API server |
| `server/api.py` | FastAPI server - manages VMs and auth |
| `server/vm_manager.py` | Firecracker VM lifecycle management |
| `server/setup_firecracker.sh` | Infrastructure setup script |

## Quick Start

### 1. Server Setup (EC2 with KVM)

```bash
# SSH into your EC2 instance (.metal or nitro for KVM support)
# Run the setup script
chmod +x server/setup_firecracker.sh
sudo ./server/setup_firecracker.sh

# Configure environment
cp env.example .env
# Edit .env with your S3 bucket, AWS credentials, etc.

# Start API server
cd server
pip install -r ../requirements.txt
python api.py
```

### 2. Client Setup (Your Machine)

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp env.example .env
# Edit .env:
#   DELTA3_API_URL=http://your-server:8000
#   GEMINI_API_KEY=your_key

# Register and get API key
curl -X POST http://your-server:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "myuser", "password": "mypass"}'

curl -X POST http://your-server:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "myuser", "password": "mypass"}'
# Save the token, then:

curl -X POST http://your-server:8000/auth/api-key \
  -H "Authorization: Bearer <your_token>"
# Add the api_key to .env as DELTA3_API_KEY

# Run the agent
python agent.py
```

## Usage

```
🎯 You: Create a fibonacci function and test it

🔧 write_file({"path": "/home/user/fib.py", ...})
📤 Result: File written: /home/user/fib.py

🔧 run_terminal({"command": "python /home/user/fib.py"})
📤 Result: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

🤖 Assistant: I created fib.py with a fibonacci function and tested it.
```

### Commands

| Command | Description |
|---------|-------------|
| `quit` / `exit` | Save environment to S3 and exit |
| `save` | Save current state to S3 (continues session) |
| `nosave` | Exit without saving |

## API Endpoints

### Authentication
- `POST /auth/register` - Create account
- `POST /auth/login` - Get JWT token
- `POST /auth/api-key` - Generate API key

### VM Management
- `POST /vm/start` - Start or restore VM
- `POST /vm/stop` - Stop VM (optionally save to S3)
- `GET /vm/status` - Check VM status

### Code Execution
- `POST /execute/code` - Run Python code
- `POST /execute/command` - Run shell command

### Files
- `POST /files/write` - Write file
- `POST /files/read` - Read file
- `GET /files/list` - List directory

## Persistence

User environments are automatically saved to S3:

```
s3://your-bucket/
  └── users/
      └── {user_id}/
          └── rootfs.ext4  # Complete VM filesystem
```

- **On `quit`**: Filesystem snapshot uploaded to S3
- **On reconnect**: Filesystem restored from S3
- **Files persist**: Code, packages, everything in `/home/user`

## Infrastructure Requirements

### Server (EC2)
- Instance type: `.metal` or Nitro-based (for KVM)
- Recommended: `m5.metal` or `c5.metal`
- OS: Ubuntu 20.04+ or Amazon Linux 2
- Storage: 50GB+ EBS

### AWS Resources
- S3 bucket for persistence
- IAM role with S3 read/write access

## Cost Estimate

| Resource | Cost |
|----------|------|
| EC2 m5.metal | ~$4.60/hr (on-demand) |
| EC2 m5.metal | ~$1.50/hr (spot) |
| S3 storage | ~$0.023/GB/month |
| Gemini API | Free tier available |

## Migration from E2B

| Change | E2B | Firecracker |
|--------|-----|-------------|
| SDK | `e2b-code-interpreter` | HTTP client to your API |
| Auth | E2B API key | Your API key system |
| Persistence | Built-in (limited) | S3 (unlimited) |
| Cost | $0.05/hr per sandbox | Your infrastructure |
| Isolation | Container | Full microVM |

## Security

- Each user gets isolated Firecracker VM
- VMs have no network access by default
- S3 data encrypted at rest
- JWT + API key authentication

## License

MIT
