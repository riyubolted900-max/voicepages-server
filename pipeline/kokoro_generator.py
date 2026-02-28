"""
Kokoro TTS Generator - Direct CLI integration
"""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

import numpy as np


class KokoroGenerator:
    """Generate TTS using Kokoro CLI directly."""
    
    KOKORO_VOICES = [
        # American Female
        "af_alloy", "af_aoede", "af_bella", "af_heart", "af_jessica", 
        "af_kore", "af_nicole", "af_nova", "af_river", "af_sarah", "af_sky",
        # American Male
        "am_adam", "am_echo", "am_eric", "am_fenrir", "am_liam", 
        "am_michael", "am_onyx", "am_puck",
        # British Female
        "bf_alice", "bf_emma", "bf_isabella", "bf_lily",
        # British Male
        "bm_daniel", "bm_fable", "bm_george", "bm_lewis",
    ]
    
    # Map our voice IDs to Kokoro voices (identity for all supported voices)
    VOICE_MAP = {
        # American Female
        "af_sky": "af_sky", "af_heart": "af_heart", "af_bella": "af_bella",
        "af_nova": "af_nova", "af_sarah": "af_sarah", "af_nicole": "af_nicole",
        "af_alloy": "af_alloy", "af_aoede": "af_aoede", "af_jessica": "af_jessica",
        "af_kore": "af_kore", "af_river": "af_river",
        # American Male
        "am_adam": "am_adam", "am_echo": "am_echo", "am_michael": "am_michael",
        "am_liam": "am_liam", "am_onyx": "am_onyx", "am_puck": "am_puck",
        "am_eric": "am_eric", "am_fenrir": "am_fenrir",
        # British Female
        "bf_alice": "bf_alice", "bf_emma": "bf_emma",
        "bf_lily": "bf_lily", "bf_isabella": "bf_isabella",
        # British Male
        "bm_daniel": "bm_daniel", "bm_george": "bm_george",
        "bm_lewis": "bm_lewis", "bm_fable": "bm_fable",
    }
    
    def __init__(self, model_path: str = "./kokoro-v1.0.onnx", 
                 voices_path: str = "./voices-v1.0.bin",
                 python_path: str = "/opt/homebrew/bin/python3.11"):
        self.model_path = model_path
        self.voices_path = voices_path
        self.python_path = python_path
        
    def is_available(self) -> bool:
        """Check if Kokoro is available."""
        return os.path.exists(self.model_path) and os.path.exists(self.voices_path)
    
    def get_kokoro_voice(self, voice_id: str) -> str:
        """Map our voice ID to Kokoro voice name."""
        return self.VOICE_MAP.get(voice_id, "af_sarah")
    
    async def generate(self, text: str, voice_id: str = "af_sky", 
                       speed: float = 1.0) -> bytes:
        """Generate TTS audio."""
        kokoro_voice = self.get_kokoro_voice(voice_id)
        
        with tempfile.NamedTemporaryFile(suffix='.txt', delete=False, mode='w', encoding='utf-8') as tmp:
            tmp.write(text)
            tmp_path = tmp.name

        # Output wav gets a fresh temp path
        out_fd, out_path = tempfile.mkstemp(suffix='.wav')
        os.close(out_fd)
        
        try:
            cmd = [
                self.python_path, "-m", "kokoro_tts",
                tmp_path, out_path,
                "--voice", kokoro_voice,
                "--speed", str(speed),
                "--model", self.model_path,
                "--voices", self.voices_path
            ]
            
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            
            if result.returncode != 0:
                raise Exception(f"Kokoro failed: {result.stderr}")
            
            with open(out_path, 'rb') as f:
                return f.read()
                
        finally:
            for f in [tmp_path, out_path]:
                try:
                    os.unlink(f)
                except:
                    pass
