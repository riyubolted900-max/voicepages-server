"""
Audio Generator - Generate TTS audio from text
Uses Kokoro TTS only (local, high quality).
"""

import io
import logging
import os
import struct
from pathlib import Path
from typing import Dict, List
import numpy as np

from config import settings
from pipeline.kokoro_generator import KokoroGenerator

logger = logging.getLogger(__name__)


class AudioGenerator:
    """Generate TTS audio using Kokoro only."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        
        # Initialize Kokoro generator
        self.kokoro = KokoroGenerator(
            model_path=os.path.join(settings.storage_dir, "kokoro-v1.0.onnx"),
            voices_path=os.path.join(settings.storage_dir, "voices-v1.0.bin"),
            python_path="/opt/homebrew/bin/python3.11"
        )
        
        self.sample_rate = settings.audio_sample_rate

    async def generate(
        self, text: str, characters: Dict,
        voice_assignments: List[Dict], use_narrator: bool = True
    ) -> bytes:
        """Generate full chapter audio with character voices."""
        if not characters or not voice_assignments:
            narrator_voice = "af_sky"
            for char_name, char_data in characters.items() if characters else []:
                if char_data.get("is_narrator"):
                    narrator_voice = char_data.get("voice_id", "af_sky")
                    break
            return await self.generate_simple(text=text, voice_id=narrator_voice, speed=1.0)

        char_voice_map = {}
        narrator_voice = "af_sky"
        for char_name, char_data in characters.items():
            if char_data.get("is_narrator"):
                narrator_voice = char_data.get("voice_id", "af_sky")
            else:
                char_voice_map[char_name] = char_data.get("voice_id", narrator_voice)

        for assignment in voice_assignments:
            char_name = assignment.get("character")
            voice_id = assignment.get("voice_id")
            if char_name and voice_id:
                char_voice_map[char_name] = voice_id

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

        if not audio_segments:
            return await self.generate_simple(text=text, voice_id=narrator_voice, speed=1.0)

        return await self.concatenate_audio(audio_segments)

    async def _detect_dialogue_with_speakers(self, text: str, char_voice_map: Dict) -> List[Dict]:
        """Detect dialogue segments with speaker attribution."""
        import re
        segments = []
        
        dialogue_pattern = r'["""\'"]([^""\'"]+)["""\'"]\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:said|replied|asked|whispered|shouted|called|murmured|yelled|answered|sighed|breathed|hissed|growled|declared|demanded|insisted|suggested|continued|added|agreed|warned|pleaded|begged|barked|ordered|screamed|announced|laughed|smiled|grinned|chuckled|groaned|stammered|stuttered|sobbed|wailed|roared|sneered|scoffed|retorted|interrupted|protested|conceded|acknowledged|remarked|observed|noted|commented|explained|offered|urged|prompted|wondered|mused|pondered|repeated|finished|began|started|managed|attempted|tried|stated|spoke)'
        
        reverse_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\s+(?:said|replied|asked|whispered|shouted|called|murmured|yelled|answered|sighed|breathed|hissed|growled|declared|demanded|insisted|suggested|continued|added|agreed|warned|pleaded|begged|barked|ordered|screamed|announced|laughed|smiled|grinned|chuckled|groaned|stammered|stuttered|sobbed|wailed|roared|sneered|scoffed|retorted|interrupted|protested|conceded|acknowledged|remarked|observed|noted|commented|explained|offered|urged|prompted|wondered|mused|pondered|repeated|finished|began|started|managed|attempted|tried|stated|spoke)\s*[,.:]\s*["""\'"]([^""\'"]+)["""\']'
        
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
        
        all_matches.sort(key=lambda x: x["start"])
        
        last_end = 0
        for match in all_matches:
            if match["start"] > last_end:
                narration = text[last_end:match["start"]].strip()
                if narration:
                    segments.append({
                        "speaker": "Narrator",
                        "text": narration,
                        "type": "narration"
                    })
            
            if match["speaker"] in char_voice_map or match["speaker"] == "Narrator":
                segments.append({
                    "speaker": match["speaker"],
                    "text": match["dialogue"],
                    "type": "dialogue"
                })
            else:
                segments.append({
                    "speaker": "Narrator",
                    "text": match["dialogue"],
                    "type": "dialogue"
                })
            
            last_end = match["end"]
        
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
        """Generate TTS using Kokoro only."""
        if len(text) > settings.max_chunk_size:
            text = text[:settings.max_chunk_size]

        text = text.replace('\x00', '').replace('\ufffd', '')
        text = ' '.join(text.split())
        if not text.strip():
            raise ValueError("Empty text after cleaning")

        # Kokoro only - fail if not available
        if not self.kokoro.is_available():
            raise RuntimeError("Kokoro TTS not available. Please download the model files.")

        return await self.kokoro.generate(text, voice_id, speed)

    def _generate_placeholder_audio(self, text: str) -> bytes:
        """Generate placeholder audio when Kokoro is unavailable."""
        duration = min(len(text) * 0.05, 30)
        sample_rate = self.sample_rate
        num_samples = int(duration * sample_rate)
        if num_samples == 0:
            num_samples = sample_rate

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
