#!/bin/bash
# VoicePages Control Script
# Usage: ./voicepages.sh [start|stop|restart|uninstall]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

get_ip() {
    if command -v ipconfig &> /dev/null; then
        ipconfig getifaddr en0 2>/dev/null || echo "localhost"
    else
        echo "localhost"
    fi
}

PORT=9000

start() {
    echo "🎧 Starting VoicePages..."
    
    # Setup virtual environment
    if [ ! -d "venv" ]; then
        echo "📦 Creating virtual environment..."
        python3 -m venv venv
    fi
    
    source venv/bin/activate
    pip install -q -r requirements.txt 2>/dev/null || pip3 install -q -r requirements.txt
    
    # Kill existing server
    pkill -f "uvicorn main:app" 2>/dev/null || true
    
    # Start server
    echo "🚀 Starting server..."
    python3 -m uvicorn main:app --host 0.0.0.0 --port $PORT &
    sleep 3
    
    SERVER_IP=$(get_ip)
    
    if curl -s http://localhost:$PORT/api/health > /dev/null 2>&1; then
        echo ""
        echo "✅ VoicePages is running!"
        echo ""
        echo "📱 Open on iPhone:"
        echo -e "   ${GREEN}http://$SERVER_IP:$PORT${NC}"
        echo ""
        echo "⚙️  Server URL is already configured!"
        echo ""
        echo "🛑 Run './voicepages.sh stop' to stop"
    else
        echo -e "${YELLOW}⚠️ Server started but health check failed${NC}"
        echo "Try accessing http://$SERVER_IP:$PORT anyway"
    fi
}

stop() {
    echo "🛑 Stopping VoicePages..."
    pkill -f "uvicorn main:app" 2>/dev/null || true
    echo "✅ Stopped"
}

restart() {
    stop
    sleep 1
    start
}

uninstall() {
    echo "🧹 Uninstalling VoicePages..."
    stop
    cd ~
    rm -rf "$SCRIPT_DIR"
    echo "✅ Removed VoicePages"
}

case "$1" in
    start)   start ;;
    stop)    stop ;;
    restart) restart ;;
    status)
        echo "📡 Checking status..."
        SERVER_IP=$(get_ip)
        
        if curl -s http://localhost:$PORT/api/health > /dev/null 2>&1; then
            echo ""
            echo -e "${GREEN}✅ VoicePages is RUNNING${NC}"
            echo ""
            echo "📱 Open on iPhone:"
            echo -e "   ${GREEN}http://$SERVER_IP:$PORT${NC}"
        else
            echo ""
            echo -e "${RED}❌ VoicePages is NOT running${NC}"
            echo ""
            echo "Run './voicepages.sh start' to start"
        fi
        ;;
    uninstall)
        read -p "Delete voicepages-server folder? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            uninstall
        else
            echo "Cancelled"
        fi
        ;;
    *) echo "Usage: $0 {start|stop|restart|status|uninstall}"
       echo ""
       echo "  start      - Start server"
       echo "  stop       - Stop server"
       echo "  restart    - Restart server"
       echo "  status     - Check if running"
       echo "  uninstall  - Remove everything"
       exit 1 ;;
esac
