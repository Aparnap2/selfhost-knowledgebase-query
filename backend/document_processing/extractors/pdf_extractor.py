"""
PDF metadata extractor.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from .base import BaseExtractor

# For PDF metadata extraction
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

logger = logging.getLogger(__name__)

class PDFExtractor(BaseExtractor):
    """Extractor for PDF documents."""
    
    def can_extract(self, file_path: str) -> bool:
        """Check if this extractor can handle the given file."""
        return Path(file_path).suffix.lower() == ".pdf" and PdfReader is not None
    
    def extract(self, file_path: str, content: Optional[str] = None) -> Dict[str, Any]:
        """Extract metadata from PDF file."""
        metadata = {}
        
        try:
            with open(file_path, "rb") as f:
                pdf = PdfReader(f)
                info = pdf.metadata
                
                if info:
                    # Extract standard PDF metadata
                    if info.title:
                        metadata["title"] = info.title
                    if info.author:
                        metadata["author"] = info.author
                    if info.subject:
                        metadata["subject"] = info.subject
                    if info.creator:
                        metadata["creator"] = info.creator
                    if info.producer:
                        metadata["producer"] = info.producer
                    
                    # Extract creation and modification dates
                    if hasattr(info, "creation_date") and info.creation_date:
                        metadata["original_creation_date"] = str(info.creation_date)
                    if hasattr(info, "modification_date") and info.modification_date:
                        metadata["original_modification_date"] = str(info.modification_date)
                    
                    # Extract keywords if available
                    if hasattr(info, "keywords") and info.keywords:
                        keywords = info.keywords
                        if isinstance(keywords, str):
                            metadata["pdf_keywords"] = [k.strip() for k in keywords.split(",")]
                        else:
                            metadata["pdf_keywords"] = keywords
                
                # Get page count
                metadata["page_count"] = len(pdf.pages)
                
        except Exception as e:
            logger.warning(f"Error extracting PDF metadata: {e}")
        
        return metadata