"""
API routes for authentication and role management.
Provides endpoints for login, user management, and role administration.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body, Query, Path
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import timedelta
import uuid

from .database import User, Role, user_roles, DatabaseManager
from .models import Permission, DocumentSensitivity, Department
from .rbac import RBACManager, create_access_token, get_current_user
from .middleware import PermissionChecker

# Create API router
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Get database dependency
def get_db():
    """Database session dependency."""
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import create_engine
    import os
    
    DB_PATH = os.getenv("DB_PATH", "/data/notebooklm.db")
    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create permission checker
permission_checker = PermissionChecker(get_db)

# Pydantic models for request/response
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Set
from datetime import datetime

class Token(BaseModel):
    """Token response model."""
    access_token: str
    token_type: str
    expires_in: int
    user_id: str
    username: str
    is_admin: bool
    permissions: List[str]

class UserCreate(BaseModel):
    """User creation request model."""
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: str
    department: Optional[str] = None
    is_admin: bool = False
    role_ids: List[str] = []

class UserUpdate(BaseModel):
    """User update request model."""
    email: Optional[str] = None
    full_name: Optional[str] = None
    password: Optional[str] = None
    department: Optional[str] = None
    is_active: Optional[bool] = None
    is_admin: Optional[bool] = None
    role_ids: Optional[List[str]] = None

class UserResponse(BaseModel):
    """User response model."""
    id: str
    username: str
    email: Optional[str]
    full_name: Optional[str]
    department: Optional[str]
    is_active: bool
    is_admin: bool
    roles: List[str]
    created_at: datetime
    updated_at: datetime
    last_login: Optional[datetime]

class RoleCreate(BaseModel):
    """Role creation request model."""
    name: str
    description: Optional[str] = None
    permissions: List[str] = []
    document_access: Dict[str, bool] = {}
    department_access: List[str] = []

class RoleUpdate(BaseModel):
    """Role update request model."""
    name: Optional[str] = None
    description: Optional[str] = None
    permissions: Optional[List[str]] = None
    document_access: Optional[Dict[str, bool]] = None
    department_access: Optional[List[str]] = None

class RoleResponse(BaseModel):
    """Role response model."""
    id: str
    name: str
    description: Optional[str]
    permissions: List[str]
    document_access: Dict[str, bool]
    department_access: List[str]
    user_count: int
    created_at: datetime
    updated_at: datetime

class PermissionResponse(BaseModel):
    """Permission response model."""
    value: str
    description: str
    category: str

# Authentication routes
@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Authenticate user and return JWT token.
    
    Args:
        form_data: OAuth2 form with username and password
        db: Database session
        
    Returns:
        Token: JWT token and user information
        
    Raises:
        HTTPException: If authentication fails
    """
    from passlib.context import CryptContext
    
    # Password hashing context
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Find user by username
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify password
    if not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is disabled",
        )
    
    # Create access token
    access_token_expires = timedelta(minutes=30)
    access_token = create_access_token(
        data={"sub": user.username},
        expires_delta=access_token_expires,
    )
    
    # Update last login time
    user.last_login = datetime.utcnow()
    db.commit()
    
    # Get user permissions
    rbac = RBACManager(db)
    permissions = list(rbac.get_user_permissions(str(user.id)))
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": access_token_expires.seconds,
        "user_id": str(user.id),
        "username": user.username,
        "is_admin": user.is_admin,
        "permissions": permissions
    }

