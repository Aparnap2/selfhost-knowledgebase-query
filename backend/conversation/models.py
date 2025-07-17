"""
Models for conversation memory and user preferences.
"""

from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class Message(BaseModel):
    """Individual message in a conversation."""
    role: str  # 'user', 'assistant', or 'system'
    content: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ConversationContext(BaseModel):
    """Context for a conversation."""
    documents: List[str] = []  # Document IDs referenced
    web_searches: List[str] = []  # Web search queries
    topics: List[str] = []  # Detected topics
    entities: List[str] = []  # Detected entities
    custom_data: Dict[str, Any] = Field(default_factory=dict)

class UserPreference(BaseModel):
    """User preferences for conversation."""
    communication_tone: Optional[str] = "neutral"  # formal, casual, technical, friendly, neutral
    response_length: Optional[str] = "balanced"  # brief, balanced, detailed
    expertise_level: Optional[str] = "intermediate"  # beginner, intermediate, expert
    include_citations: Optional[bool] = True
    include_code_examples: Optional[bool] = True
    preferred_language: Optional[str] = "en"
    custom_preferences: Dict[str, Any] = Field(default_factory=dict)

class ConversationMemoryCreate(BaseModel):
    """Schema for creating a new conversation memory."""
    user_id: str
    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: Optional[str] = None
    messages: List[Message] = Field(default_factory=list)
    context: ConversationContext = Field(default_factory=ConversationContext)
    preferences: UserPreference = Field(default_factory=UserPreference)

class ConversationMemoryUpdate(BaseModel):
    """Schema for updating conversation memory."""
    title: Optional[str] = None
    messages: Optional[List[Message]] = None
    context: Optional[ConversationContext] = None
    preferences: Optional[UserPreference] = None

class ConversationMemoryResponse(BaseModel):
    """Schema for conversation memory response."""
    id: str
    user_id: str
    session_id: str
    title: Optional[str]
    messages: List[Message]
    context: ConversationContext
    preferences: UserPreference
    created_at: datetime
    updated_at: datetime