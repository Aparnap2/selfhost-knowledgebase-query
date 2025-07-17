"""
Authentication and authorization models for the Self-Hosted AI Knowledge Base Assistant.
Implements comprehensive RBAC (Role-Based Access Control) system.
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
import uuid

class Permission(str, Enum):
    """System permissions for granular access control."""
    # Document permissions
    DOCUMENT_READ = "document:read"
    DOCUMENT_WRITE = "document:write"
    DOCUMENT_DELETE = "document:delete"
    DOCUMENT_UPLOAD = "document:upload"
    
    # Query permissions
    QUERY_BASIC = "query:basic"
    QUERY_ADVANCED = "query:advanced"
    QUERY_WEB_SEARCH = "query:web_search"
    
    # System permissions
    SYSTEM_ADMIN = "system:admin"
    SYSTEM_MONITOR = "system:monitor"
    USER_MANAGE = "user:manage"
    
    # Agent permissions
    AGENT_EXECUTE = "agent:execute"
    AGENT_COORDINATE = "agent:coordinate"
    AGENT_CONFIGURE = "agent:configure"
    
    # Python execution permissions
    CODE_EXECUTE = "code:execute"
    CODE_VISUALIZE = "code:visualize"

class DocumentSensitivity(str, Enum):
    """Document sensitivity levels for access control."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"

class Department(str, Enum):
    """Organization departments for document categorization."""
    GENERAL = "general"
    HR = "hr"
    FINANCE = "finance"
    ENGINEERING = "engineering"
    MARKETING = "marketing"
    LEGAL = "legal"
    OPERATIONS = "operations"

class Role(BaseModel):
    """User role definition with associated permissions."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: Optional[str] = None
    permissions: List[Permission] = []
    document_access: Dict[DocumentSensitivity, bool] = Field(default_factory=dict)
    department_access: List[Department] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class User(BaseModel):
    """Enhanced user model with RBAC support."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    hashed_password: str
    roles: List[str] = []  # Role IDs
    department: Optional[Department] = None
    is_active: bool = True
    is_admin: bool = False
    preferences: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_login: Optional[datetime] = None

class DocumentMetadata(BaseModel):
    """Enhanced document metadata for access control and organization."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    filename: str
    file_type: str
    file_size: int
    sensitivity: DocumentSensitivity = DocumentSensitivity.INTERNAL
    department: Department = Department.GENERAL
    tags: List[str] = []
    version: str = "1.0"
    author: Optional[str] = None
    description: Optional[str] = None
    access_groups: List[str] = []  # Role IDs that can access this document
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    indexed_at: Optional[datetime] = None

class ConversationMemory(BaseModel):
    """Persistent conversation memory for personalized interactions."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_id: str
    messages: List[Dict[str, Any]] = []
    context: Dict[str, Any] = Field(default_factory=dict)
    preferences: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class UserSession(BaseModel):
    """User session tracking for security and personalization."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    session_token: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime
    is_active: bool = True

# Default roles configuration
DEFAULT_ROLES = {
    "admin": Role(
        name="Administrator",
        description="Full system access",
        permissions=list(Permission),
        document_access={
            DocumentSensitivity.PUBLIC: True,
            DocumentSensitivity.INTERNAL: True,
            DocumentSensitivity.CONFIDENTIAL: True,
            DocumentSensitivity.RESTRICTED: True
        },
        department_access=list(Department)
    ),
    "manager": Role(
        name="Manager",
        description="Department management access",
        permissions=[
            Permission.DOCUMENT_READ,
            Permission.DOCUMENT_WRITE,
            Permission.DOCUMENT_UPLOAD,
            Permission.QUERY_BASIC,
            Permission.QUERY_ADVANCED,
            Permission.QUERY_WEB_SEARCH,
            Permission.AGENT_EXECUTE,
            Permission.CODE_EXECUTE,
            Permission.CODE_VISUALIZE
        ],
        document_access={
            DocumentSensitivity.PUBLIC: True,
            DocumentSensitivity.INTERNAL: True,
            DocumentSensitivity.CONFIDENTIAL: True,
            DocumentSensitivity.RESTRICTED: False
        }
    ),
    "employee": Role(
        name="Employee",
        description="Standard employee access",
        permissions=[
            Permission.DOCUMENT_READ,
            Permission.DOCUMENT_UPLOAD,
            Permission.QUERY_BASIC,
            Permission.QUERY_WEB_SEARCH,
            Permission.AGENT_EXECUTE,
            Permission.CODE_EXECUTE
        ],
        document_access={
            DocumentSensitivity.PUBLIC: True,
            DocumentSensitivity.INTERNAL: True,
            DocumentSensitivity.CONFIDENTIAL: False,
            DocumentSensitivity.RESTRICTED: False
        }
    ),
    "guest": Role(
        name="Guest",
        description="Limited read-only access",
        permissions=[
            Permission.DOCUMENT_READ,
            Permission.QUERY_BASIC
        ],
        document_access={
            DocumentSensitivity.PUBLIC: True,
            DocumentSensitivity.INTERNAL: False,
            DocumentSensitivity.CONFIDENTIAL: False,
            DocumentSensitivity.RESTRICTED: False
        }
    )
}