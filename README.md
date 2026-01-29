# DELTA3 - AI Coding Assistant

A serverless AI coding environment powered by Google Gemini. Write, run, and debug code through a web interface or SMS.

## Features

- 🤖 **Gemini AI** - Google's most capable AI for coding
- ⚡ **Instant Execution** - Run Python code in seconds
- 💾 **Persistent Environment** - Files AND chat context saved across sessions
- 🌐 **Web Interface** - Beautiful, responsive UI
- 📱 **SMS Support** - Code via text messages (Twilio)
- 🔐 **User Accounts** - Isolated workspaces per user
- 💰 **Pay-per-use** - Serverless = pay only when used

## How Persistence Works

Each user gets a persistent workspace that survives across Lambda invocations:

```
User Request → Lambda Invocation
                    ↓
            ┌──────────────────┐
            │ 1. Restore files │ ← Download from S3
            │    from S3       │
            └──────────────────┘
                    ↓
            ┌──────────────────┐
            │ 2. Load chat     │ ← Load last 20 messages
            │    history       │   into Gemini context
            └──────────────────┘
                    ↓
            ┌──────────────────┐
            │ 3. Process       │ ← Gemini sees your files
            │    message       │   and conversation
            └──────────────────┘
                    ↓
            ┌──────────────────┐
            │ 4. Sync files    │ ← Upload changes to S3
            │    to S3         │
            └──────────────────┘
                    ↓
            ┌──────────────────┐
            │ 5. Save chat     │ ← Persist conversation
            │    history       │
            └──────────────────┘
```

**What persists:**
- ✅ All files you create (Python, text, etc.)
- ✅ File modifications
- ✅ Chat history (last 100 messages)
- ✅ Context between messages (AI remembers what you discussed)

**Storage location:** `s3://bucket/users/{user_id}/workspace/`

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      DELTA3 v3.0                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐                 │
│   │  Web UI  │    │ Twilio   │    │  Future  │                 │
│   │          │    │  SMS     │    │ Channels │                 │
│   └────┬─────┘    └────┬─────┘    └────┬─────┘                 │
│        │               │               │                        │
│        └───────────────┼───────────────┘                        │
│                        ▼                                        │
│            ┌───────────────────────┐                            │
│            │     API Gateway       │                            │
│            └───────────┬───────────┘                            │
│                        ▼                                        │
│   ┌─────────────────────────────────────────────────────┐      │
│   │                  Lambda Functions                    │      │
│   │  ┌────────────┐  ┌────────────┐  ┌────────────┐    │      │
│   │  │   Auth     │  │   Chat     │  │  Twilio    │    │      │
│   │  └────────────┘  └────────────┘  └────────────┘    │      │
│   └─────────────────────────────────────────────────────┘      │
│                        │                                        │
│           ┌────────────┼────────────┐                          │
│           ▼            ▼            ▼                          │
│    ┌──────────┐  ┌──────────┐  ┌──────────┐                   │
│    │ DynamoDB │  │    S3    │  │  Gemini  │                   │
│    │  Users   │  │  Files   │  │   API    │                   │
│    └──────────┘  └──────────┘  └──────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- AWS Account
- AWS CLI configured (`aws configure`)
- AWS SAM CLI (`brew install aws-sam-cli`)
- Google Gemini API key ([Get one free](https://makersuite.google.com/app/apikey))

### Deploy

```bash
# Clone the repo
git clone https://github.com/stickfigure3/DEALTA3.git
cd DEALTA3

# Deploy to AWS
chmod +x deploy.sh
./deploy.sh dev

# Output will show your URLs
```

### Use

1. Visit the frontend URL from deployment output
2. Create an account
3. Add your Gemini API key
4. Start chatting!

## Project Structure

```
DELTA3/
├── frontend/               # Web UI (static HTML/CSS/JS)
│   ├── index.html
│   ├── style.css
│   └── app.js
├── lambda/                 # AWS Lambda functions
│   ├── auth/              # Authentication
│   │   └── handler.py
│   ├── chat/              # Chat + code execution
│   │   └── handler.py
│   ├── twilio/            # SMS webhook
│   │   └── handler.py
│   └── shared/            # Shared utilities
│       ├── storage.py     # DynamoDB + S3
│       └── gemini.py      # Gemini AI
├── infrastructure/        # CloudFormation/SAM
│   └── template.yaml
├── deploy.sh              # Deployment script
├── requirements.txt
├── env.example
└── README.md
```

## AI Tools Available

The AI has access to these tools for code execution:

| Tool | Description |
|------|-------------|
| `execute_python` | Run Python code directly |
| `execute_shell` | Run shell commands |
| `write_file` | Save files (persisted to S3) |
| `read_file` | Read file contents |
| `list_files` | List files in workspace |
| `delete_file` | Delete files |

**Example conversation:**
```
You: Create a calculator module and test it

AI: [Uses write_file to create calculator.py]
    [Uses execute_python to test it]
    
    ✅ Created calculator.py with add, subtract, multiply, divide functions.
    Test results: 2+2=4, 10-3=7, 4*5=20, 10/2=5.0

You: Now add a power function

AI: [Uses read_file to see current code]
    [Uses write_file to update it]
    
    ✅ Added power(base, exp) function. Test: 2^3=8
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Create account |
| `/auth/login` | POST | Login, get session |
| `/auth/me` | GET | Get user info |
| `/auth/gemini-key` | POST | Set Gemini API key |
| `/chat/send` | POST | Send message to AI |
| `/chat/history` | GET | Get chat history |
| `/chat/clear` | POST | Clear chat history |
| `/files/list` | GET | List user files |
| `/files/read` | POST | Read file |
| `/files/write` | POST | Write file |
| `/twilio/webhook` | POST | Twilio SMS webhook |

## SMS Commands (Twilio)

| Command | Description |
|---------|-------------|
| `HELP` | Show available commands |
| `REGISTER <email> <password>` | Create account |
| `LINK <email> <password>` | Link phone to account |
| `KEY <gemini-api-key>` | Set Gemini API key |
| `CLEAR` | Clear chat history |
| Any other message | Chat with AI |

## Local Development

```bash
# Install dependencies
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Set environment variables
cp env.example .env
# Edit .env with your values

# Run frontend locally
cd frontend
python3 -m http.server 3000

# For Lambda testing, use SAM local
cd infrastructure
sam local start-api
```

## Cost Estimate

| Service | Estimated Cost |
|---------|---------------|
| Lambda | ~$0.20 per million requests |
| API Gateway | ~$1.00 per million requests |
| DynamoDB | ~$1.25/month (on-demand) |
| S3 | ~$0.023/GB/month |
| **Total** | **~$5-10/month** for light use |

Compare to always-on EC2: ~$4.60/hr for m5.metal = $110/day

## Security

- Each user has isolated storage
- Gemini API keys encrypted at rest
- Sessions expire after 7 days
- API keys never logged
- HTTPS enforced via API Gateway

## Roadmap

- [ ] Slack integration
- [ ] Discord bot
- [ ] Multiple language support (JS, Go, etc.)
- [ ] Collaborative workspaces
- [ ] Custom model support

## License

MIT

---

Built with ❤️ using AWS Lambda, DynamoDB, S3, and Google Gemini
