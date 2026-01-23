# DELTA3 - AI Coding Agent

An AI coding assistant powered by Google Gemini that executes code on a remote server. Write code, run scripts, and build projects using natural language.

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Your Mac    │     │   Gemini     │     │   EC2        │
│  (CLI)       │────▶│   API        │     │   Server     │
│              │◀────│              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘
       │                                         ▲
       │         HTTP API calls                  │
       └─────────────────────────────────────────┘
```

1. You type a request in the CLI
2. Gemini AI decides what tools to use
3. Tools execute on your EC2 server
4. Results return to you

## Features

- 🤖 **Natural Language → Code** - Describe what you want, AI writes & runs it
- 📁 **File Operations** - Create, read, edit files
- 💻 **Run Commands** - Execute Python, shell commands
- 🔐 **User Auth** - JWT tokens + API keys
- 🖥️ **Remote Execution** - Code runs on EC2, not your machine

## Quick Start

### Prerequisites
- Python 3.9+
- AWS EC2 instance (m5.metal for Firecracker, or any for subprocess mode)
- Google Gemini API key

### 1. Clone & Install

```bash
git clone https://github.com/stickfigure3/DEALTA3.git
cd DEALTA3
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Server Setup (EC2)

SSH into your EC2 instance:

```bash
# Clone repo on server
git clone https://github.com/stickfigure3/DEALTA3.git
cd DEALTA3

# Install dependencies
sudo apt-get update && sudo apt-get install -y python3 python3-pip python3.12-venv
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# (Optional) Install Firecracker for VM isolation
chmod +x server/setup_firecracker.sh
sudo ./server/setup_firecracker.sh

# Create config
cat > .env << 'EOF'
SECRET_KEY=your_random_secret_key_here
S3_BUCKET=your-bucket-name
AWS_REGION=us-east-1
EOF

# Start server
cd server
python3 api.py
```

Server runs on port 8000.

### 3. Register & Get API Key

```bash
# Register
curl -X POST http://YOUR_EC2_IP:8000/auth/register \
  -H "Content-Type: application/json" \
  -d '{"username": "yourname", "password": "yourpassword"}'

# Login (get token)
TOKEN=$(curl -s -X POST http://YOUR_EC2_IP:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "yourname", "password": "yourpassword"}' | jq -r '.token')

# Get API key
curl -X POST http://YOUR_EC2_IP:8000/auth/api-key \
  -H "Authorization: Bearer $TOKEN"
```

### 4. Configure Client

Create `.env` in your local DELTA3 folder:

```bash
DELTA3_API_URL=http://YOUR_EC2_IP:8000
DELTA3_API_KEY=delta3_xxxxxxxxxxxx
GEMINI_API_KEY=your_gemini_api_key
```

### 5. Run

```bash
source venv/bin/activate
python agent.py
```

## Usage Examples

```
🎯 You: Create a fibonacci function and test it with n=10

🔧 write_file({"path": "/home/user/fib.py", ...})
📤 Result: File written

🔧 run_terminal({"command": "python fib.py"})
📤 Result: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

🤖 Assistant: Created fib.py and ran it. Result shows first 10 Fibonacci numbers.
```

### Commands
| Command | Description |
|---------|-------------|
| `quit` | Save and exit |
| `save` | Save current state |
| `nosave` | Exit without saving |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Create account |
| `/auth/login` | POST | Get JWT token |
| `/auth/api-key` | POST | Generate API key |
| `/vm/start` | POST | Start workspace |
| `/vm/stop` | POST | Stop workspace |
| `/execute/code` | POST | Run Python code |
| `/execute/command` | POST | Run shell command |
| `/files/write` | POST | Write file |
| `/files/read` | POST | Read file |
| `/files/list` | GET | List files |
| `/health` | GET | Health check |

## Project Structure

```
DELTA3/
├── agent.py              # CLI client
├── requirements.txt      # Dependencies
├── .env                  # Local config (gitignored)
├── env.example           # Config template
└── server/
    ├── api.py            # FastAPI server
    ├── vm_manager.py     # VM lifecycle (Firecracker)
    └── setup_firecracker.sh  # Infrastructure setup
```

## Security Notes

- Each user gets isolated workspace
- API keys required for all operations
- JWT tokens expire in 30 days
- Server should be behind firewall (only allow your IP)

## Cost

| Resource | Cost |
|----------|------|
| EC2 m5.metal | ~$4.60/hr (stop when not using!) |
| EC2 t3.medium | ~$0.04/hr (no Firecracker) |
| Gemini API | Free tier available |

**Tip:** Use smaller instance without Firecracker for development, m5.metal only for production isolation.

## License

MIT
