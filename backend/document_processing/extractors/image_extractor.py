"""
Image metadata extractor.
"""

import logging
from typing import Dict, Any, Optional
from pathlib import Path
from .base import BaseExtractor

# For image metadata extraction
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    Image = None
    TAGS = None

logger = logging.getLogger(__name__)

class ImageExtractor(BaseExtractor):
    """Extractor for image files."""
    
    def can_extract(self, file_path: str) -> bool:
        """Check if this extractor can handle the given file."""
        ext = Path(file_path).suffix.lower()
        return ext in [".jpg", ".jpeg", ".png", ".tiff", ".gif"] and Image is not None
    
    def extract(self, file_path: str, content: Optional[str] = None) -> Dict[str, Any]:
        """Extract metadata from image file."""
        metadata = {}
        
        try:
            with Image.open(file_path) as img:
                # Basic image properties
                metadata["width"] = img.width
                metadata["height"] = img.height
                metadata["image_format"] = img.format
                metadata["image_mode"] = img.mode
                
                # Extract EXIF data if available
                if hasattr(img, "_getexif") and img._getexif():
                    exif = {
                        TAGS.get(tag, tag): value
                        for tag, value in img._getexif().items()
                        if tag in TAGS
                    }
                    
                    # Extract relevant EXIF metadata
                    if "DateTimeOriginal" in exif:
                        metadata["original_creation_date"] = exif["DateTimeOriginal"]
                    if "Make" in exif:
                        metadata["camera_make"] = exif["Make"]
                    if "Model" in exif:
                        metadata["camera_model"] = exif["Model"]
                    if "GPSInfo" in exif:
                        metadata["has_gps_data"] = True
                    
                    # Store filtered EXIF data
                    safe_exif = {k: v for k, v in exif.items() if k in [
                        "Software", "Artist", "Copyright", "ImageDescription"
                    ]}
                    if safe_exif:
                        metadata["exif"] = safe_exif
        
        except Exception as e:
            logger.warning(f"Error extracting image metadata: {e}")
        
        return metadata