"""
Conversation memory manager for storing and retrieving user interactions.
"""

import logging
import json
from typing import List, Dict, Any, Optional, Union
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import desc, func
import numpy as np

from ..auth.database import ConversationMemory, User

logger = logging.getLogger(__name__)

class ConversationMemoryManager:
    """Manager for conversation memory storage and retrieval."""
    
    def __init__(self, db_session: Session):
        """Initialize with database session."""
        self.db = db_session
    
    def create_conversation(self, user_id: str, title: Optional[str] = None) -> ConversationMemory:
        """
        Create a new conversation memory.
        
        Args:
            user_id: User ID
            title: Optional conversation title
            
        Returns:
            ConversationMemory: Created conversation memory
        """
        # Generate session ID
        session_id = str(uuid.uuid4())
        
        # Create conversation memory
        conversation = ConversationMemory(
            user_id=user_id,
            session_id=session_id,
            title=title or f"Conversation {datetime.utcnow().strftime('%Y-%m-%d %H:%M')}",
            messages=[],
            context={},
            preferences={}
        )
        
        # Save to database
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)
        
        return conversation
    
    def get_conversation(self, session_id: str) -> Optional[ConversationMemory]:
        """
        Get conversation memory by session ID.
        
        Args:
            session_id: Session ID
            
        Returns:
            Optional[ConversationMemory]: Conversation memory or None if not found
        """
        return self.db.query(ConversationMemory).filter(
            ConversationMemory.session_id == session_id
        ).first()
    
    def get_user_conversations(self, user_id: str, limit: int = 10) -> List[ConversationMemory]:
        """
        Get conversations for a user.
        
        Args:
            user_id: User ID
            limit: Maximum number of conversations to return
            
        Returns:
            List[ConversationMemory]: List of conversation memories
        """
        return self.db.query(ConversationMemory).filter(
            ConversationMemory.user_id == user_id
        ).order_by(desc(ConversationMemory.updated_at)).limit(limit).all()
    
    def store_message(self, session_id: str, message: Dict[str, Any]) -> bool:
        """
        Store a message in conversation memory.
        
        Args:
            session_id: Session ID
            message: Message to store (dict with role, content, etc.)
            
        Returns:
            bool: True if successful, False otherwise
        """
        conversation = self.get_conversation(session_id)
        if not conversation:
            return False
        
        # Get current messages
        try:
            messages = conversation.messages or []
        except (TypeError, json.JSONDecodeError):
            messages = []
        
        # Add timestamp if not present
        if "timestamp" not in message:
            message["timestamp"] = datetime.utcnow().isoformat()
        
        # Add new message
        messages.append(message)
        
        # Update conversation
        conversation.messages = messages
        conversation.updated_at = datetime.utcnow()
        
        # Save to database
        self.db.commit()
        return True
    
    def update_context(self, session_id: str, context: Dict[str, Any]) -> bool:
        """
        Update conversation context.
        
        Args:
            session_id: Session ID
            context: Updated context
            
        Returns:
            bool: True if successful, False otherwise
        """
        conversation = self.get_conversation(session_id)
        if not conversation:
            return False
        
        # Update context
        conversation.context = context
        conversation.updated_at = datetime.utcnow()
        
        # Save to database
        self.db.commit()
        return True
    
    def update_preferences(self, session_id: str, preferences: Dict[str, Any]) -> bool:
        """
        Update user preferences for a conversation.
        
        Args:
            session_id: Session ID
            preferences: Updated preferences
            
        Returns:
            bool: True if successful, False otherwise
        """
        conversation = self.get_conversation(session_id)
        if not conversation:
            return False
        
        # Update preferences
        conversation.preferences = preferences
        conversation.updated_at = datetime.utcnow()
        
        # Save to database
        self.db.commit()
        return True
    
    def get_relevant_context(self, user_id: str, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get relevant context from past conversations.
        
        Args:
            user_id: User ID
            query: Current query
            limit: Maximum number of context items to return
            
        Returns:
            List[Dict[str, Any]]: List of relevant context items
        """
        # Get user's conversations
        conversations = self.get_user_conversations(user_id, limit=10)
        
        # Extract relevant messages
        relevant_messages = []
        for conversation in conversations:
            try:
                messages = conversation.messages or []
                for message in messages:
                    # Simple relevance check (in a real system, use embeddings)
                    if any(term in message.get("content", "").lower() for term in query.lower().split()):
                        relevant_messages.append({
                            "session_id": conversation.session_id,
                            "message": message,
                            "timestamp": message.get("timestamp")
                        })
            except (TypeError, json.JSONDecodeError):
                continue
        
        # Sort by relevance (in a real system, use semantic similarity)
        relevant_messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        
        return relevant_messages[:limit]
    
    def delete_conversation(self, session_id: str) -> bool:
        """
        Delete a conversation.
        
        Args:
            session_id: Session ID
            
        Returns:
            bool: True if successful, False otherwise
        """
        conversation = self.get_conversation(session_id)
        if not conversation:
            return False
        
        # Delete conversation
        self.db.delete(conversation)
        self.db.commit()
        return True
    
    def cleanup_old_conversations(self, days: int = 30) -> int:
        """
        Clean up old conversations.
        
        Args:
            days: Number of days to keep conversations
            
        Returns:
            int: Number of deleted conversations
        """
        cutoff_date = datetime.utcnow() - datetime.timedelta(days=days)
        result = self.db.query(ConversationMemory).filter(
            ConversationMemory.updated_at < cutoff_date
        ).delete()
        self.db.commit()
        return result