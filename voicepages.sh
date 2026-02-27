#!/bin/bash
# VoicePages Startup Script
# AI Multi-Voice Audiobook Server with Kokoro TTS

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
PID_FILE="$SCRIPT_DIR/.voicepages.pid"
LOG_FILE="$SCRIPT_DIR/voicepages.log"
PORT="${PORT:-9000}"

# Kokoro model files
KOKORO_MODEL_URL="https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/kokoro-v1.0.onnx"
KOKORO_VOICES_URL="https://github.com/nazdridoy/kokoro-tts/releases/download/v1.0.0/voices-v1.0.bin"

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
    return 1
}

get_pid() {
    if [ -f "$PID_FILE" ]; then
        cat "$PID_FILE"
    fi
}

check_kokoro() {
    local model_path="$SCRIPT_DIR/storage/kokoro-v1.0.onnx"
    local voices_path="$SCRIPT_DIR/storage/voices-v1.0.bin"
    
    if [ -f "$model_path" ] && [ -f "$voices_path" ]; then
        return 0
    else
        return 1
    fi
}

download_kokoro() {
    echo ""
    echo -e "${BOLD}Downloading Kokoro TTS models...${NC}"
    
    mkdir -p "$SCRIPT_DIR/storage"
    
    local model_path="$SCRIPT_DIR/storage/kokoro-v1.0.onnx"
    local voices_path="$SCRIPT_DIR/storage/voices-v1.0.bin"
    
    if [ ! -f "$model_path" ]; then
        echo -n "  Downloading kokoro-v1.0.onnx (325MB)... "
        if curl -L -o "$model_path" "$KOKORO_MODEL_URL" 2>/dev/null; then
            echo -e "${GREEN}OK${NC}"
        else
            echo -e "${RED}FAILED${NC}"
            return 1
        fi
    else
        echo -e "  kokoro-v1.0.onnx: ${GREEN}already exists${NC}"
    fi
    
    if [ ! -f "$voices_path" ]; then
        echo -n "  Downloading voices-v1.0.bin (26MB)... "
        if curl -L -o "$voices_path" "$KOKORO_VOICES_URL" 2>/dev/null; then
            echo -e "${GREEN}OK${NC}"
        else
            echo -e "${RED}FAILED${NC}"
            return 1
        fi
    else
        echo -e "  voices-v1.0.bin: ${GREEN}already exists${NC}"
    fi
    
    echo -e "${GREEN}Kokoro models ready!${NC}"
}

install() {
    echo -e "${BOLD}VoicePages Install${NC}"
    echo ""
    echo -e "Using Kokoro TTS for high-quality voice synthesis"
    echo ""

    # Check Python 3.10+ (required for Kokoro)
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: python3 not found.${NC}"
        echo "  Install Python 3.10+: https://www.python.org/downloads/"
        echo "  Or: brew install python@3.11"
        exit 1
    fi
    
    PYVER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
    PYMAJOR=$(python3 -c "import sys; print(sys.version_info.major)")
    PYMINOR=$(python3 -c "import sys; print(sys.version_info.minor)")
    
    if [ "$PYMAJOR" -lt 3 ] || { [ "$PYMAJOR" -eq 3 ] && [ "$PYMINOR" -lt 10 ]; }; then
        echo -e "${RED}Error: Python 3.10+ required for Kokoro TTS${NC}"
        echo "  Current: $PYVER"
        echo "  Install: brew install python@3.11"
        exit 1
    fi
    
    echo -e "  Python: ${GREEN}$PYVER${NC}"

    # Create venv
    if [ ! -d "$VENV_DIR" ]; then
        echo "  Creating virtual environment..."
        python3 -m venv "$VENV_DIR"
    fi
    source "$VENV_DIR/bin/activate"

    # Install Python deps
    echo "  Installing Python dependencies..."
    pip install -q --upgrade pip 2>/dev/null || true
    pip install -q -r "$SCRIPT_DIR/requirements.txt" 2>&1 | tail -1

    # Create storage directories
    mkdir -p "$SCRIPT_DIR/storage/books"
    mkdir -p "$SCRIPT_DIR/storage/audio"

    # Download Kokoro models
    download_kokoro

    # Check for web build
    if [ -d "$SCRIPT_DIR/web" ] && [ -f "$SCRIPT_DIR/web/index.html" ]; then
        echo -e "  Web app: ${GREEN}built${NC}"
    else
        echo -e "  Web app: ${YELLOW}not built${NC}"
    fi

    # Check Ollama
    if command -v ollama &> /dev/null && pgrep -x ollama > /dev/null; then
        echo -e "  Ollama:    ${GREEN}running${NC}"
    else
        echo -e "  Ollama:    ${YELLOW}not running${NC} (optional: brew install ollama)"
    fi

    echo ""
    echo -e "${GREEN}Install complete!${NC}"
    echo ""
    echo "To start: ${BOLD}./voicepages.sh start${NC}"
}

