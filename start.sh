#!/bin/bash
# VoicePages Startup Script
# Run this to start the API server with real TTS!

set -e

echo "🎧 VoicePages Starting..."

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Get local IP
get_ip() {
    if command -v ipconfig &> /dev/null; then
        ipconfig getifaddr en0 2>/dev/null || echo "localhost"
    else
        echo "localhost"
    fi
}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SERVER_IP=$(get_ip)
PORT=9000
WEB_PORT=3000

echo -e "${GREEN}Server IP: $SERVER_IP${NC}"
echo -e "${GREEN}API Port: $PORT${NC}"
echo -e "${GREEN}Web Port: $WEB_PORT${NC}"
echo ""

# Setup virtual environment if needed
cd "$SCRIPT_DIR"

if [ ! -d "venv" ]; then
    echo "📦 Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "📦 Installing dependencies..."
source venv/bin/activate
pip install -q -r requirements.txt 2>/dev/null || pip3 install -q -r requirements.txt

# Start server in background
echo "🚀 Starting VoicePages server..."
python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT &
SERVER_PID=$!

sleep 3

# Check if server started
if curl -s http://localhost:$PORT/api/health > /dev/null 2>&1; then
    echo -e "${GREEN}✅ Server running at http://$SERVER_IP:$PORT${NC}"
else
    echo -e "${YELLOW}⚠️ Server started but health check failed${NC}"
fi

echo ""
echo "📱 On your iPhone, open:"
echo -e "   ${GREEN}http://$SERVER_IP:$WEB_PORT${NC}"
echo ""
echo "📖 In Settings, enter server URL:"
echo -e "   ${GREEN}http://$SERVER_IP:$PORT${NC}"
echo ""
echo "🛑 Press Ctrl+C to stop"
echo ""

# Keep running
trap "kill $SERVER_PID 2>/dev/null; exit" INT TERM
wait
