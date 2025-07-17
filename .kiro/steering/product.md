# DeepResearch - Self-Hosted AI Knowledge Base Assistant

DeepResearch is a comprehensive self-hosted AI knowledge base assistant that prioritizes data privacy and isolation while providing efficient access to organizational knowledge through document processing, web search, AI-powered assistance, and Python code execution capabilities.

## Current Features

- **Document Processing**: Upload and process various document types (PDF, DOCX, TXT, etc.) with vector search across document collections
- **Web Research**: Search the web and extract content from web pages, combining results with local documents
- **AI-Powered Assistance**: Ask questions about documents and web content with contextual answers and citations using local LLM models
- **Python Code Execution**: Write and execute Python code with data visualizations and persistent sessions
- **Modern UI**: Responsive React/TypeScript frontend with real-time feedback and dark mode support
- **Basic Authentication**: JWT-based authentication with demo user support

## Target Features (PRD Alignment)

- **Enhanced RBAC**: Granular role-based access control for documents and features
- **Metadata Tagging**: Tag documents with attributes like sensitivity, department, and version
- **Persistent Memory**: AI's ability to retain context and remember past interactions
- **Personalized Content Creation**: Generate content in user's specified tone
- **Multi-node Agent Architecture**: Orchestration of multiple AI agents for complex tasks
- **Agent-to-Agent Communication**: Enable seamless information exchange between AI agents
- **Complete Offline Mode**: Full functionality without external internet connectivity
- **End-to-End Encryption**: Encryption of data at rest and in transit
- **System Monitoring**: Integration with Langfuse for tracking performance and usage

## Architecture

The system uses a microservices architecture with:
- React/TypeScript frontend (port 5173)
- FastAPI backend with streaming support (port 8001)
- ChromaDB vector database (port 8000)
- Python executor service (port 3001)
- Ollama LLM inference service (port 11434)

## Key Dependencies

- **LLM Models**: Uses Ollama with configurable models (default: gemma3:1b-it-qat for chat, nomic-embed-text for embeddings)
- **Vector Database**: ChromaDB for document and web content storage
- **Document Processing**: PyPDF2, python-docx, BeautifulSoup4
- **Authentication**: JWT with python-jose and passlib (to be enhanced with RBAC)