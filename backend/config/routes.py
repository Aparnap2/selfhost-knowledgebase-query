"""
API routes for system configuration.
"""

from fastapi import APIRouter, Depends, HTTPException, status, Body
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from pydantic import BaseModel

from ..auth.database import User
from ..auth.middleware import PermissionChecker
from ..auth.models import Permission
from ..auth.rbac import get_current_user as rbac_get_current_user
from .offline_mode import OfflineModeManager
from .model_checker import ModelChecker

# Create API router
router = APIRouter(prefix="/config", tags=["Configuration"])

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

# Create managers
offline_mode_manager = OfflineModeManager()
model_checker = ModelChecker()

class OfflineModeUpdate(BaseModel):
    """Offline mode update request model."""
    mode: str

@router.get("/offline-mode")
async def get_offline_mode(
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Get current offline mode status.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        dict: Offline mode status
    """
    return offline_mode_manager.get_offline_status()

@router.put("/offline-mode")
async def set_offline_mode(
    update: OfflineModeUpdate,
    current_user: User = Depends(permission_checker.require_permissions([Permission.SYSTEM_ADMIN]))
):
    """
    Set offline mode.
    
    Args:
        update: Offline mode update
        current_user: Current authenticated user with SYSTEM_ADMIN permission
        
    Returns:
        dict: Updated offline mode status
        
    Raises:
        HTTPException: If update fails
    """
    try:
        return offline_mode_manager.set_offline_mode(update.mode)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/ollama-status")
async def check_ollama_status(
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Check Ollama availability.
    
    Args:
        current_user: Current authenticated user
        
    Returns:
        dict: Ollama status
    """
    is_available, error_message = offline_mode_manager.check_ollama_availability()
    
    return {
        "is_available": is_available,
        "error_message": error_message
    }

@router.get("/model-status/{model_name}")
async def check_model_status(
    model_name: str,
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Check if a specific model is available in Ollama.
    
    Args:
        model_name: Model name to check
        current_user: Current authenticated user
        
    Returns:
        dict: Model status
    """
    is_available, error_message = offline_mode_manager.check_model_availability(model_name)
    
    return {
        "model_name": model_name,
        "is_available": is_available,
        "error_message": error_message
    }

@router.get("/models")
async def get_models_status(
    force_check: bool = False,
    current_user: User = Depends(rbac_get_current_user)
):
    """
    Get status of all required models.
    
    Args:
        force_check: Force a new check regardless of cache
        current_user: Current authenticated user
        
    Returns:
        dict: Models status
    """
    return model_checker.get_model_status(force_check=force_check)

@router.post("/models/pull")
async def pull_missing_models(
    current_user: User = Depends(permission_checker.require_permissions([Permission.SYSTEM_ADMIN]))
):
    """
    Pull missing models from Ollama.
    
    Args:
        current_user: Current authenticated user with SYSTEM_ADMIN permission
        
    Returns:
        dict: Pull status
    """
    return model_checker.pull_missing_models()