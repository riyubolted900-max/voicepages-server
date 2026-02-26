"""
Audio Generator - Generate TTS audio from text
Supports macOS Speech (built-in), Kokoro, and fallback options.
"""

import io
import logging
import os
import subprocess
import struct
import tempfile
from pathlib import Path
from typing import Dict, List
import httpx
import numpy as np

from config import settings

logger = logging.getLogger(__name__)


class AudioGenerator:
    """
    Generate TTS audio using configured backend.

    Priority:
    1. Kokoro via MLX-Audio (if running)
    2. macOS Speech (built-in, always available on Mac)
    3. Placeholder (for testing only)
    """

    MAC_VOICE_MAP = {
        "af_sky": "Samantha", "af_heart": "Victoria", "af_bella": "Zoey",
        "af_nova": "Samantha", "af_sarah": "Allison", "af_nicole": "Samantha",
        "am_adam": "Daniel", "am_echo": "Alex", "am_michael": "Daniel",
        "am_liam": "Alex",
        "bm_daniel": "Daniel", "bm_george": "Oliver", "bm_lewis": "Oliver",
        "bm_fable": "Oliver",
        "bf_alice": "Samantha", "bf_emma": "Samantha", "bf_lily": "Samantha",
        "bf_isabella": "Samantha",
    }

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.backend = settings.tts_backend
        self.kokoro_url = settings.kokoro_url
        self.sample_rate = settings.audio_sample_rate

    async def generate(
        self, text: str, characters: Dict,
        voice_assignments: List[Dict], use_narrator: bool = True
    ) -> bytes:
        """Generate full chapter audio with character voices."""
        if not characters or not voice_assignments:
            # No character data - use single voice
            narrator_voice = "af_sky"
            for char_name, char_data in characters.items() if characters else []:
                if char_data.get("is_narrator"):
                    narrator_voice = char_data.get("voice_id", "af_sky")
                    break
            return await self.generate_simple(text=text, voice_id=narrator_voice, speed=1.0)

        # Build a mapping of character names to their voices
        char_voice_map = {}
        narrator_voice = "af_sky"
        for char_name, char_data in characters.items():
            if char_data.get("is_narrator"):
                narrator_voice = char_data.get("voice_id", "af_sky")
            else:
                char_voice_map[char_name] = char_data.get("voice_id", narrator_voice)

        # Build voice assignment map from voice_assignments list
        # Format: [{"character": "Name", "voice_id": "af_sky"}, ...]
        for assignment in voice_assignments:
            char_name = assignment.get("character")
            voice_id = assignment.get("voice_id")
            if char_name and voice_id:
                char_voice_map[char_name] = voice_id

        # Detect dialogue and generate audio per segment
        segments = await self._detect_dialogue_with_speakers(text, char_voice_map)
        
        audio_segments = []
        for segment in segments:
            speaker = segment.get("speaker", "Narrator")
            segment_text = segment.get("text", "")
            if not segment_text.strip():
                continue
            
            voice_id = char_voice_map.get(speaker, narrator_voice)
            try:
                audio = await self.generate_simple(text=segment_text, voice_id=voice_id, speed=1.0)
                audio_segments.append(audio)
            except Exception as e:
                logger.warning(f"Failed to generate audio for {speaker}: {e}")
                # Fallback to narrator voice
                audio = await self.generate_simple(text=segment_text, voice_id=narrator_voice, speed=1.0)
                audio_segments.append(audio)

        if not audio_segments:
            return await self.generate_simple(text=text, voice_id=narrator_voice, speed=1.0)

        return await self.concatenate_audio(audio_segments)

    async def _detect_dialogue_with_speakers(self, text: str, char_voice_map: Dict) -> List[Dict]:
        """Detect dialogue segments with speaker attribution."""
        import re
        segments = []
        
        # Pattern to find dialogue with speaker attribution
        # Matches: "dialogue" Name said / "dialogue," Name replied
        dialogue_pattern = r'["""\'"]([^""\'"]+)["""\'"]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:said|replied|asked|whispered|shouted|called|murmured|yelled|answered|sighed|breathed|hissed|growled|declared|demanded|insisted|suggested|continued|added|agreed|warned|pleaded|begged|barked|ordered|screamed|announced|laughed|smiled|grinned|chuckled|groaned|stammered|stuttered|sobbed|wailed|roared|sneered|scoffed|retorted|interrupted|protested|conceded|acknowledged|remarked|observed|noted|commented|explained|offered|urged|prompted|wondered|mused|pondered|repeated|finished|began|started|managed|attempted|tried|stated|spoke)'
        
        # Pattern for Name said, "dialogue"
        reverse_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:said|replied|asked|whispered|shouted|called|murmured|yelled|answered|sighed|breathed|hissed|growled|declared|demanded|insisted|suggested|continued|added|agreed|warned|pleaded|begged|barked|ordered|screamed|announced|laughed|smiled|grinned|chuckled|groaned|stammered|stuttered|sobbed|wailed|roared|sneered|scoffed|retorted|interrupted|protested|conceded|acknowledged|remarked|observed|noted|commented|explained|offered|urged|prompted|wondered|mused|pondered|repeated|finished|began|started|managed|attempted|tried|stated|spoke)\s*[,.:]\s*["""\'"]([^""\'"]+)["""\']'
        
        # Find all matches and their positions
        all_matches = []
        
        for m in re.finditer(dialogue_pattern, text):
            all_matches.append({
                "start": m.start(),
                "end": m.end(),
                "speaker": m.group(2).strip(),
                "dialogue": m.group(1).strip(),
                "type": "dialogue"
            })
        
        for m in re.finditer(reverse_pattern, text):
            all_matches.append({
                "start": m.start(),
                "end": m.end(),
                "speaker": m.group(1).strip(),
                "dialogue": m.group(2).strip(),
                "type": "dialogue"
            })
        
        # Sort by position
        all_matches.sort(key=lambda x: x["start"])
        
        # Build segments
        last_end = 0
        for match in all_matches:
            # Add narration before this dialogue
            if match["start"] > last_end:
                narration = text[last_end:match["start"]].strip()
                if narration:
                    segments.append({
                        "speaker": "Narrator",
                        "text": narration,
                        "type": "narration"
                    })
            
            # Add dialogue
            if match["speaker"] in char_voice_map or match["speaker"] == "Narrator":
                segments.append({
                    "speaker": match["speaker"],
                    "text": match["dialogue"],
                    "type": "dialogue"
                })
            else:
                # Unknown speaker - treat as narrator
                segments.append({
                    "speaker": "Narrator",
                    "text": match["dialogue"],
                    "type": "dialogue"
                })
            
            last_end = match["end"]
        
        # Add remaining narration
        if last_end < len(text):
            remaining = text[last_end:].strip()
            if remaining:
                segments.append({
                    "speaker": "Narrator",
                    "text": remaining,
                    "type": "narration"
                })
        
        return segments if segments else [{"speaker": "Narrator", "text": text, "type": "narration"}]

    async def generate_simple(
        self, text: str, voice_id: str = "af_sky", speed: float = 1.0
    ) -> bytes:
        """Generate TTS for text with a single voice."""
        if len(text) > settings.max_chunk_size:
            text = text[:settings.max_chunk_size]

        text = text.replace('\x00', '').replace('\ufffd', '')
        text = ' '.join(text.split())
        if not text.strip():
            raise ValueError("Empty text after cleaning")

        # Try Kokoro first
        if self.backend == "kokoro":
            try:
                return await self._generate_kokoro(text, voice_id, speed)
            except Exception as e:
                logger.warning(f"Kokoro failed, falling back to macOS Speech: {e}")

        # Try macOS Speech
        try:
            return await self._generate_mac_speech(text, voice_id, speed)
        except Exception as e:
            logger.error(f"macOS Speech failed: {e}")

        # Last resort
        logger.warning("All TTS backends failed, using placeholder audio")
        return self._generate_placeholder_audio(text)

    async def _generate_kokoro(self, text: str, voice_id: str, speed: float) -> bytes:
        """Generate audio using Kokoro TTS via MLX-Audio HTTP API."""
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
                raise Exception(f"Kokoro API error: {response.status_code}")

    async def _generate_mac_speech(self, text: str, voice_id: str, speed: float) -> bytes:
        """Generate audio using macOS built-in Speech."""
        voice_name = self.MAC_VOICE_MAP.get(voice_id, "Samantha")
        rate = int(180 * speed)

        logger.info(f"macOS TTS: voice={voice_name}, rate={rate}")

        with tempfile.NamedTemporaryFile(suffix='.aiff', delete=False) as tmp_in:
            tmp_aiff = tmp_in.name
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_out:
            tmp_wav = tmp_out.name

        try:
            subprocess.run(
                ['say', '-v', voice_name, '-r', str(rate), '-o', tmp_aiff, text],
                check=True, capture_output=True
            )
            subprocess.run(
                ['afconvert', '-f', 'WAVE', '-d', 'LEI16@24000', tmp_aiff, tmp_wav],
                check=True, capture_output=True
            )
            with open(tmp_wav, 'rb') as f:
                raw_wav = f.read()
            # afconvert adds a non-standard FLLR padding chunk that breaks
            # browser HTML5 Audio decoders. Re-encode as a clean WAV.
            return self._clean_wav(raw_wav)
        finally:
            for f in [tmp_aiff, tmp_wav]:
                try:
                    os.unlink(f)
                except OSError:
                    pass

    def _clean_wav(self, wav_bytes: bytes) -> bytes:
        """
        Strip non-standard chunks (FLLR, etc.) from WAV files.

        macOS afconvert produces WAV files with a FLLR (filler) padding chunk
        between the 'fmt ' and 'data' chunks. Most browser HTML5 Audio decoders
        don't handle non-standard chunks and fail to load the audio.

        This method parses the WAV, extracts only fmt and data chunks,
        and writes a clean, browser-compatible WAV file.
        """
        if len(wav_bytes) < 44:
            return wav_bytes

        # Verify RIFF/WAVE header
        if wav_bytes[:4] != b'RIFF' or wav_bytes[8:12] != b'WAVE':
            return wav_bytes

        # Parse chunks to find fmt and data
        fmt_chunk = None
        data_chunk = None
        pos = 12  # Skip RIFF header + 'WAVE'

        while pos < len(wav_bytes) - 8:
            chunk_id = wav_bytes[pos:pos+4]
            chunk_size = struct.unpack('<I', wav_bytes[pos+4:pos+8])[0]
            chunk_data = wav_bytes[pos+8:pos+8+chunk_size]

            if chunk_id == b'fmt ':
                fmt_chunk = chunk_data
            elif chunk_id == b'data':
                data_chunk = chunk_data
            # Skip all other chunks (FLLR, LIST, etc.)

            pos += 8 + chunk_size
            # Chunks are word-aligned (padded to even size)
            if chunk_size % 2 == 1:
                pos += 1

        if fmt_chunk is None or data_chunk is None:
            logger.warning("Could not parse WAV chunks, returning original")
            return wav_bytes

        # Build a clean WAV: RIFF header + fmt + data only
        fmt_size = len(fmt_chunk)
        data_size = len(data_chunk)
        # RIFF size = 4 (WAVE) + 8 (fmt header) + fmt_size + 8 (data header) + data_size
        riff_size = 4 + 8 + fmt_size + 8 + data_size

        clean = io.BytesIO()
        clean.write(b'RIFF')
        clean.write(struct.pack('<I', riff_size))
        clean.write(b'WAVE')
        clean.write(b'fmt ')
        clean.write(struct.pack('<I', fmt_size))
        clean.write(fmt_chunk)
        clean.write(b'data')
        clean.write(struct.pack('<I', data_size))
        clean.write(data_chunk)

        result = clean.getvalue()
        logger.debug(f"Cleaned WAV: {len(wav_bytes)} -> {len(result)} bytes (removed {len(wav_bytes) - len(result)} bytes of padding)")
        return result

    def _generate_placeholder_audio(self, text: str) -> bytes:
        """Generate placeholder audio when all TTS backends are unavailable."""
        duration = min(len(text) * 0.05, 30)
        sample_rate = self.sample_rate
        num_samples = int(duration * sample_rate)
        if num_samples == 0:
            num_samples = sample_rate  # 1 second minimum

        t = np.linspace(0, duration, num_samples)
        samples = np.sin(2 * np.pi * 200 * t) * 0.3
        fade = int(0.1 * sample_rate)
        if fade > 0 and num_samples > 2 * fade:
            samples[:fade] *= np.linspace(0, 1, fade)
            samples[-fade:] *= np.linspace(1, 0, fade)
        samples_int = (samples * 32767).astype(np.int16)

        wav = io.BytesIO()
        wav.write(b'RIFF')
        wav.write(struct.pack('<I', 36 + num_samples * 2))
        wav.write(b'WAVE')
        wav.write(b'fmt ')
        wav.write(struct.pack('<I', 16))
        wav.write(struct.pack('<HH', 1, 1))
        wav.write(struct.pack('<I', sample_rate))
        wav.write(struct.pack('<I', sample_rate * 2))
        wav.write(struct.pack('<HH', 2, 16))
        wav.write(b'data')
        wav.write(struct.pack('<I', num_samples * 2))
        wav.write(samples_int.tobytes())
        return wav.getvalue()

    async def concatenate_audio(self, audio_segments: List[bytes], pause_ms: int = 300) -> bytes:
        """Concatenate multiple audio segments with pauses between them."""
        if not audio_segments:
            return b''
        if len(audio_segments) == 1:
            return audio_segments[0]

        header = audio_segments[0][:44]
        sample_rate = struct.unpack('<I', header[24:28])[0]

        pause_samples = int(sample_rate * pause_ms / 1000)
        pause = np.zeros(pause_samples, dtype=np.int16)

        arrays = []
        for i, segment in enumerate(audio_segments):
            if len(segment) > 44:
                arrays.append(np.frombuffer(segment[44:], dtype=np.int16))
                if i < len(audio_segments) - 1:
                    arrays.append(pause)

        if not arrays:
            return audio_segments[0]

        combined = np.concatenate(arrays)
        num_samples = len(combined)

        wav = io.BytesIO()
        wav.write(b'RIFF')
        wav.write(struct.pack('<I', 36 + num_samples * 2))
        wav.write(b'WAVE')
        wav.write(b'fmt ')
        wav.write(struct.pack('<I', 16))
        wav.write(struct.pack('<HH', 1, 1))
        wav.write(struct.pack('<I', sample_rate))
        wav.write(struct.pack('<I', sample_rate * 2))
        wav.write(struct.pack('<HH', 2, 16))
        wav.write(b'data')
        wav.write(struct.pack('<I', num_samples * 2))
        wav.write(combined.tobytes())
        return wav.getvalue()
