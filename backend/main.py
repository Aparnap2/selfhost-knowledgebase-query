from fastapi import FastAPI, File, UploadFile, HTTPException, Depends, status, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from fastapi_limiter import FastAPILimiter
from fastapi_limiter.depends import RateLimiter
from starlette.middleware.csrf import CSRFMiddleware
from starlette.middleware import Middleware
from pydantic import BaseModel, Field, validator
import chromadb
import faiss
import numpy as np
import sqlite3
import pandas as pd
import matplotlib.pyplot as plt
import os
import uuid
import subprocess
import aiohttp
import requests
import json
import redis.asyncio as redis
from typing import List, Dict, Optional, Any, Union
from loguru import logger
import asyncio
from jose import JWTError, jwt
from passlib.context import CryptContext
from datetime import datetime, timedelta
import traceback
import secure
import tempfile
from sqlalchemy.orm import Session

# Configure loguru logger
logger.remove()
logger.add(
    "logs/notebooklm.log",
    rotation="10 MB",
    retention="1 week",
    level=os.getenv("LOGLEVEL", "INFO"),
    format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)

# JWT Config
SECRET_KEY = os.getenv("SECRET_KEY", "notebooklm-secret-key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/login")

# In-memory demo user
fake_users_db = {
    "demo": {
        "username": "demo",
        "full_name": "Demo User",
        "hashed_password": pwd_context.hash("demo123"),
        "disabled": False,
    }
}

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_user(db, username: str):
    user = db.get(username)
    if user:
        return user
    return None

def authenticate_user(db, username: str, password: str):
    user = get_user(db, username)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username)
    if user is None:
        raise credentials_exception
    return user

# Import our improved Ollama client
from ollama_client import OllamaClient

# Security headers configuration
security_headers = secure.Secure()

# Create middleware list
middleware = [
    Middleware(
        CORSMiddleware,
        allow_origins=[os.getenv("ALLOWED_ORIGINS", "*")],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["*"],
    ),
    # Add CSRF protection
    Middleware(
        CSRFMiddleware,
        secret=os.getenv("CSRF_SECRET", "notebooklm-csrf-secret"),
    ),
]

app = FastAPI(
    title="NotebookLM API",
    description="API for NotebookLM document assistant",
    version="1.0.0",
    middleware=middleware,
)

# Add security headers middleware
@app.middleware("http")
async def set_secure_headers(request: Request, call_next):
    response = await call_next(request)
    security_headers.framework.fastapi(response)
    return response

# Add request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = datetime.utcnow()
    method = request.method
    path = request.url.path
    
    logger.info(f"Request: {method} {path}")
    
    try:
        response = await call_next(request)
        process_time = (datetime.utcnow() - start_time).total_seconds() * 1000
        logger.info(f"Response: {method} {path} - Status: {response.status_code} - Time: {process_time:.2f}ms")
        return response
    except Exception as e:
        logger.error(f"Error processing request {method} {path}: {str(e)}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"},
        )

# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception: {str(exc)}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred"},
    )

# Auth endpoints
@app.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}

# Configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://ollama:11434")  # Use internal port for container communication
CHROMA_HOST = os.getenv("CHROMA_HOST", "http://chroma:8000")
DB_PATH = os.getenv("DB_PATH", "/data/notebooklm.db")
MODEL_NAME = os.getenv("MODEL_NAME", "gemma3:1b-it-qat")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "nomic-embed-text:latest")  # Make sure this matches the model name exactly
OLLAMA_REQUIRED = True  # Set to True since we want to use the actual Ollama models

# Initialize Ollama client
ollama_client = OllamaClient(OLLAMA_HOST)

# Get database dependency
def get_db():
    """Database session dependency."""
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import create_engine
    
    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.on_event("startup")
async def startup_event():
    # Initialize the Ollama client
    await ollama_client.initialize()
    logger.info(f"Initialized Ollama client with host: {OLLAMA_HOST}")
    logger.info(f"Using models - Chat: {MODEL_NAME}, Embedding: {EMBEDDING_MODEL}")
    
    # Initialize web search client
    await web_search.initialize()
    logger.info("Initialized web search client")
    
    # Initialize rate limiter if Redis URL is provided
    redis_url = os.getenv("REDIS_URL")
    if redis_url:
        try:
            redis_instance = redis.from_url(redis_url)
            await FastAPILimiter.init(redis_instance)
            logger.info("Rate limiter initialized with Redis")
        except Exception as e:
            logger.error(f"Failed to initialize rate limiter: {str(e)}")
            logger.warning("Rate limiting will be disabled")
    else:
        logger.warning("REDIS_URL not provided, rate limiting will be disabled")

