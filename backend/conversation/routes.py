"""
API routes for conversation memory management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query, Path, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

from ..auth.database import User, ConversationMemory
from ..auth.middleware import PermissionChecker
from ..auth.models import Permission
from ..auth.rbac import get_current_user as rbac_get_current_user
from .memory_manager import ConversationMemoryManager
from .preference_routes import router as preference_router

# Create API router
router = APIRouter(prefix="/conversations", tags=["Conversations"])

# Include preference router
router.include_router(preference_router)

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

@router.post("", status_code=status.HTTP_201_CREATED)
async def create_conversation(
    title: Optional[str] = Body(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Create a new conversation memory.
    
    Args:
        title: Optional conversation title
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        dict: Created conversation memory
    """
    memory_manager = ConversationMemoryManager(db)
    conversation = memory_manager.create_conversation(
        user_id=str(current_user.id),
        title=title
    )
    
    return conversation.to_dict()

@router.get("")
async def get_user_conversations(
    limit: int = Query(10, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Get conversations for the current user.
    
    Args:
        limit: Maximum number of conversations to return
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[dict]: List of conversation memories
    """
    memory_manager = ConversationMemoryManager(db)
    conversations = memory_manager.get_user_conversations(str(current_user.id), limit)
    
    return [conversation.to_dict() for conversation in conversations]

@router.get("/{session_id}")
async def get_conversation(
    session_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Get a specific conversation memory.
    
    Args:
        session_id: Session ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        dict: Conversation memory
        
    Raises:
        HTTPException: If conversation not found or user doesn't have access
    """
    memory_manager = ConversationMemoryManager(db)
    conversation = memory_manager.get_conversation(session_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with session ID {session_id} not found"
        )
    
    # Check if user has access to this conversation
    if str(conversation.user_id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation"
        )
    
    return conversation.to_dict()

@router.post("/{session_id}/messages")
async def add_message(
    message: Dict[str, Any] = Body(...),
    session_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Add a message to a conversation.
    
    Args:
        message: Message to add
        session_id: Session ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        dict: Success status
        
    Raises:
        HTTPException: If conversation not found or user doesn't have access
    """
    memory_manager = ConversationMemoryManager(db)
    conversation = memory_manager.get_conversation(session_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with session ID {session_id} not found"
        )
    
    # Check if user has access to this conversation
    if str(conversation.user_id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation"
        )
    
    # Validate message format
    if "role" not in message or "content" not in message:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Message must contain 'role' and 'content' fields"
        )
    
    # Store message
    success = memory_manager.store_message(session_id, message)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store message"
        )
    
    return {"success": True}

@router.put("/{session_id}/context")
async def update_context(
    context: Dict[str, Any] = Body(...),
    session_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Update conversation context.
    
    Args:
        context: Updated context
        session_id: Session ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        dict: Success status
        
    Raises:
        HTTPException: If conversation not found or user doesn't have access
    """
    memory_manager = ConversationMemoryManager(db)
    conversation = memory_manager.get_conversation(session_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with session ID {session_id} not found"
        )
    
    # Check if user has access to this conversation
    if str(conversation.user_id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation"
        )
    
    # Update context
    success = memory_manager.update_context(session_id, context)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update context"
        )
    
    return {"success": True}

@router.put("/{session_id}/preferences")
async def update_preferences(
    preferences: Dict[str, Any] = Body(...),
    session_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Update user preferences for a conversation.
    
    Args:
        preferences: Updated preferences
        session_id: Session ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        dict: Success status
        
    Raises:
        HTTPException: If conversation not found or user doesn't have access
    """
    memory_manager = ConversationMemoryManager(db)
    conversation = memory_manager.get_conversation(session_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with session ID {session_id} not found"
        )
    
    # Check if user has access to this conversation
    if str(conversation.user_id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation"
        )
    
    # Update preferences
    success = memory_manager.update_preferences(session_id, preferences)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )
    
    return {"success": True}

@router.delete("/{session_id}")
async def delete_conversation(
    session_id: str = Path(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Delete a conversation.
    
    Args:
        session_id: Session ID
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        dict: Success status
        
    Raises:
        HTTPException: If conversation not found or user doesn't have access
    """
    memory_manager = ConversationMemoryManager(db)
    conversation = memory_manager.get_conversation(session_id)
    
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation with session ID {session_id} not found"
        )
    
    # Check if user has access to this conversation
    if str(conversation.user_id) != str(current_user.id) and not current_user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this conversation"
        )
    
    # Delete conversation
    success = memory_manager.delete_conversation(session_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete conversation"
        )
    
    return {"success": True}