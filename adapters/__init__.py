"""TTS Adapters"""
from adapters.base import TTSAdapter, TTSRequest, TTSResponse
from adapters.kokoro import KokoroAdapter
from adapters.mac_say import MacSayTTS

__all__ = ["TTSAdapter", "TTSRequest", "TTSResponse", "KokoroAdapter", "MacSayTTS"]
