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

# Check prerequisites
MISSING=""
command -v python3 &>/dev/null || MISSING="$MISSING python3"
command -v git &>/dev/null || MISSING="$MISSING git"

if [ -n "$MISSING" ]; then
    echo -e "${RED}Missing required tools:$MISSING${NC}"
    echo "Install them first (e.g., brew install python3 git)"
    exit 1
fi

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
