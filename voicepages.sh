#!/bin/bash
# VoicePages - AI Multi-Voice Audiobook Server
# Usage: ./voicepages.sh {install|start|stop|restart|status|uninstall|logs}

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PID_FILE="$SCRIPT_DIR/.voicepages.pid"
LOG_FILE="$SCRIPT_DIR/voicepages.log"
PORT="${PORT:-9000}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

get_ip() {
    ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || echo "localhost"
}

is_running() {
    if [ -f "$PID_FILE" ]; then
        local pid
        pid=$(cat "$PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$PID_FILE"
    fi
    # Also check by process name
    pgrep -f "uvicorn main:app.*--port $PORT" > /dev/null 2>&1
}

get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    else
        pgrep -f "uvicorn main:app.*--port $PORT" 2>/dev/null | head -1
    fi
}

install() {
    echo -e "${BOLD}VoicePages Install${NC}"
    echo ""

    # Check Python 3
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: python3 not found. Install Python 3.10+ first.${NC}"
        exit 1
    fi
    PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    echo -e "  Python: ${GREEN}$PYVER${NC}"

    # Create venv
    if [ ! -d "$VENV_DIR" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"

    # Install Python deps
    echo "  Installing Python dependencies..."
    pip install -q --upgrade pip 2>/dev/null
    pip install -q -r "$SCRIPT_DIR/requirements.txt" 2>&1 | tail -1

    # Create storage directories
    mkdir -p "$SCRIPT_DIR/storage/books"
    mkdir -p "$SCRIPT_DIR/storage/audio"

    # Create .env if missing
    if [ ! -f "$SCRIPT_DIR/.env" ]; then
        if [ -f "$SCRIPT_DIR/.env.example" ]; then
            cp "$SCRIPT_DIR/.env.example" "$SCRIPT_DIR/.env"
            echo -e "  Created ${CYAN}.env${NC} from example (uses macOS Speech by default)"
        fi
    fi

    # Check for web build
    if [ -d "$SCRIPT_DIR/web" ] && [ -f "$SCRIPT_DIR/web/index.html" ]; then
        echo -e "  Web app: ${GREEN}built${NC}"
    else
        echo -e "  Web app: ${YELLOW}not built${NC} (build voicepages-web and copy dist/ to web/)"
    fi

    # Check optional services
    echo ""
    echo -e "${BOLD}Optional services:${NC}"
    if curl -s http://localhost:11434/api/version > /dev/null 2>&1; then
        echo -e "  Ollama:    ${GREEN}running${NC} (character detection enabled)"
    else
        echo -e "  Ollama:    ${YELLOW}not running${NC} (install: brew install ollama && ollama pull llama3.2:3b)"
    fi

    echo ""
    echo -e "${GREEN}Install complete!${NC} Run: ${BOLD}./voicepages.sh start${NC}"
}

start() {
    if is_running; then
        local pid
        pid=$(get_pid)
        echo -e "${YELLOW}VoicePages is already running${NC} (PID $pid)"
        echo -e "  http://$(get_ip):$PORT"
        return 0
    fi

    echo -e "Starting VoicePages..."

    # Ensure venv exists
    if [ ! -d "$VENV_DIR" ]; then
        echo "Running install first..."
        install
    fi

    source "$VENV_DIR/bin/activate"

    # Start server in background
    cd "$SCRIPT_DIR"
    nohup python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT" > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"

    # Wait for startup
    echo -n "  Waiting for server"
    for i in {1..15}; do
        if curl -s "http://localhost:$PORT/api/health" > /dev/null 2>&1; then
            echo ""
            local ip
            ip=$(get_ip)
            echo ""
            echo -e "${GREEN}VoicePages is running!${NC}"
            echo ""
            echo -e "  Local:   http://localhost:$PORT"
            echo -e "  Phone:   ${BOLD}http://$ip:$PORT${NC}"
            echo ""
            echo -e "  Stop:    ./voicepages.sh stop"
            echo -e "  Logs:    ./voicepages.sh logs"
            return 0
        fi
        echo -n "."
        sleep 1
    done

    echo ""
    echo -e "${YELLOW}Server started (PID $pid) but health check timed out.${NC}"
    echo "  Check logs: ./voicepages.sh logs"
}

stop() {
    if ! is_running; then
        echo "VoicePages is not running."
        return 0
    fi

    local pid
    pid=$(get_pid)
    echo -n "Stopping VoicePages (PID $pid)..."
    kill "$pid" 2>/dev/null || true

    # Wait for clean shutdown
    for i in {1..10}; do
        if ! kill -0 "$pid" 2>/dev/null; then
            rm -f "$PID_FILE"
            echo -e " ${GREEN}stopped${NC}"
            return 0
        fi
        sleep 0.5
    done

    # Force kill
    kill -9 "$pid" 2>/dev/null || true
    rm -f "$PID_FILE"
    echo -e " ${GREEN}stopped (forced)${NC}"
}

status() {
    local ip
    ip=$(get_ip)

    if is_running; then
        local pid
        pid=$(get_pid)
        echo -e "${GREEN}VoicePages is RUNNING${NC} (PID $pid)"
        echo ""
        echo -e "  Local:   http://localhost:$PORT"
        echo -e "  Phone:   ${BOLD}http://$ip:$PORT${NC}"

        # Show uptime info from health endpoint
        local health
        health=$(curl -s "http://localhost:$PORT/api/health" 2>/dev/null || echo "{}")
        echo ""
        echo -e "  Health:  $health"
    else
        echo -e "${RED}VoicePages is NOT running${NC}"
        echo ""
        echo -e "  Start:   ./voicepages.sh start"
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -50 "$LOG_FILE"
        echo ""
        echo -e "${CYAN}(showing last 50 lines — full log: $LOG_FILE)${NC}"
    else
        echo "No log file found. Start the server first."
    fi
}

do_uninstall() {
    echo -e "${BOLD}Uninstalling VoicePages...${NC}"

    # Stop if running
    if is_running; then
        stop
    fi

    # Remove venv
    if [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
        echo "  Removed virtual environment"
    fi

    # Remove generated files
    rm -f "$PID_FILE" "$LOG_FILE"
    rm -rf "$SCRIPT_DIR/storage"
    rm -rf "$SCRIPT_DIR/__pycache__" "$SCRIPT_DIR"/*/__pycache__

    echo ""
    echo -e "${GREEN}Uninstalled.${NC} The source code is still in: $SCRIPT_DIR"
    echo "  To fully remove: rm -rf \"$SCRIPT_DIR\""
}

case "${1:-help}" in
    install)   install ;;
    start)     start ;;
    stop)      stop ;;
    restart)   stop; sleep 1; start ;;
    status)    status ;;
    logs)      logs ;;
    uninstall)
        echo -e "${YELLOW}This will remove the venv, storage, and cached data.${NC}"
        echo -n "Continue? (y/n) "
        read -r reply
        if [[ "$reply" =~ ^[Yy] ]]; then
            do_uninstall
        else
            echo "Cancelled."
        fi
        ;;
    *)
        echo -e "${BOLD}VoicePages${NC} - AI Multi-Voice Audiobook Server"
        echo ""
        echo "Usage: $0 <command>"
        echo ""
        echo "Commands:"
        echo "  install    Install dependencies and set up environment"
        echo "  start      Start the server (runs in background)"
        echo "  stop       Stop the server"
        echo "  restart    Stop then start"
        echo "  status     Check if running and show URLs"
        echo "  logs       Show recent server logs"
        echo "  uninstall  Remove venv, storage, and cached data"
        echo ""
        echo "One-liner install & start:"
        echo "  ./voicepages.sh install && ./voicepages.sh start"
        ;;
esac
