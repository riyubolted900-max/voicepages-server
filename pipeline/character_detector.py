"""
Character Detector - Identify characters from book text
Simplified LLM-based approach (no BookNLP dependency)
"""

import json
import logging
from typing import Dict, List
import httpx

from config import settings

logger = logging.getLogger(__name__)


class CharacterDetector:
    """
    Detect characters from book text using LLM.
    
    This is a simplified version. For production, consider:
    - BookNLP for accurate character detection
    - Named Entity Recognition (NER)
    - Coreference resolution
    """
    
    def __init__(self):
        self.ollama_url = settings.ollama_url
        self.llm_model = settings.llm_model
    
    async def detect(self, chapters: List[str]) -> Dict:
        """
        Detect characters from chapter texts.
        
        Args:
            chapters: List of chapter text strings
        
        Returns:
            Dictionary of character_name -> {gender, description}
        """
        # Combine first few chapters for character detection
        # (full book would be too long)
        sample_text = "\n\n".join(chapters[:3])[:8000]
        
        # Use LLM to detect characters
        prompt = f"""Analyze the following text from a book and identify all characters (people) who speak or are mentioned.
        
For each character, determine:
- Name (how they're referred to in the book)
- Gender (male/female/unknown)
- Role (main character, supporting, minor)

Return ONLY a JSON object with this structure (no other text):
{{
  "characters": {{
    "Character Name": {{
      "gender": "male/female/unknown",
      "role": "main/supporting/minor",
      "description": "brief description"
    }}
  }}
}}

Text to analyze:
{sample_text}

JSON:"""

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
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
                    
                    # Parse JSON
                    try:
                        data = json.loads(text)
                        characters = data.get("characters", {})
                        
                        # Add narrator
                        characters["Narrator"] = {
                            "gender": "unknown",
                            "role": "system",
                            "description": "Story narration"
                        }
                        
                        logger.info(f"Detected {len(characters)} characters")
                        return characters
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse LLM response, using fallback")
                        
        except Exception as e:
            logger.warning(f"LLM character detection failed: {e}")
        
        # Fallback: return simple narrator-only
        return {
            "Narrator": {
                "gender": "unknown",
                "role": "system",
                "description": "Story narration"
            }
        }
    
    async def detect_dialogue(self, chapter_text: str) -> List[Dict]:
        """
        Detect dialogue segments in a chapter.
        
        Returns list of:
        {speaker: str, text: str, type: "dialogue"/"narration"}
        """
        # Simple heuristic: detect quoted speech
        import re
        
        segments = []
        
        # Pattern for dialogue in quotes
        dialogue_pattern = r'[""]([^""]+)[""]'
        
        last_end = 0
        for match in re.finditer(dialogue_pattern, chapter_text):
            # Add narration before this dialogue
            if match.start() > last_end:
                narration = chapter_text[last_end:match.start()].strip()
                if narration:
                    segments.append({
                        "speaker": "Narrator",
                        "text": narration,
                        "type": "narration"
                    })
            
            # Add dialogue
            segments.append({
                "speaker": "Unknown",  # Would need NER to identify speaker
                "text": match.group(1),
                "type": "dialogue"
            })
            
            last_end = match.end()
        
        # Add remaining narration
        if last_end < len(chapter_text):
            remaining = chapter_text[last_end:].strip()
            if remaining:
                segments.append({
                    "speaker": "Narrator",
                    "text": remaining,
                    "type": "narration"
                })
        
        return segments if segments else [{"speaker": "Narrator", "text": chapter_text, "type": "narration"}]
