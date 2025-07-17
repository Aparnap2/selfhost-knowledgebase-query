"""
Conversation memory manager for storing and retrieving user interactions.
"""

import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
from sqlalchemy.orm import Session
from ..auth.database import ConversationMemory, User
from .models import Message, ConversationContext, UserPreference

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
        ).order_by(ConversationMemory.updated_at.desc()).limit(limit).all()
    
    def store_message(self, session_id: str, message: Message) -> bool:
        """
        Store a message in conversation memory.
        
        Args:
            session_id: Session ID
            message: Message to store
            
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
        
        # Add new message
        messages.append({
            "role": message.role,
            "content": message.content,
            "timestamp": message.timestamp.isoformat(),
            "metadata": message.metadata
        })
        
        # Update conversation
        conversation.messages = messages
        conversation.updated_at = datetime.utcnow()
        
        # Save to database
        self.db.commit()
        return True
    
    def update_context(self, session_id: str, context: ConversationContext) -> bool:
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
        conversation.context = context.dict()
        conversation.updated_at = datetime.utcnow()
        
        # Save to database
        self.db.commit()
        return True
    
    def update_preferences(self, session_id: str, preferences: UserPreference) -> bool:
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
        conversation.preferences = preferences.dict()
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