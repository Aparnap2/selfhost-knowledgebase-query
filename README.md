# Enhanced Knowledge Base Assistant

Enterprise-grade self-hosted AI knowledge base with multi-agent coordination, advanced document processing, and comprehensive security features.

## 🚀 Key Features

- **🤖 Multi-Agent Architecture**
  - Specialized agents using LangChain and LlamaIndex
  - LangGraph coordination for complex queries
  - Intelligent task routing and result synthesis

- **📄 Enhanced Document Processing**
  - Docling integration for advanced parsing
  - LlamaIndex for semantic understanding
  - Complex document structure preservation

- **🔐 Enterprise Security**
  - Role-based access control (RBAC)
  - Data encryption at rest
  - Document sensitivity levels

- **💾 Persistent Memory**
  - Conversation history preservation
  - User preference learning
  - Context-aware responses

- **📊 Monitoring & Analytics**
  - Langfuse LLM call tracking
  - Performance metrics
  - System health monitoring

- **🌐 Complete Offline Mode**
  - Full offline functionality
  - Local Ollama inference
  - Automatic connectivity detection

## Prerequisites

- Docker and Docker Compose
- Ollama (running locally)
- At least 4GB of RAM
- 10GB of free disk space

## Quick Start

1. Ensure Ollama is running:
   ```
   docker run -d --name ollama -p 11434:11434 -v ollama_data:/root/.ollama ollama/ollama
   ```

2. Pull the models you want to use:
   ```
   curl -X POST http://localhost:11434/api/pull -d '{"model":"gemma3:1b-it-qat"}'
   curl -X POST http://localhost:11434/api/pull -d '{"model":"nomic-embed-text"}'
   ```

3. Clone this repository:
   ```
   git clone https://github.com/yourusername/self_host_booklm.git
   cd self_host_booklm
   ```

4. Start the services:
   ```
   ./start-services.sh
   ```

5. Access the application at http://localhost:5173

## Services

- **Frontend**: React application with TypeScript (port 5173)
- **Backend**: FastAPI server with multi-agent coordination (port 8001)
- **ChromaDB**: Vector database with LlamaIndex integration (port 8000)
- **Python Executor**: Code execution with session support (port 3001)
- **Langfuse**: LLM monitoring and analytics (port 3000)
- **Ollama**: Local LLM inference service (port 11434)

## Configuration

You can configure the application by setting environment variables in the `.env` file:

```
# Ollama Configuration
MODEL_NAME=gemma3:1b-it-qat
EMBEDDING_MODEL=nomic-embed-text
OLLAMA_TEMPERATURE=0.7

# Web Search Configuration
SEARCH_ENGINE=https://www.google.com/search?q=
SEARCH_USE_CACHE=true
SEARCH_CACHE_TTL=86400
```

## Troubleshooting

If you encounter issues, run the debug script:
```
./debug.sh
```

Common issues and solutions:

1. **Ollama connectivity**: Ensure Ollama is running and accessible at `http://localhost:11434`
2. **Containers not starting**: Check logs with `docker logs <container_name>`
3. **Services can't connect**: Ensure all containers are on the same network with `docker network connect booklm_network ollama`
4. **Python executor fails**: Check permissions for the volumes
5. **UI issues**: Clear browser cache or try a different browser

## Development

To run services in development mode:

```
docker-compose up -d chroma
docker-compose up -d backend
cd frontend && npm run dev
cd python-executor && npm run dev
```

## Recent Updates

- ✅ Multi-agent architecture with LangGraph
- ✅ Enhanced document processing with Docling
- ✅ RBAC system with granular permissions
- ✅ Conversation memory and user preferences
- ✅ Langfuse monitoring integration
- ✅ Basic encryption service
- ✅ Complete offline mode support

## Roadmap

- [ ] Frontend admin panels for user/role management
- [ ] TLS configuration for data in transit
- [ ] Comprehensive test suite
- [ ] Performance optimization
- [ ] Advanced agent personalities
- [ ] Knowledge graph visualization

## License

This project is licensed under the MIT License - see the LICENSE file for details.