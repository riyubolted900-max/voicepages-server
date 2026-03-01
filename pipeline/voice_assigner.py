"""
Voice Assigner - Assign TTS voices to characters
Works with both Kokoro and macOS Speech voices.
"""

import json
import logging
from typing import Dict, List
import httpx

from config import settings

logger = logging.getLogger(__name__)


# Unified voice list that works with both Kokoro and macOS Speech
AVAILABLE_VOICES = [
    # American Female (Kokoro)
    {"id": "af_sky", "name": "Sky", "gender": "female", "accent": "american", "style": "calm", "engine": "kokoro"},
    {"id": "af_heart", "name": "Heart", "gender": "female", "accent": "american", "style": "warm", "engine": "kokoro"},
    {"id": "af_bella", "name": "Bella", "gender": "female", "accent": "american", "style": "bright", "engine": "kokoro"},
    {"id": "af_nova", "name": "Nova", "gender": "female", "accent": "american", "style": "confident", "engine": "kokoro"},
    {"id": "af_sarah", "name": "Sarah", "gender": "female", "accent": "american", "style": "friendly", "engine": "kokoro"},
    {"id": "af_nicole", "name": "Nicole", "gender": "female", "accent": "american", "style": "smooth", "engine": "kokoro"},
    {"id": "af_alloy", "name": "Alloy", "gender": "female", "accent": "american", "style": "neutral", "engine": "kokoro"},
    {"id": "af_aoede", "name": "Aoede", "gender": "female", "accent": "american", "style": "melodic", "engine": "kokoro"},
    {"id": "af_jessica", "name": "Jessica", "gender": "female", "accent": "american", "style": "professional", "engine": "kokoro"},
    {"id": "af_kore", "name": "Kore", "gender": "female", "accent": "american", "style": "youthful", "engine": "kokoro"},
    {"id": "af_river", "name": "River", "gender": "female", "accent": "american", "style": "casual", "engine": "kokoro"},

    # American Male (Kokoro)
    {"id": "am_adam", "name": "Adam", "gender": "male", "accent": "american", "style": "deep", "engine": "kokoro"},
    {"id": "am_echo", "name": "Echo", "gender": "male", "accent": "american", "style": "energetic", "engine": "kokoro"},
    {"id": "am_michael", "name": "Michael", "gender": "male", "accent": "american", "style": "steady", "engine": "kokoro"},
    {"id": "am_liam", "name": "Liam", "gender": "male", "accent": "american", "style": "casual", "engine": "kokoro"},
    {"id": "am_onyx", "name": "Onyx", "gender": "male", "accent": "american", "style": "deep", "engine": "kokoro"},
    {"id": "am_puck", "name": "Puck", "gender": "male", "accent": "american", "style": "playful", "engine": "kokoro"},
    {"id": "am_eric", "name": "Eric", "gender": "male", "accent": "american", "style": "authoritative", "engine": "kokoro"},
    {"id": "am_fenrir", "name": "Fenrir", "gender": "male", "accent": "american", "style": "strong", "engine": "kokoro"},

    # British Female (Kokoro)
    {"id": "bf_alice", "name": "Alice", "gender": "female", "accent": "british", "style": "gentle", "engine": "kokoro"},
    {"id": "bf_emma", "name": "Emma", "gender": "female", "accent": "british", "style": "authoritative", "engine": "kokoro"},
    {"id": "bf_lily", "name": "Lily", "gender": "female", "accent": "british", "style": "sweet", "engine": "kokoro"},
    {"id": "bf_isabella", "name": "Isabella", "gender": "female", "accent": "british", "style": "elegant", "engine": "kokoro"},

    # British Male (Kokoro)
    {"id": "bm_daniel", "name": "Daniel", "gender": "male", "accent": "british", "style": "warm", "engine": "kokoro"},
    {"id": "bm_george", "name": "George", "gender": "male", "accent": "british", "style": "distinguished", "engine": "kokoro"},
    {"id": "bm_lewis", "name": "Lewis", "gender": "male", "accent": "british", "style": "clear", "engine": "kokoro"},
    {"id": "bm_fable", "name": "Fable", "gender": "male", "accent": "british", "style": "animated", "engine": "kokoro"},
]

VOICE_BY_ID = {v["id"]: v for v in AVAILABLE_VOICES}


class VoiceAssigner:
    """Assign TTS voices to characters based on their properties."""

    def __init__(self):
        self.available_voices = AVAILABLE_VOICES
        self.ollama_url = settings.ollama_url
        self.llm_model = settings.llm_model

        self.voices_by_gender = {
            "male": [v for v in self.available_voices if v["gender"] == "male"],
            "female": [v for v in self.available_voices if v["gender"] == "female"],
        }

        self.narrator_voice = "af_sky"

    def get_available_voices(self) -> List[Dict]:
        return self.available_voices

    async def assign_voices(self, characters: Dict) -> Dict:
        """
        Assign voices to detected characters.

        Returns:
            Dict of character_name -> {voice_id, voice_name, reasoning}
        """
        assignments = {}
        used_voices = set()

        # Sort: main first, then supporting, then minor
        role_order = {"main": 0, "supporting": 1, "minor": 2, "system": 3}
        sorted_chars = sorted(
            characters.items(),
            key=lambda x: role_order.get(x[1].get("role", "minor"), 2)
        )

        for char_name, char_data in sorted_chars:
            if char_name.lower() == "narrator" or char_data.get("role") == "system":
                assignments[char_name] = {
                    "voice_id": self.narrator_voice,
                    "voice_name": "Sky",
                    "reasoning": "Default narrator voice (calm, neutral)"
                }
                used_voices.add(self.narrator_voice)
                continue

            gender = char_data.get("gender", "unknown")

            if gender in ("male", "female"):
                candidates = self.voices_by_gender.get(gender, [])
            else:
                candidates = self.available_voices

            available = [v for v in candidates if v["id"] not in used_voices]
            if not available:
                available = candidates

            if available:
                voice = available[0]
                used_voices.add(voice["id"])
            else:
                voice = {"id": self.narrator_voice, "name": "Sky", "style": "calm"}

            assignments[char_name] = {
                "voice_id": voice["id"],
                "voice_name": voice.get("name", voice["id"]),
                "reasoning": f"Assigned {voice.get('style', 'default')} voice for {gender} character"
            }

        logger.info(f"Assigned voices to {len(assignments)} characters")
        return assignments

    async def assign_voice_with_llm(self, character_name: str, character_description: str) -> Dict:
        """Use LLM to intelligently assign a voice."""
        voices_json = json.dumps(self.available_voices[:10])

        prompt = f"""You are a voice casting director. Select the best voice for this character:

{voices_json}

Character: {character_name}
Description: {character_description}

Return ONLY JSON: {{"voice_id": "id", "reasoning": "why"}}
JSON:"""

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.ollama_url}/api/generate",
                    json={
                        "model": self.llm_model,
                        "prompt": prompt,
                        "stream": False,
                        "format": "json"
                    }
                )

                if response.status_code == 200:
                    result = response.json()
                    text = result.get("response", "{}")
                    data = json.loads(text)
                    voice_id = data.get("voice_id", self.narrator_voice)
                    if voice_id not in VOICE_BY_ID:
                        voice_id = self.narrator_voice
                    return {
                        "voice_id": voice_id,
                        "reasoning": data.get("reasoning", "Default assignment")
                    }
        except Exception as e:
            logger.warning(f"LLM voice assignment failed: {e}")

        return {"voice_id": self.narrator_voice, "reasoning": "Default fallback"}
