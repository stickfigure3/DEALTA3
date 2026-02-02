#!/bin/bash
# DELTA3 Local Development Startup Script

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to cleanup background processes
cleanup() {
    echo -e "\n${YELLOW}Shutting down servers...${NC}"
    kill 0
    exit 0
}

trap cleanup SIGINT SIGTERM

echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                DELTA3 Local Development Setup                 ║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"

# Check if .env exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Creating from env.example...${NC}"
    cp env.example .env
    echo -e "${RED}❌ Please edit .env and add your GEMINI_API_KEY${NC}"
    echo -e "${YELLOW}   Get one free at: https://makersuite.google.com/app/apikey${NC}"
    exit 1
fi

# Check for Gemini API key
if ! grep -q "GEMINI_API_KEY=AIza" .env; then
    echo -e "${RED}❌ GEMINI_API_KEY not set in .env file${NC}"
    echo -e "${YELLOW}   Get one free at: https://makersuite.google.com/app/apikey${NC}"
    echo -e "${YELLOW}   Then add it to your .env file${NC}"
    exit 1
fi

# Load environment variables
export $(grep -v '^#' .env | xargs)

# Check if Python virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}📦 Creating Python virtual environment...${NC}"
    python3 -m venv venv
fi

# Activate virtual environment
echo -e "${GREEN}🐍 Activating virtual environment...${NC}"
source venv/bin/activate

# Install/update dependencies
echo -e "${GREEN}📦 Installing dependencies...${NC}"
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Create local data directory if it doesn't exist
mkdir -p local/data/chat local/data/files

# Start backend server in background
echo -e "${GREEN}🚀 Starting backend server on http://localhost:8000...${NC}"
python local/server.py &
BACKEND_PID=$!

# Wait for backend to start
sleep 2

# Check if backend started successfully
if ! kill -0 $BACKEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Backend server failed to start${NC}"
    exit 1
fi

# Start frontend server in background
echo -e "${GREEN}🌐 Starting frontend server on http://localhost:3000...${NC}"
cd frontend
python3 -m http.server 3000 &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
sleep 1

# Check if frontend started successfully
if ! kill -0 $FRONTEND_PID 2>/dev/null; then
    echo -e "${RED}❌ Frontend server failed to start${NC}"
    kill $BACKEND_PID
    exit 1
fi

echo -e "\n${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    ✅ DELTA3 is running!                       ║${NC}"
echo -e "${GREEN}╠═══════════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Frontend:  http://localhost:3000                             ║${NC}"
echo -e "${GREEN}║  Backend:   http://localhost:8000                             ║${NC}"
echo -e "${GREEN}║  API Docs:  http://localhost:8000/docs                        ║${NC}"
echo -e "${GREEN}║                                                                ║${NC}"
echo -e "${GREEN}║  Login with:                                                   ║${NC}"
echo -e "${GREEN}║    Email:    root                                              ║${NC}"
echo -e "${GREEN}║    Password: root                                              ║${NC}"
echo -e "${GREEN}║                                                                ║${NC}"
echo -e "${GREEN}║  Press Ctrl+C to stop all servers                             ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"

# Wait for both processes
wait
