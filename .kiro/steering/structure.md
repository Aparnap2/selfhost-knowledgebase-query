# Project Structure & Organization

## Current Structure

### Root Directory Structure
```
├── .kiro/                    # Kiro IDE configuration and steering
├── backend/                  # FastAPI Python backend service
├── frontend/                 # React TypeScript frontend application
├── python-executor/          # Node.js service for Python code execution
├── data/                     # Persistent data storage (SQLite, plots)
├── docker-compose.yml        # Multi-service container orchestration
├── start-services.sh         # Service startup script
├── debug.sh                  # Debugging utilities
└── README.md                 # Project documentation
```

### Backend Service (`/backend`)
```
backend/
├── main.py                   # FastAPI application entry point
├── ollama_client.py          # Ollama LLM client wrapper
├── web_search.py             # Web search and content extraction
├── test_web_search.py        # Web search tests
├── requirements.txt          # Python dependencies
├── Dockerfile                # Backend container configuration
├── cache/                    # Web search cache storage
└── logs/                     # Application logs
```

### Frontend Application (`/frontend`)
```
frontend/
├── src/
│   ├── App.tsx              # Main application component
│   ├── main.tsx             # Application entry point
│   ├── components/          # Reusable React components
│   │   ├── Alert.jsx        # Alert/notification component
│   │   ├── CitationList.jsx # Source citations display
│   │   ├── Login.jsx        # Authentication component
│   │   ├── PythonExecutor.tsx # Code execution interface
│   │   └── WebSearch.tsx    # Web search interface
│   └── styles/              # Component-specific styles
├── public/                  # Static assets
├── package.json             # Node.js dependencies and scripts
├── tsconfig.json            # TypeScript configuration
├── vite.config.ts           # Vite build configuration
└── Dockerfile               # Frontend container configuration
```

### Python Executor Service (`/python-executor`)
```
python-executor/
├── server.js                # Node.js server for Python execution
├── healthcheck.py           # Service health monitoring
├── package.json             # Node.js dependencies
├── requirements.txt         # Python dependencies for execution
├── Dockerfile               # Container configuration
├── plots/                   # Generated visualization storage
├── sessions/                # Python session persistence
└── tmp/                     # Temporary execution files
```

## Target Structure (PRD Alignment)

### Enhanced Backend Structure
```
backend/
├── main.py                   # FastAPI application entry point
├── ollama_client.py          # Ollama LLM client wrapper
├── web_search.py             # Web search and content extraction
├── auth/                     # Enhanced authentication and RBAC
│   ├── models.py             # User and role models
│   ├── permissions.py        # Permission definitions
│   └── rbac.py               # Role-based access control
├── agents/                   # Multi-agent architecture
│   ├── coordinator.py        # Agent orchestration
│   ├── personalities.py      # Agent personality definitions
│   ├── communication.py      # A2A communication protocol
│   └── memory.py             # Persistent memory management
├── document_processing/      # Enhanced document processing
│   ├── ingestion.py          # Document ingestion pipeline
│   ├── metadata.py           # Document metadata management
│   └── tagging.py            # Document tagging system
├── encryption/               # End-to-end encryption
│   ├── at_rest.py            # Data at rest encryption
│   └── in_transit.py         # Data in transit encryption
├── monitoring/               # System monitoring
│   └── langfuse_client.py    # Langfuse integration
├── requirements.txt          # Python dependencies
├── Dockerfile                # Backend container configuration
├── cache/                    # Web search cache storage
└── logs/                     # Application logs
```

### New Components
- **Monitoring Service**: Integration with Langfuse for system monitoring
- **Agent Coordination Service**: For multi-agent orchestration
- **Encryption Service**: For end-to-end data encryption
- **Metadata Management**: For document tagging and access control

## Data Directory Enhancement (`/data`)
- `notebooklm.db` - SQLite database for document metadata
- `agents/` - Agent definitions and configurations
- `memory/` - Persistent conversation memory
- `metadata/` - Document metadata and tagging information
- `encryption/` - Encryption keys and configurations
- Generated plots and visualizations
- Persistent storage mounted across containers

## Key Conventions

### File Naming
- React components: PascalCase (e.g., `PythonExecutor.tsx`)
- Python modules: snake_case (e.g., `web_search.py`)
- Configuration files: lowercase with extensions (e.g., `docker-compose.yml`)

### Component Organization
- Frontend components are organized by functionality in `/src/components`
- Backend modules are organized by feature (client, search, auth, agents)
- Each service has its own Dockerfile and dependency management

### Data Flow
- Frontend communicates with backend via REST API (port 8001)
- Backend integrates with ChromaDB (port 8000) and Ollama (port 11434)
- Python executor runs as separate service (port 3001)
- Agent communication through dedicated A2A protocol
- All services connected via Docker bridge network

### Environment Configuration
- Service-specific environment variables in docker-compose.yml
- Frontend environment variables prefixed with `VITE_`
- Backend configuration through environment variables and defaults
- Security configuration in dedicated environment files

## Implementation Priorities
1. Enhance authentication with RBAC structure
2. Implement document metadata and tagging system
3. Develop agent architecture and communication protocol
4. Add persistent memory for conversations
5. Integrate monitoring with Langfuse
6. Implement end-to-end encryption