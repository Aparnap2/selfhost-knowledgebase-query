"""
Middleware for automatic permission checking on API endpoints.
Provides decorators and dependencies for securing FastAPI routes.
"""

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from typing import Callable, List, Optional, Union, Dict, Any
from .rbac import RBACManager, get_current_user
from .models import Permission, DocumentSensitivity
from .database import User
import logging
from functools import wraps

# Configure logger
logger = logging.getLogger(__name__)

# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class PermissionChecker:
    """Permission checking middleware for FastAPI."""
    
    def __init__(self, db_dependency: Callable):
        """
        Initialize permission checker with database dependency.
        
        Args:
            db_dependency: Callable that returns a database session
        """
        self.get_db = db_dependency
    
    def require_permissions(self, permissions: List[Union[Permission, str]]):
        """
        Dependency for requiring multiple permissions (ANY match).
        
        Args:
            permissions: List of required permissions (any one is sufficient)
            
        Returns:
            Callable: Dependency function
        """
        async def permission_dependency(
            request: Request,
            current_user: User = Depends(get_current_user),
            db: Session = Depends(self.get_db)
        ) -> User:
            rbac = RBACManager(db)
            
            # Admin users bypass permission checks
            if current_user.is_admin:
                return current_user
            
            # Check if user has any of the required permissions
            user_permissions = rbac.get_user_permissions(str(current_user.id))
            
            for permission in permissions:
                perm_value = permission.value if isinstance(permission, Permission) else permission
                if perm_value in user_permissions:
                    return current_user
            
            # No matching permission found
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions. Required: {[p.value if isinstance(p, Permission) else p for p in permissions]}"
            )
        
        return permission_dependency
    
    def require_all_permissions(self, permissions: List[Union[Permission, str]]):
        """
        Dependency for requiring all specified permissions (ALL must match).
        
        Args:
            permissions: List of required permissions (all are required)
            
        Returns:
            Callable: Dependency function
        """
        async def all_permissions_dependency(
            request: Request,
            current_user: User = Depends(get_current_user),
            db: Session = Depends(self.get_db)
        ) -> User:
            rbac = RBACManager(db)
            
            # Admin users bypass permission checks
            if current_user.is_admin:
                return current_user
            
            # Check if user has all required permissions
            user_permissions = rbac.get_user_permissions(str(current_user.id))
            
            for permission in permissions:
                perm_value = permission.value if isinstance(permission, Permission) else permission
                if perm_value not in user_permissions:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Missing required permission: {perm_value}"
                    )
            
            return current_user
        
        return all_permissions_dependency
    
    def require_document_access(
        self, 
        min_sensitivity: Optional[DocumentSensitivity] = None,
        permission: Union[Permission, str] = Permission.DOCUMENT_READ
    ):
        """
        Dependency for requiring document access with minimum sensitivity level.
        
        Args:
            min_sensitivity: Minimum sensitivity level required
            permission: Document permission required
            
        Returns:
            Callable: Dependency function
        """
        async def document_access_dependency(
            request: Request,
            document_id: str,
            current_user: User = Depends(get_current_user),
            db: Session = Depends(self.get_db)
        ) -> User:
            # Admin users bypass permission checks
            if current_user.is_admin:
                return current_user
                
            # Check basic permission
            rbac = RBACManager(db)
            if not rbac.check_permission(str(current_user.id), permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Insufficient permissions: {permission}"
                )
            
            # Check metadata-based access
            from ..document_processing.access_control import MetadataAccessControl
            metadata_access = MetadataAccessControl(db)
            if not metadata_access.can_access_document(str(current_user.id), document_id, permission):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Access denied to document: {document_id}"
                )
            
            # If minimum sensitivity is specified, check it
            if min_sensitivity:
                from .database import DocumentMetadata
                doc = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
                if not doc:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Document not found: {document_id}"
                    )
                
                # Check if document sensitivity meets minimum requirement
                doc_sensitivity = DocumentSensitivity(doc.sensitivity_level)
                sensitivity_levels = list(DocumentSensitivity)
                if sensitivity_levels.index(doc_sensitivity) < sensitivity_levels.index(min_sensitivity):
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail=f"Document sensitivity level too low. Required: {min_sensitivity.value}"
                    )
            
            return current_user
        
        return document_access_dependency
    
    def filter_documents_for_user(self, permission: Union[Permission, str] = Permission.DOCUMENT_READ):
        """
        Dependency for filtering documents based on user permissions and metadata.
        
        Args:
            permission: Document permission required
            
        Returns:
            Callable: Dependency function that returns list of accessible document IDs
        """
        async def document_filter_dependency(
            current_user: User = Depends(get_current_user),
            db: Session = Depends(self.get_db)
        ) -> List[str]:
            # First get documents user has permission to access
            rbac = RBACManager(db)
            permission_docs = rbac.filter_documents_by_permission(str(current_user.id), permission)
            
            # Then filter by metadata access control
            from ..document_processing.access_control import MetadataAccessControl
            metadata_access = MetadataAccessControl(db)
            return metadata_access.filter_documents_by_metadata(str(current_user.id), permission_docs)
        
        return document_filter_dependency

# Audit logging middleware
async def audit_log_middleware(request: Request, call_next):
    """
    Middleware for audit logging of API requests.
    
    Args:
        request: FastAPI request
        call_next: Next middleware in chain
        
    Returns:
        Response: FastAPI response
    """
    # Extract user information if available
    user_id = None
    try:
        token = await oauth2_scheme(request)
        from .rbac import jwt, SECRET_KEY, ALGORITHM
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("sub")
    except Exception:
        # No valid token or user, continue as anonymous
        pass
    
    # Log request
    logger.info(
        f"AUDIT: {request.method} {request.url.path} - User: {user_id or 'anonymous'} - "
        f"Client: {request.client.host if request.client else 'unknown'}"
    )
    
    # Process request
    response = await call_next(request)
    
    # Log response status
    logger.info(
        f"AUDIT: {request.method} {request.url.path} - Status: {response.status_code} - "
        f"User: {user_id or 'anonymous'}"
    )
    
    return response

# Function to create permission middleware for FastAPI
def create_permission_middleware(db_dependency: Callable) -> PermissionChecker:
    """
    Create permission middleware with database dependency.
    
    Args:
        db_dependency: Callable that returns a database session
        
    Returns:
        PermissionChecker: Permission checking middleware
    """
    return PermissionChecker(db_dependency)