@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get current user information.
    
    Args:
        current_user: Current authenticated user
        db: Database session
        
    Returns:
        UserResponse: User information
    """
    # Convert user to response model
    return {
        "id": str(current_user.id),
        "username": current_user.username,
        "email": current_user.email,
        "full_name": current_user.full_name,
        "department": current_user.department,
        "is_active": current_user.is_active,
        "is_admin": current_user.is_admin,
        "roles": [role.name for role in current_user.roles],
        "created_at": current_user.created_at,
        "updated_at": current_user.updated_at,
        "last_login": current_user.last_login
    }

# User management routes
@router.post("/users", response_model=UserResponse)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_permissions([Permission.USER_MANAGE, Permission.SYSTEM_ADMIN]))
):
    """
    Create a new user.
    
    Args:
        user_data: User creation data
        db: Database session
        current_user: Current authenticated user with USER_MANAGE permission
        
    Returns:
        UserResponse: Created user information
        
    Raises:
        HTTPException: If username already exists
    """
    from passlib.context import CryptContext
    
    # Password hashing context
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Check if username already exists
    existing_user = db.query(User).filter(User.username == user_data.username).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Username '{user_data.username}' already exists"
        )
    
    # Check if email already exists (if provided)
    if user_data.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{user_data.email}' already exists"
            )
    
    # Create new user
    new_user = User(
        username=user_data.username,
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=pwd_context.hash(user_data.password),
        department=user_data.department,
        is_admin=user_data.is_admin
    )
    
    # Add roles if provided
    if user_data.role_ids:
        for role_id in user_data.role_ids:
            role = db.query(Role).filter(Role.id == role_id).first()
            if role:
                new_user.roles.append(role)
    
    # Save user to database
    db.add(new_user)
    db.commit()
    db.refresh(new_user)
    
    # Convert user to response model
    return {
        "id": str(new_user.id),
        "username": new_user.username,
        "email": new_user.email,
        "full_name": new_user.full_name,
        "department": new_user.department,
        "is_active": new_user.is_active,
        "is_admin": new_user.is_admin,
        "roles": [role.name for role in new_user.roles],
        "created_at": new_user.created_at,
        "updated_at": new_user.updated_at,
        "last_login": new_user.last_login
    }

@router.get("/users", response_model=List[UserResponse])
async def get_users(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_permissions([Permission.USER_MANAGE, Permission.SYSTEM_ADMIN]))
):
    """
    Get list of users.
    
    Args:
        skip: Number of users to skip
        limit: Maximum number of users to return
        db: Database session
        current_user: Current authenticated user with USER_MANAGE permission
        
    Returns:
        List[UserResponse]: List of users
    """
    users = db.query(User).offset(skip).limit(limit).all()
    
    # Convert users to response models
    return [
        {
            "id": str(user.id),
            "username": user.username,
            "email": user.email,
            "full_name": user.full_name,
            "department": user.department,
            "is_active": user.is_active,
            "is_admin": user.is_admin,
            "roles": [role.name for role in user.roles],
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_login": user.last_login
        }
        for user in users
    ]

@router.get("/users/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_permissions([Permission.USER_MANAGE, Permission.SYSTEM_ADMIN]))
):
    """
    Get user by ID.
    
    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user with USER_MANAGE permission
        
    Returns:
        UserResponse: User information
        
    Raises:
        HTTPException: If user not found
    """
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Convert user to response model
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "department": user.department,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "roles": [role.name for role in user.roles],
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login
    }

@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: str,
    user_data: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_permissions([Permission.USER_MANAGE, Permission.SYSTEM_ADMIN]))
):
    """
    Update user by ID.
    
    Args:
        user_id: User ID
        user_data: User update data
        db: Database session
        current_user: Current authenticated user with USER_MANAGE permission
        
    Returns:
        UserResponse: Updated user information
        
    Raises:
        HTTPException: If user not found or email already exists
    """
    from passlib.context import CryptContext
    
    # Password hashing context
    pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
    
    # Find user by ID
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Check if email already exists (if provided and changed)
    if user_data.email and user_data.email != user.email:
        existing_email = db.query(User).filter(User.email == user_data.email).first()
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Email '{user_data.email}' already exists"
            )
    
    # Update user fields
    if user_data.email is not None:
        user.email = user_data.email
    if user_data.full_name is not None:
        user.full_name = user_data.full_name
    if user_data.password is not None:
        user.hashed_password = pwd_context.hash(user_data.password)
    if user_data.department is not None:
        user.department = user_data.department
    if user_data.is_active is not None:
        user.is_active = user_data.is_active
    if user_data.is_admin is not None:
        user.is_admin = user_data.is_admin
    
    # Update roles if provided
    if user_data.role_ids is not None:
        # Clear existing roles
        user.roles = []
        
        # Add new roles
        for role_id in user_data.role_ids:
            role = db.query(Role).filter(Role.id == role_id).first()
            if role:
                user.roles.append(role)
    
    # Update timestamp
    user.updated_at = datetime.utcnow()
    
    # Save changes to database
    db.commit()
    db.refresh(user)
    
    # Convert user to response model
    return {
        "id": str(user.id),
        "username": user.username,
        "email": user.email,
        "full_name": user.full_name,
        "department": user.department,
        "is_active": user.is_active,
        "is_admin": user.is_admin,
        "roles": [role.name for role in user.roles],
        "created_at": user.created_at,
        "updated_at": user.updated_at,
        "last_login": user.last_login
    }

@router.delete("/users/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_permissions([Permission.USER_MANAGE, Permission.SYSTEM_ADMIN]))
):
    """
    Delete user by ID.
    
    Args:
        user_id: User ID
        db: Database session
        current_user: Current authenticated user with USER_MANAGE permission
        
    Raises:
        HTTPException: If user not found or is the current user
    """
    # Find user by ID
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User with ID {user_id} not found"
        )
    
    # Prevent deleting the current user
    if str(user.id) == str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete your own user account"
        )
    
    # Delete user
    db.delete(user)
    db.commit()
    
    return None

# Role management routes
@router.post("/roles", response_model=RoleResponse)
async def create_role(
    role_data: RoleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_permissions([Permission.USER_MANAGE, Permission.SYSTEM_ADMIN]))
):
    """
    Create a new role.
    
    Args:
        role_data: Role creation data
        db: Database session
        current_user: Current authenticated user with USER_MANAGE permission
        
    Returns:
        RoleResponse: Created role information
        
    Raises:
        HTTPException: If role name already exists or permissions are invalid
    """
    # Check if role name already exists
    existing_role = db.query(Role).filter(Role.name == role_data.name).first()
    if existing_role:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Role name '{role_data.name}' already exists"
        )
    
    # Validate permissions
    valid_permissions = [p.value for p in Permission]
    for permission in role_data.permissions:
        if permission not in valid_permissions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid permission: {permission}"
            )
    
    # Validate document access
    valid_sensitivities = [s.value for s in DocumentSensitivity]
    for sensitivity in role_data.document_access:
        if sensitivity not in valid_sensitivities:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sensitivity level: {sensitivity}"
            )
    
    # Validate department access
    valid_departments = [d.value for d in Department]
    for department in role_data.department_access:
        if department not in valid_departments:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid department: {department}"
            )
    
    # Create new role
    new_role = Role(
        name=role_data.name,
        description=role_data.description,
        permissions=role_data.permissions,
        document_access=role_data.document_access,
        department_access=role_data.department_access
    )
    
    # Save role to database
    db.add(new_role)
    db.commit()
    db.refresh(new_role)
    
    # Convert role to response model
    return {
        "id": str(new_role.id),
        "name": new_role.name,
        "description": new_role.description,
        "permissions": new_role.permissions,
        "document_access": new_role.document_access,
        "department_access": new_role.department_access,
        "user_count": len(new_role.users),
        "created_at": new_role.created_at,
        "updated_at": new_role.updated_at
    }

@router.get("/roles", response_model=List[RoleResponse])
async def get_roles(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get list of roles.
    
    Args:
        skip: Number of roles to skip
        limit: Maximum number of roles to return
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[RoleResponse]: List of roles
    """
    roles = db.query(Role).offset(skip).limit(limit).all()
    
    # Convert roles to response models
    return [
        {
            "id": str(role.id),
            "name": role.name,
            "description": role.description,
            "permissions": role.permissions,
            "document_access": role.document_access,
            "department_access": role.department_access,
            "user_count": len(role.users),
            "created_at": role.created_at,
            "updated_at": role.updated_at
        }
        for role in roles
    ]

