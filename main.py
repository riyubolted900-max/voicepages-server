"""
VoicePages Server - Main Entry Point
AI-Powered Multi-Voice Audiobook Reader

Run: uvicorn main:app --host 0.0.0.0 --port 9000 --reload
"""

import os
import asyncio
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.responses import StreamingResponse, JSONResponse, FileResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import aiosqlite
import logging

from config import settings
from pipeline.file_parser import FileParser
from pipeline.character_detector import CharacterDetector
from pipeline.voice_assigner import VoiceAssigner
from pipeline.audio_generator import AudioGenerator
from models.book import Book, Chapter, Character, VoiceProfile

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Web app location (embedded in server)
WEB_APP_DIR = Path(__file__).parent / "web"

# Initialize storage paths
STORAGE_DIR = Path("storage")
STORAGE_DIR.mkdir(exist_ok=True)
BOOKS_DIR = STORAGE_DIR / "books"
BOOKS_DIR.mkdir(exist_ok=True)
AUDIO_DIR = STORAGE_DIR / "audio"
AUDIO_DIR.mkdir(exist_ok=True)
DB_PATH = STORAGE_DIR / "voicepages.db"

# Initialize pipeline components
file_parser = FileParser()
character_detector = CharacterDetector()
voice_assigner = VoiceAssigner()
audio_generator = AudioGenerator(AUDIO_DIR)


# ============================================================================
# Authentication Dependency
# ============================================================================

async def verify_api_key(x_api_key: str = None):
    """
    Verify API key if password is configured.
    Add header: X-API-Key: your_password
    """
    if not settings.api_password:
        return True  # No password configured, allow all
    
    if not x_api_key:
        raise HTTPException(status_code=401, detail="X-API-Key header required")
    
    if x_api_key != settings.api_password:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    return True


# Quick alias for Depends
def require_auth(x_api_key: str = Header(None)):
    """Use this in endpoints that need authentication."""
    return verify_api_key(x_api_key)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize database on startup."""
    await init_db()
    logger.info("VoicePages Server started")
    yield
    logger.info("VoicePages Server shutting down")


async def init_db():
    """Initialize SQLite database with required tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # Books table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS books (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                author TEXT,
                file_path TEXT NOT NULL,
                file_type TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Chapters table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chapters (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT NOT NULL,
                chapter_number INTEGER NOT NULL,
                title TEXT,
                text_content TEXT NOT NULL,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        
        # Characters table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS characters (
                id TEXT PRIMARY KEY,
                book_id TEXT NOT NULL,
                name TEXT NOT NULL,
                gender TEXT,
                voice_id TEXT,
                is_narrator INTEGER DEFAULT 0,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        
        # Bookmarks table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bookmarks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT NOT NULL,
                chapter_id INTEGER NOT NULL,
                position REAL DEFAULT 0,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (book_id) REFERENCES books(id)
            )
        """)
        
        # Audio cache table
        await db.execute("""
            CREATE TABLE IF NOT EXISTS audio_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                book_id TEXT NOT NULL,
                chapter_id INTEGER NOT NULL,
                audio_path TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(book_id, chapter_id)
            )
        """)

        # Indices for common queries
        await db.execute("CREATE INDEX IF NOT EXISTS idx_chapters_book_id ON chapters(book_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_characters_book_id ON characters(book_id)")
        await db.execute("CREATE INDEX IF NOT EXISTS idx_bookmarks_book_id ON bookmarks(book_id)")

        await db.commit()


# Create FastAPI app
app = FastAPI(
    title="VoicePages Server",
    description="AI-Powered Multi-Voice Audiobook Reader API",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS for local network access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Helper Dependencies
# ============================================================================

async def get_db():
    """Database dependency."""
    db = await aiosqlite.connect(DB_PATH)
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/api/status")
async def root():
    """Health check endpoint."""
    return {
        "status": "running",
        "name": "VoicePages Server",
        "version": "1.0.0"
    }


@app.get("/api/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "storage": str(STORAGE_DIR),
        "audio_dir": str(AUDIO_DIR)
    }


@app.post("/api/books/upload")
async def upload_book(
    file: UploadFile = File(...),
    x_api_key: str = Header(None),
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Upload and process a book file.
    
    Supported formats: epub, pdf, txt, doc, docx
    Requires auth if password is configured.
    
    Returns: book_id, title, author, chapter_count
    """
    await verify_api_key(x_api_key)
    import uuid
    import aiofiles
    
    # Generate unique book ID
    book_id = str(uuid.uuid4())[:8]
    
    # Save uploaded file
    file_ext = file.filename.split('.')[-1].lower()
    if file_ext not in ['epub', 'pdf', 'txt', 'doc', 'docx']:
        raise HTTPException(status_code=400, detail="Unsupported file type")
    
    file_path = BOOKS_DIR / f"{book_id}.{file_ext}"
    
    # Write file to disk
    content = await file.read()
    async with aiofiles.open(file_path, 'wb') as f:
        await f.write(content)
    
    # Parse file and extract chapters
    logger.info(f"Parsing book: {file.filename}")
    chapters = await file_parser.parse_file(str(file_path), file_ext)
    
    # Extract basic metadata
    title = file.filename.replace(f".{file_ext}", "")
    author = "Unknown"
    
    # Detect characters (simplified - uses filename as title for now)
    characters = await character_detector.detect(chapters)
    
    # Assign voices to characters
    voice_assignments = await voice_assigner.assign_voices(characters)
    
    # Store in database
    await db.execute(
        "INSERT INTO books (id, title, author, file_path, file_type) VALUES (?, ?, ?, ?, ?)",
        (book_id, title, author, str(file_path), file_ext)
    )
    
    # Insert chapters
    for i, chapter_text in enumerate(chapters):
        await db.execute(
            "INSERT INTO chapters (book_id, chapter_number, title, text_content) VALUES (?, ?, ?, ?)",
            (book_id, i + 1, f"Chapter {i + 1}", chapter_text)
        )
    
    # Insert characters
    for char_name, char_data in characters.items():
        is_narrator = 1 if char_name.lower() == "narrator" else 0
        voice_id = voice_assignments.get(char_name, {}).get("voice_id", "af_sky")
        await db.execute(
            "INSERT INTO characters (id, book_id, name, gender, voice_id, is_narrator) VALUES (?, ?, ?, ?, ?, ?)",
            (f"{book_id}_{char_name}", book_id, char_name, char_data.get("gender", "unknown"), voice_id, is_narrator)
        )
    
    await db.commit()
    
    logger.info(f"Book uploaded successfully: {book_id} with {len(chapters)} chapters")
    
    return {
        "book_id": book_id,
        "title": title,
        "author": author,
        "chapter_count": len(chapters),
        "characters": list(characters.keys())
    }


