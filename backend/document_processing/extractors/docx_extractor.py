"""
DOCX metadata extractor.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from .base import BaseExtractor

# For DOCX metadata extraction
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

logger = logging.getLogger(__name__)

class DOCXExtractor(BaseExtractor):
    """Extractor for DOCX documents."""
    
    def can_extract(self, file_path: str) -> bool:
        """Check if this extractor can handle the given file."""
        return Path(file_path).suffix.lower() == ".docx" and DocxDocument is not None
    
    def extract(self, file_path: str, content: Optional[str] = None) -> Dict[str, Any]:
        """Extract metadata from DOCX file."""
        metadata = {}
        
        try:
            doc = DocxDocument(file_path)
            core_props = doc.core_properties
            
            # Extract standard DOCX metadata
            if core_props.title:
                metadata["title"] = core_props.title
            if core_props.author:
                metadata["author"] = core_props.author
            if core_props.subject:
                metadata["subject"] = core_props.subject
            if core_props.keywords:
                metadata["docx_keywords"] = [k.strip() for k in core_props.keywords.split(",")]
            if core_props.created:
                metadata["original_creation_date"] = str(core_props.created)
            if core_props.modified:
                metadata["original_modification_date"] = str(core_props.modified)
            if core_props.last_modified_by:
                metadata["last_modified_by"] = core_props.last_modified_by
            if core_props.revision:
                metadata["revision"] = core_props.revision
                metadata["version"] = f"1.{core_props.revision}"
            
            # Get page count (approximate)
            metadata["page_count"] = len(doc.paragraphs) // 40 + 1  # Rough estimate
            
        except Exception as e:
            logger.warning(f"Error extracting DOCX metadata: {e}")
        
        return metadata