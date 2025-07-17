"""
Text file metadata extractor.
"""

import logging
import os
from typing import Dict, Any, Optional
from pathlib import Path
import re
from .base import BaseExtractor

logger = logging.getLogger(__name__)

class TextExtractor(BaseExtractor):
    """Extractor for text-based files."""
    
    def can_extract(self, file_path: str) -> bool:
        """Check if this extractor can handle the given file."""
        ext = Path(file_path).suffix.lower()
        return ext in [".txt", ".md", ".py", ".js", ".html", ".css", ".json", ".xml", ".csv"]
    
    def extract(self, file_path: str, content: Optional[str] = None) -> Dict[str, Any]:
        """Extract metadata from text file."""
        metadata = {}
        
        try:
            # If content is not provided, read it
            if content is None:
                with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            
            # Get line count
            line_count = content.count('\n') + 1
            metadata["line_count"] = line_count
            
            # Get file stats
            stats = os.stat(file_path)
            metadata["created_timestamp"] = stats.st_ctime
            metadata["modified_timestamp"] = stats.st_mtime
            
            # Extract potential title from first line
            lines = content.split('\n', 5)
            if lines and lines[0].strip():
                title = lines[0].strip()
                # Remove markdown heading markers
                title = re.sub(r'^#+\s+', '', title)
                # Remove HTML tags
                title = re.sub(r'<[^>]+>', '', title)
                # Limit length
                if len(title) > 100:
                    title = title[:97] + "..."
                metadata["title"] = title
            
            # Detect language/file type
            ext = Path(file_path).suffix.lower()
            if ext == ".py":
                metadata["language"] = "Python"
            elif ext == ".js":
                metadata["language"] = "JavaScript"
            elif ext == ".html":
                metadata["language"] = "HTML"
            elif ext == ".css":
                metadata["language"] = "CSS"
            elif ext == ".json":
                metadata["language"] = "JSON"
            elif ext == ".xml":
                metadata["language"] = "XML"
            elif ext == ".md":
                metadata["language"] = "Markdown"
            elif ext == ".csv":
                metadata["language"] = "CSV"
            else:
                metadata["language"] = "Plain Text"
            
        except Exception as e:
            logger.warning(f"Error extracting text file metadata: {e}")
        
        return metadata