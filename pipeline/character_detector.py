"""
Character Detector - Identify characters from book text
Uses LLM via Ollama for character detection and dialogue attribution.
"""

import json
import logging
import re
from typing import Dict, List
import httpx

from config import settings

logger = logging.getLogger(__name__)


class CharacterDetector:
    """
    Detect characters from book text using LLM.
    Falls back to simple heuristics if LLM is unavailable.
    """

    def __init__(self):
        self.ollama_url = settings.ollama_url
        self.llm_model = settings.llm_model

    async def detect(self, chapters: List[str]) -> Dict:
        """
        Detect characters from chapter texts.

        Returns:
            Dictionary of character_name -> {gender, role, description}
        """
        # Combine first few chapters for character detection
        sample_text = "\n\n".join(chapters[:3])[:8000]

        # Try LLM-based detection first
        characters = await self._detect_with_llm(sample_text)
        if characters and len(characters) > 1:
            return characters

        # Fallback: heuristic-based detection
        characters = self._detect_with_heuristics(sample_text)
        return characters

    async def _detect_with_llm(self, sample_text: str) -> Dict:
        """Use Ollama LLM to detect characters."""
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

                    try:
                        data = json.loads(text)
                        characters = data.get("characters", {})

                        # Always add narrator
                        characters["Narrator"] = {
                            "gender": "unknown",
                            "role": "system",
                            "description": "Story narration"
                        }

                        logger.info(f"LLM detected {len(characters)} characters")
                        return characters
                    except json.JSONDecodeError:
                        logger.warning("Failed to parse LLM response JSON")
                        return {}

        except httpx.ConnectError:
            logger.warning(f"Cannot connect to Ollama at {self.ollama_url}")
        except Exception as e:
            logger.warning(f"LLM character detection failed: {e}")

        return {}

    def _detect_with_heuristics(self, text: str) -> Dict:
        """Fallback: detect characters using regex patterns."""
        characters = {}

        # Find quoted dialogue and nearby proper nouns
        dialogue_pattern = r'["\u201c]([^"\u201d]+)["\u201d]\s*(?:said|asked|replied|whispered|shouted|exclaimed|muttered|cried)?\s*(\w+)?'

        speakers = {}
        for match in re.finditer(dialogue_pattern, text):
            speaker = match.group(2)
            if speaker and speaker[0].isupper() and len(speaker) > 1:
                speakers[speaker] = speakers.get(speaker, 0) + 1

        # Add detected speakers as characters
        for name, count in sorted(speakers.items(), key=lambda x: -x[1]):
            if count >= 2:
                characters[name] = {
                    "gender": "unknown",
                    "role": "main" if count >= 5 else "supporting",
                    "description": f"Character mentioned {count} times"
                }

        # Always add narrator
        characters["Narrator"] = {
            "gender": "unknown",
            "role": "system",
            "description": "Story narration"
        }

        logger.info(f"Heuristic detected {len(characters)} characters")
        return characters

    async def detect_dialogue(self, chapter_text: str) -> List[Dict]:
        """Detect dialogue segments in a chapter."""
        segments = []
        dialogue_pattern = r'["\u201c]([^"\u201d]+)["\u201d]'

        last_end = 0
        for match in re.finditer(dialogue_pattern, chapter_text):
            if match.start() > last_end:
                narration = chapter_text[last_end:match.start()].strip()
                if narration:
                    segments.append({
                        "speaker": "Narrator",
                        "text": narration,
                        "type": "narration"
                    })
            segments.append({
                "speaker": "Unknown",
                "text": match.group(1),
                "type": "dialogue"
            })
            last_end = match.end()

        if last_end < len(chapter_text):
            remaining = chapter_text[last_end:].strip()
            if remaining:
                segments.append({
                    "speaker": "Narrator",
                    "text": remaining,
                    "type": "narration"
                })

        return segments if segments else [{"speaker": "Narrator", "text": chapter_text, "type": "narration"}]