@app.get("/api/books")
async def list_books(db: aiosqlite.Connection = Depends(get_db)):
    """List all uploaded books."""
    cursor = await db.execute("""
        SELECT id, title, author, file_type, created_at,
               (SELECT COUNT(*) FROM chapters WHERE book_id = books.id) as chapter_count
        FROM books ORDER BY created_at DESC
    """)
    rows = await cursor.fetchall()
    
    books = []
    for row in rows:
        books.append({
            "id": row[0],
            "title": row[1],
            "author": row[2],
            "file_type": row[3],
            "created_at": row[4],
            "chapter_count": row[5]
        })
    
    return books


@app.get("/api/books/{book_id}")
async def get_book(book_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get book details."""
    cursor = await db.execute(
        "SELECT id, title, author, file_type, file_path FROM books WHERE id = ?",
        (book_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Book not found")
    
    # Get chapters
    chapters_cursor = await db.execute(
        "SELECT chapter_number, title FROM chapters WHERE book_id = ? ORDER BY chapter_number",
        (book_id,)
    )
    chapters = []
    async for ch in chapters_cursor:
        chapters.append({
            "chapter_number": ch[0],
            "title": ch[1]
        })
    
    return {
        "id": row[0],
        "title": row[1],
        "author": row[2],
        "file_type": row[3],
        "chapters": chapters
    }


@app.get("/api/books/{book_id}/chapters/{chapter_id}")
async def get_chapter(
    book_id: str,
    chapter_id: int,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Get chapter text content."""
    cursor = await db.execute(
        "SELECT chapter_number, title, text_content FROM chapters WHERE book_id = ? AND chapter_number = ?",
        (book_id, chapter_id)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    return {
        "chapter_number": row[0],
        "title": row[1],
        "text": row[2]
    }


@app.post("/api/books/{book_id}/chapters/{chapter_id}/audio")
async def generate_chapter_audio(
    book_id: str,
    chapter_id: int,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Generate audio for a chapter.
    Uses character detection + voice assignment + TTS.
    """
    import io
    
    # Get chapter text
    cursor = await db.execute(
        "SELECT text_content FROM chapters WHERE book_id = ? AND chapter_number = ?",
        (book_id, chapter_id)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Chapter not found")
    
    chapter_text = row[0]
    
    # Get characters for this book
    char_cursor = await db.execute(
        "SELECT name, gender, voice_id, is_narrator FROM characters WHERE book_id = ?",
        (book_id,)
    )
    characters = {}
    async for row in char_cursor:
        characters[row[0]] = {
            "gender": row[1],
            "voice_id": row[2],
            "is_narrator": bool(row[3])
        }
    
    # Generate audio using the pipeline
    logger.info(f"Generating audio for book {book_id}, chapter {chapter_id}")
    
    try:
        audio_bytes = await audio_generator.generate(
            text=chapter_text,
            characters=characters,
            voice_assignments=voice_assigner.get_available_voices()
        )
        
        # Cache the audio
        import aiofiles
        audio_path = AUDIO_DIR / f"{book_id}_{chapter_id}.wav"
        async with aiofiles.open(audio_path, 'wb') as f:
            await f.write(audio_bytes)
        
        # Save to cache table
        await db.execute(
            "INSERT OR REPLACE INTO audio_cache (book_id, chapter_id, audio_path) VALUES (?, ?, ?)",
            (book_id, chapter_id, str(audio_path))
        )
        await db.commit()
        
        # Return audio with Content-Length (needed for Howler.js / HTML5 Audio)
        return Response(
            content=audio_bytes,
            media_type="audio/wav",
            headers={
                "Content-Disposition": f"inline; filename=chapter_{chapter_id}.wav",
                "Content-Length": str(len(audio_bytes)),
                "Accept-Ranges": "bytes"
            }
        )
        
    except Exception as e:
        logger.error(f"Error generating audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/books/{book_id}/chapters/{chapter_id}/audio")
async def get_chapter_audio(
    book_id: str,
    chapter_id: int,
    db: aiosqlite.Connection = Depends(get_db)
):
    """
    Stream cached audio for a chapter.
    If not cached, returns 404 - client should call generate endpoint.
    """
    import io
    
    cursor = await db.execute(
        "SELECT audio_path FROM audio_cache WHERE book_id = ? AND chapter_id = ?",
        (book_id, chapter_id)
    )
    row = await cursor.fetchone()
    
    if not row:
        raise HTTPException(status_code=404, detail="Audio not generated yet. POST to generate.")
    
    audio_path = Path(row[0])
    if not audio_path.exists():
        raise HTTPException(status_code=404, detail="Audio file not found")

    with open(audio_path, 'rb') as f:
        audio_bytes = f.read()

    # Clean WAV if it has non-standard chunks (FLLR from afconvert)
    if audio_bytes[:4] == b'RIFF' and b'FLLR' in audio_bytes[:100]:
        audio_bytes = audio_generator._clean_wav(audio_bytes)
        # Overwrite the cached file with the clean version
        with open(audio_path, 'wb') as f:
            f.write(audio_bytes)

    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f"inline; filename=chapter_{chapter_id}.wav",
            "Content-Length": str(len(audio_bytes)),
            "Accept-Ranges": "bytes"
        }
    )


@app.get("/api/books/{book_id}/characters")
async def get_characters(book_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get all characters for a book with voice assignments."""
    cursor = await db.execute(
        "SELECT id, name, gender, voice_id, is_narrator FROM characters WHERE book_id = ?",
        (book_id,)
    )
    
    characters = []
    async for row in cursor:
        characters.append({
            "id": row[0],
            "name": row[1],
            "gender": row[2],
            "voice_id": row[3],
            "is_narrator": bool(row[4])
        })
    
    return characters


@app.put("/api/books/{book_id}/characters/{char_name}/voice")
async def update_character_voice(
    book_id: str,
    char_name: str,
    body: dict,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Update a character's assigned voice."""
    voice_id = body.get("voice_id")
    if not voice_id:
        raise HTTPException(status_code=400, detail="voice_id required in body")

    # Validate voice_id exists
    valid_ids = {v["id"] for v in voice_assigner.get_available_voices()}
    if voice_id not in valid_ids:
        raise HTTPException(status_code=400, detail=f"Invalid voice_id: {voice_id}")

    await db.execute(
        "UPDATE characters SET voice_id = ? WHERE book_id = ? AND name = ?",
        (voice_id, book_id, char_name)
    )
    await db.commit()

    return {"status": "updated", "character": char_name, "voice_id": voice_id}


@app.post("/api/books/{book_id}/bookmark")
async def save_bookmark(
    book_id: str,
    body: dict,
    db: aiosqlite.Connection = Depends(get_db)
):
    """Save reading position bookmark."""
    chapter_id = body.get("chapter_id", 1)
    position = body.get("position", 0.0)

    await db.execute("DELETE FROM bookmarks WHERE book_id = ?", (book_id,))
    await db.execute(
        "INSERT INTO bookmarks (book_id, chapter_id, position) VALUES (?, ?, ?)",
        (book_id, chapter_id, position)
    )
    await db.commit()

    return {"status": "saved", "book_id": book_id, "chapter_id": chapter_id, "position": position}


@app.get("/api/books/{book_id}/bookmark")
async def get_bookmark(book_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Get saved reading position."""
    cursor = await db.execute(
        "SELECT chapter_id, position FROM bookmarks WHERE book_id = ? ORDER BY updated_at DESC LIMIT 1",
        (book_id,)
    )
    row = await cursor.fetchone()
    
    if not row:
        return {"chapter_id": 1, "position": 0.0}
    
    return {"chapter_id": row[0], "position": row[1]}


@app.get("/api/voices")
async def list_voices():
    """List all available TTS voices."""
    return voice_assigner.get_available_voices()


@app.post("/api/tts/generate")
async def generate_tts(
    text: str,
    voice_id: str = "af_sky",
    speed: float = 1.0
):
    """
    Generate TTS for given text with specified voice.
    
    Use this for testing individual voice output.
    """
    import io
    
    try:
        audio_bytes = await audio_generator.generate_simple(
            text=text,
            voice_id=voice_id,
            speed=speed
        )
        
        return StreamingResponse(
            io.BytesIO(audio_bytes),
            media_type="audio/wav"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/api/books/{book_id}")
async def delete_book(book_id: str, db: aiosqlite.Connection = Depends(get_db)):
    """Delete a book and all associated data."""
    await db.execute("DELETE FROM audio_cache WHERE book_id = ?", (book_id,))
    await db.execute("DELETE FROM bookmarks WHERE book_id = ?", (book_id,))
    await db.execute("DELETE FROM characters WHERE book_id = ?", (book_id,))
    await db.execute("DELETE FROM chapters WHERE book_id = ?", (book_id,))
    await db.execute("DELETE FROM books WHERE id = ?", (book_id,))
    await db.commit()
    
    # Delete audio files
    for audio_file in AUDIO_DIR.glob(f"{book_id}_*.wav"):
        audio_file.unlink()
    
    # Delete book file
    book_files = BOOKS_DIR.glob(f"{book_id}.*")
    for bf in book_files:
        bf.unlink()
    
    return {"status": "deleted", "book_id": book_id}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=9000)


# ============================================================================
# Serve Web App (at specific prefix to not interfere with API)
# ============================================================================

if WEB_APP_DIR.exists():
    # Serve static files from root
    
    @app.get("/")
    async def serve_index():
        return FileResponse(str(WEB_APP_DIR / "index.html"))
    
    # Serve assets
    @app.get("/assets/{path:path}")
    async def serve_assets(path: str):
        file_path = WEB_APP_DIR / "assets" / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        raise HTTPException(status_code=404, detail="Asset not found")
    
    # Serve test page
    @app.get("/test_audio.html")
    async def serve_test_audio():
        test_path = WEB_APP_DIR / "test_audio.html"
        if test_path.exists():
            return FileResponse(str(test_path))
        raise HTTPException(status_code=404)

    # Serve favicon
    @app.get("/favicon.svg")
    async def serve_favicon():
        favicon_path = WEB_APP_DIR / "favicon.svg"
        if favicon_path.exists():
            return FileResponse(str(favicon_path))
        raise HTTPException(status_code=404)

    # Serve debug page
    @app.get("/debug.html")
    async def serve_debug():
        debug_path = WEB_APP_DIR / "debug.html"
        if debug_path.exists():
            return FileResponse(str(debug_path))
        raise HTTPException(status_code=404)

    # SPA fallback
    @app.get("/{path:path}")
    async def serve_spa_fallback(path: str):
        if path.startswith("api/"):
            raise HTTPException(status_code=404, detail="API endpoint not found")
        return FileResponse(str(WEB_APP_DIR / "index.html"))
    
    logger.info(f"Serving web app from {WEB_APP_DIR} at /")
else:
    logger.warning(f"Web app not found at {WEB_APP_DIR}")
