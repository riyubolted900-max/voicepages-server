"""Kokoro TTS Adapter - Uses local MLX-Audio server"""
import httpx
from typing import List, Dict
from adapters.base import TTSAdapter, TTSRequest, TTSResponse
from config import settings

# Kokoro voice definitions
KOKORO_VOICES = {
    # Male voices
    "am_adam": {"gender": "male", "age": "adult", "accent": "american", "style": "deep"},
    "am_echo": {"gender": "male", "age": "young", "accent": "american", "style": "energetic"},
    "am_liam": {"gender": "male", "age": "adult", "accent": "american", "style": "casual"},
    "am_michael": {"gender": "male", "age": "adult", "accent": "american", "style": "steady"},
    "bm_daniel": {"gender": "male", "age": "adult", "accent": "british", "style": "warm"},
    "bm_george": {"gender": "male", "age": "elder", "accent": "british", "style": "distinguished"},
    "bm_lewis": {"gender": "male", "age": "adult", "accent": "british", "style": "clear"},
    "bm_fable": {"gender": "male", "age": "adult", "accent": "british", "style": "animated"},
    # Female voices
    "af_heart": {"gender": "female", "age": "adult", "accent": "american", "style": "warm"},
    "af_bella": {"gender": "female", "age": "young", "accent": "american", "style": "bright"},
    "af_nova": {"gender": "female", "age": "adult", "accent": "american", "style": "confident"},
    "af_sky": {"gender": "female", "age": "adult", "accent": "american", "style": "neutral"},
    "af_nicole": {"gender": "female", "age": "adult", "accent": "american", "style": "smooth"},
    "af_sarah": {"gender": "female", "age": "adult", "accent": "american", "style": "friendly"},
    "bf_alice": {"gender": "female", "age": "adult", "accent": "british", "style": "gentle"},
    "bf_emma": {"gender": "female", "age": "adult", "accent": "british", "style": "authoritative"},
    "bf_lily": {"gender": "female", "age": "young", "accent": "british", "style": "sweet"},
    "bf_isabella": {"gender": "female", "age": "adult", "accent": "british", "style": "elegant"},
}


class KokoroAdapter(TTSAdapter):
    """Adapter for Kokoro via MLX-Audio OpenAI-compatible API."""

    def __init__(self, base_url: str = None):
        self.base_url = base_url or settings.kokoro_url
        self.voice_map = KOKORO_VOICES

    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Generate audio using Kokoro TTS."""
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/v1/audio/speech",
                    json={
                        "model": "mlx-community/Kokoro-82M-bf16",
                        "input": request.text,
                        "voice": request.voice_id,
                        "speed": request.speed,
                        "response_format": "wav"
                    },
                    timeout=60.0
                )
                response.raise_for_status()
                return TTSResponse(
                    audio_bytes=response.content,
                    duration_seconds=len(response.content) / (24000 * 2),
                    sample_rate=24000
                )
            except httpx.ConnectError:
                raise RuntimeError(
                    f"Cannot connect to Kokoro server at {self.base_url}. "
                    "Start with: mlx_audio serve --model mlx-community/Kokoro-82M-bf16 --port 8000"
                )

    def get_available_voices(self) -> List[Dict]:
        return [{"id": k, **v} for k, v in self.voice_map.items()]

    def get_voice_for_profile(self, gender: str, age: str, style: str) -> str:
        candidates = [
            vid for vid, meta in self.voice_map.items()
            if meta["gender"] == gender
        ]
        return candidates[0] if candidates else "af_sky"
