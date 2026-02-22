# VoicePages 🚀
AI-Powered Multi-Voice Audiobook Reader

Transforms ebooks (EPUB, PDF, TXT) into audiobooks with different voices for each character.

## One-Line Setup

```bash
cd ~ && rm -rf voicepages-server && git clone https://github.com/riyubolted900-max/voicepages-server.git && cd voicepages-server && chmod +x voicepages.sh && ./voicepages.sh start
```

## Commands

```bash
./voicepages.sh start      # Start server
./voicepages.sh stop       # Stop server
./voicepages.sh restart   # Restart server
./voicepages.sh uninstall # Remove everything
```

## Access

- **iPhone:** `http://YOUR_MAC_IP:3000`
- **Server:** `http://YOUR_MAC_IP:9000`
- Find IP: System Settings → Network → Wi-Fi → IP Address

## First Time Setup

1. Open browser to `http://localhost:3000`
2. Go to Settings ⚙️
3. Set Server URL to `http://localhost:9000`
4. Upload a book and start listening!

## Troubleshooting

**Can't connect from iPhone?**
- Make sure Mac and iPhone on same WiFi
- Use bridged networking in VM (if using VM)
- Check firewall: System Settings → Network → Firewall

**No audio?**
- Server uses macOS Speech - works automatically!
- Try different voices in book settings

---

## Development

```bash
# Install
pip install -r requirements.txt

# Run
uvicorn main:app --host 0.0.0.0 --port 9000

# Web app
cd ../voicepages-web
npm install && npm run dev
```

---

## Tech Stack

- **Server:** FastAPI, SQLite, Python
- **TTS:** macOS Speech (built-in)
- **Web:** React, Vite, PWA

---

## License

MIT