@app.on_event("shutdown")
async def shutdown_event():
    # Close the Ollama client session
    await ollama_client.close()
    logger.info("Closed Ollama client session")
    
    # Close the web search client session
    await web_search.close()
    logger.info("Closed web search client session")

# Import web search module
from web_search import WebSearch

# Import auth, document processing, conversation, and config routes
from auth.routes import router as auth_router
from document_processing.routes import router as metadata_router
from conversation.routes import router as conversation_router
from config.routes import router as config_router

# Include routers
app.include_router(auth_router)
app.include_router(metadata_router)
app.include_router(conversation_router)
app.include_router(config_router)

# Initialize components
# Use service name for Chroma in Docker Compose environment
chroma_host = "chroma"  # Service name from docker-compose.yml
chroma_port = 8000

# Initialize Chroma client
client = chromadb.HttpClient(host=chroma_host, port=chroma_port)
collection = client.get_or_create_collection("documents", metadata={"hnsw:space": "cosine"})
web_collection = client.get_or_create_collection("web_content", metadata={"hnsw:space": "cosine"})
dimension = 768  # Updated dimension for nomic-embed-text
faiss_index = faiss.IndexFlatL2(dimension)

# Initialize web search client
web_search = WebSearch()

# SQLite setup
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS documents
                 (id TEXT PRIMARY KEY, filename TEXT, content TEXT)''')
conn.commit()

class QueryRequest(BaseModel):
    query: str
    top_k: int = 5

class ExecuteCodeRequest(BaseModel):
    code: str

async def get_mock_embedding(text: str) -> List[float]:
    import hashlib
    import struct
    
    # Define a fixed dimension for the mock embedding
    dimension = 768  # Common dimension for small embedding models
    
    # Create a deterministic but simple embedding from the text
    hash_obj = hashlib.md5(text.encode('utf-8'))
    hash_bytes = hash_obj.digest()
    
    # Use the hash to seed a simple embedding
    mock_embedding = []
    for i in range(0, len(hash_bytes), 4):
        if i + 4 <= len(hash_bytes):
            val = struct.unpack('f', hash_bytes[i:i+4])[0]
            mock_embedding.append(val)
    
    # Pad to dimension size
    while len(mock_embedding) < dimension:
        mock_embedding.append(0.0)
    
    # Normalize the embedding
    import math
    norm = math.sqrt(sum(x*x for x in mock_embedding))
    if norm > 0:
        mock_embedding = [x/norm for x in mock_embedding]
    
    return mock_embedding[:dimension]

async def get_embedding(text: str) -> List[float]:
    """Generate embeddings for text using Ollama or fallback to mock embeddings"""
    # Ensure we have valid text to embed
    if not text or not text.strip():
        logger.warning("Empty or whitespace-only text provided for embedding")
        text = " "  # Fallback to space to avoid empty string
    
    # Try to get embeddings from Ollama
    try:
        logger.info(f"Generating embeddings for text using model: {EMBEDDING_MODEL}")
        logger.debug(f"Text to embed (first 100 chars): {text[:100]}...")
        
        # Log the Ollama client configuration
        logger.debug(f"Ollama client base URL: {ollama_client.base_url}")
        logger.debug(f"Ollama client session: {'initialized' if ollama_client.session else 'not initialized'}")
        
        # Generate embeddings
        embeddings = await ollama_client.generate_embeddings(EMBEDDING_MODEL, text)
        
        if not embeddings:
            error_msg = "Received empty embeddings from Ollama"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        if not isinstance(embeddings, list) or not all(isinstance(x, (int, float)) for x in embeddings):
            error_msg = f"Unexpected embeddings format: {type(embeddings)}"
            logger.error(error_msg)
            raise ValueError(error_msg)
            
        logger.info(f"Successfully generated embeddings of length: {len(embeddings)}")
        return embeddings
        
    except Exception as e:
        error_msg = f"Ollama embedding error: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        if OLLAMA_REQUIRED:
            raise HTTPException(
                status_code=503,
                detail=f"Ollama service required but unavailable: {str(e)}"
            )
    
    # Fallback to mock embeddings if Ollama is not available and not required
    logger.warning("Falling back to mock embeddings")
    return get_mock_embedding(text)

@app.get("/health")
async def health():
    # Always return healthy for health checks
    return {"status": "healthy"}

@app.get("/files")
async def get_files(user: dict = Depends(get_current_user)):
    try:
        cursor.execute("SELECT id, filename FROM documents")
        files = [{"id": row[0], "filename": row[1]} for row in cursor.fetchall()]
        return files
    except Exception as e:
        logger.error(f"Error fetching files: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch files")

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...), 
    user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
    rate_limiter: None = Depends(RateLimiter(times=10, seconds=60)) # 10 uploads per minute
):
    try:
        content = await file.read()
        
        # Determine file type and extract text accordingly
        file_extension = os.path.splitext(file.filename)[1].lower()
        
        # Handle different file types
        if file_extension in ['.pdf']:
            # For PDF files, we need to use a PDF parser
            logger.info(f"Processing PDF file: {file.filename}")
            try:
                import io
                from PyPDF2 import PdfReader
                pdf = PdfReader(io.BytesIO(content))
                text = ""
                for page in pdf.pages:
                    text += page.extract_text() + "\n"
            except ImportError:
                logger.warning("PyPDF2 not installed. Treating PDF as binary.")
                text = f"Binary PDF file: {file.filename}"
        elif file_extension in ['.docx', '.doc']:
            # For Word documents
            logger.info(f"Processing Word file: {file.filename}")
            try:
                import io
                from docx import Document
                doc = Document(io.BytesIO(content))
                text = "\n".join([para.text for para in doc.paragraphs])
            except ImportError:
                logger.warning("python-docx not installed. Treating Word file as binary.")
                text = f"Binary Word file: {file.filename}"
        elif file_extension in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv']:
            # For text files, try UTF-8 decoding
            logger.info(f"Processing text file: {file.filename}")
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                # If UTF-8 fails, try with error handling
                text = content.decode("utf-8", errors="replace")
        else:
            # For other binary files, just store metadata
            logger.info(f"Processing binary file: {file.filename}")
            text = f"Binary file: {file.filename}"
        
        doc_id = str(uuid.uuid4())
        
        # Store in SQLite
        cursor.execute("INSERT INTO documents (id, filename, content) VALUES (?, ?, ?)",
                      (doc_id, file.filename, text))
        conn.commit()
        
        # Generate embedding
        embedding = await get_embedding(text)
        
        # Extract metadata using our new metadata extraction service
        from document_processing.metadata import MetadataExtractor
        
        # Create a temporary file to extract metadata
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # Extract metadata
            extractor = MetadataExtractor(db)
            metadata = extractor.extract_metadata(
                temp_path,
                content=text,
                user_id=user.get("id")  # Use user ID if available
            )
            
            # Add filename and file type
            metadata["filename"] = file.filename
            metadata["file_type"] = file_extension
            
            # Store metadata in database
            doc_metadata = extractor.store_metadata(doc_id, metadata, user.get("id"))
            logger.info(f"Stored metadata for document: {doc_id}")
            
            # Use extracted metadata for Chroma
            chroma_metadata = {
                "filename": file.filename,
                "file_type": file_extension,
                "sensitivity": metadata.get("sensitivity", "internal"),
                "department": metadata.get("department", "general")
            }
            
            # Add tags if available
            if "tags" in metadata and metadata["tags"]:
                chroma_metadata["tags"] = ",".join(metadata["tags"])
                
        except Exception as e:
            logger.warning(f"Error extracting metadata: {str(e)}")
            # Fallback to basic metadata
            chroma_metadata = {"filename": file.filename, "file_type": file_extension}
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
        
        # Store in Chroma with enhanced metadata
        collection.add(
            documents=[text],
            embeddings=[embedding],
            ids=[doc_id],
            metadatas=[chroma_metadata]
        )
        
        # Add to FAISS
        faiss_index.add(np.array([embedding], dtype='float32'))
        
        return {"id": doc_id, "filename": file.filename}
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process file: {str(e)}")

from fastapi.responses import StreamingResponse

class StreamingQueryRequest(QueryRequest):
    stream: bool = False

@app.post("/query")
async def query(
    request: StreamingQueryRequest, 
    user: dict = Depends(get_current_user),
    rate_limiter: None = Depends(RateLimiter(times=5, seconds=60)) # 5 requests per minute
):
    try:
        # Generate query embedding
        query_embedding = await get_embedding(request.query)
        
        # Search Chroma if available, otherwise provide a fallback
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=request.top_k,
            include=["documents", "metadatas", "distances"]
        )
        
        # Helper to format sources
        def format_source(id, doc, meta, dist):
            cursor.execute("SELECT filename, content FROM documents WHERE id = ?", (id,))
            filename, content = cursor.fetchone()
            return {
                "id": id,
                "filename": filename,
                "snippet": content[:200],
                "distance": dist
            }

        # Retrieve sources
        sources = [format_source(id, doc, meta, dist)
                   for id, doc, meta, dist in zip(
                        results["ids"][0], results["documents"][0], results["metadatas"][0], results["distances"][0]
                    )]
        
        # Check if we should include web search results
        include_web = any(keyword in request.query.lower() for keyword in ["search", "web", "internet", "online", "find"])
        web_results = []
        
        if include_web:
            try:
                # Perform a web search
                search_results = await web_search.search(
                    query=request.query,
                    num_results=3  # Limit to 3 results
                )
                
                if search_results.get("results"):
                    # Extract content from the first result
                    result = search_results["results"][0]
                    content_data = await web_search.extract_content(result["link"])
                    
                    if content_data["success"]:
                        web_results.append({
                            "title": result["title"],
                            "url": result["link"],
                            "snippet": result["snippet"],
                            "content": content_data["content"][:1000]  # Limit content length
                        })
                        
                        # Also search the web collection
                        web_query_embedding = await get_embedding(request.query)
                        web_search_results = web_collection.query(
                            query_embeddings=[web_query_embedding],
                            n_results=2,
                            include=["documents", "metadatas", "distances"]
                        )
                        
                        if web_search_results["ids"][0]:
                            for i, doc_id in enumerate(web_search_results["ids"][0]):
                                web_results.append({
                                    "title": web_search_results["metadatas"][0][i].get("title", "Unknown"),
                                    "url": web_search_results["metadatas"][0][i].get("url", "#"),
                                    "content": web_search_results["documents"][0][i][:1000]  # Limit content length
                                })
            except Exception as e:
                logger.error(f"Error including web results: {str(e)}")
        
        # Generate response with Ollama
        document_context = "\n".join([src["snippet"] for src in sources])
        web_context = "\n\n".join([f"Web: {r['title']}\nURL: {r['url']}\n{r['content']}" for r in web_results]) if web_results else ""
        
        # Combine contexts
        if document_context and web_context:
            context = f"Document Context:\n{document_context}\n\nWeb Context:\n{web_context}"
        elif web_context:
            context = f"Web Context:\n{web_context}"
        else:
            context = document_context
        
        prompt = f"Based on the following context:\n{context}\n\nAnswer the query: {request.query}\n\nProvide citations to the documents and web sources where applicable."
        
        # Generate visualization if quantitative
        visualization = None
        if any(keyword in request.query.lower() for keyword in ["analyze", "plot", "chart"]):
            visualization = await generate_visualization(context)
        
        # Handle streaming response if requested
        if request.stream:
            async def stream_response():
                try:
                    # Send the sources and visualization as the first chunk
                    initial_data = {
                        "type": "metadata",
                        "sources": sources,
                        "visualization": visualization
                    }
                    yield json.dumps(initial_data) + "\n"
                    
                    # Stream the response from Ollama
                    async for chunk in ollama_client.chat(
                        model=MODEL_NAME,
                        messages=[{"role": "user", "content": prompt}],
                        stream=True,
                        temperature=0.7
                    ):
                        if "message" in chunk and "content" in chunk["message"]:
                            yield json.dumps({
                                "type": "content",
                                "content": chunk["message"]["content"]
                            }) + "\n"
                except Exception as e:
                    logger.error(f"Streaming error: {str(e)}")
                    yield json.dumps({
                        "type": "error",
                        "error": str(e)
                    }) + "\n"
            
            return StreamingResponse(
                stream_response(),
                media_type="application/x-ndjson"
            )
        
        # Non-streaming response
        try:
            # Use our custom Ollama client to generate a response
            response = await ollama_client.chat(
                model=MODEL_NAME,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7
            )
            
            # Log successful response
            logger.info(f"Successfully received response from Ollama model: {MODEL_NAME}")
            
        except Exception as e:
            logger.error(f"Ollama chat error: {str(e)}")
            if OLLAMA_REQUIRED:
                # Since Ollama is required, we'll raise an exception
                raise HTTPException(
                    status_code=503, 
                    detail=f"Ollama service required but unavailable: {str(e)}"
                )
            else:
                # Provide a fallback response
                response = {
                    "message": {
                        "content": f"Here are the relevant documents for your query: '{request.query}'\n\n" + 
                                  "\n\n".join([f"Document: {src['filename']}\nExcerpt: {src['snippet']}..." for src in sources])
                    }
                }
        
        return {
            "response": response["message"]["content"],
            "sources": sources,
            "visualization": visualization
        }
    except HTTPException:
        # Re-raise HTTPExceptions to be handled by FastAPI
        raise
    except Exception as e:
        logger.error(f"Query error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to process query")

async def generate_visualization(context: str):
    try:
        df = pd.read_csv(pd.compat.StringIO(context)) if "," in context else None
        if df is not None and not df.empty:
            plt.figure(figsize=(8, 6))
            df.plot()
            plt.tight_layout()
            output_path = f"/data/plot_{uuid.uuid4()}.png"
            plt.savefig(output_path)
            plt.close()
            return output_path
        return None
    except Exception as e:
        logger.error(f"Visualization error: {str(e)}")
        return None

@app.post("/execute")
async def execute_code(
    request: ExecuteCodeRequest, 
    user: dict = Depends(get_current_user),
    rate_limiter: None = Depends(RateLimiter(times=5, seconds=60)) # 5 code executions per minute
):
    code_file = f"/data/{uuid.uuid4()}.py"
    try:
        with open(code_file, "w") as f:
            f.write(request.code)
        
        result = subprocess.run(
            ["python", code_file],
            capture_output=True,
            text=True,
            timeout=30,
            cwd="/data"
        )
        return {"output": result.stdout, "error": result.stderr}
    except subprocess.TimeoutExpired:
        raise HTTPException(status_code=408, detail="Code execution timed out")
    except Exception as e:
        logger.error(f"Code execution error: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to execute code")
    finally:
        if os.path.exists(code_file):
            os.remove(code_file)
class WebSearchRequest(BaseModel):
    query: str
    provider: Optional[str] = None
    num_results: int = 5
    extract_content: bool = False

@app.post("/search")
async def search_web(
    request: WebSearchRequest,
    user: dict = Depends(get_current_user),
    rate_limiter: None = Depends(RateLimiter(times=5, seconds=60))  # 5 searches per minute
):
    try:
        # Perform the web search
        search_results = await web_search.search(
            query=request.query,
            provider=request.provider,
            num_results=request.num_results
        )
        
        # Extract content if requested
        if request.extract_content and search_results.get("results"):
            for i, result in enumerate(search_results["results"]):
                if i >= 3:  # Limit to first 3 results to avoid timeouts
                    break
                    
                content_data = await web_search.extract_content(result["link"])
                if content_data["success"]:
                    result["extracted_content"] = content_data["content"]
                    
                    # Store in vector database for future use
                    try:
                        doc_id = f"web_{hashlib.md5(result['link'].encode()).hexdigest()}"
                        
                        # Generate embedding for the content
                        content_text = f"Title: {content_data['title']}\n\nContent: {content_data['content']}"
                        embedding = await get_embedding(content_text)
                        
                        # Store in Chroma
                        web_collection.upsert(
                            documents=[content_text],
                            embeddings=[embedding],
                            ids=[doc_id],
                            metadatas=[{
                                "url": result["link"],
                                "title": content_data["title"],
                                "source": "web_search",
                                "query": request.query
                            }]
                        )
                        
                        logger.info(f"Stored web content in vector database: {result['link']}")
                    except Exception as e:
                        logger.error(f"Failed to store web content in vector database: {str(e)}")
        
        return search_results
    except Exception as e:
        logger.error(f"Web search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Web search failed: {str(e)}")

class WebContentRequest(BaseModel):
    url: str

@app.post("/extract")
async def extract_web_content(
    request: WebContentRequest,
    user: dict = Depends(get_current_user),
    rate_limiter: None = Depends(RateLimiter(times=10, seconds=60))  # 10 extractions per minute
):
    try:
        content_data = await web_search.extract_content(request.url)
        return content_data
    except Exception as e:
        logger.error(f"Content extraction error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Content extraction failed: {str(e)}")