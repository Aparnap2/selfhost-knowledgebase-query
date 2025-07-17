"""
Metadata extraction service for document processing.
Provides automatic metadata detection and manual tagging capabilities.
"""

import os
import re
import magic
import logging
import datetime
from typing import Dict, List, Optional, Any, Tuple
from pathlib import Path
import hashlib
import json

# For PDF metadata extraction
try:
    from PyPDF2 import PdfReader
except ImportError:
    PdfReader = None

# For DOCX metadata extraction
try:
    from docx import Document as DocxDocument
except ImportError:
    DocxDocument = None

# For image metadata extraction
try:
    from PIL import Image
    from PIL.ExifTags import TAGS
except ImportError:
    Image = None
    TAGS = None

from sqlalchemy.orm import Session
from ..auth.database import DocumentMetadata, User
from ..auth.models import DocumentSensitivity, Department

# Configure logging
logger = logging.getLogger(__name__)

class MetadataExtractor:
    """
    Service for extracting and managing document metadata.
    Provides both automatic metadata detection and manual tagging capabilities.
    """
    
    def __init__(self, db_session: Session = None):
        """
        Initialize the metadata extractor.
        
        Args:
            db_session: SQLAlchemy database session
        """
        self.db = db_session
        self.mime_magic = magic.Magic(mime=True)
    
    def extract_metadata(self, file_path: str, content: Optional[str] = None, 
                         user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract metadata from a document file.
        
        Args:
            file_path: Path to the document file
            content: Optional pre-extracted content
            user_id: Optional ID of the user who uploaded the document
            
        Returns:
            Dict[str, Any]: Extracted metadata
        """
        # Basic file metadata
        file_info = self._get_file_info(file_path)
        
        # Content-based metadata
        content_metadata = {}
        if content:
            content_metadata = self._analyze_content(content)
        
        # Format-specific metadata
        format_metadata = self._extract_format_metadata(file_path)
        
        # Combine all metadata
        metadata = {
            **file_info,
            **content_metadata,
            **format_metadata
        }
        
        # Add default values for required fields
        metadata["sensitivity"] = metadata.get("sensitivity", DocumentSensitivity.INTERNAL.value)
        metadata["department"] = metadata.get("department", Department.GENERAL.value)
        metadata["tags"] = metadata.get("tags", [])
        metadata["version"] = metadata.get("version", "1.0")
        
        # Add user information if available
        if user_id and self.db:
            user = self.db.query(User).filter(User.id == user_id).first()
            if user:
                metadata["created_by"] = str(user.id)
                # If user has department, use it as default
                if user.department and not metadata.get("department_detected"):
                    metadata["department"] = user.department
        
        return metadata
    
    def _get_file_info(self, file_path: str) -> Dict[str, Any]:
        """
        Get basic file information.
        
        Args:
            file_path: Path to the file
            
        Returns:
            Dict[str, Any]: Basic file metadata
        """
        path = Path(file_path)
        
        # Get file size
        try:
            file_size = path.stat().st_size
        except (FileNotFoundError, PermissionError):
            file_size = 0
        
        # Get file type using magic
        try:
            mime_type = self.mime_magic.from_file(file_path)
        except Exception as e:
            logger.warning(f"Error detecting MIME type: {e}")
            mime_type = "application/octet-stream"
        
        # Calculate file hash for integrity checking
        try:
            with open(file_path, "rb") as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()
        except Exception as e:
            logger.warning(f"Error calculating file hash: {e}")
            file_hash = None
        
        return {
            "filename": path.name,
            "file_type": mime_type,
            "file_extension": path.suffix.lower()[1:] if path.suffix else "",
            "file_size": file_size,
            "file_hash": file_hash,
            "created_at": datetime.datetime.utcnow(),
            "updated_at": datetime.datetime.utcnow()
        }
    
    def _analyze_content(self, content: str) -> Dict[str, Any]:
        """
        Analyze document content to extract metadata.
        
        Args:
            content: Document content as text
            
        Returns:
            Dict[str, Any]: Content-based metadata
        """
        metadata = {}
        
        # Extract potential keywords
        keywords = self._extract_keywords(content)
        if keywords:
            metadata["keywords"] = keywords
        
        # Detect potential sensitivity level
        sensitivity, confidence = self._detect_sensitivity(content)
        if sensitivity and confidence > 0.7:
            metadata["sensitivity"] = sensitivity
            metadata["sensitivity_confidence"] = confidence
        
        # Detect potential department
        department, dept_confidence = self._detect_department(content)
        if department and dept_confidence > 0.7:
            metadata["department"] = department
            metadata["department_confidence"] = dept_confidence
            metadata["department_detected"] = True
        
        # Extract potential document title
        title = self._extract_title(content)
        if title:
            metadata["title"] = title
        
        return metadata
    
    def _extract_format_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract format-specific metadata based on file type.
        
        Args:
            file_path: Path to the document file
            
        Returns:
            Dict[str, Any]: Format-specific metadata
        """
        # Use the extractor registry to get the appropriate extractor
        from .extractors.registry import ExtractorRegistry
        registry = ExtractorRegistry()
        return registry.extract_metadata(file_path)
    
    def _extract_pdf_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from PDF files.
        
        Args:
            file_path: Path to the PDF file
            
        Returns:
            Dict[str, Any]: PDF metadata
        """
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
    
    def _extract_docx_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from DOCX files.
        
        Args:
            file_path: Path to the DOCX file
            
        Returns:
            Dict[str, Any]: DOCX metadata
        """
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
    
    def _extract_image_metadata(self, file_path: str) -> Dict[str, Any]:
        """
        Extract metadata from image files.
        
        Args:
            file_path: Path to the image file
            
        Returns:
            Dict[str, Any]: Image metadata
        """
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
    
    def _extract_keywords(self, content: str, max_keywords: int = 10) -> List[str]:
        """
        Extract potential keywords from document content.
        
        Args:
            content: Document content as text
            max_keywords: Maximum number of keywords to extract
            
        Returns:
            List[str]: Extracted keywords
        """
        # Simple keyword extraction based on frequency
        # In a production system, this would use NLP techniques
        words = re.findall(r'\b[a-zA-Z]{4,15}\b', content.lower())
        
        # Filter out common stop words
        stop_words = {
            "about", "above", "after", "again", "against", "all", "and", "any", "are", "because",
            "been", "before", "being", "below", "between", "both", "but", "can", "did", "does",
            "doing", "down", "during", "each", "few", "for", "from", "further", "had", "has",
            "have", "having", "here", "how", "into", "just", "more", "most", "not", "now",
            "only", "other", "our", "out", "over", "same", "should", "some", "such", "than",
            "that", "the", "their", "them", "then", "there", "these", "they", "this", "those",
            "through", "under", "until", "very", "was", "were", "what", "when", "where", "which",
            "while", "who", "whom", "why", "will", "with", "you", "your"
        }
        
        filtered_words = [word for word in words if word not in stop_words]
        
        # Count word frequency
        word_counts = {}
        for word in filtered_words:
            word_counts[word] = word_counts.get(word, 0) + 1
        
        # Sort by frequency and return top keywords
        sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
        return [word for word, count in sorted_words[:max_keywords]]
    
    def _extract_title(self, content: str) -> Optional[str]:
        """
        Extract potential document title from content.
        
        Args:
            content: Document content as text
            
        Returns:
            Optional[str]: Extracted title or None
        """
        # Look for title patterns in the first few lines
        lines = content.split('\n')
        first_lines = [line.strip() for line in lines[:10] if line.strip()]
        
        # Check for common title patterns
        for line in first_lines:
            # Title case line that's not too long
            if line.istitle() and 3 <= len(line.split()) <= 12:
                return line
            
            # Line with "Title:" prefix
            title_match = re.match(r'^(?:title|subject|document):\s*(.+)$', line, re.IGNORECASE)
            if title_match:
                return title_match.group(1).strip()
        
        # If no clear title pattern, use the first non-empty line
        if first_lines:
            # Truncate if too long
            title = first_lines[0]
            return title[:100] if len(title) > 100 else title
        
        return None
    
    def _detect_sensitivity(self, content: str) -> Tuple[str, float]:
        """
        Detect document sensitivity level based on content.
        
        Args:
            content: Document content as text
            
        Returns:
            Tuple[str, float]: Detected sensitivity level and confidence score
        """
        # Define sensitivity patterns and keywords
        sensitivity_patterns = {
            DocumentSensitivity.RESTRICTED.value: [
                r'\bconfidential\b', r'\brestricted\b', r'\bsecret\b', r'\bprivate\b',
                r'\bsensitive\b', r'\bdo not share\b', r'\binternal use only\b',
                r'\bproprietary\b', r'\bnot for distribution\b', r'\bclassified\b'
            ],
            DocumentSensitivity.CONFIDENTIAL.value: [
                r'\bconfidential\b', r'\bsensitive\b', r'\binternal\b', r'\bproprietary\b',
                r'\bnot for public\b', r'\bcompany confidential\b'
            ],
            DocumentSensitivity.INTERNAL.value: [
                r'\binternal\b', r'\bfor internal use\b', r'\bstaff only\b',
                r'\bemployees only\b', r'\bcompany use\b'
            ],
            DocumentSensitivity.PUBLIC.value: [
                r'\bpublic\b', r'\bfor public release\b', r'\bpublicly available\b',
                r'\bpublic domain\b', r'\bopen access\b', r'\bunrestricted\b'
            ]
        }
        
        # Count matches for each sensitivity level
        matches = {}
        for level, patterns in sensitivity_patterns.items():
            count = 0
            for pattern in patterns:
                count += len(re.findall(pattern, content, re.IGNORECASE))
            matches[level] = count
        
        # Determine the most likely sensitivity level
        if sum(matches.values()) == 0:
            # No matches, default to INTERNAL
            return DocumentSensitivity.INTERNAL.value, 0.5
        
        # Find the level with the most matches
        max_level = max(matches.items(), key=lambda x: x[1])
        
        # Calculate confidence (simple ratio of matches)
        total_matches = sum(matches.values())
        confidence = max_level[1] / total_matches if total_matches > 0 else 0.5
        
        # Apply business rules
        # If any RESTRICTED patterns are found, increase their weight
        if matches[DocumentSensitivity.RESTRICTED.value] > 0:
            confidence = max(confidence, 0.8)
        
        return max_level[0], confidence
    
    def _detect_department(self, content: str) -> Tuple[str, float]:
        """
        Detect document department based on content.
        
        Args:
            content: Document content as text
            
        Returns:
            Tuple[str, float]: Detected department and confidence score
        """
        # Define department keywords
        department_keywords = {
            Department.HR.value: [
                "human resources", "hr", "personnel", "recruitment", "hiring",
                "employee", "staff", "benefits", "compensation", "payroll",
                "onboarding", "training", "development", "performance review"
            ],
            Department.FINANCE.value: [
                "finance", "accounting", "budget", "financial", "revenue",
                "expense", "cost", "profit", "loss", "balance sheet",
                "income statement", "cash flow", "tax", "audit", "investment"
            ],
            Department.ENGINEERING.value: [
                "engineering", "development", "software", "hardware", "system",
                "architecture", "code", "programming", "technical", "technology",
                "design", "implementation", "algorithm", "database", "infrastructure"
            ],
            Department.MARKETING.value: [
                "marketing", "brand", "campaign", "advertisement", "promotion",
                "market research", "customer", "social media", "content", "seo",
                "analytics", "lead generation", "sales funnel", "conversion"
            ],
            Department.LEGAL.value: [
                "legal", "law", "compliance", "regulation", "contract",
                "agreement", "terms", "conditions", "policy", "license",
                "intellectual property", "patent", "trademark", "copyright"
            ],
            Department.OPERATIONS.value: [
                "operations", "logistics", "supply chain", "procurement",
                "inventory", "warehouse", "shipping", "distribution", "production",
                "quality control", "facilities", "maintenance"
            ]
        }
        
        # Count matches for each department
        matches = {}
        for dept, keywords in department_keywords.items():
            count = 0
            for keyword in keywords:
                count += len(re.findall(r'\b' + re.escape(keyword) + r'\b', content, re.IGNORECASE))
            matches[dept] = count
        
        # Determine the most likely department
        if sum(matches.values()) == 0:
            # No matches, default to GENERAL
            return Department.GENERAL.value, 0.5
        
        # Find the department with the most matches
        max_dept = max(matches.items(), key=lambda x: x[1])
        
        # Calculate confidence (simple ratio of matches)
        total_matches = sum(matches.values())
        confidence = max_dept[1] / total_matches if total_matches > 0 else 0.5
        
        return max_dept[0], confidence
    
    def validate_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and sanitize metadata.
        
        Args:
            metadata: Document metadata to validate
            
        Returns:
            Dict[str, Any]: Validated and sanitized metadata
        """
        validated = {}
        
        # Validate required fields
        validated["filename"] = self._sanitize_string(metadata.get("filename", "unknown"))
        validated["file_type"] = self._sanitize_string(metadata.get("file_type", "application/octet-stream"))
        validated["file_size"] = max(0, int(metadata.get("file_size", 0)))
        
        # Validate sensitivity level
        sensitivity = metadata.get("sensitivity", DocumentSensitivity.INTERNAL.value)
        if sensitivity not in [s.value for s in DocumentSensitivity]:
            sensitivity = DocumentSensitivity.INTERNAL.value
        validated["sensitivity_level"] = sensitivity
        
        # Validate department
        department = metadata.get("department", Department.GENERAL.value)
        if department not in [d.value for d in Department]:
            department = Department.GENERAL.value
        validated["department"] = department
        
        # Validate tags
        tags = metadata.get("tags", [])
        if isinstance(tags, list):
            validated["tags"] = [self._sanitize_string(tag) for tag in tags[:20]]  # Limit to 20 tags
        else:
            validated["tags"] = []
        
        # Validate version
        version = metadata.get("version", "1.0")
        if not re.match(r'^\d+\.\d+$', str(version)):
            version = "1.0"
        validated["version"] = version
        
        # Validate author
        if "author" in metadata and metadata["author"]:
            validated["author"] = self._sanitize_string(metadata["author"])
        
        # Validate title
        if "title" in metadata and metadata["title"]:
            validated["title"] = self._sanitize_string(metadata["title"])
        
        # Validate description
        if "description" in metadata and metadata["description"]:
            validated["description"] = self._sanitize_string(metadata["description"])
        
        # Validate access permissions
        if "access_permissions" in metadata and isinstance(metadata["access_permissions"], dict):
            access_permissions = {}
            
            # Validate users list
            if "users" in metadata["access_permissions"] and isinstance(metadata["access_permissions"]["users"], list):
                access_permissions["users"] = [str(user_id) for user_id in metadata["access_permissions"]["users"]]
            else:
                access_permissions["users"] = []
            
            # Validate roles list
            if "roles" in metadata["access_permissions"] and isinstance(metadata["access_permissions"]["roles"], list):
                access_permissions["roles"] = [str(role_id) for role_id in metadata["access_permissions"]["roles"]]
            else:
                access_permissions["roles"] = []
            
            validated["access_permissions"] = access_permissions
        else:
            validated["access_permissions"] = {"users": [], "roles": []}
        
        # Process custom fields
        custom_fields = {}
        for key, value in metadata.items():
            if key not in validated and key not in ["id", "document_id", "created_at", "updated_at", "indexed_at"]:
                # Sanitize string values
                if isinstance(value, str):
                    custom_fields[key] = self._sanitize_string(value)
                # Handle lists and dicts specially
                elif isinstance(value, (list, dict)):
                    try:
                        # Convert to JSON string and back to ensure it's serializable
                        json_value = json.dumps(value)
                        custom_fields[key] = json.loads(json_value)
                    except (TypeError, json.JSONDecodeError):
                        # If not serializable, convert to string
                        custom_fields[key] = str(value)
                # Copy other values directly
                else:
                    custom_fields[key] = value
        
        # Store custom fields in description as JSON if there are any
        if custom_fields:
            # If description already exists and is JSON, merge with custom fields
            if "description" in validated and validated["description"]:
                try:
                    existing_data = json.loads(validated["description"])
                    if isinstance(existing_data, dict):
                        existing_data.update(custom_fields)
                        validated["description"] = json.dumps(existing_data)
                except (json.JSONDecodeError, TypeError):
                    # If description is not JSON, store custom fields separately
                    validated["custom_fields"] = json.dumps(custom_fields)
            else:
                # No existing description, store custom fields as JSON
                validated["description"] = json.dumps(custom_fields)
        
        return validated
    
    def _sanitize_string(self, value: str) -> str:
        """
        Sanitize string values to prevent injection attacks.
        
        Args:
            value: String to sanitize
            
        Returns:
            str: Sanitized string
        """
        if not isinstance(value, str):
            return str(value)
        
        # Remove control characters except tabs and newlines
        value = ''.join(c for c in value if ord(c) >= 32 or c in '\t\n\r')
        
        # Remove potentially dangerous HTML/script tags
        value = re.sub(r'<script[^>]*>.*?</script>', '', value, flags=re.DOTALL | re.IGNORECASE)
        value = re.sub(r'<style[^>]*>.*?</style>', '', value, flags=re.DOTALL | re.IGNORECASE)
        value = re.sub(r'<iframe[^>]*>.*?</iframe>', '', value, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove potentially dangerous attributes
        value = re.sub(r'(on\w+)\s*=\s*(["\'])[^"\'>]*\2', '', value, flags=re.IGNORECASE)
        
        # Limit length based on context
        max_length = 1000  # Default max length
        
        # Get the caller function name to determine context-specific limits
        import inspect
        caller_frame = inspect.currentframe().f_back
        caller_function = caller_frame.f_code.co_name if caller_frame else ""
        
        if caller_function == "_extract_title":
            max_length = 200  # Shorter limit for titles
        elif caller_function == "update_tags":
            max_length = 50   # Short limit for tags
        
        if len(value) > max_length:
            value = value[:max_length]
        
        return value
    
    def store_metadata(self, document_id: str, metadata: Dict[str, Any], user_id: Optional[str] = None) -> DocumentMetadata:
        """
        Store document metadata in the database.
        
        Args:
            document_id: Document ID (from ChromaDB)
            metadata: Document metadata
            user_id: Optional ID of the user who uploaded the document
            
        Returns:
            DocumentMetadata: Stored metadata object
        """
        if not self.db:
            raise ValueError("Database session is required to store metadata")
        
        # Validate metadata
        validated = self.validate_metadata(metadata)
        
        # Check if document metadata already exists
        existing = self.db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
        
        if existing:
            # Update existing metadata
            for key, value in validated.items():
                if hasattr(existing, key):
                    setattr(existing, key, value)
            
            existing.updated_at = datetime.datetime.utcnow()
            self.db.commit()
            self.db.refresh(existing)
            return existing
        else:
            # Create new metadata entry
            new_metadata = DocumentMetadata(
                document_id=document_id,
                filename=validated["filename"],
                file_type=validated["file_type"],
                file_size=validated["file_size"],
                sensitivity_level=validated["sensitivity_level"],
                department=validated["department"],
                tags=validated["tags"],
                version=validated["version"],
                created_by=user_id,
                access_permissions={"users": [], "roles": []}
            )
            
            # Add additional metadata as JSON
            additional_metadata = {k: v for k, v in validated.items() 
                                 if k not in ["filename", "file_type", "file_size", 
                                             "sensitivity_level", "department", "tags", "version"]}
            
            if additional_metadata:
                new_metadata.description = json.dumps(additional_metadata)
            
            self.db.add(new_metadata)
            self.db.commit()
            self.db.refresh(new_metadata)
            return new_metadata
    
    def update_tags(self, document_id: str, tags: List[str]) -> bool:
        """
        Update document tags.
        
        Args:
            document_id: Document ID
            tags: New tags list
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.db:
            raise ValueError("Database session is required to update tags")
        
        # Find document metadata
        doc_metadata = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.document_id == document_id
        ).first()
        
        if not doc_metadata:
            return False
        
        # Sanitize tags
        sanitized_tags = [self._sanitize_string(tag) for tag in tags[:20]]
        
        # Update tags
        doc_metadata.tags = sanitized_tags
        doc_metadata.updated_at = datetime.datetime.utcnow()
        
        self.db.commit()
        return True
    
    def update_sensitivity(self, document_id: str, sensitivity: str) -> bool:
        """
        Update document sensitivity level.
        
        Args:
            document_id: Document ID
            sensitivity: New sensitivity level
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.db:
            raise ValueError("Database session is required to update sensitivity")
        
        # Validate sensitivity level
        if sensitivity not in [s.value for s in DocumentSensitivity]:
            return False
        
        # Find document metadata
        doc_metadata = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.document_id == document_id
        ).first()
        
        if not doc_metadata:
            return False
        
        # Update sensitivity
        doc_metadata.sensitivity_level = sensitivity
        doc_metadata.updated_at = datetime.datetime.utcnow()
        
        self.db.commit()
        return True
    
    def update_department(self, document_id: str, department: str) -> bool:
        """
        Update document department.
        
        Args:
            document_id: Document ID
            department: New department
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.db:
            raise ValueError("Database session is required to update department")
        
        # Validate department
        if department not in [d.value for d in Department]:
            return False
        
        # Find document metadata
        doc_metadata = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.document_id == document_id
        ).first()
        
        if not doc_metadata:
            return False
        
        # Update department
        doc_metadata.department = department
        doc_metadata.updated_at = datetime.datetime.utcnow()
        
        self.db.commit()
        return True
        
    def apply_manual_tags(self, document_id: str, metadata_updates: Dict[str, Any]) -> bool:
        """
        Apply manual metadata tags to a document.
        
        Args:
            document_id: Document ID
            metadata_updates: Dictionary of metadata fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.db:
            raise ValueError("Database session is required to apply manual tags")
        
        # Find document metadata
        doc_metadata = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.document_id == document_id
        ).first()
        
        if not doc_metadata:
            return False
        
        # Update fields based on provided metadata
        updated = False
        
        # Update sensitivity level
        if "sensitivity_level" in metadata_updates:
            sensitivity = metadata_updates["sensitivity_level"]
            if sensitivity in [s.value for s in DocumentSensitivity]:
                doc_metadata.sensitivity_level = sensitivity
                updated = True
        
        # Update department
        if "department" in metadata_updates:
            department = metadata_updates["department"]
            if department in [d.value for d in Department]:
                doc_metadata.department = department
                updated = True
        
        # Update tags
        if "tags" in metadata_updates and isinstance(metadata_updates["tags"], list):
            sanitized_tags = [self._sanitize_string(tag) for tag in metadata_updates["tags"][:20]]
            doc_metadata.tags = sanitized_tags
            updated = True
        
        # Update version
        if "version" in metadata_updates:
            version = metadata_updates["version"]
            if re.match(r'^\d+\.\d+$', str(version)):
                doc_metadata.version = version
                updated = True
        
        # Update description
        if "description" in metadata_updates:
            doc_metadata.description = self._sanitize_string(metadata_updates["description"])
            updated = True
        
        # Update access permissions
        if "access_permissions" in metadata_updates and isinstance(metadata_updates["access_permissions"], dict):
            current_permissions = doc_metadata.access_permissions or {"users": [], "roles": []}
            
            if "users" in metadata_updates["access_permissions"]:
                current_permissions["users"] = metadata_updates["access_permissions"]["users"]
            if "roles" in metadata_updates["access_permissions"]:
                current_permissions["roles"] = metadata_updates["access_permissions"]["roles"]
            
            doc_metadata.access_permissions = current_permissions
            updated = True
        
        # Update custom fields
        if "custom_fields" in metadata_updates and isinstance(metadata_updates["custom_fields"], dict):
            # Get existing description as JSON if possible
            try:
                description_data = json.loads(doc_metadata.description) if doc_metadata.description else {}
            except (json.JSONDecodeError, TypeError):
                description_data = {}
            
            # Update with custom fields
            for key, value in metadata_updates["custom_fields"].items():
                if key not in ["id", "document_id", "created_at", "updated_at", "indexed_at"]:
                    description_data[key] = self._sanitize_string(value) if isinstance(value, str) else value
            
            # Store back as JSON
            doc_metadata.description = json.dumps(description_data)
            updated = True
        
        if updated:
            doc_metadata.updated_at = datetime.datetime.utcnow()
            self.db.commit()
            return True
        
        return False
        
    def apply_manual_tags(self, document_id: str, metadata_updates: Dict[str, Any]) -> bool:
        """
        Apply manual metadata tags to a document.
        
        Args:
            document_id: Document ID
            metadata_updates: Dictionary of metadata fields to update
            
        Returns:
            bool: True if successful, False otherwise
        """
        if not self.db:
            raise ValueError("Database session is required to apply manual tags")
        
        # Find document metadata
        doc_metadata = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.document_id == document_id
        ).first()
        
        if not doc_metadata:
            return False
        
        # Update fields based on provided metadata
        updated = False
        
        # Update sensitivity level
        if "sensitivity_level" in metadata_updates:
            sensitivity = metadata_updates["sensitivity_level"]
            if sensitivity in [s.value for s in DocumentSensitivity]:
                doc_metadata.sensitivity_level = sensitivity
                updated = True
        
        # Update department
        if "department" in metadata_updates:
            department = metadata_updates["department"]
            if department in [d.value for d in Department]:
                doc_metadata.department = department
                updated = True
        
        # Update tags
        if "tags" in metadata_updates and isinstance(metadata_updates["tags"], list):
            sanitized_tags = [self._sanitize_string(tag) for tag in metadata_updates["tags"][:20]]
            doc_metadata.tags = sanitized_tags
            updated = True
        
        # Update version
        if "version" in metadata_updates:
            version = metadata_updates["version"]
            if re.match(r'^\d+\.\d+$', str(version)):
                doc_metadata.version = version
                updated = True
        
        # Update description
        if "description" in metadata_updates:
            doc_metadata.description = self._sanitize_string(metadata_updates["description"])
            updated = True
        
        # Update access permissions
        if "access_permissions" in metadata_updates and isinstance(metadata_updates["access_permissions"], dict):
            current_permissions = doc_metadata.access_permissions or {"users": [], "roles": []}
            
            if "users" in metadata_updates["access_permissions"]:
                current_permissions["users"] = metadata_updates["access_permissions"]["users"]
            if "roles" in metadata_updates["access_permissions"]:
                current_permissions["roles"] = metadata_updates["access_permissions"]["roles"]
            
            doc_metadata.access_permissions = current_permissions
            updated = True
        
        # Update custom fields
        if "custom_fields" in metadata_updates and isinstance(metadata_updates["custom_fields"], dict):
            # Get existing description as JSON if possible
            try:
                description_data = json.loads(doc_metadata.description) if doc_metadata.description else {}
            except (json.JSONDecodeError, TypeError):
                description_data = {}
            
            # Update with custom fields
            for key, value in metadata_updates["custom_fields"].items():
                if key not in ["id", "document_id", "created_at", "updated_at", "indexed_at"]:
                    description_data[key] = self._sanitize_string(value) if isinstance(value, str) else value
            
            # Store back as JSON
            doc_metadata.description = json.dumps(description_data)
            updated = True
        
        if updated:
            doc_metadata.updated_at = datetime.datetime.utcnow()
            self.db.commit()
            return True
        
        return False