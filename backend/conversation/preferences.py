"""
User preference management for conversation personalization.
"""

import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from ..auth.database import User

logger = logging.getLogger(__name__)

class UserPreferenceManager:
    """Manager for user preferences."""
    
    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session
    
    def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """
        Get user preferences.
        
        Args:
            user_id: User ID
            
        Returns:
            Dict[str, Any]: User preferences
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return {}
        
        # Return preferences or empty dict if None
        return user.preferences or {}
    
    def update_user_preferences(self, user_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Update user preferences.
        
        Args:
            user_id: User ID
            preferences: Updated preferences
            
        Returns:
            bool: True if successful, False otherwise
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        # Get current preferences
        current_preferences = user.preferences or {}
        
        # Update with new preferences
        current_preferences.update(preferences)
        
        # Save to database
        user.preferences = current_preferences
        self.db.commit()
        
        return True
    
    def get_communication_styles(self) -> List[Dict[str, Any]]:
        """
        Get available communication styles.
        
        Returns:
            List[Dict[str, Any]]: Available communication styles
        """
        return [
            {
                "id": "formal",
                "name": "Formal",
                "description": "Professional and business-like communication"
            },
            {
                "id": "casual",
                "name": "Casual",
                "description": "Friendly and conversational tone"
            },
            {
                "id": "technical",
                "name": "Technical",
                "description": "Detailed technical explanations with terminology"
            },
            {
                "id": "simple",
                "name": "Simple",
                "description": "Clear and straightforward explanations"
            },
            {
                "id": "concise",
                "name": "Concise",
                "description": "Brief and to-the-point responses"
            }
        ]
    
    def get_expertise_levels(self) -> List[Dict[str, Any]]:
        """
        Get available expertise levels.
        
        Returns:
            List[Dict[str, Any]]: Available expertise levels
        """
        return [
            {
                "id": "beginner",
                "name": "Beginner",
                "description": "Basic explanations with minimal jargon"
            },
            {
                "id": "intermediate",
                "name": "Intermediate",
                "description": "Balanced explanations with some technical details"
            },
            {
                "id": "expert",
                "name": "Expert",
                "description": "Advanced explanations with full technical details"
            }
        ]
    
    def apply_preferences_to_prompt(self, prompt: str, preferences: Dict[str, Any]) -> str:
        """
        Apply user preferences to a prompt.
        
        Args:
            prompt: Original prompt
            preferences: User preferences
            
        Returns:
            str: Modified prompt with preference instructions
        """
        # Extract relevant preferences
        communication_style = preferences.get("communication_style", "neutral")
        expertise_level = preferences.get("expertise_level", "intermediate")
        response_length = preferences.get("response_length", "balanced")
        include_citations = preferences.get("include_citations", True)
        
        # Build preference instructions
        instructions = []
        
        # Add communication style instruction
        if communication_style == "formal":
            instructions.append("Use formal and professional language.")
        elif communication_style == "casual":
            instructions.append("Use a casual and conversational tone.")
        elif communication_style == "technical":
            instructions.append("Use technical language with proper terminology.")
        elif communication_style == "simple":
            instructions.append("Use simple and easy-to-understand language.")
        elif communication_style == "concise":
            instructions.append("Be concise and direct.")
        
        # Add expertise level instruction
        if expertise_level == "beginner":
            instructions.append("Explain concepts as if to a beginner with minimal jargon.")
        elif expertise_level == "expert":
            instructions.append("Provide detailed technical explanations suitable for experts.")
        
        # Add response length instruction
        if response_length == "brief":
            instructions.append("Keep the response brief and to the point.")
        elif response_length == "detailed":
            instructions.append("Provide a detailed and comprehensive response.")
        
        # Add citation instruction
        if include_citations:
            instructions.append("Include citations to sources where applicable.")
        
        # Combine instructions
        if instructions:
            preference_text = " ".join(instructions)
            return f"{prompt}\n\nPreferences: {preference_text}"
        
        return prompt