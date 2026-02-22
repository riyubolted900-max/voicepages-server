"""
Voice Assigner - Assign TTS voices to characters
Uses macOS built-in voices - no setup needed!
"""

import json
import logging
import subprocess
from typing import Dict, List
import httpx

from config import settings

logger = logging.getLogger(__name__)


# Available voices from macOS Speech
# These work out of the box on any Mac!
AVAILABLE_VOICES = [
    # American Female - Premium (Neural)
    {"id": "af_nova", "name": "Nova", "gender": "female", "accent": "american", "style": "neural", "quality": "premium"},
    {"id": "af_shimmer", "name": "Shimmer", "gender": "female", "accent": "american", "style": "neural", "quality": "premium"},
    
    # American Female - Standard
    {"id": "af_samantha", "name": "Samantha", "gender": "female", "accent": "american", "style": "clear", "quality": "standard"},
    {"id": "af_zoey", "name": "Zoey", "gender": "female", "accent": "american", "style": "young", "quality": "standard"},
    {"id": "af_allison", "name": "Allison", "gender": "female", "accent": "american", "style": "warm", "quality": "standard"},
    {"id": "af_ava", "name": "Ava", "gender": "female", "accent": "american", "style": "modern", "quality": "standard"},
    {"id": "af_victoria", "name": "Victoria", "gender": "female", "accent": "american", "style": "professional", "quality": "standard"},
    
    # American Male
    {"id": "am_alex", "name": "Alex", "gender": "male", "accent": "american", "style": "default", "quality": "standard"},
    {"id": "am_daniel", "name": "Daniel", "gender": "male", "accent": "american", "style": "deep", "quality": "standard"},
    {"id": "am_fred", "name": "Fred", "gender": "male", "accent": "american", "style": "robotic", "quality": "standard"},
    
    # British Female
    {"id": "bf_amelie", "name": "Amelie", "gender": "female", "accent": "british", "style": "elegant", "quality": "standard"},
    
    # British Male
    {"id": "bm_daniel", "name": "Daniel (UK)", "gender": "male", "accent": "british", "style": "professional", "quality": "standard"},
    {"id": "bm_oliver", "name": "Oliver", "gender": "male", "accent": "british", "style": "formal", "quality": "standard"},
]

# Legacy IDs for compatibility
LEGACY_VOICE_MAP = {
    "af_sky": "af_samantha",
    "af_heart": "af_victoria",
    "af_bella": "af_zoey",
    "af_sarah": "af_allison",
    "am_adam": "am_daniel",
    "am_echo": "am_alex",
    "am_michael": "am_daniel",
    "bm_daniel": "bm_daniel",
    "bm_george": "bm_oliver",
    "bm_felix": "bm_oliver",
    "bf_alice": "bf_amelie",
    "bf_emma": "bf_amelie",
    "bf_isabella": "bf_amelie",
}


class VoiceAssigner:
    """
    Assign TTS voices to characters based on their properties.
    Uses macOS built-in voices - works instantly!
    """
    
    def __init__(self):
        self.available_voices = AVAILABLE_VOICES
        self.ollama_url = settings.ollama_url
        self.llm_model = settings.llm_model
        
        # Build lookup maps
        self.voices_by_gender = {
            "male": [v for v in self.available_voices if v["gender"] == "male"],
            "female": [v for v in self.available_voices if v["gender"] == "female"],
        }
        
        # Default narrator voice (warm, clear)
        self.narrator_voice = "af_samantha"
    
    def get_available_voices(self) -> List[Dict]:
        """Return list of all available TTS voices."""
        return self.available_voices
    
    def _normalize_voice_id(self, voice_id: str) -> str:
        """Normalize voice ID to current format."""
        return LEGACY_VOICE_MAP.get(voice_id, voice_id)
    
    async def assign_voices(self, characters: Dict) -> Dict:
        """
        Assign voices to detected characters.
        
        Args:
            characters: Dict of character_name -> {gender, role, description}
        
        Returns:
            Dict of character_name -> {voice_id, reasoning}
        """
        assignments = {}
        
        # Separate main characters from minor
        main_chars = {k: v for k, v in characters.items() 
                     if v.get("role") == "main"}
        supporting = {k: v for k, v in characters.items() 
                     if v.get("role") == "supporting"}
        
        # Assign voices to main characters (ensure variety)
        used_voices = set()
        
        for i, (char_name, char_data) in enumerate(main_chars.items()):
            gender = char_data.get("gender", "unknown")
            
            if gender == "male":
                candidates = self.voices_by_gender.get("male", [])
            elif gender == "female":
                candidates = self.voices_by_gender.get("female", [])
            else:
                # Default to female
                candidates = self.voices_by_gender.get("female", [])
            
            # Filter out used voices to maximize variety
            available = [v for v in candidates if v["id"] not in used_voices]
            
            if available:
                voice = available[0]
                used_voices.add(voice["id"])
            elif candidates:
                voice = candidates[0]
            else:
                voice = {"id": self.narrator_voice, "name": "Samantha"}
            
            assignments[char_name] = {
                "voice_id": voice["id"],
                "voice_name": voice.get("name", voice["id"]),
                "reasoning": f"Assigned {voice['style']} voice for {gender} character"
            }
        
        # Handle narrator
        if "Narrator" in characters:
            assignments["Narrator"] = {
                "voice_id": self.narrator_voice,
                "voice_name": "Samantha",
                "reasoning": "Default narrator voice (clear, warm)"
            }
        
        # Minor characters reuse voices
        minor_voices = list(used_voices) if used_voices else [self.narrator_voice]
        for i, (char_name, char_data) in enumerate(supporting.items()):
            voice_id = minor_voices[i % len(minor_voices)]
            assignments[char_name] = {
                "voice_id": voice_id,
                "voice_name": next((v["name"] for v in self.available_voices if v["id"] == voice_id), voice_id),
                "reasoning": "Supporting character voice"
            }
        
        logger.info(f"Assigned voices to {len(assignments)} characters")
        return assignments
    
    async def assign_voice_with_llm(
        self, 
        character_name: str, 
        character_description: str
    ) -> Dict:
        """
        Use LLM to intelligently assign a voice based on character description.
        """
        voices_json = json.dumps(self.available_voices[:10])
        
        prompt = f"""You are a voice casting director. Given a character's description, 
select the best voice from this list:

{voices_json}

Character: {character_name}
Description: {character_description}

Return ONLY JSON with:
{{"voice_id": "the voice id", "reasoning": "brief explanation why this voice fits"}}

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
                    
                    return {
                        "voice_id": self._normalize_voice_id(data.get("voice_id", self.narrator_voice)),
                        "reasoning": data.get("reasoning", "Default assignment")
                    }
        
        except Exception as e:
            logger.warning(f"LLM voice assignment failed: {e}")
        
        # Fallback
        return {
            "voice_id": self.narrator_voice,
            "reasoning": "Default fallback"
        }
