"""Kokoro TTS Adapter - Uses local MLX-Audio server"""
import httpx
from adapters.base import TTSAdapter, TTSRequest, TTSResponse
import config

class KokoroAdapter(TTSAdapter):
    """Adapter for Kokoro via MLX-Audio OpenAI-compatible API."""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or config.KOKORO_URL
        self.voice_map = config.VOICES
    
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
                # Fallback: return error indication
                raise RuntimeError(f"Cannot connect to Kokoro server at {self.base_url}. Start with: mlx_audio serve")
    
    def get_available_voices(self) -> list[dict]:
        return [{"id": k, **v} for k, v in self.voice_map.items()]
    
    def get_voice_for_profile(self, gender: str, age: str, style: str) -> str:
        candidates = [
            vid for vid, meta in self.voice_map.items()
            if meta["gender"] == gender
        ]
        return candidates[0] if candidates else "af_sky"
