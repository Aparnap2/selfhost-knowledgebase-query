"""
Database models and schema for enhanced authentication and RBAC system.
"""

from sqlalchemy import create_engine, Column, String, Boolean, DateTime, Text, Integer, ForeignKey, Table, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
import json

Base = declarative_base()

# Association table for many-to-many relationship between users and roles
user_roles = Table(
    'user_roles',
    Base.metadata,
    Column('user_id', UUID(as_uuid=True), ForeignKey('users.id'), primary_key=True),
    Column('role_id', UUID(as_uuid=True), ForeignKey('roles.id'), primary_key=True),
    Column('assigned_at', DateTime(timezone=True), server_default=func.now())
)

class User(Base):
    """Enhanced user model with RBAC support."""
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), unique=True, nullable=True, index=True)
    full_name = Column(String(255), nullable=True)
    hashed_password = Column(String(255), nullable=False)
    department = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    is_admin = Column(Boolean, default=False, nullable=False)
    preferences = Column(JSON, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    last_login = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    roles = relationship("Role", secondary=user_roles, back_populates="users")
    documents = relationship("DocumentMetadata", back_populates="created_by_user")
    conversations = relationship("ConversationMemory", back_populates="user")
    sessions = relationship("UserSession", back_populates="user")
    
    def __repr__(self):
        return f"<User(username='{self.username}', email='{self.email}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user to dictionary representation."""
        return {
            'id': str(self.id),
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'department': self.department,
            'is_active': self.is_active,
            'is_admin': self.is_admin,
            'preferences': self.preferences,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'roles': [role.name for role in self.roles]
        }

class Role(Base):
    """Role model for RBAC system."""
    __tablename__ = 'roles'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    permissions = Column(JSON, nullable=False, default=list)
    document_access = Column(JSON, nullable=False, default=dict)
    department_access = Column(JSON, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    users = relationship("User", secondary=user_roles, back_populates="roles")
    
    def __repr__(self):
        return f"<Role(name='{self.name}', description='{self.description}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert role to dictionary representation."""
        return {
            'id': str(self.id),
            'name': self.name,
            'description': self.description,
            'permissions': self.permissions,
            'document_access': self.document_access,
            'department_access': self.department_access,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'user_count': len(self.users)
        }

class DocumentMetadata(Base):
    """Enhanced document metadata for access control and organization."""
    __tablename__ = 'document_metadata'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(String(255), unique=True, nullable=False, index=True)  # ChromaDB document ID
    filename = Column(String(500), nullable=False)
    file_type = Column(String(50), nullable=False)
    file_size = Column(Integer, nullable=False, default=0)
    sensitivity_level = Column(String(50), nullable=False, default='internal')
    department = Column(String(100), nullable=False, default='general')
    tags = Column(JSON, nullable=False, default=list)
    version = Column(String(20), nullable=False, default='1.0')
    description = Column(Text, nullable=True)
    access_permissions = Column(JSON, nullable=False, default=dict)
    created_by = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    indexed_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    created_by_user = relationship("User", back_populates="documents")
    
    def __repr__(self):
        return f"<DocumentMetadata(filename='{self.filename}', sensitivity='{self.sensitivity_level}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert document metadata to dictionary representation."""
        return {
            'id': str(self.id),
            'document_id': self.document_id,
            'filename': self.filename,
            'file_type': self.file_type,
            'file_size': self.file_size,
            'sensitivity_level': self.sensitivity_level,
            'department': self.department,
            'tags': self.tags,
            'version': self.version,
            'description': self.description,
            'access_permissions': self.access_permissions,
            'created_by': str(self.created_by) if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'indexed_at': self.indexed_at.isoformat() if self.indexed_at else None
        }

class ConversationMemory(Base):
    """Persistent conversation memory for personalized interactions."""
    __tablename__ = 'conversation_memory'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    session_id = Column(String(255), nullable=False, index=True)
    messages = Column(JSON, nullable=False, default=list)
    context = Column(JSON, nullable=False, default=dict)
    preferences = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", back_populates="conversations")
    
    def __repr__(self):
        return f"<ConversationMemory(user_id='{self.user_id}', session_id='{self.session_id}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert conversation memory to dictionary representation."""
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'session_id': self.session_id,
            'messages': self.messages,
            'context': self.context,
            'preferences': self.preferences,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class UserSession(Base):
    """User session tracking for security and personalization."""
    __tablename__ = 'user_sessions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id'), nullable=False)
    session_token = Column(String(500), unique=True, nullable=False, index=True)
    ip_address = Column(String(45), nullable=True)  # IPv6 compatible
    user_agent = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="sessions")
    
    def __repr__(self):
        return f"<UserSession(user_id='{self.user_id}', expires_at='{self.expires_at}')>"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert user session to dictionary representation."""
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'session_token': self.session_token,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'is_active': self.is_active
        }

# Database configuration and session management
class DatabaseManager:
    """Database manager for handling connections and sessions."""
    
    def __init__(self, database_url: str):
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
    
    def get_session(self):
        """Get database session."""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def init_default_data(self):
        """Initialize database with default roles and admin user."""
        from .models import DEFAULT_ROLES
        from passlib.context import CryptContext
        
        pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        db = self.SessionLocal()
        
        try:
            # Create default roles if they don't exist
            for role_name, role_data in DEFAULT_ROLES.items():
                existing_role = db.query(Role).filter(Role.name == role_data.name).first()
                if not existing_role:
                    new_role = Role(
                        name=role_data.name,
                        description=role_data.description,
                        permissions=[p.value for p in role_data.permissions],
                        document_access={k.value: v for k, v in role_data.document_access.items()},
                        department_access=[d.value for d in role_data.department_access]
                    )
                    db.add(new_role)
            
            # Create default admin user if it doesn't exist
            admin_user = db.query(User).filter(User.username == "admin").first()
            if not admin_user:
                admin_role = db.query(Role).filter(Role.name == "Administrator").first()
                admin_user = User(
                    username="admin",
                    email="admin@localhost",
                    full_name="System Administrator",
                    hashed_password=pwd_context.hash("admin123"),
                    is_admin=True,
                    department="general"
                )
                if admin_role:
                    admin_user.roles.append(admin_role)
                db.add(admin_user)
            
            # Keep the demo user for backward compatibility
            demo_user = db.query(User).filter(User.username == "demo").first()
            if not demo_user:
                employee_role = db.query(Role).filter(Role.name == "Employee").first()
                demo_user = User(
                    username="demo",
                    email="demo@localhost",
                    full_name="Demo User",
                    hashed_password=pwd_context.hash("demo123"),
                    department="general"
                )
                if employee_role:
                    demo_user.roles.append(employee_role)
                db.add(demo_user)
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            raise e
        finally:
            db.close()