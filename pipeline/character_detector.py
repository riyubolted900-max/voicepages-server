"""
Character Detector - Identify characters from book text
Uses LLM via Ollama for character detection and dialogue attribution.
"""

import json
import logging
import re
from collections import Counter
from typing import Dict, List
import httpx

from config import settings

logger = logging.getLogger(__name__)

# Words that look like proper nouns but are not character names
NOT_NAMES = frozenset({
    'The', 'She', 'He', 'His', 'Her', 'They', 'But', 'And', 'Then', 'After',
    'Before', 'When', 'With', 'Even', 'Every', 'Just', 'Not', 'That', 'This',
    'What', 'Where', 'How', 'Why', 'There', 'Now', 'Here', 'Its', 'One',
    'Two', 'Three', 'Each', 'All', 'Some', 'Any', 'More', 'Most', 'Other',
    'Chapter', 'Part', 'Book', 'Prologue', 'Epilogue', 'Section',
    'Still', 'Though', 'Because', 'While', 'Until', 'Once', 'Only',
    'Perhaps', 'Maybe', 'Never', 'Always', 'Also', 'Already', 'Again',
    'However', 'Instead', 'Besides', 'Meanwhile', 'Otherwise', 'Furthermore',
    'Suddenly', 'Finally', 'Eventually', 'Apparently', 'Clearly',
    'Originally', 'Curiosity', 'Silence', 'Nothing', 'Something',
    'Everything', 'Someone', 'Anyone', 'Everyone', 'Nobody', 'Somebody',
    'Darkness', 'Light', 'Morning', 'Night', 'Evening', 'Tomorrow',
})

# Speech/dialogue verbs for attribution detection
SPEECH_VERBS = (
    r'(?:said|asked|replied|whispered|shouted|exclaimed|muttered|cried|called|'
    r'snapped|murmured|yelled|answered|sighed|breathed|hissed|growled|declared|'
    r'demanded|insisted|suggested|continued|added|agreed|warned|pleaded|begged|'
    r'barked|ordered|screamed|announced|laughed|smiled|grinned|chuckled|groaned|'
    r'stammered|stuttered|sobbed|wailed|roared|sneered|scoffed|retorted|'
    r'interrupted|protested|conceded|acknowledged|remarked|observed|noted|'
    r'commented|explained|offered|urged|prompted|wondered|mused|pondered|'
    r'repeated|finished|began|started|managed|attempted|tried|stated|spoke)'
)