@router.get("/roles/{role_id}", response_model=RoleResponse)
async def get_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Get role by ID.
    
    Args:
        role_id: Role ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        RoleResponse: Role information
        
    Raises:
        HTTPException: If role not found
    """
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found"
        )
    
    # Convert role to response model
    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "permissions": role.permissions,
        "document_access": role.document_access,
        "department_access": role.department_access,
        "user_count": len(role.users),
        "created_at": role.created_at,
        "updated_at": role.updated_at
    }

@router.put("/roles/{role_id}", response_model=RoleResponse)
async def update_role(
    role_id: str,
    role_data: RoleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_permissions([Permission.USER_MANAGE, Permission.SYSTEM_ADMIN]))
):
    """
    Update role by ID.
    
    Args:
        role_id: Role ID
        role_data: Role update data
        db: Database session
        current_user: Current authenticated user with USER_MANAGE permission
        
    Returns:
        RoleResponse: Updated role information
        
    Raises:
        HTTPException: If role not found, name already exists, or permissions are invalid
    """
    # Find role by ID
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found"
        )
    
    # Check if name already exists (if provided and changed)
    if role_data.name and role_data.name != role.name:
        existing_role = db.query(Role).filter(Role.name == role_data.name).first()
        if existing_role:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Role name '{role_data.name}' already exists"
            )
    
    # Validate permissions (if provided)
    if role_data.permissions:
        valid_permissions = [p.value for p in Permission]
        for permission in role_data.permissions:
            if permission not in valid_permissions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid permission: {permission}"
                )
    
    # Validate document access (if provided)
    if role_data.document_access:
        valid_sensitivities = [s.value for s in DocumentSensitivity]
        for sensitivity in role_data.document_access:
            if sensitivity not in valid_sensitivities:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid sensitivity level: {sensitivity}"
                )
    
    # Validate department access (if provided)
    if role_data.department_access:
        valid_departments = [d.value for d in Department]
        for department in role_data.department_access:
            if department not in valid_departments:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid department: {department}"
                )
    
    # Update role fields
    if role_data.name is not None:
        role.name = role_data.name
    if role_data.description is not None:
        role.description = role_data.description
    if role_data.permissions is not None:
        role.permissions = role_data.permissions
    if role_data.document_access is not None:
        role.document_access = role_data.document_access
    if role_data.department_access is not None:
        role.department_access = role_data.department_access
    
    # Update timestamp
    role.updated_at = datetime.utcnow()
    
    # Save changes to database
    db.commit()
    db.refresh(role)
    
    # Convert role to response model
    return {
        "id": str(role.id),
        "name": role.name,
        "description": role.description,
        "permissions": role.permissions,
        "document_access": role.document_access,
        "department_access": role.department_access,
        "user_count": len(role.users),
        "created_at": role.created_at,
        "updated_at": role.updated_at
    }

@router.delete("/roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_permissions([Permission.USER_MANAGE, Permission.SYSTEM_ADMIN]))
):
    """
    Delete role by ID.
    
    Args:
        role_id: Role ID
        db: Database session
        current_user: Current authenticated user with USER_MANAGE permission
        
    Raises:
        HTTPException: If role not found or has users assigned
    """
    # Find role by ID
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Role with ID {role_id} not found"
        )
    
    # Check if role has users assigned
    if role.users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete role '{role.name}' because it has {len(role.users)} users assigned"
        )
    
    # Delete role
    db.delete(role)
    db.commit()
    
    return None

@router.get("/permissions", response_model=List[PermissionResponse])
async def get_permissions(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of all available permissions.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List[PermissionResponse]: List of permissions
    """
    # Define permission categories and descriptions
    permission_info = {
        Permission.DOCUMENT_READ.value: {
            "description": "Read documents",
            "category": "Document"
        },
        Permission.DOCUMENT_WRITE.value: {
            "description": "Create and edit documents",
            "category": "Document"
        },
        Permission.DOCUMENT_DELETE.value: {
            "description": "Delete documents",
            "category": "Document"
        },
        Permission.DOCUMENT_UPLOAD.value: {
            "description": "Upload new documents",
            "category": "Document"
        },
        Permission.QUERY_BASIC.value: {
            "description": "Perform basic queries",
            "category": "Query"
        },
        Permission.QUERY_ADVANCED.value: {
            "description": "Perform advanced queries",
            "category": "Query"
        },
        Permission.QUERY_WEB_SEARCH.value: {
            "description": "Perform web searches",
            "category": "Query"
        },
        Permission.SYSTEM_ADMIN.value: {
            "description": "Full system administration",
            "category": "System"
        },
        Permission.SYSTEM_MONITOR.value: {
            "description": "Monitor system performance",
            "category": "System"
        },
        Permission.USER_MANAGE.value: {
            "description": "Manage users and roles",
            "category": "System"
        },
        Permission.AGENT_EXECUTE.value: {
            "description": "Execute AI agents",
            "category": "Agent"
        },
        Permission.AGENT_COORDINATE.value: {
            "description": "Coordinate multiple agents",
            "category": "Agent"
        },
        Permission.AGENT_CONFIGURE.value: {
            "description": "Configure agent settings",
            "category": "Agent"
        },
        Permission.CODE_EXECUTE.value: {
            "description": "Execute Python code",
            "category": "Code"
        },
        Permission.CODE_VISUALIZE.value: {
            "description": "Create data visualizations",
            "category": "Code"
        }
    }
    
    # Return all permissions with descriptions and categories
    return [
        {
            "value": p.value,
            "description": permission_info[p.value]["description"],
            "category": permission_info[p.value]["category"]
        }
        for p in Permission
    ]

@router.get("/sensitivity-levels", response_model=List[str])
async def get_sensitivity_levels(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of all document sensitivity levels.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List[str]: List of sensitivity levels
    """
    return [s.value for s in DocumentSensitivity]

@router.get("/departments", response_model=List[str])
async def get_departments(
    current_user: User = Depends(get_current_user)
):
    """
    Get list of all departments.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        List[str]: List of departments
    """
    return [d.value for d in Department]