# Local Development Server

This directory contains the local development server for DELTA3.

## Contents

- `server.py` - FastAPI server that mimics AWS Lambda + API Gateway
- `data/` - Local storage (replaces DynamoDB and S3)
  - `users.json` - User accounts and sessions
  - `memories.json` - AI memory system
  - `chat/` - Chat histories per user
  - `files/` - User file workspaces

## Usage

From the project root:

```bash
# Quick start
./dev.sh

# Or manually
python local/server.py
```

The server will:
1. Create a `data/` directory for storage
2. Auto-create a root user (email: `root`, password: `root`)
3. Load your Gemini API key from `.env`
4. Start FastAPI server on http://localhost:8000

## API Documentation

Visit http://localhost:8000/docs for interactive API documentation.

## Storage

The `data/` directory is gitignored and safe to delete. It will be recreated on next startup.

To reset everything:

```bash
rm -rf local/data/
```
