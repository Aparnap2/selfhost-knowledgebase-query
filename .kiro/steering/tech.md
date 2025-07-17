# Technology Stack & Build System

## Current Implementation

### Frontend Stack
- **Framework**: React 19 with TypeScript
- **Build Tool**: Vite 6.3.1
- **Styling**: Styled Components 6.1.8
- **HTTP Client**: Axios 1.9.0
- **Linting**: ESLint with TypeScript support

### Backend Stack
- **Framework**: FastAPI 0.115.0 with Python
- **Server**: Uvicorn 0.30.6
- **AI/ML**: Ollama 0.3.3, ChromaDB 0.5.5, Transformers 4.44.2
- **Database**: SQLite3 with Pandas for data processing
- **Authentication**: JWT with python-jose and passlib (basic implementation)
- **Web Scraping**: BeautifulSoup4, crawl4ai, requests

### Python Executor Service
- **Runtime**: Node.js with Python subprocess execution
- **Session Management**: UUID-based session handling
- **Visualization**: Matplotlib support with persistent plot storage

### Infrastructure
- **Containerization**: Docker with Docker Compose
- **Vector Database**: ChromaDB 0.5.5
- **LLM Service**: Ollama (external container)
- **Networking**: Custom Docker bridge network (booklm_network)

## Target Implementation (PRD Alignment)

### Security Enhancements
- **RBAC System**: Comprehensive role-based access control
- **End-to-End Encryption**: Data encryption at rest and in transit
- **Metadata Management**: Document tagging and access control
- **Complete Offline Mode**: Full functionality without internet connectivity

### AI & Agent Architecture
- **Document Processing**: Enhanced with Docling and Llamaindex
- **Multi-Agent Framework**: For orchestrating multiple specialized AI agents
- **Agent Communication**: Protocol for A2A information exchange
- **Graph RAG**: For defining and influencing agent personalities
- **Global Context RAG**: For maintaining context across agent communications

### Monitoring & Production Readiness
- **System Monitoring**: Integration with Langfuse
- **Scalability**: Horizontal scaling capabilities
- **High Availability**: Production-grade reliability
- **Comprehensive Logging**: Enhanced error tracking and performance metrics

## Common Commands

### Development
```bash
# Start all services
./start-services.sh

# Development mode (individual services)
docker-compose up -d chroma
docker-compose up -d backend
cd frontend && npm run dev
cd python-executor && npm run dev

# View logs
docker-compose logs -f

# Stop services
docker-compose down
```

### Frontend Development
```bash
cd frontend
npm run dev          # Development server
npm run build        # Production build
npm run lint         # ESLint check
npm run preview      # Preview production build
```

### Debugging
```bash
./debug.sh           # Run debug script
docker logs <container_name>  # View container logs
```

## Environment Configuration
- Frontend: `.env` file with `VITE_API_URL`
- Backend: Environment variables for Ollama, ChromaDB, and database paths
- All services: Configurable through docker-compose.yml environment section

## Development Roadmap
1. Enhance authentication with full RBAC implementation
2. Implement document metadata tagging system
3. Develop persistent memory for conversations
4. Build multi-agent architecture and communication protocol
5. Integrate Langfuse monitoring
6. Implement end-to-end encryption
7. Ensure complete offline functionality