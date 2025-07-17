"""
Audit logging for document metadata access.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from ..auth.database import DocumentMetadata, User

# Configure logger
logger = logging.getLogger(__name__)

class MetadataAuditLogger:
    """Audit logger for document metadata access."""
    
    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session
    
    def log_metadata_access(self, user_id: str, document_id: str, action: str) -> None:
        """
        Log document metadata access.
        
        Args:
            user_id: User ID
            document_id: Document ID
            action: Action performed (read, write, delete)
        """
        # Get user and document info for context
        user = self.db.query(User).filter(User.id == user_id).first()
        document = self.db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
        
        username = user.username if user else "unknown"
        filename = document.filename if document else "unknown"
        sensitivity = document.sensitivity_level if document else "unknown"
        
        # Log the access
        logger.info(
            f"METADATA ACCESS: {action} - User: {username} ({user_id}) - "
            f"Document: {filename} ({document_id}) - Sensitivity: {sensitivity}"
        )
    
    def log_metadata_update(self, user_id: str, document_id: str, 
                           fields_updated: Dict[str, Any]) -> None:
        """
        Log document metadata update.
        
        Args:
            user_id: User ID
            document_id: Document ID
            fields_updated: Dictionary of updated fields
        """
        # Get user and document info for context
        user = self.db.query(User).filter(User.id == user_id).first()
        document = self.db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
        
        username = user.username if user else "unknown"
        filename = document.filename if document else "unknown"
        
        # Log the update
        logger.info(
            f"METADATA UPDATE: User: {username} ({user_id}) - "
            f"Document: {filename} ({document_id}) - "
            f"Fields: {', '.join(fields_updated.keys())}"
        )