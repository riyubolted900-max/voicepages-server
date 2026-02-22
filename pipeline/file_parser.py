"""
File Parser - Extract text from various ebook formats
Supports: EPUB, PDF, TXT, DOC, DOCX
"""

import io
from pathlib import Path
from typing import List
import logging

logger = logging.getLogger(__name__)


class FileParser:
    """
    Parser for extracting text content from ebook files.
    Returns a list of chapter texts.
    """
    
    def __init__(self):
        self.supported_formats = ['epub', 'pdf', 'txt', 'doc', 'docx']
    
    async def parse_file(self, file_path: str, file_type: str) -> List[str]:
        """
        Parse a file and return list of chapter texts.
        
        Args:
            file_path: Path to the file
            file_type: Extension (epub, pdf, txt, doc, docx)
        
        Returns:
            List of chapter text strings
        """
        file_type = file_type.lower()
        
        if file_type == 'epub':
            return await self._parse_epub(file_path)
        elif file_type == 'pdf':
            return await self._parse_pdf(file_path)
        elif file_type == 'txt':
            return await self._parse_txt(file_path)
        elif file_type in ['doc', 'docx']:
            return await self._parse_docx(file_path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")
    
    async def _parse_epub(self, file_path: str) -> List[str]:
        """Parse EPUB file and extract chapters."""
        try:
            import ebooklib
            from ebooklib import epub
        except ImportError:
            logger.warning("ebooklib not installed, using fallback")
            return await self._parse_txt(file_path)
        
        import warnings
        warnings.filterwarnings("ignore")

        book = epub.read_epub(file_path)
        chapters = []

        for item in book.get_items():
            if item.get_type() == ebooklib.ITEM_DOCUMENT:
                # Get text content
                try:
                    content = item.get_content().decode('utf-8', errors='ignore')
                except Exception:
                    continue

                # Extract text from HTML
                text = self._extract_text_from_html(content)

                # Skip very short items (front matter, title pages, etc.)
                # A real chapter typically has at least 500 chars
                if text.strip() and len(text.strip()) >= 500:
                    chapters.append(text)
        
        # If no chapters found, treat entire content as one chapter
        if not chapters:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                chapters = self._split_into_chunks(content)
        
        return chapters if chapters else ["Empty book"]
    
    async def _parse_pdf(self, file_path: str) -> List[str]:
        """Parse PDF file and extract text by pages as chapters."""
        try:
            from PyPDF2 import PdfReader
        except ImportError:
            raise ImportError("PyPDF2 required for PDF parsing: pip install PyPDF2")
        
        reader = PdfReader(file_path)
        chapters = []
        
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text.strip():
                chapters.append(text)
        
        # Group pages into chapters (every 5 pages = 1 chapter)
        grouped = []
        chunk_size = 5
        for i in range(0, len(chapters), chunk_size):
            chapter_text = "\n\n".join(chapters[i:i+chunk_size])
            if chapter_text.strip():
                grouped.append(chapter_text)
        
        return grouped if grouped else ["Empty PDF"]
    
    async def _parse_txt(self, file_path: str) -> List[str]:
        """Parse plain text file."""
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        
        return self._split_into_chunks(content)
    
    async def _parse_docx(self, file_path: str) -> List[str]:
        """Parse DOCX file."""
        try:
            from docx import Document
        except ImportError:
            raise ImportError("python-docx required for DOCX parsing: pip install python-docx")
        
        doc = Document(file_path)
        paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
        
        content = "\n\n".join(paragraphs)
        return self._split_into_chunks(content)
    
    def _extract_text_from_html(self, html_content: str) -> str:
        """Extract readable text from HTML."""
        try:
            from bs4 import BeautifulSoup
        except ImportError:
            # Fallback: strip HTML tags
            import re
            text = re.sub(r'<[^>]+>', ' ', html_content)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()
        
        soup = BeautifulSoup(html_content, 'lxml')
        
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.decompose()
        
        text = soup.get_text()
        
        # Clean up whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = ' '.join(chunk for chunk in chunks if chunk)
        
        return text
    
    def _split_into_chunks(self, content: str, chunk_size: int = 5000) -> List[str]:
        """
        Split long text into manageable chunks.
        Attempts to split at chapter boundaries if possible.
        """
        # First try to detect chapters (common patterns)
        import re
        
        # Common chapter indicators
        chapter_patterns = [
            r'\nchapter\s+\d+',
            r'\nChapter\s+\d+',
            r'\nCHAPTER\s+\d+',
            r'\n\s*\d+\.',
            r'\n\s*I+\.',
            r'\n\s*Part\s+\d+',
        ]
        
        chapter_starts = []
        for pattern in chapter_patterns:
            chapter_starts.extend(re.finditer(pattern, content, re.IGNORECASE))
        
        if chapter_starts:
            # Sort by position and split
            chapter_starts.sort(key=lambda x: x.start())
            
            chunks = []
            for i, match in enumerate(chapter_starts):
                start = match.start()
                end = chapter_starts[i+1].start() if i + 1 < len(chapter_starts) else len(content)
                chunk = content[start:end].strip()
                if chunk:
                    chunks.append(chunk)
            
            if chunks:
                return chunks
        
        # Fallback: chunk by size
        chunks = []
        while len(content) > chunk_size:
            # Find a good break point (end of sentence)
            break_point = content.rfind('. ', 0, chunk_size)
            if break_point == -1:
                break_point = content.rfind(' ', 0, chunk_size)
            
            if break_point == -1:
                break_point = chunk_size
            
            chunks.append(content[:break_point + 1].strip())
            content = content[break_point + 1:]
        
        if content.strip():
            chunks.append(content.strip())
        
        return chunks if chunks else [content] if content.strip() else ["Empty content"]
