"""TTS Adapter Base Interface"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class TTSRequest:
    text: str
    voice_id: str
    speed: float = 1.0
    emotion: Optional[str] = None
    output_format: str = "wav"

@dataclass
class TTSResponse:
    audio_bytes: bytes
    duration_seconds: float
    sample_rate: int = 24000

class TTSAdapter(ABC):
    """Base interface for all TTS backends."""
    
    @abstractmethod
    async def synthesize(self, request: TTSRequest) -> TTSResponse:
        """Generate audio from text."""
        pass
    
    @abstractmethod
    def get_available_voices(self) -> list[dict]:
        """Return list of available voices with metadata."""
        pass
    
    @abstractmethod
    def get_voice_for_profile(self, gender: str, age: str, style: str) -> str:
        """Map character profile to best matching voice_id."""
        pass
