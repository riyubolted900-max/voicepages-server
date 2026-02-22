"""
Data Models for VoicePages
"""

from dataclasses import dataclass
from typing import List, Optional
from datetime import datetime


@dataclass
class Book:
    """Book model."""
    id: str
    title: str
    author: str
    file_path: str
    file_type: str
    created_at: Optional[datetime] = None
    
    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "author": self.author,
            "file_type": self.file_type,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class Chapter:
    """Chapter model."""
    id: int
    book_id: str
    chapter_number: int
    title: str
    text_content: str
    
    def to_dict(self):
        return {
            "id": self.id,
            "book_id": self.book_id,
            "chapter_number": self.chapter_number,
            "title": self.title,
            # Don't include full text in listings
            "text_length": len(self.text_content)
        }


@dataclass
class Character:
    """Character model with voice assignment."""
    id: str
    book_id: str
    name: str
    gender: str  # male, female, unknown
    voice_id: str
    is_narrator: bool = False
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "voice_id": self.voice_id,
            "is_narrator": self.is_narrator
        }


@dataclass
class VoiceProfile:
    """Voice profile from TTS engine."""
    id: str
    name: str
    gender: str
    accent: str  # american, british
    style: str
    
    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "gender": self.gender,
            "accent": self.accent,
            "style": self.style
        }


@dataclass
class Bookmark:
    """Reading position bookmark."""
    id: Optional[int]
    book_id: str
    chapter_id: int
    position: float  # seconds or percentage
    updated_at: Optional[datetime] = None
    
    def to_dict(self):
        return {
            "book_id": self.book_id,
            "chapter_id": self.chapter_id,
            "position": self.position,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }
