"""
Registry for document metadata extractors.
"""

import logging
from typing import Dict, List, Any, Optional, Type
from .base import BaseExtractor
from .pdf_extractor import PDFExtractor
from .docx_extractor import DOCXExtractor
from .image_extractor import ImageExtractor
from .text_extractor import TextExtractor

logger = logging.getLogger(__name__)

class ExtractorRegistry:
    """Registry for document metadata extractors."""
    
    def __init__(self):
        """Initialize the registry with available extractors."""
        self.extractors = []
        
        # Register default extractors
        self.register(PDFExtractor())
        self.register(DOCXExtractor())
        self.register(ImageExtractor())
        self.register(TextExtractor())
    
    def register(self, extractor: BaseExtractor) -> None:
        """
        Register a new extractor.
        
        Args:
            extractor: The extractor to register
        """
        self.extractors.append(extractor)
        logger.debug(f"Registered extractor: {extractor.__class__.__name__}")
    
    def get_extractor(self, file_path: str) -> Optional[BaseExtractor]:
        """
        Get the appropriate extractor for a file.
        
        Args:
            file_path: Path to the file
            
        Returns:
            BaseExtractor: The appropriate extractor, or None if no suitable extractor is found
        """
        for extractor in self.extractors:
            if extractor.can_extract(file_path):
                return extractor
        return None
    
    def extract_metadata(self, file_path: str, content: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract metadata from a file using the appropriate extractor.
        
        Args:
            file_path: Path to the file
            content: Optional pre-extracted content
            
        Returns:
            Dict[str, Any]: Extracted metadata
        """
        extractor = self.get_extractor(file_path)
        if extractor:
            logger.debug(f"Using {extractor.__class__.__name__} for {file_path}")
            return extractor.extract(file_path, content)
        else:
            logger.warning(f"No suitable extractor found for {file_path}")
            return {}