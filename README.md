# DELTA3 - AI Coding Agent

A CLI tool that connects to an AI coding agent running in a cloud sandbox. The agent can write, execute, and persist code across sessions.

## How It Works

```
┌─────────────┐     ┌──────────────┐     ┌─────────────┐
│   Your      │     │   Google     │     │    E2B      │
│  Terminal   │────▶│   Gemini     │────▶│  Sandbox    │
│             │◀────│    API       │◀────│  (Cloud)    │
└─────────────┘     └──────────────┘     └─────────────┘
```

1. **You** type a request in your terminal
2. **Gemini AI** receives your request and decides what tools to use
3. **E2B Sandbox** executes the code in a secure cloud environment
4. Results flow back through Gemini to you

## Features

- 🔧 **Execute Python code** in a secure cloud sandbox
- 📁 **Read/write files** that persist across sessions
- 💻 **Run terminal commands** (pip install, python scripts, etc.)
- 🔄 **Persistent sandbox** - reconnect to continue where you left off
- 🤖 **Agentic loop** - AI automatically chains tool calls to complete tasks

## Quick Start

### 1. Install Dependencies

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Set Up API Keys

Create a `.env` file:

```bash
E2B_API_KEY=your_e2b_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

Get your keys from:
- **E2B**: https://e2b.dev/dashboard
- **Gemini**: https://aistudio.google.com/app/apikey

### 3. Run the Agent

```bash
source venv/bin/activate
python agent.py
```

## Usage Examples

```
🎯 You: Create a python file that calculates fibonacci numbers and run it

🔧 write_file({"path": "/home/user/fib.py", ...})
📤 Result: File written: /home/user/fib.py

🔧 run_terminal({"command": "python /home/user/fib.py"})
📤 Result: [0, 1, 1, 2, 3, 5, 8, 13, 21, 34]

🤖 Assistant: I created fib.py and ran it. The first 10 Fibonacci numbers are shown above.
```

## Commands

| Command | Description |
|---------|-------------|
| `quit` or `exit` | Exit (sandbox stays alive for reconnection) |
| `new` | Create a fresh sandbox |

## Architecture

### Components

- **`agent.py`** - Main CLI application
- **Google Gemini** - LLM that decides which tools to use
- **E2B Sandbox** - Secure cloud environment for code execution

### Tools Available to the AI

| Tool | Description |
|------|-------------|
| `execute_code` | Run Python code directly |
| `write_file` | Save files to `/home/user/` |
| `read_file` | Read file contents |
| `run_terminal` | Execute shell commands |
| `list_files` | List directory contents |

### File Storage & Persistence

Files are saved in the E2B sandbox at `/home/user/`.

**Persistence behavior:**
- ✅ Files persist when you `quit` the agent (sandbox stays alive)
- ✅ Files persist when you reconnect using saved `.sandbox_id`
- ❌ Files are lost if you type `new` (creates fresh sandbox)
- ❌ Files are lost if sandbox times out (default 5 min, max 24h Pro / 1h Free)

**Tested example:**
```
Step 1: Write file → persist_test.py created
Step 2: Quit agent
Step 3: Restart agent → reconnects to same sandbox
Step 4: File still exists, runs successfully: "I survived!"
```

## Cost

- **E2B**: ~$0.05/hour per sandbox (free tier available)
- **Gemini**: Free tier available with rate limits

## Requirements

- Python 3.9+
- E2B API key
- Google Gemini API key
