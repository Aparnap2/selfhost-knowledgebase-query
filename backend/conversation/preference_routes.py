"""
API routes for user preference management.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, List

from ..auth.database import User
from ..auth.rbac import get_current_user as rbac_get_current_user
from .preferences import UserPreferenceManager

# Create API router
router = APIRouter(prefix="/preferences", tags=["Preferences"])

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

@router.get("")
async def get_user_preferences(
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Get user preferences.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        dict: User preferences
    """
    preference_manager = UserPreferenceManager(db)
    preferences = preference_manager.get_user_preferences(str(current_user.id))
    
    return preferences

@router.put("")
async def update_user_preferences(
    preferences: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Update user preferences.
    
    Args:
        preferences: Updated preferences
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        dict: Success status and updated preferences
        
    Raises:
        HTTPException: If update fails
    """
    preference_manager = UserPreferenceManager(db)
    success = preference_manager.update_user_preferences(str(current_user.id), preferences)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update preferences"
        )
    
    # Get updated preferences
    updated_preferences = preference_manager.get_user_preferences(str(current_user.id))
    
    return {
        "success": True,
        "preferences": updated_preferences
    }

@router.get("/communication-styles")
async def get_communication_styles(
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Get available communication styles.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[dict]: Available communication styles
    """
    preference_manager = UserPreferenceManager(db)
    return preference_manager.get_communication_styles()

@router.get("/expertise-levels")
async def get_expertise_levels(
    db: Session = Depends(get_db),
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Get available expertise levels.
    
    Args:
        db: Database session
        current_user: Current authenticated user
        
    Returns:
        List[dict]: Available expertise levels
    """
    preference_manager = UserPreferenceManager(db)
    return preference_manager.get_expertise_levels()