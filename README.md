# DeepResearch - Self-Hosted Research Assistant

DeepResearch is a self-hosted research assistant that allows you to upload documents, search the web, ask questions about your data, and execute Python code with visualizations.

## Features

- **Document Processing**
  - Upload and process various document types (PDF, DOCX, TXT, etc.)
  - Extract text and metadata from documents
  - Vector search across your document collection

- **Web Research**
  - Search the web for information
  - Extract content from web pages
  - Combine web search results with your documents

- **AI-Powered Assistance**
  - Ask questions about your documents and web content
  - Get contextual answers with citations
  - Streaming responses for better user experience

- **Python Code Execution**
  - Write and execute Python code
  - Create data visualizations with matplotlib
  - Persistent sessions for multi-step analysis
  - Support for common data science libraries

- **Modern UI**
  - Responsive design for desktop and mobile
  - Real-time feedback and progress indicators
  - Dark mode support

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
- **Backend**: FastAPI server with streaming support (port 8001)
- **Chroma**: Vector database for document and web content storage (port 8000)
- **Python Executor**: Enhanced code execution service with session support (port 3001)
- **Ollama**: LLM inference service (port 11434)

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

## Roadmap

- [ ] Knowledge graph visualization
- [ ] Support for more document types (PPT, Excel, etc.)
- [ ] OCR for images and scanned documents
- [ ] Multi-user support with authentication
- [ ] Plugin system for extensibility
- [ ] Workflow automation

## License

This project is licensed under the MIT License - see the LICENSE file for details.