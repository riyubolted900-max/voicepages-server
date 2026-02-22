"""
macOS Speech TTS Adapter
Uses built-in 'say' command - no setup needed!
"""

import os
import subprocess
import tempfile
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class MacSayTTS:
    """
    macOS built-in TTS using 'say' command.
    Works instantly, no setup required!
    """

    # Map generic voice IDs to macOS voice names
    VOICE_MAP = {
        "af_sky": "Samantha",
        "af_heart": "Victoria",
        "af_bella": "Zoey",
        "af_nova": "Samantha",
        "af_sarah": "Allison",
        "af_nicole": "Samantha",
        "am_adam": "Daniel",
        "am_echo": "Alex",
        "am_michael": "Daniel",
        "am_liam": "Alex",
        "bm_daniel": "Daniel",
        "bm_george": "Oliver",
        "bm_lewis": "Oliver",
        "bm_fable": "Oliver",
        "bf_alice": "Samantha",
        "bf_emma": "Samantha",
        "bf_lily": "Samantha",
        "bf_isabella": "Samantha",
        # macOS-specific voices
        "af_samantha": "Samantha",
        "af_zoey": "Zoey",
        "af_allison": "Allison",
        "af_ava": "Ava",
        "af_victoria": "Victoria",
        "am_alex": "Alex",
        "am_daniel": "Daniel",
        "am_fred": "Fred",
        "am_ralph": "Ralph",
        "bf_amelie": "Samantha",
        "bm_oliver": "Oliver",
        "af_shimmer": "Samantha",
    }

    def __init__(self):
        self.sample_rate = 24000

    async def speak(self, text: str, voice_id: str = "af_samantha", speed: float = 1.0) -> bytes:
        """Generate speech audio as WAV bytes."""
        voice_name = self.VOICE_MAP.get(voice_id, "Samantha")
        rate = int(180 * speed)

        logger.info(f"Generating speech: voice={voice_name}, rate={rate}, text={text[:50]}...")

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

            # Convert AIFF to WAV using afconvert (built into macOS)
            subprocess.run(
                ['afconvert', '-f', 'WAVE', '-d', 'LEI16@24000', tmp_aiff, tmp_wav],
                check=True,
                capture_output=True
            )

            with open(tmp_wav, 'rb') as f:
                audio_data = f.read()

            return audio_data

        finally:
            for f in [tmp_aiff, tmp_wav]:
                try:
                    os.unlink(f)
                except OSError:
                    pass

    async def list_voices(self) -> List[Dict]:
        """List available macOS voices."""
        voices = []
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
                        voices.append({
                            "id": f"mac_{name.lower()}",
                            "name": name,
                            "gender": "unknown",
                            "accent": "american",
                            "style": "standard"
                        })
        except Exception:
            pass
        return voices


# Export singleton
tts = MacSayTTS()
