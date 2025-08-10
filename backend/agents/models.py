"""
Agent models using Pydantic v2 and LangChain types.
"""

from pydantic import BaseModel, Field, ConfigDict
from langchain_core.messages import BaseMessage
from typing import List, Dict, Any, Optional, Union
from enum import Enum
from datetime import datetime
import uuid

class AgentType(str, Enum):
    """Types of specialized agents."""
    DOCUMENT_SEARCH = "document_search"
    ANALYSIS = "analysis"
    CONTENT_GENERATION = "content_generation"
    WEB_RESEARCH = "web_research"
    CODE_EXECUTION = "code_execution"

class MessageType(str, Enum):
    """Types of messages between agents."""
    TASK_REQUEST = "task_request"
    TASK_RESPONSE = "task_response"
    COORDINATION = "coordination"
    ERROR = "error"
    STATUS_UPDATE = "status_update"

class TaskPriority(str, Enum):
    """Task priority levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class AgentPersonality(BaseModel):
    """Agent personality configuration using Pydantic v2."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    name: str
    description: str
    communication_style: str = "professional"
    expertise_areas: List[str] = Field(default_factory=list)
    response_patterns: Dict[str, str] = Field(default_factory=dict)
    max_context_length: int = 4000
    temperature: float = 0.7

class AgentTask(BaseModel):
    """Task assigned to an agent."""
    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    task_type: str
    input_data: Dict[str, Any]
    context: Dict[str, Any] = Field(default_factory=dict)
    priority: TaskPriority = TaskPriority.MEDIUM
    deadline: Optional[datetime] = None
    assigned_agent: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AgentResult(BaseModel):
    """Result from agent task execution."""
    task_id: str
    agent_id: str
    success: bool
    result_data: Dict[str, Any] = Field(default_factory=dict)
    error_message: Optional[str] = None
    execution_time: float = 0.0
    confidence_score: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    completed_at: datetime = Field(default_factory=datetime.utcnow)

class AgentMessage(BaseModel):
    """Message between agents."""
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    sender_id: str
    recipient_id: str
    message_type: MessageType
    content: Dict[str, Any]
    correlation_id: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    requires_response: bool = False

class AgentStatus(BaseModel):
    """Current status of an agent."""
    agent_id: str
    agent_type: AgentType
    is_active: bool = True
    current_tasks: List[str] = Field(default_factory=list)
    completed_tasks: int = 0
    error_count: int = 0
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    performance_metrics: Dict[str, float] = Field(default_factory=dict)

class CoordinationPlan(BaseModel):
    """Plan for coordinating multiple agents."""
    plan_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    required_agents: List[AgentType]
    execution_steps: List[Dict[str, Any]] = Field(default_factory=list)
    dependencies: Dict[str, List[str]] = Field(default_factory=dict)
    estimated_duration: float = 0.0
    created_at: datetime = Field(default_factory=datetime.utcnow)