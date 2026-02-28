"""
Minimax API Client
Direct integration with Minimax API (not through Ollama)
"""

import os
import json
import logging
from typing import Dict, Optional
import httpx

logger = logging.getLogger(__name__)

MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
MINIMAX_BASE_URL = "https://api.minimax.chat/v1"


class MinimaxClient:
    """Client for Minimax API."""
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key or MINIMAX_API_KEY
        self.base_url = MINIMAX_BASE_URL
        
    def is_configured(self) -> bool:
        return bool(self.api_key)
    
    async def generate(
        self, 
        prompt: str, 
        model: str = "MiniMax-Text-01",
        temperature: float = 0.7,
        max_tokens: int = 4096
    ) -> Optional[str]:
        """Generate text using Minimax API."""
        if not self.is_configured():
            logger.warning("Minimax API key not configured")
            return None
            
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": max_tokens
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    f"{self.base_url}/text/chatcompletion_v2",
                    headers=headers,
                    json=payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    return result.get("choices", [{}])[0].get("message", {}).get("content", "")
                else:
                    logger.warning(f"Minimax API error: {response.status_code} - {response.text}")
                    return None
                    
        except Exception as e:
            logger.warning(f"Minimax API request failed: {e}")
            return None


# Singleton instance
minimax_client = MinimaxClient()
