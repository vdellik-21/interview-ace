#!/bin/bash
# ═══════════════════════════════════════════
# InterviewAce — Development Server Launcher
# Starts: Backend (FastAPI) + Frontend (Vite) + Electron
# ═══════════════════════════════════════════

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${GREEN}🎯 Starting InterviewAce Development Servers${NC}"
echo ""

# Check .env exists
if [ ! -f ".env" ]; then
    echo -e "${YELLOW}⚠️  No .env file found. Copying from .env.example...${NC}"
    cp .env.example .env
    echo -e "${YELLOW}   Please edit .env with your ANTHROPIC_API_KEY and audio device names.${NC}"
    exit 1
fi

# Start backend
echo -e "${BLUE}[1/3] Starting Backend (FastAPI) on port 8000...${NC}"
cd backend
if [ ! -d "venv" ]; then
    echo "  Creating Python virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt -q
else
    source venv/bin/activate
fi
uvicorn app.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Start frontend
echo -e "${BLUE}[2/3] Starting Frontend (Vite) on port 5173...${NC}"
cd frontend
if [ ! -d "node_modules" ]; then
    echo "  Installing frontend dependencies..."
    npm install -q
fi
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for servers to be ready
sleep 3

# Start Electron
echo -e "${BLUE}[3/3] Starting Electron Shell...${NC}"
cd electron
if [ ! -d "node_modules" ]; then
    echo "  Installing Electron dependencies..."
    npm install -q
fi
npm start &
ELECTRON_PID=$!
cd ..

echo ""
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo -e "${GREEN}  InterviewAce is running!${NC}"
echo -e "${GREEN}  Backend:  http://localhost:8000${NC}"
echo -e "${GREEN}  Frontend: http://localhost:5173${NC}"
echo -e "${GREEN}  Electron: Running as desktop app${NC}"
echo -e "${GREEN}═══════════════════════════════════════════${NC}"
echo ""
echo "Press Ctrl+C to stop all services."

# Cleanup on exit
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    kill $ELECTRON_PID 2>/dev/null
    echo -e "${GREEN}All services stopped.${NC}"
}
trap cleanup EXIT

# Wait for any process to exit
wait
