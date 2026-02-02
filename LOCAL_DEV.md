# DELTA3 Local Development Guide

Run the entire DELTA3 stack (frontend + backend) locally without AWS.

## Quick Start

```bash
# 1. Clone the repo
git clone https://github.com/stickfigure3/DEALTA3.git
cd DEALTA3

# 2. Set up environment
cp env.example .env
# Edit .env and add your Gemini API key

# 3. Run everything
./dev.sh
```

Visit http://localhost:3000 and login with:
- Email: `root`
- Password: `root`

## Prerequisites

- Python 3.8 or higher
- Gemini API key ([Get one free](https://makersuite.google.com/app/apikey))

## Manual Setup

If you prefer to set things up manually:

### 1. Environment Configuration

```bash
# Copy the example env file
cp env.example .env

# Edit .env and set your Gemini API key
# Required: GEMINI_API_KEY=AIzaSy...
```

### 2. Install Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 3. Start Backend

```bash
# In terminal 1
python local/server.py
```

The backend will start at http://localhost:8000

### 4. Start Frontend

```bash
# In terminal 2
cd frontend
python3 -m http.server 3000
```

The frontend will be at http://localhost:3000

## Architecture (Local Mode)

```
┌─────────────────────────────────────────────────────────────┐
│                     Local Development                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   Frontend (http://localhost:3000)                          │
│   └── Static HTML/CSS/JS                                    │
│        └── Detects localhost and uses local API             │
│                                                              │
│   Backend (http://localhost:8000)                           │
│   └── FastAPI Server (mimics AWS Lambda)                    │
│        ├── Auth endpoints                                   │
│        ├── Chat endpoints                                   │
│        ├── File management                                  │
│        └── Memory system                                    │
│                                                              │
│   Storage (local/data/)                                     │
│   ├── users.json       (replaces DynamoDB)                  │
│   ├── memories.json    (replaces DynamoDB)                  │
│   ├── chat/            (replaces S3)                        │
│   └── files/           (replaces S3)                        │
│                                                              │
│   External Services                                         │
│   └── Google Gemini API (same as production)               │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Key Differences from Production

| Feature | Production | Local Development |
|---------|-----------|-------------------|
| Backend | AWS Lambda | FastAPI server |
| User DB | DynamoDB | local/data/users.json |
| Memory DB | DynamoDB | local/data/memories.json |
| File storage | S3 | local/data/files/ |
| Chat history | DynamoDB | local/data/chat/ |
| Authentication | Sessions in DynamoDB | Sessions in users.json |
| Root user | N/A | Auto-created (root/root) |

## Default Credentials

A root user is automatically created on first run:

- **Email:** `root`
- **Password:** `root`
- **Gemini Key:** Auto-configured from `.env`

You can create additional users through the web interface.

## API Documentation

When the backend is running, visit:

- **Interactive Docs:** http://localhost:8000/docs
- **OpenAPI Schema:** http://localhost:8000/openapi.json

## Available Endpoints

All endpoints are identical to production:

### Auth
- `POST /auth/register` - Create new account
- `POST /auth/login` - Login and get session token
- `GET /auth/me` - Get current user info
- `POST /auth/gemini-key` - Set Gemini API key
- `POST /auth/logout` - Logout

### Chat
- `POST /chat/send` - Send message to AI
- `GET /chat/history` - Get chat history
- `POST /chat/clear` - Clear chat history

### Files
- `GET /files/list` - List files in workspace
- `POST /files/read` - Read file content
- `POST /files/write` - Write/update file
- `POST /files/delete` - Delete file

### Memory
- `GET /memories` - Get saved memories
- `DELETE /memories` - Delete a memory

## Data Storage

All local data is stored in `local/data/`:

```
local/data/
├── users.json              # User accounts and sessions
├── memories.json           # AI memory system
├── chat/                   # Chat histories
│   └── user@example_com.json
└── files/                  # User workspaces
    └── user@example_com/
        ├── script.py
        └── notes.txt
```

This data persists across restarts.

## Development Tips

### Hot Reloading

The FastAPI server supports auto-reload during development:

```bash
# Backend auto-reloads when code changes
python local/server.py
```

For frontend changes, just refresh the browser.

### Clearing Data

```bash
# Clear all local data
rm -rf local/data/

# Clear specific user's data
rm local/data/chat/username_example_com.json
rm -rf local/data/files/username_example_com/
```

### Testing API Endpoints

```bash
# Using curl
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"root","password":"root"}'

# Using the interactive docs
open http://localhost:8000/docs
```

### Debugging

The local server prints all requests and errors to the console. Check the terminal where you ran `python local/server.py` for logs.

## Troubleshooting

### Port Already in Use

If port 8000 or 3000 is already in use:

```bash
# Find and kill process on port 8000
lsof -ti:8000 | xargs kill -9

# Or change the port in local/server.py
uvicorn.run(app, host="0.0.0.0", port=8001)

# And update frontend/app.js
const API_URL = 'http://localhost:8001'
```

### Gemini API Errors

Common issues:

- **"Gemini API key not set"** - Check `.env` file has `GEMINI_API_KEY=AIza...`
- **"Invalid API key"** - Verify key is valid at https://makersuite.google.com/
- **Rate limit errors** - Free tier has limits; wait or upgrade

### Import Errors

If you see `ModuleNotFoundError`:

```bash
# Make sure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

### CORS Errors

The local server has CORS enabled for all origins. If you still see CORS errors:

1. Make sure backend is running on port 8000
2. Check frontend is accessing `http://localhost:8000` (not `127.0.0.1`)
3. Clear browser cache and reload

## Switching to Production

When ready to deploy:

```bash
# Deploy to AWS
./deploy.sh dev
```

Your local data won't transfer to AWS - production uses separate storage.

## File Structure

```
DELTA3/
├── dev.sh                  # 🆕 Local dev startup script
├── LOCAL_DEV.md           # 🆕 This guide
├── local/
│   ├── server.py          # Local FastAPI server
│   └── data/              # Local storage (gitignored)
├── frontend/              # Frontend (works in both modes)
│   ├── index.html
│   ├── style.css
│   └── app.js            # Auto-detects local vs production
├── src/
│   ├── agent/            # Gemini agent (shared)
│   ├── handlers/         # Lambda handlers (production only)
│   └── storage/          # Storage layer (production only)
└── requirements.txt      # 🆕 Includes local dev dependencies
```

## Next Steps

- Explore the [Memory System](docs/README_MEMORY.md)
- Check [API Reference](docs/MEMORY_API_REFERENCE.md)
- Review [Architecture Diagrams](docs/architecture.mmd)
- Read the main [README](README.md)

## Contributing

Local development makes it easy to:
- Test changes without AWS costs
- Debug with full logging
- Iterate quickly on features
- Test the full stack end-to-end

Just make your changes and run `./dev.sh` to see them in action!
