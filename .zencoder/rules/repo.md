---
description: Repository Information Overview
alwaysApply: true
---

# Enhanced Knowledge Base Assistant Information

## Summary
Enterprise-grade self-hosted AI knowledge base with multi-agent coordination, advanced document processing, and comprehensive security features. The system uses LangChain and LlamaIndex for specialized agents, provides enhanced document processing, enterprise security features, persistent memory, monitoring capabilities, and complete offline mode functionality.

## Structure
- **backend/**: FastAPI server with multi-agent coordination
- **frontend/**: React application with TypeScript
- **python-executor/**: Code execution service with session support
- **data/**: Storage for database files and persistent data
- **.kiro/**: Project specifications and steering documents
- **docker-compose.yml**: Main service orchestration configuration

## Projects

### Backend (FastAPI Server)

#### Language & Runtime
**Language**: Python
**Version**: 3.11
**Framework**: FastAPI 0.115.0
**Package Manager**: pip

#### Dependencies
**Main Dependencies**:
- fastapi==0.115.0
- uvicorn==0.30.6
- ollama==0.3.3
- chromadb==0.5.5
- llamaindex==0.11.20
- langchain==0.3.7
- langgraph==0.2.45
- docling==2.5.2
- langfuse==2.56.0
- cryptography==43.0.1

#### Build & Installation
```bash
pip install -r backend/requirements.txt
```

#### Docker
**Dockerfile**: backend/Dockerfile
**Base Image**: python:3.11-slim
**Run Command**: uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info

### Frontend (React Application)

#### Language & Runtime
**Language**: TypeScript/JavaScript
**Version**: Node.js 18
**Framework**: React 19.0.0, Vite 6.3.1
**Package Manager**: npm

#### Dependencies
**Main Dependencies**:
- react==19.0.0
- react-dom==19.0.0
- axios==1.9.0
- styled-components==6.1.8
**Development Dependencies**:
- typescript==5.4.5
- vite==6.3.1
- eslint==9.22.0

#### Build & Installation
```bash
cd frontend
npm install
npm run dev
```

#### Docker
**Dockerfile**: frontend/Dockerfile
**Base Image**: node:18-alpine
**Run Command**: npm run dev -- --host 0.0.0.0 --port 5173

### Python Executor (Code Execution Service)

#### Language & Runtime
**Language**: JavaScript (Node.js) with Python integration
**Version**: Node.js 18, Python 3.11
**Package Manager**: npm, pip

#### Dependencies
**Node.js Dependencies**:
- uuid==9.0.1
**Python Dependencies**:
- pandas==2.2.2
- numpy==1.26.4
- matplotlib==3.9.2

#### Build & Installation
```bash
cd python-executor
npm install
pip install -r requirements.txt
```

#### Docker
**Dockerfile**: python-executor/Dockerfile
**Base Image**: python:3.11-slim with Node.js 18
**Run Command**: node server.js

## System Configuration

### Docker Compose Setup
**Services**:
- chroma: Vector database (port 8000)
- backend: FastAPI server (port 8001)
- frontend: React application (port 5173)
- python-executor: Code execution service (port 3001)
- langfuse: LLM monitoring (port 3000)

### Deployment
**Start Command**:
```bash
./start-services.sh
```

**Prerequisites**:
- Docker and Docker Compose
- Ollama (running locally)
- At least 4GB of RAM
- 10GB of free disk space

### External Dependencies
- Ollama: Local LLM inference service (port 11434)
- Required models: gemma3:1b-it-qat, nomic-embed-text