start() {
    if is_running; then
        local pid
        pid=$(get_pid)
        echo -e "${YELLOW}VoicePages is already running${NC} (PID $pid)"
        echo "  http://$(get_ip):$ 0
   PORT"
        return fi

    echo -e "Starting VoicePages..."

    # Ensure venv exists
    if [ ! -d "$VENV_DIR" ]; then
        echo "Running install first..."
        install
    fi

    # Download Kokoro if missing
    if ! check_kokoro; then
        download_kokoro
    fi

    source "$VENV_DIR/bin/activate"

    # Start server
    cd "$SCRIPT_DIR"
    nohup python3 -m uvicorn main:app --host 0.0.0.0 --port "$PORT" > "$LOG_FILE" 2>&1 &
    local pid=$!
    echo "$pid" > "$PID_FILE"

    # Wait for startup
    echo -n "  Waiting for server"
    for i in {1..15}; do
        if curl -s "http://localhost:$PORT/api/health" > /dev/null 2>&1; then
            break
        fi
        echo -n "."
        sleep 1
    done

    echo ""
    local ip
    ip=$(get_ip)
    echo ""
    echo -e "${GREEN}VoicePages is running!${NC}"
    echo ""
    echo "  Local:   http://localhost:$PORT"
    echo "  Network: http://$ip:$PORT"
    echo ""
    echo "Kokoro TTS: $(check_kokoro && echo "${GREEN}Ready${NC}" || echo "${YELLOW}Not found${NC}")"
}

stop() {
    if is_running; then
        local pid
        pid=$(get_pid)
        echo "Stopping VoicePages (PID $pid)..."
        kill "$pid" 2>/dev/null || true
        rm -f "$PID_FILE"
        echo -e "${GREEN}Stopped${NC}"
    else
        echo "VoicePages is not running"
    fi
}

status() {
    if is_running; then
        local pid
        pid=$(get_pid)
        echo -e "${GREEN}VoicePages is running${NC} (PID $pid)"
        echo "  http://$(get_ip):$PORT"
        echo "Kokoro: $(check_kokoro && echo "${GREEN}Ready${NC}" || echo "${YELLOW}Not found${NC}")"
    else
        echo -e "${YELLOW}VoicePages is not running${NC}"
        echo "Run: ./voicepages.sh start"
    fi
}

logs() {
    if [ -f "$LOG_FILE" ]; then
        tail -30 "$LOG_FILE"
    else
        echo "No logs found"
    fi
}

do_uninstall() {
    echo -e "${BOLD}Uninstalling VoicePages...${NC}"

    if is_running; then
        stop
    fi

    if [ -d "$VENV_DIR" ]; then
        rm -rf "$VENV_DIR"
        echo "  Removed virtual environment"
    fi

    rm -f "$PID_FILE" "$LOG_FILE"
    rm -rf "$SCRIPT_DIR/storage"
    rm -rf "$SCRIPT_DIR/__pycache__" "$SCRIPT_DIR"/*/__pycache__

    echo ""
    echo -e "${GREEN}Uninstalled.${NC} Source code still in: $SCRIPT_DIR"
}

case "${1:-help}" in
    install)   install ;;
    start)     start ;;
    stop)      stop ;;
    restart)   stop; sleep 1; start ;;
    status)    status ;;
    logs)      logs ;;
    uninstall)
        echo -e "${YELLOW}This will remove venv, storage, and cached data.${NC}"
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
        echo "  install    Install dependencies + download Kokoro models"
        echo "  start      Start the server"
        echo "  stop       Stop the server"
        echo "  restart    Stop then start"
        echo "  status     Check if running"
        echo "  logs       Show server logs"
        echo "  uninstall  Remove venv and data"
        echo ""
        echo "One-liner:"
        echo "  ./voicepages.sh install && ./voicepages.sh start"
        ;;
esac
