"""
Audio Generator - Generate TTS audio from text
Supports macOS Speech (built-in), Kokoro, and fallback options
"""

import io
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional
import httpx
import numpy as np

from config import settings

logger = logging.getLogger(__name__)


class AudioGenerator:
    """
    Generate TTS audio using configured backend.
    
    Priority:
    1. macOS Speech (built-in, works instantly!)
    2. Kokoro via MLX-Audio
    3. Placeholder (for testing)
    """
    
    # Map generic voice IDs to macOS voices
    VOICE_MAP = {
        # Female American
        "af_sky": "Samantha",
        "af_heart": "Victoria", 
        "af_bella": "Zoey",
        "af_nova": "Nova",
        "af_sarah": "Allison",
        
        # Male American
        "am_adam": "Daniel",
        "am_echo": "Alex",
        "am_michael": "Daniel",
        
        # British
        "bm_daniel": "Daniel",
        "bm_george": "Oliver",
        "bm_felix": "Oliver",
        
        # Female British
        "bf_alice": "Amelie",
        "bf_emma": "Amelie",
        "bf_isabella": "Amelie",
    }
    
    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # TTS Configuration
        self.backend = settings.tts_backend
        self.kokoro_url = settings.kokoro_url
        self.sample_rate = settings.audio_sample_rate
        
        # Check available backends
        self.use_mac_speech = True  # Always available on Mac!
    
    async def generate(
        self, 
        text: str, 
        characters: Dict,
        voice_assignments: List[Dict],
        use_narrator: bool = True
    ) -> bytes:
        """Generate full chapter audio with character voices."""
        # Find narrator voice
        narrator_voice = "af_sky"
        for char_name, char_data in characters.items():
            if char_data.get("is_narrator"):
                narrator_voice = char_data.get("voice_id", "af_sky")
                break
        
        return await self.generate_simple(
            text=text,
            voice_id=narrator_voice,
            speed=1.0
        )
    
    async def generate_simple(
        self, 
        text: str, 
        voice_id: str = "af_sky",
        speed: float = 1.0
    ) -> bytes:
        """
        Generate simple TTS for text with single voice.
        
        Args:
            text: Text to convert to speech
            voice_id: Voice identifier
            speed: Playback speed (0.5 - 2.0)
        
        Returns:
            WAV audio bytes
        """
        # Truncate very long texts
        if len(text) > settings.max_chunk_size:
            text = text[:settings.max_chunk_size]
        
        # Try macOS Speech first (works everywhere on Mac!)
        if self.use_mac_speech:
            try:
                return await self._generate_mac_speech(text, voice_id, speed)
            except Exception as e:
                logger.error(f"macOS Speech failed: {e}")
                # Don't fall back silently - raise the error
                raise Exception(f"TTS generation failed: {e}")
        
        # Try Kokoro
        if self.backend == "kokoro":
            try:
                return await self._generate_kokoro(text, voice_id, speed)
            except Exception as e:
                logger.warning(f"Kokoro failed: {e}")
        
        # Fallback: placeholder
        logger.warning("Using placeholder audio")
        return self._generate_placeholder_audio(text)
    
    async def _generate_mac_speech(
        self, 
        text: str, 
        voice_id: str,
        speed: float
    ) -> bytes:
        """Generate audio using macOS built-in Speech."""
        
        # Clean text - remove null bytes and other problematic characters
        text = text.replace('\x00', '')  # Remove null bytes
        text = text.replace('\ufffd', '')  # Remove replacement character
        text = ' '.join(text.split())  # Normalize whitespace
        
        if not text.strip():
            raise ValueError("Empty text after cleaning")
        
        # Map to macOS voice
        voice_name = self.VOICE_MAP.get(voice_id, "Samantha")
        
        # Convert speed (say uses words per minute, ~180 default)
        rate = int(180 * speed)
        
        logger.info(f"macOS TTS: voice={voice_name}, rate={rate}")
        
        # Create temp files
        with tempfile.NamedTemporaryFile(suffix='.aiff', delete=False) as tmp_in:
            tmp_aiff = tmp_in.name
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_out:
            tmp_wav = tmp_out.name
        
        try:
            # Generate speech to AIFF
            subprocess.run(
                ['say', '-v', voice_name, '-r', str(rate), '-o', tmp_aiff, text],
                check=True,
                capture_output=True
            )
            
            # Convert AIFF to WAV
            subprocess.run(
                ['afconvert', '-f', 'WAVE', '-d', 'LEI16@24000', tmp_aiff, tmp_wav],
                check=True,
                capture_output=True
            )
            
            # Read result
            with open(tmp_wav, 'rb') as f:
                audio_data = f.read()
            
            return audio_data
            
        finally:
            # Cleanup
            for f in [tmp_aiff, tmp_wav]:
                try:
                    os.unlink(f)
                except:
                    pass
    
    async def _generate_kokoro(
        self, 
        text: str, 
        voice_id: str,
        speed: float
    ) -> bytes:
        """Generate audio using Kokoro TTS via MLX-Audio HTTP API."""
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{self.kokoro_url}/v1/audio/speech",
                    json={
                        "model": "kokoro",
                        "input": text,
                        "voice": voice_id,
                        "speed": speed,
                        "response_format": "wav"
                    }
                )
                
                if response.status_code == 200:
                    return response.content
                else:
                    logger.error(f"Kokoro API error: {response.status_code}")
                    raise Exception(f"TTS failed: {response.status_code}")
        
        except httpx.ConnectError:
            raise Exception(f"Cannot connect to Kokoro at {self.kokoro_url}")
    
    def _generate_placeholder_audio(self, text: str) -> bytes:
        """Generate placeholder audio when TTS is unavailable."""
        import struct
        
        duration = min(len(text) * 0.05, 30)
        sample_rate = self.sample_rate
        num_samples = int(duration * sample_rate)
        
        t = np.linspace(0, duration, num_samples)
        base_freq = 200
        frequency = base_freq + 50 * np.sin(2 * np.pi * 2 * t)
        samples = np.sin(2 * np.pi * frequency * t)
        noise = np.random.normal(0, 0.05, num_samples)
        samples = samples * 0.3 + noise
        
        fade_samples = int(0.1 * sample_rate)
        envelope = np.ones(num_samples)
        envelope[:fade_samples] = np.linspace(0, 1, fade_samples)
        envelope[-fade_samples:] = np.linspace(1, 0, fade_samples)
        samples = samples * envelope
        
        samples_int = (samples * 32767).astype(np.int16)
        
        # Build WAV
        wav_buffer = io.BytesIO()
        wav_buffer.write(b'RIFF')
        wav_buffer.write(struct.pack('<I', 36 + num_samples * 2))
        wav_buffer.write(b'WAVE')
        wav_buffer.write(b'fmt ')
        wav_buffer.write(struct.pack('<I', 16))
        wav_buffer.write(struct.pack('<H', 1))
        wav_buffer.write(struct.pack('<H', 1))
        wav_buffer.write(struct.pack('<I', sample_rate))
        wav_buffer.write(struct.pack('<I', sample_rate * 2))
        wav_buffer.write(struct.pack('<H', 2))
        wav_buffer.write(struct.pack('<H', 16))
        wav_buffer.write(b'data')
        wav_buffer.write(struct.pack('<I', num_samples * 2))
        wav_buffer.write(samples_int.tobytes())
        
        return wav_buffer.getvalue()
    
    async def concatenate_audio(
        self, 
        audio_segments: List[bytes],
        pause_ms: int = 300
    ) -> bytes:
        """Concatenate multiple audio segments with pauses."""
        import struct
        
        if not audio_segments:
            return b''
        
        if len(audio_segments) == 1:
            return audio_segments[0]
        
        header = audio_segments[0][:44]
        sample_rate = struct.unpack('<I', header[22:26])[0]
        
        arrays = []
        for segment in audio_segments:
            if len(segment) > 44:
                arrays.append(np.frombuffer(segment[44:], dtype=np.int16))
        
        if not arrays:
            return audio_segments[0]
        
        pause_samples = int(sample_rate * pause_ms / 1000)
        pause = np.zeros(pause_samples, dtype=np.int16)
        
        combined = np.concatenate([arr for arr in arrays])
        
        wav_buffer = io.BytesIO()
        num_samples = len(combined)
        
        wav_buffer.write(b'RIFF')
        wav_buffer.write(struct.pack('<I', 36 + num_samples * 2))
        wav_buffer.write(b'WAVE')
        wav_buffer.write(b'fmt ')
        wav_buffer.write(struct.pack('<I', 16))
        wav_buffer.write(struct.pack('<H', 1))
        wav_buffer.write(struct.pack('<H', 1))
        wav_buffer.write(struct.pack('<I', sample_rate))
        wav_buffer.write(struct.pack('<I', sample_rate * 2))
        wav_buffer.write(struct.pack('<H', 2))
        wav_buffer.write(struct.pack('<H', 16))
        wav_buffer.write(b'data')
        wav_buffer.write(struct.pack('<I', num_samples * 2))
        wav_buffer.write(combined.tobytes())
        
        return wav_buffer.getvalue()