class CharacterDetector:
    """
    Detect characters from book text using LLM.
    Falls back to improved heuristics if LLM is unavailable.
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
        # Use more chapters for better detection (up to 15)
        num_sample = min(len(chapters), 15)
        sample_text = "\n\n".join(chapters[:num_sample])[:50000]

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
            async with httpx.AsyncClient(timeout=15.0) as client:
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
                        characters["narrator"] = {
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

    def _is_valid_name(self, name: str) -> bool:
        """Check if a word is likely a character name."""
        if not name or len(name) < 2:
            return False
        if name in NOT_NAMES:
            return False
        if not name[0].isupper():
            return False
        # Must be alphabetic
        if not name.isalpha():
            return False
        # Reject all-caps words (like THE, BUT)
        if name.isupper() and len(name) > 1:
            return False
        return True

    def _detect_with_heuristics(self, text: str) -> Dict:
        """Fallback: detect characters using improved regex patterns."""
        speakers = Counter()

        # Pattern 1: closing-quote followed by Name + speech verb
        # Matches: \u201cdialogue,\u201d Name said / \u201cdialogue.\u201d Name whispered
        pattern1 = re.compile(
            r'[\u201d"\u2019\']\s*' + r'([A-Z][a-z]{2,})\s+' + SPEECH_VERBS,
            re.MULTILINE
        )
        for m in pattern1.finditer(text):
            name = m.group(1)
            if self._is_valid_name(name):
                speakers[name] += 1

        # Pattern 2: Name + speech verb + opening-quote
        # Matches: Name said, \u201cdialogue\u201d / Name whispered, \u201cdialogue\u201d
        pattern2 = re.compile(
            r'([A-Z][a-z]{2,})\s+' + SPEECH_VERBS + r'\s*[,.]?\s*[\u201c"\u2018\']',
            re.MULTILINE
        )
        for m in pattern2.finditer(text):
            name = m.group(1)
            if self._is_valid_name(name):
                speakers[name] += 1

        # Pattern 3: closing-quote + comma/period + Name (no verb needed)
        # Matches: \u201cdialogue,\u201d Name turned. / \u201cI know.\u201d Name looked.
        pattern3 = re.compile(
            r'[\u201d"]\s*([A-Z][a-z]{2,})\s+(?:\w+ed|\w+ing|looked|turned|stood|sat|rose|fell|shook|nodded|smiled|frowned|paused)',
            re.MULTILINE
        )
        for m in pattern3.finditer(text):
            name = m.group(1)
            if self._is_valid_name(name):
                speakers[name] += 1

        # Pattern 4: Name's + dialogue context
        # Matches: Name's voice / Name's eyes / Name's hand
        pattern4 = re.compile(r"([A-Z][a-z]{2,})'s\s+(?:voice|eyes|hand|face|head|lips|words|tone|gaze|expression|mouth)")
        for m in pattern4.finditer(text):
            name = m.group(1)
            if self._is_valid_name(name):
                speakers[name] += 1

        # Infer gender using only high-confidence patterns
        # Avoid object pronouns like "gave her" which refer to other characters
        gender_hints = {}
        for name in speakers:
            esc = re.escape(name)

            # Pattern 1: "Name + possessive pronoun + body/attribute noun"
            # e.g., "Aldrik ran his hand" / "Vhalla shook her head"
            body_nouns = r'(?:hand|hands|head|hair|eyes|face|lips|arms|arm|chest|brow|jaw|chin|shoulders|fingers|throat|back|knee|nose)'
            for m in re.finditer(esc + r'[^.]{0,20}\bhis\s+' + body_nouns, text):
                gender_hints.setdefault(name, Counter())['male'] += 2
            for m in re.finditer(esc + r'[^.]{0,20}\bher\s+' + body_nouns, text):
                gender_hints.setdefault(name, Counter())['female'] += 2

            # Pattern 2: "Name, he/she" — appositive constructions
            for m in re.finditer(esc + r',?\s+he\s+' + SPEECH_VERBS, text):
                gender_hints.setdefault(name, Counter())['male'] += 3
            for m in re.finditer(esc + r',?\s+she\s+' + SPEECH_VERBS, text):
                gender_hints.setdefault(name, Counter())['female'] += 3

            # Pattern 3: "he/she" as subject right after Name's action sentence
            # "Name verbed. He/She..."
            for m in re.finditer(esc + r'\s+\w+(?:ed|s)\b[^.!?]{0,25}[.!?]\s+He\b', text):
                gender_hints.setdefault(name, Counter())['male'] += 1
            for m in re.finditer(esc + r'\s+\w+(?:ed|s)\b[^.!?]{0,25}[.!?]\s+She\b', text):
                gender_hints.setdefault(name, Counter())['female'] += 1

        # Build characters dict
        characters = {}
        for name, count in speakers.most_common(15):
            if count >= 1:
                # Determine gender
                gender = "unknown"
                if name in gender_hints:
                    gc = gender_hints[name]
                    if gc.get('female', 0) > gc.get('male', 0):
                        gender = "female"
                    elif gc.get('male', 0) > gc.get('female', 0):
                        gender = "male"

                # Determine role based on frequency
                if count >= 10:
                    role = "main"
                elif count >= 3:
                    role = "supporting"
                else:
                    role = "minor"

                characters[name] = {
                    "gender": gender,
                    "role": role,
                    "description": f"Detected from dialogue ({count} attributions)"
                }

        # Always add narrator
        characters["narrator"] = {
            "gender": "unknown",
            "role": "system",
            "description": "Story narration"
        }

        logger.info(f"Heuristic detected {len(characters)} characters")
        return characters

    async def detect_dialogue(self, chapter_text: str) -> List[Dict]:
        """Detect dialogue segments in a chapter."""
        segments = []
        dialogue_pattern = r'[\u201c"]([^\u201d"]+)[\u201d"]'

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
