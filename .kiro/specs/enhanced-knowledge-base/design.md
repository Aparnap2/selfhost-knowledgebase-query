# Design Document

## Overview

This design document outlines the architecture and implementation approach for enhancing the existing DeepResearch system to meet the Self-Hosted AI Knowledge Base Assistant PRD requirements. The design builds upon the current microservices architecture while adding new components for RBAC, multi-agent coordination, encryption, and monitoring.

## Architecture

### Current Architecture Enhancement

The existing architecture will be enhanced with the following new components:

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │   Backend       │    │   ChromaDB      │
│   (React/TS)    │◄──►│   (FastAPI)     │◄──►│   (Vector DB)   │
│   Port 5173     │    │   Port 8001     │    │   Port 8000     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Python        │    │   Agent         │    │   Monitoring    │
│   Executor      │    │   Coordinator   │    │   (Langfuse)    │
│   Port 3001     │    │   Port 8002     │    │   Port 8003     │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │
                                ▼
                       ┌─────────────────┐
                       │   Ollama        │
                       │   (LLM Service) │
                       │   Port 11434    │
                       └─────────────────┘
```

### New Components

1. **Agent Coordinator Service** (Port 8002): Manages multi-agent orchestration and A2A communication
2. **Monitoring Service** (Port 8003): Langfuse integration for system monitoring
3. **Enhanced Authentication Module**: RBAC implementation within the backend
4. **Encryption Service**: End-to-end encryption for data at rest and in transit
5. **Memory Management Service**: Persistent conversation and user context storage

## Components and Interfaces

### 1. Enhanced Authentication and RBAC System

#### Database Schema Extensions
```sql
-- Users table enhancement
CREATE TABLE users (
    id UUID PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Roles table
CREATE TABLE roles (
    id UUID PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    description TEXT,
    permissions JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User roles mapping
CREATE TABLE user_roles (
    user_id UUID REFERENCES users(id),
    role_id UUID REFERENCES roles(id),
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, role_id)
);

-- Document metadata
CREATE TABLE document_metadata (
    document_id UUID PRIMARY KEY,
    sensitivity_level VARCHAR(50),
    department VARCHAR(100),
    version VARCHAR(20),
    tags JSONB,
    access_permissions JSONB,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### RBAC Implementation
```python
# backend/auth/rbac.py
class Permission(Enum):
    READ_DOCUMENT = "read_document"
    WRITE_DOCUMENT = "write_document"
    DELETE_DOCUMENT = "delete_document"
    ADMIN_USERS = "admin_users"
    ADMIN_SYSTEM = "admin_system"

class RBACManager:
    def __init__(self, db_session):
        self.db = db_session
    
    def check_permission(self, user_id: UUID, permission: Permission, resource_id: UUID = None) -> bool:
        """Check if user has permission for specific resource"""
        pass
    
    def get_user_permissions(self, user_id: UUID) -> List[Permission]:
        """Get all permissions for a user"""
        pass
    
    def filter_documents_by_permission(self, user_id: UUID, documents: List[Document]) -> List[Document]:
        """Filter documents based on user permissions"""
        pass
```

### 2. Multi-Agent Architecture

#### Agent Coordinator Service
```python
# backend/agents/coordinator.py
class AgentCoordinator:
    def __init__(self):
        self.agents = {}
        self.communication_bus = AgentCommunicationBus()
    
    async def process_query(self, query: str, user_context: UserContext) -> AgentResponse:
        """Coordinate multiple agents to process a complex query"""
        # Determine required agents
        required_agents = self.analyze_query_requirements(query)
        
        # Create execution plan
        execution_plan = self.create_execution_plan(required_agents, query)
        
        # Execute plan with agent coordination
        results = await self.execute_plan(execution_plan, user_context)
        
        # Synthesize final response
        return self.synthesize_response(results)

class Agent:
    def __init__(self, agent_id: str, personality: AgentPersonality):
        self.id = agent_id
        self.personality = personality
        self.memory = AgentMemory()
    
    async def process_task(self, task: AgentTask, context: AgentContext) -> AgentResult:
        """Process a specific task assigned to this agent"""
        pass
    
    async def communicate_with_agent(self, target_agent_id: str, message: AgentMessage) -> AgentMessage:
        """Send message to another agent"""
        pass
```

#### Agent Communication Protocol
```python
# backend/agents/communication.py
class AgentMessage:
    sender_id: str
    recipient_id: str
    message_type: MessageType
    content: Dict[str, Any]
    timestamp: datetime
    correlation_id: str

class AgentCommunicationBus:
    def __init__(self):
        self.message_queue = asyncio.Queue()
        self.subscribers = {}
    
    async def send_message(self, message: AgentMessage):
        """Send message between agents"""
        pass
    
    async def subscribe(self, agent_id: str, callback: Callable):
        """Subscribe agent to receive messages"""
        pass
```

### 3. Persistent Memory System

#### Memory Management
```python
# backend/agents/memory.py
class ConversationMemory:
    def __init__(self, user_id: UUID):
        self.user_id = user_id
        self.conversation_history = []
        self.user_preferences = {}
        self.context_embeddings = []
    
    async def store_interaction(self, query: str, response: str, context: Dict):
        """Store user interaction in memory"""
        pass
    
    async def retrieve_relevant_context(self, current_query: str, limit: int = 5) -> List[MemoryItem]:
        """Retrieve relevant past interactions"""
        pass
    
    async def update_user_preferences(self, preferences: Dict):
        """Update user preferences and communication style"""
        pass

class UserPreferences:
    communication_tone: str  # formal, casual, technical
    preferred_response_length: str  # brief, detailed, comprehensive
    domain_expertise: List[str]  # areas of expertise
    notification_settings: Dict
```

### 4. Enhanced Document Processing

#### Document Ingestion Pipeline
```python
# backend/document_processing/ingestion.py
class EnhancedDocumentProcessor:
    def __init__(self):
        self.docling_processor = DoclingProcessor()
        self.llamaindex_processor = LlamaIndexProcessor()
        self.metadata_extractor = MetadataExtractor()
    
    async def process_document(self, file_path: str, metadata: DocumentMetadata) -> ProcessedDocument:
        """Process document with enhanced extraction capabilities"""
        # Extract content using Docling
        content = await self.docling_processor.extract_content(file_path)
        
        # Create structured representation with LlamaIndex
        structured_doc = await self.llamaindex_processor.create_document(content)
        
        # Extract and enhance metadata
        enhanced_metadata = await self.metadata_extractor.extract_metadata(file_path, content)
        
        # Generate embeddings
        embeddings = await self.generate_embeddings(structured_doc)
        
        return ProcessedDocument(
            content=structured_doc,
            metadata=enhanced_metadata,
            embeddings=embeddings
        )
```

### 5. End-to-End Encryption

#### Encryption Service
```python
# backend/encryption/service.py
class EncryptionService:
    def __init__(self):
        self.key_manager = KeyManager()
        self.cipher = AESCipher()
    
    async def encrypt_data_at_rest(self, data: bytes, data_type: str) -> EncryptedData:
        """Encrypt data for storage"""
        key = await self.key_manager.get_encryption_key(data_type)
        encrypted_data = self.cipher.encrypt(data, key)
        return EncryptedData(
            data=encrypted_data,
            key_id=key.id,
            algorithm="AES-256-GCM"
        )
    
    async def decrypt_data_at_rest(self, encrypted_data: EncryptedData) -> bytes:
        """Decrypt stored data"""
        key = await self.key_manager.get_key_by_id(encrypted_data.key_id)
        return self.cipher.decrypt(encrypted_data.data, key)
    
    def setup_tls_context(self) -> ssl.SSLContext:
        """Setup TLS context for data in transit"""
        pass
```

### 6. Monitoring Integration

#### Langfuse Integration
```python
# backend/monitoring/langfuse_client.py
class LangfuseMonitor:
    def __init__(self, api_key: str, host: str):
        self.client = Langfuse(api_key=api_key, host=host)
    
    async def track_llm_call(self, model: str, input_text: str, output_text: str, metadata: Dict):
        """Track LLM API calls"""
        self.client.generation(
            name="ollama_chat",
            model=model,
            input=input_text,
            output=output_text,
            metadata=metadata
        )
    
    async def track_user_interaction(self, user_id: str, query: str, response: str, satisfaction: float):
        """Track user interactions and satisfaction"""
        pass
    
    async def track_system_metrics(self, metrics: SystemMetrics):
        """Track system performance metrics"""
        pass
```

## Data Models

### Enhanced Document Model
```python
class DocumentMetadata(BaseModel):
    document_id: UUID
    filename: str
    file_type: str
    sensitivity_level: SensitivityLevel
    department: Optional[str]
    version: Optional[str]
    tags: List[str]
    access_permissions: Dict[str, List[str]]
    created_by: UUID
    created_at: datetime
    updated_at: datetime

class ProcessedDocument(BaseModel):
    id: UUID
    content: str
    structured_content: Dict
    metadata: DocumentMetadata
    embeddings: List[float]
    chunks: List[DocumentChunk]
```

### Agent Models
```python
class AgentPersonality(BaseModel):
    name: str
    description: str
    communication_style: str
    expertise_areas: List[str]
    response_patterns: Dict[str, str]

class AgentTask(BaseModel):
    task_id: UUID
    task_type: TaskType
    input_data: Dict[str, Any]
    context: Dict[str, Any]
    priority: int
    deadline: Optional[datetime]
```

## Error Handling

### Comprehensive Error Management
```python
class KnowledgeBaseException(Exception):
    """Base exception for knowledge base operations"""
    pass

class AuthorizationError(KnowledgeBaseException):
    """Raised when user lacks required permissions"""
    pass

class EncryptionError(KnowledgeBaseException):
    """Raised when encryption/decryption fails"""
    pass

class AgentCommunicationError(KnowledgeBaseException):
    """Raised when agent communication fails"""
    pass

# Error handling middleware
@app.middleware("http")
async def error_handling_middleware(request: Request, call_next):
    try:
        response = await call_next(request)
        return response
    except AuthorizationError as e:
        return JSONResponse(
            status_code=403,
            content={"error": "Authorization failed", "detail": str(e)}
        )
    except EncryptionError as e:
        logger.error(f"Encryption error: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": "Security operation failed"}
        )
```

## Testing Strategy

### Unit Testing
- Test individual components (RBAC, encryption, agents) in isolation
- Mock external dependencies (Ollama, ChromaDB)
- Test error conditions and edge cases

### Integration Testing
- Test service-to-service communication
- Test end-to-end workflows (document upload, query processing)
- Test agent coordination and communication

### Security Testing
- Test RBAC enforcement
- Test encryption/decryption operations
- Test authentication and authorization flows
- Penetration testing for security vulnerabilities

### Performance Testing
- Load testing for concurrent users
- Performance testing for large document collections
- Agent coordination performance under load
- Memory usage and optimization testing