"""
macOS Speech TTS Adapter
Uses built-in 'say' command - no setup needed!
"""

import os
import subprocess
import tempfile
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class MacSayTTS:
    """
    macOS built-in TTS using 'say' command.
    Works instantly, no setup required!
    
    Available voices: say -v "?" to list
    """
    
    # Quality voices for audiobooks
    VOICES = {
        # American Female
        "af_samantha": {"name": "Samantha", "gender": "female", "accent": "american"},
        "af_zoey": {"name": "Zoey", "gender": "female", "accent": "american"},
        "af_allison": {"name": "Allison", "gender": "female", "accent": "american"},
        "af_ava": {"name": "Ava", "gender": "female", "accent": "american"},
        "af_victoria": {"name": "Victoria", "gender": "female", "accent": "american"},
        
        # American Male
        "am_alex": {"name": "Alex", "gender": "male", "accent": "american"},
        "am_daniel": {"name": "Daniel", "gender": "male", "accent": "american"},
        "am_fred": {"name": "Fred", "gender": "male", "accent": "american"},
        "am_ralph": {"name": "Ralph", "gender": "male", "accent": "american"},
        
        # British
        "bf_amelie": {"name": "Amelie", "gender": "female", "accent": "british"},
        "bf_daniel": {"name": "Daniel", "gender": "male", "accent": "british"},
        "bf_oliver": {"name": "Oliver", "gender": "male", "accent": "british"},
        
        # Premium (Neural)
        "af_nova": {"name": "Nova", "gender": "female", "accent": "american", "neural": True},
        "af_shimmer": {"name": "Shimmer", "gender": "female", "accent": "american", "neural": True},
    }
    
    # Map Kokoro voice IDs to macOS voices
    VOICE_MAP = {
        "af_sky": "Samantha",
        "af_heart": "Victoria",
        "af_bella": "Zoey",
        "af_nova": "Nova",
        "am_adam": "Daniel",
        "am_echo": "Alex",
        "bm_daniel": "Daniel",
        "bm_george": "Oliver",
        "bf_alice": "Amelie",
        "bf_emma": "Amelie",
    }
    
    def __init__(self):
        self.sample_rate = 24000
    
    async def speak(self, text: str, voice_id: str = "af_samantha", speed: float = 1.0) -> bytes:
        """
        Generate speech audio.
        
        Args:
            text: Text to speak
            voice_id: Voice identifier (e.g., "af_samantha")
            speed: Speech rate (0.5 - 2.0)
        
        Returns:
            WAV audio bytes
        """
        # Map to macOS voice
        voice_name = self.VOICE_MAP.get(voice_id, "Samantha")
        
        # Convert speed to macOS rate (words per minute)
        # Default say is ~180 wpm. speed 1.0 = 180, speed 2.0 = 360
        rate = int(180 * speed)
        
        logger.info(f"Generating speech: voice={voice_name}, rate={rate}, text={text[:50]}...")
        
        try:
            # Create temp file
            with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp:
                tmp_path = tmp.name
            
            # Generate speech
            cmd = [
                'say',
                '-v', voice_name,
                '-r', str(rate),
                '-o', tmp_path,
                text
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Read the generated audio
            with open(tmp_path, 'rb') as f:
                audio_data = f.read()
            
            # Clean up
            os.unlink(tmp_path)
            
            # Convert to standard WAV if needed
            return self._ensure_wav(audio_data)
            
        except Exception as e:
            logger.error(f"macOS TTS failed: {e}")
            raise
    
    def _ensure_wav(self, data: bytes) -> bytes:
        """Ensure data is valid WAV."""
        # macOS 'say' outputs AIFF by default, need to convert
        # For now, return as-is (browser can play AIFF)
        # TODO: Convert to WAV using afconvert
        return data
    
    async def list_voices(self) -> list:
        """List available voices."""
        voices = []
        
        # Get actual available voices
        try:
            result = subprocess.run(
                ['say', '-v', '?'],
                capture_output=True,
                text=True,
                check=True
            )
            
            for line in result.stdout.strip().split('\n'):
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        gender = "female" if name.startswith("af") or name.startswith("BF") else "male"
                        voices.append({
                            "id": f"mac_{name.lower()}",
                            "name": name,
                            "gender": gender,
                            "accent": "american" if name.startswith("a") else "british",
                            "style": "neural" if "Premium" in line else "standard"
                        })
        except:
            pass
        
        return voices


# Export singleton
tts = MacSayTTS()
