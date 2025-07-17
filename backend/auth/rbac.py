"""
Role-Based Access Control (RBAC) system for the Self-Hosted AI Knowledge Base Assistant.
Provides permission checking and enforcement for secure access control.
"""

from typing import List, Dict, Any, Optional, Set, Union
from sqlalchemy.orm import Session
from .models import Permission, DocumentSensitivity, Department
from .database import User, Role, DocumentMetadata
import uuid
from fastapi import HTTPException, status, Depends
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import os
from datetime import datetime, timedelta
import logging

# Configure logger
logger = logging.getLogger(__name__)

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "notebooklm-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

class RBACManager:
    """Manager for Role-Based Access Control operations."""
    
    def __init__(self, db_session: Session):
        """Initialize RBAC manager with database session."""
        self.db = db_session
    
    def check_permission(self, user_id: str, permission: Union[Permission, str], 
                         resource_id: Optional[str] = None) -> bool:
        """
        Check if user has specific permission, optionally for a specific resource.
        
        Args:
            user_id: User ID to check permissions for
            permission: Permission to check (can be Permission enum or string)
            resource_id: Optional resource ID (e.g., document ID) to check against
            
        Returns:
            bool: True if user has permission, False otherwise
        """
        # Convert string permission to enum if needed
        if isinstance(permission, str):
            try:
                permission = Permission(permission)
            except ValueError:
                logger.warning(f"Invalid permission string: {permission}")
                return False
        
        # Get user with roles
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User not found: {user_id}")
            return False
        
        # Admin users have all permissions
        if user.is_admin:
            return True
        
        # Check user roles for permission
        user_permissions = set()
        for role in user.roles:
            role_permissions = set(role.permissions)
            user_permissions.update(role_permissions)
        
        # Check if user has the required permission
        if permission.value not in user_permissions:
            return False
        
        # If resource_id is provided, check resource-specific permissions
        if resource_id and permission.value.startswith("document:"):
            return self._check_document_permission(user, permission, resource_id)
        
        return True
    
    def _check_document_permission(self, user: User, permission: Permission, document_id: str) -> bool:
        """
        Check document-specific permissions.
        
        Args:
            user: User object
            permission: Document permission to check
            document_id: Document ID to check against
            
        Returns:
            bool: True if user has permission for the document, False otherwise
        """
        # Get document metadata
        doc_metadata = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.document_id == document_id
        ).first()
        
        if not doc_metadata:
            logger.warning(f"Document not found: {document_id}")
            return False
        
        # Check sensitivity level access
        sensitivity = doc_metadata.sensitivity_level
        
        for role in user.roles:
            # Check if role has access to this sensitivity level
            role_access = role.document_access
            if sensitivity in role_access and role_access[sensitivity]:
                # Check department access
                if doc_metadata.department in role.department_access:
                    return True
        
        # Check specific document access permissions
        access_permissions = doc_metadata.access_permissions
        if str(user.id) in access_permissions.get("users", []):
            return True
        
        # Check if any of user's roles have explicit access
        user_role_ids = [str(role.id) for role in user.roles]
        for role_id in user_role_ids:
            if role_id in access_permissions.get("roles", []):
                return True
        
        return False
    
    def get_user_permissions(self, user_id: str) -> Set[str]:
        """
        Get all permissions for a user.
        
        Args:
            user_id: User ID to get permissions for
            
        Returns:
            Set[str]: Set of permission strings
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User not found: {user_id}")
            return set()
        
        # Admin users have all permissions
        if user.is_admin:
            return {p.value for p in Permission}
        
        # Collect permissions from all roles
        user_permissions = set()
        for role in user.roles:
            role_permissions = set(role.permissions)
            user_permissions.update(role_permissions)
        
        return user_permissions
    
    def filter_documents_by_permission(self, user_id: str, 
                                       permission: Union[Permission, str] = Permission.DOCUMENT_READ) -> List[str]:
        """
        Filter documents based on user permissions.
        
        Args:
            user_id: User ID to filter documents for
            permission: Permission to check (defaults to DOCUMENT_READ)
            
        Returns:
            List[str]: List of document IDs the user has access to
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.warning(f"User not found: {user_id}")
            return []
        
        # Admin users have access to all documents
        if user.is_admin:
            docs = self.db.query(DocumentMetadata.document_id).all()
            return [doc.document_id for doc in docs]
        
        # Get user's roles
        user_roles = user.roles
        
        # Get accessible sensitivity levels for user
        accessible_sensitivity_levels = set()
        accessible_departments = set()
        
        for role in user_roles:
            # Check if role has the required permission
            if isinstance(permission, str):
                has_permission = permission in role.permissions
            else:
                has_permission = permission.value in role.permissions
                
            if not has_permission:
                continue
                
            # Add accessible sensitivity levels
            for sensitivity, has_access in role.document_access.items():
                if has_access:
                    accessible_sensitivity_levels.add(sensitivity)
            
            # Add accessible departments
            accessible_departments.update(set(role.department_access))
        
        # Query documents based on sensitivity and department
        accessible_docs = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.sensitivity_level.in_(accessible_sensitivity_levels),
            DocumentMetadata.department.in_(accessible_departments)
        ).all()
        
        # Get document IDs
        doc_ids = [doc.document_id for doc in accessible_docs]
        
        # Add documents with explicit user or role access
        user_role_ids = [str(role.id) for role in user_roles]
        
        explicit_access_docs = self.db.query(DocumentMetadata).filter(
            DocumentMetadata.document_id.notin_(doc_ids)
        ).all()
        
        for doc in explicit_access_docs:
            access_permissions = doc.access_permissions
            
            # Check user-specific access
            if str(user.id) in access_permissions.get("users", []):
                doc_ids.append(doc.document_id)
                continue
            
            # Check role-specific access
            for role_id in user_role_ids:
                if role_id in access_permissions.get("roles", []):
                    doc_ids.append(doc.document_id)
                    break
        
        return doc_ids

# JWT token functions
def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create JWT access token.
    
    Args:
        data: Data to encode in token
        expires_delta: Optional expiration time
        
    Returns:
        str: Encoded JWT token
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends()) -> User:
    """
    Get current user from JWT token.
    
    Args:
        token: JWT token
        db: Database session
        
    Returns:
        User: Current user object
        
    Raises:
        HTTPException: If token is invalid or user not found
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Decode JWT token
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    # Get user from database
    user = db.query(User).filter(User.username == username).first()
    if user is None:
        raise credentials_exception
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled"
        )
    
    return user

# Permission dependency
def require_permission(permission: Union[Permission, str]):
    """
    Dependency for requiring specific permission.
    
    Args:
        permission: Required permission
        
    Returns:
        Callable: Dependency function
    """
    async def permission_dependency(
        current_user: User = Depends(get_current_user),
        db: Session = Depends()
    ) -> User:
        rbac = RBACManager(db)
        if not rbac.check_permission(current_user.id, permission):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions: {permission}"
            )
        return current_user
    
    return permission_dependency

# Document permission dependency
def require_document_permission(permission: Union[Permission, str] = Permission.DOCUMENT_READ):
    """
    Dependency for requiring document-specific permission.
    
    Args:
        permission: Required document permission
        
    Returns:
        Callable: Dependency function
    """
    async def document_permission_dependency(
        document_id: str,
        current_user: User = Depends(get_current_user),
        db: Session = Depends()
    ) -> User:
        rbac = RBACManager(db)
        if not rbac.check_permission(current_user.id, permission, document_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Not enough permissions for document: {document_id}"
            )
        return current_user
    
    return document_permission_dependency