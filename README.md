# VoicePages
AI-Powered Multi-Voice Audiobook Reader

Transforms ebooks (EPUB, PDF, TXT, DOCX) into audiobooks with different voices for each character.

## One-Line Install & Start

```bash
# Fresh install:
git clone https://github.com/riyubolted900-max/voicepages-server.git ~/voicepages-server && cd ~/voicepages-server && chmod +x voicepages.sh && ./voicepages.sh install && ./voicepages.sh start

# If already cloned (update & start):
cd ~/voicepages-server && git pull && ./voicepages.sh install && ./voicepages.sh start
```

## Commands

```bash
./voicepages.sh install    # Install dependencies
./voicepages.sh start      # Start server (background)
./voicepages.sh stop       # Stop server
./voicepages.sh restart    # Restart server
./voicepages.sh status     # Check if running + show URLs
./voicepages.sh logs       # View server logs
./voicepages.sh uninstall  # Remove venv, storage, cached data
```

## Access

Once running, the server serves both the API and web app on port 9000:

- **On Mac:** http://localhost:9000
- **On iPhone:** http://YOUR_MAC_IP:9000
- Find your Mac's IP: `ipconfig getifaddr en0`

## First Time

1. Run the install command above
2. Open http://localhost:9000 in your browser
3. Upload a book (EPUB, PDF, TXT, or DOCX)
4. Start listening with multi-voice audio!

On iPhone: connect to the same WiFi, open `http://<mac-ip>:9000`

## Optional: Better Voices with Ollama

For automatic character detection and smarter voice assignment:

```bash
brew install ollama
ollama pull llama3.2:3b
ollama serve
```

## Troubleshooting

**Can't connect from iPhone?**
- Mac and iPhone must be on the same WiFi network
- Check firewall: System Settings > Network > Firewall (allow port 9000)

**No audio?**
- macOS Speech works by default with no setup
- Check logs: `./voicepages.sh logs`

## Tech Stack

- **Server:** FastAPI, SQLite (aiosqlite), Python
- **TTS:** macOS Speech (built-in), Kokoro TTS (optional, better quality)
- **LLM:** Ollama + Llama 3.2 (optional, for character detection)
- **Web:** React, Vite, Zustand, Howler.js, PWA
- **Formats:** EPUB, PDF, DOCX, TXT

## License

MIT
