"""
Document access control based on metadata.
"""

import logging
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from ..auth.database import DocumentMetadata, User, Role
from ..auth.models import Permission, DocumentSensitivity
from ..auth.rbac import RBACManager

logger = logging.getLogger(__name__)

class MetadataAccessControl:
    """Access control for documents based on metadata."""
    
    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session
        self.rbac_manager = RBACManager(db_session)
    
    def filter_documents_by_metadata(self, user_id: str, documents: List[str]) -> List[str]:
        """
        Filter documents based on user permissions and document metadata.
        
        Args:
            user_id: User ID
            documents: List of document IDs
            
        Returns:
            List[str]: Filtered list of document IDs the user can access
        """
        if not documents:
            return []
        
        # Get user
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return []
        
        # Admin users can access all documents
        if user.is_admin:
            return documents
        
        # Get user roles
        user_roles = user.roles
        
        # Get document metadata
        doc_metadata_list = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.document_id.in_(documents)
        ).all()
        
        # Filter documents based on metadata and user permissions
        accessible_docs = []
        for doc in doc_metadata_list:
            # Check if user has explicit access
            if doc.access_permissions and "users" in doc.access_permissions:
                if str(user.id) in doc.access_permissions["users"]:
                    accessible_docs.append(doc.document_id)
                    continue
            
            # Check if user's roles have access
            if doc.access_permissions and "roles" in doc.access_permissions:
                if any(str(role.id) in doc.access_permissions["roles"] for role in user_roles):
                    accessible_docs.append(doc.document_id)
                    continue
            
            # Check sensitivity level access
            has_sensitivity_access = False
            for role in user_roles:
                if role.document_access and doc.sensitivity_level in role.document_access:
                    if role.document_access[doc.sensitivity_level]:
                        has_sensitivity_access = True
                        break
            
            # Check department access
            has_department_access = False
            for role in user_roles:
                if role.department_access and doc.department in role.department_access:
                    has_department_access = True
                    break
            
            # Add document if user has both sensitivity and department access
            if has_sensitivity_access and has_department_access:
                accessible_docs.append(doc.document_id)
        
        return accessible_docs
    
    def can_access_document(self, user_id: str, document_id: str, permission: Permission) -> bool:
        """
        Check if user can access a specific document with the given permission.
        
        Args:
            user_id: User ID
            document_id: Document ID
            permission: Required permission
            
        Returns:
            bool: True if user has access, False otherwise
        """
        # First check if user has the permission
        if not self.rbac_manager.check_permission(user_id, permission):
            return False
        
        # Then check if user can access this document based on metadata
        filtered_docs = self.filter_documents_by_metadata(user_id, [document_id])
        return document_id in filtered_docs