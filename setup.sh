#!/bin/bash
# VoicePages One-Line Installer
# Usage: curl -sSL https://raw.githubusercontent.com/riyubolted900-max/voicepages-server/main/setup.sh | bash
# Or:    bash setup.sh

set -euo pipefail

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

INSTALL_DIR="${VOICEPAGES_DIR:-$HOME/voicepages}"
REPO_ORG="riyubolted900-max"

echo ""
echo -e "${BOLD}VoicePages Installer${NC}"
echo -e "AI Multi-Voice Audiobook Server"
echo ""

# Ensure git is present
if ! command -v git &>/dev/null; then
    echo -e "${RED}git not found. Install it first (e.g., brew install git).${NC}"
    exit 1
fi

# Ensure Python 3.10+ is available, auto-install if needed
ensure_python() {
    local PYTHON=""
    for cmd in python3.13 python3.12 python3.11 python3.10 python3; do
        if command -v "$cmd" &>/dev/null; then
            local major minor
            major=$("$cmd" -c "import sys; print(sys.version_info.major)")
            minor=$("$cmd" -c "import sys; print(sys.version_info.minor)")
            if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
                PYTHON="$cmd"
                break
            fi
        fi
    done

    if [ -n "$PYTHON" ]; then
        echo -e "  Python: ${GREEN}$($PYTHON --version)${NC}"
        return 0
    fi

    echo -e "  ${YELLOW}Python 3.10+ not found — attempting to install...${NC}"

    if [[ "$OSTYPE" == "darwin"* ]]; then
        if ! command -v brew &>/dev/null; then
            echo -e "${RED}Homebrew not found. Install it from https://brew.sh then re-run setup.${NC}"
            exit 1
        fi
        brew install python@3.11
    elif command -v apt-get &>/dev/null; then
        sudo apt-get update -qq
        sudo apt-get install -y python3.11 python3.11-venv python3.11-dev
    elif command -v dnf &>/dev/null; then
        sudo dnf install -y python3.11
    else
        echo -e "${RED}Cannot auto-install Python on this system.${NC}"
        echo "Install Python 3.10+ manually: https://www.python.org/downloads/"
        exit 1
    fi

    # Verify after install
    for cmd in python3.11 python3.10 python3; do
        if command -v "$cmd" &>/dev/null; then
            local major minor
            major=$("$cmd" -c "import sys; print(sys.version_info.major)")
            minor=$("$cmd" -c "import sys; print(sys.version_info.minor)")
            if [ "$major" -ge 3 ] && [ "$minor" -ge 10 ]; then
                echo -e "  Python: ${GREEN}$($cmd --version)${NC}"
                return 0
            fi
        fi
    done

    echo -e "${RED}Python 3.10+ install failed. Please install manually.${NC}"
    exit 1
}

ensure_python

# Check for node/npm (needed to build web app)
HAS_NODE=false
if command -v node &>/dev/null && command -v npm &>/dev/null; then
    HAS_NODE=true
fi

# Clone or update both repos
echo -e "Setting up in: ${BOLD}$INSTALL_DIR${NC}"
mkdir -p "$INSTALL_DIR"

if [ -d "$INSTALL_DIR/voicepages-server/.git" ]; then
    echo "  Updating voicepages-server..."
    cd "$INSTALL_DIR/voicepages-server" && git pull --quiet
else
    echo "  Cloning voicepages-server..."
    git clone --quiet "https://github.com/$REPO_ORG/voicepages-server.git" "$INSTALL_DIR/voicepages-server"
fi

if [ -d "$INSTALL_DIR/voicepages-web/.git" ]; then
    echo "  Updating voicepages-web..."
    cd "$INSTALL_DIR/voicepages-web" && git pull --quiet
else
    echo "  Cloning voicepages-web..."
    git clone --quiet "https://github.com/$REPO_ORG/voicepages-web.git" "$INSTALL_DIR/voicepages-web"
fi

# Build and deploy web app (requires node/npm)
if $HAS_NODE; then
    echo "  Building web app..."
    cd "$INSTALL_DIR/voicepages-web"
    npm install --silent 2>&1 | tail -1
    npm run build --silent 2>&1 | tail -1

    rm -rf "$INSTALL_DIR/voicepages-server/web"
    cp -r "$INSTALL_DIR/voicepages-web/dist" "$INSTALL_DIR/voicepages-server/web"
    echo -e "  Web app: ${GREEN}built and deployed${NC}"
else
    echo -e "  ${YELLOW}Node.js not found — skipping web build${NC}"
    echo "  (The server includes a pre-built web app)"
fi

# Run server install
cd "$INSTALL_DIR/voicepages-server"
chmod +x voicepages.sh
./voicepages.sh install

echo ""
echo -e "${GREEN}Setup complete!${NC}"
echo ""
echo "Quick start:"
echo -e "  cd $INSTALL_DIR/voicepages-server"
echo -e "  ${BOLD}./voicepages.sh start${NC}"
echo ""
echo "Or one-liner:"
echo -e "  ${BOLD}$INSTALL_DIR/voicepages-server/voicepages.sh start${NC}"
echo ""
echo "Commands:"
echo "  ./voicepages.sh start      Start server"
echo "  ./voicepages.sh stop       Stop server"
echo "  ./voicepages.sh status     Check status"
echo "  ./voicepages.sh restart    Restart server"
echo "  ./voicepages.sh logs       View logs"
echo "  ./voicepages.sh uninstall  Clean up"
