"""
VoicePages Configuration
"""

import os
from pathlib import Path

# Base paths
BASE_DIR = Path(__file__).parent
STORAGE_DIR = os.environ.get("STORAGE_DIR", str(BASE_DIR / "storage"))

# Server config
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "9000"))

# TTS Configuration
# Set to "kokoro" for local MLX-Audio, or "elevenlabs" for API
TTS_BACKEND = os.environ.get("TTS_BACKEND", "kokoro")
KOKORO_URL = os.environ.get("KOKORO_URL", "http://localhost:8000")
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")

# Ollama (LLM) Configuration
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
LLM_MODEL = os.environ.get("LLM_MODEL", "minimax-m2.5:cloud")

# Audio settings
AUDIO_SAMPLE_RATE = int(os.environ.get("AUDIO_SAMPLE_RATE", "24000"))
AUDIO_SPEED = float(os.environ.get("AUDIO_SPEED", "1.0"))

# CORS - allow all for local development
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "*").split(",")

# Book processing
MAX_CHUNK_SIZE = int(os.environ.get("MAX_CHUNK_SIZE", "5000"))  # characters per TTS chunk

# Security - API password (optional - leave empty for no auth)
API_PASSWORD = os.environ.get("API_PASSWORD", "")

# Create settings object for easy import
class Settings:
    host = HOST
    port = PORT
    tts_backend = TTS_BACKEND
    kokoro_url = KOKORO_URL
    elevenlabs_api_key = ELEVENLABS_API_KEY
    ollama_url = OLLAMA_URL
    llm_model = LLM_MODEL
    audio_sample_rate = AUDIO_SAMPLE_RATE
    audio_speed = AUDIO_SPEED
    cors_origins = CORS_ORIGINS
    max_chunk_size = MAX_CHUNK_SIZE
    storage_dir = STORAGE_DIR
    api_password = API_PASSWORD

settings = Settings()
