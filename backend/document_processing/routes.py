"""
API routes for document processing and metadata management.
Provides endpoints for document upload, metadata management, and tagging.
"""

from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, Body, Query, Path
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
import os
import uuid
import json
import tempfile
import sqlite3
from datetime import datetime

from ..auth.database import User, DocumentMetadata
from ..auth.models import Permission, DocumentSensitivity, Department
from ..auth.rbac import get_current_user
from ..auth.middleware import PermissionChecker
from .metadata import MetadataExtractor

# Create API router
router = APIRouter(prefix="/documents", tags=["Documents"])

# Get database dependency
def get_db():
    """Database session dependency."""
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import create_engine
    import os
    
    DB_PATH = os.getenv("DB_PATH", "/data/notebooklm.db")
    engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Create permission checker
permission_checker = PermissionChecker(get_db)

# Pydantic models for request/response
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any
from datetime import datetime

class DocumentMetadataResponse(BaseModel):
    """Document metadata response model."""
    id: str
    document_id: str
    filename: str
    file_type: str
    file_size: int
    sensitivity_level: str
    department: str
    tags: List[str]
    version: str
    description: Optional[str]
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime
    indexed_at: Optional[datetime]

class DocumentMetadataUpdate(BaseModel):
    """Document metadata update request model."""
    sensitivity_level: Optional[str] = None
    department: Optional[str] = None
    tags: Optional[List[str]] = None
    version: Optional[str] = None
    description: Optional[str] = None
    access_permissions: Optional[Dict[str, List[str]]] = None

class DocumentUploadResponse(BaseModel):
    """Document upload response model."""
    document_id: str
    filename: str
    file_type: str
    file_size: int
    metadata: DocumentMetadataResponse

class TagsUpdate(BaseModel):
    """Tags update request model."""
    tags: List[str]

class SensitivityUpdate(BaseModel):
    """Sensitivity update request model."""
    sensitivity_level: str

class DepartmentUpdate(BaseModel):
    """Department update request model."""
    department: str

class AccessPermissionsUpdate(BaseModel):
    """Access permissions update request model."""
    users: Optional[List[str]] = None
    roles: Optional[List[str]] = None

class ManualTaggingRequest(BaseModel):
    """Manual metadata tagging request model."""
    sensitivity_level: Optional[str] = None
    department: Optional[str] = None
    tags: Optional[List[str]] = None
    version: Optional[str] = None
    description: Optional[str] = None
    access_permissions: Optional[Dict[str, List[str]]] = None
    custom_fields: Optional[Dict[str, Any]] = None

# Document routes
@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    sensitivity: Optional[str] = Form(None),
    department: Optional[str] = Form(None),
    tags: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_permissions([Permission.DOCUMENT_UPLOAD]))
):
    """
    Upload a document with metadata.
    
    Args:
        file: Document file to upload
        sensitivity: Optional sensitivity level
        department: Optional department
        tags: Optional comma-separated tags
        description: Optional document description
        db: Database session
        current_user: Current authenticated user with DOCUMENT_UPLOAD permission
        
    Returns:
        DocumentUploadResponse: Uploaded document information
        
    Raises:
        HTTPException: If file upload fails
    """
    try:
        # Read file content
        content = await file.read()
        file_size = len(content)
        
        # Check file size limit (10MB)
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="File size exceeds 10MB limit"
            )
        
        # Create temporary file for processing
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            temp_file.write(content)
            temp_path = temp_file.name
        
        try:
            # Extract text content based on file type
            file_extension = os.path.splitext(file.filename)[1].lower()
            text_content = ""
            
            if file_extension in ['.pdf']:
                # For PDF files
                try:
                    from PyPDF2 import PdfReader
                    pdf = PdfReader(temp_path)
                    text_content = ""
                    for page in pdf.pages:
                        text_content += page.extract_text() + "\n"
                except Exception as e:
                    text_content = f"Error extracting PDF content: {str(e)}"
            
            elif file_extension in ['.docx', '.doc']:
                # For Word documents
                try:
                    from docx import Document
                    doc = Document(temp_path)
                    text_content = "\n".join([para.text for para in doc.paragraphs])
                except Exception as e:
                    text_content = f"Error extracting DOCX content: {str(e)}"
            
            elif file_extension in ['.txt', '.md', '.py', '.js', '.html', '.css', '.json', '.xml', '.csv']:
                # For text files
                try:
                    with open(temp_path, 'r', encoding='utf-8', errors='replace') as f:
                        text_content = f.read()
                except Exception as e:
                    text_content = f"Error reading text file: {str(e)}"
            
            else:
                # For other binary files
                text_content = f"Binary file: {file.filename}"
            
            # Generate document ID
            document_id = str(uuid.uuid4())
            
            # Process metadata
            metadata_extractor = MetadataExtractor(db)
            
            # Prepare initial metadata
            initial_metadata = {
                "filename": file.filename,
                "file_type": file.content_type or "application/octet-stream",
                "file_size": file_size
            }
            
            # Add user-provided metadata if available
            if sensitivity:
                initial_metadata["sensitivity"] = sensitivity
            if department:
                initial_metadata["department"] = department
            if tags:
                initial_metadata["tags"] = [tag.strip() for tag in tags.split(",")]
            if description:
                initial_metadata["description"] = description
            
            # Extract and store metadata
            extracted_metadata = metadata_extractor.extract_metadata(
                temp_path,
                content=text_content,
                user_id=str(current_user.id)
            )
            
            # Merge extracted and user-provided metadata
            merged_metadata = {**extracted_metadata, **initial_metadata}
            
            # Store metadata in database
            doc_metadata = metadata_extractor.store_metadata(
                document_id,
                merged_metadata,
                str(current_user.id)
            )
            
            # Store document content in ChromaDB
            from chromadb import HttpClient
            import numpy as np
            
            # Initialize Chroma client
            chroma_host = os.getenv("CHROMA_HOST", "chroma")
            chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
            client = HttpClient(host=chroma_host, port=chroma_port)
            collection = client.get_or_create_collection("documents", metadata={"hnsw:space": "cosine"})
            
            # Generate embedding
            from ..main import get_embedding
            embedding = await get_embedding(text_content)
            
            # Store in Chroma with enhanced metadata
            chroma_metadata = {
                "filename": file.filename,
                "file_type": file_extension[1:] if file_extension else "",
                "sensitivity": merged_metadata.get("sensitivity_level", DocumentSensitivity.INTERNAL.value),
                "department": merged_metadata.get("department", Department.GENERAL.value),
                "tags": ",".join(merged_metadata.get("tags", [])),
                "created_by": str(current_user.id),
                "created_at": datetime.utcnow().isoformat()
            }
            
            collection.add(
                documents=[text_content],
                embeddings=[embedding],
                ids=[document_id],
                metadatas=[chroma_metadata]
            )
            
            # Store in SQLite for full-text search
            conn = sqlite3.connect(os.getenv("DB_PATH", "/data/notebooklm.db"), check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO documents (id, filename, content) VALUES (?, ?, ?)",
                        (document_id, file.filename, text_content))
            conn.commit()
            conn.close()
            
            # Prepare response
            response = {
                "document_id": document_id,
                "filename": file.filename,
                "file_type": file.content_type or "application/octet-stream",
                "file_size": file_size,
                "metadata": {
                    "id": str(doc_metadata.id),
                    "document_id": doc_metadata.document_id,
                    "filename": doc_metadata.filename,
                    "file_type": doc_metadata.file_type,
                    "file_size": doc_metadata.file_size,
                    "sensitivity_level": doc_metadata.sensitivity_level,
                    "department": doc_metadata.department,
                    "tags": doc_metadata.tags,
                    "version": doc_metadata.version,
                    "description": doc_metadata.description,
                    "created_by": str(doc_metadata.created_by) if doc_metadata.created_by else None,
                    "created_at": doc_metadata.created_at,
                    "updated_at": doc_metadata.updated_at,
                    "indexed_at": doc_metadata.indexed_at
                }
            }
            
            return response
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process document: {str(e)}"
        )

@router.get("/metadata", response_model=List[DocumentMetadataResponse])
async def get_all_document_metadata(
    skip: int = 0,
    limit: int = 100,
    sensitivity: Optional[str] = None,
    department: Optional[str] = None,
    tag: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    accessible_docs: List[str] = Depends(permission_checker.filter_documents_for_user(Permission.DOCUMENT_READ))
):
    """
    Get metadata for all accessible documents with optional filtering.
    
    Args:
        skip: Number of documents to skip
        limit: Maximum number of documents to return
        sensitivity: Optional sensitivity level filter
        department: Optional department filter
        tag: Optional tag filter
        db: Database session
        current_user: Current authenticated user
        accessible_docs: List of document IDs the user has access to
        
    Returns:
        List[DocumentMetadataResponse]: List of document metadata
    """
    # Start with base query for accessible documents
    query = db.query(DocumentMetadata).filter(DocumentMetadata.document_id.in_(accessible_docs))
    
    # Apply filters if provided
    if sensitivity:
        query = query.filter(DocumentMetadata.sensitivity_level == sensitivity)
    if department:
        query = query.filter(DocumentMetadata.department == department)
    if tag:
        # Filter by tag (using JSON contains)
        query = query.filter(DocumentMetadata.tags.contains(tag))
    
    # Apply pagination
    documents = query.offset(skip).limit(limit).all()
    
    # Convert to response models
    return [
        {
            "id": str(doc.id),
            "document_id": doc.document_id,
            "filename": doc.filename,
            "file_type": doc.file_type,
            "file_size": doc.file_size,
            "sensitivity_level": doc.sensitivity_level,
            "department": doc.department,
            "tags": doc.tags,
            "version": doc.version,
            "description": doc.description,
            "created_by": str(doc.created_by) if doc.created_by else None,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
            "indexed_at": doc.indexed_at
        }
        for doc in documents
    ]

@router.get("/metadata/{document_id}", response_model=DocumentMetadataResponse)
async def get_document_metadata(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_document_access(permission=Permission.DOCUMENT_READ))
):
    """
    Get metadata for a specific document.
    
    Args:
        document_id: Document ID
        db: Database session
        current_user: Current authenticated user with document access
        
    Returns:
        DocumentMetadataResponse: Document metadata
        
    Raises:
        HTTPException: If document not found
    """
    doc = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    # Convert to response model
    return {
        "id": str(doc.id),
        "document_id": doc.document_id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "sensitivity_level": doc.sensitivity_level,
        "department": doc.department,
        "tags": doc.tags,
        "version": doc.version,
        "description": doc.description,
        "created_by": str(doc.created_by) if doc.created_by else None,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "indexed_at": doc.indexed_at
    }

@router.put("/metadata/{document_id}", response_model=DocumentMetadataResponse)
async def update_document_metadata(
    document_id: str,
    metadata: DocumentMetadataUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_document_access(permission=Permission.DOCUMENT_WRITE))
):
    """
    Update metadata for a specific document.
    
    Args:
        document_id: Document ID
        metadata: Document metadata update
        db: Database session
        current_user: Current authenticated user with DOCUMENT_WRITE permission
        
    Returns:
        DocumentMetadataResponse: Updated document metadata
        
    Raises:
        HTTPException: If document not found or metadata invalid
    """
    # Find document metadata
    doc = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    # Update metadata fields
    if metadata.sensitivity_level is not None:
        # Validate sensitivity level
        if metadata.sensitivity_level not in [s.value for s in DocumentSensitivity]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid sensitivity level: {metadata.sensitivity_level}"
            )
        doc.sensitivity_level = metadata.sensitivity_level
    
    if metadata.department is not None:
        # Validate department
        if metadata.department not in [d.value for d in Department]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid department: {metadata.department}"
            )
        doc.department = metadata.department
    
    if metadata.tags is not None:
        # Validate tags
        if not isinstance(metadata.tags, list):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Tags must be a list"
            )
        # Sanitize tags
        sanitized_tags = [tag[:100] for tag in metadata.tags[:20]]  # Limit to 20 tags, 100 chars each
        doc.tags = sanitized_tags
    
    if metadata.version is not None:
        # Validate version format
        import re
        if not re.match(r'^\d+\.\d+$', metadata.version):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Version must be in format X.Y"
            )
        doc.version = metadata.version
    
    if metadata.description is not None:
        # Sanitize description
        doc.description = metadata.description[:1000]  # Limit to 1000 chars
    
    if metadata.access_permissions is not None:
        # Validate access permissions
        if not isinstance(metadata.access_permissions, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Access permissions must be a dictionary"
            )
        
        # Update access permissions
        current_permissions = doc.access_permissions or {"users": [], "roles": []}
        
        if "users" in metadata.access_permissions:
            current_permissions["users"] = metadata.access_permissions["users"]
        if "roles" in metadata.access_permissions:
            current_permissions["roles"] = metadata.access_permissions["roles"]
        
        doc.access_permissions = current_permissions
    
    # Update timestamp
    doc.updated_at = datetime.utcnow()
    
    # Save changes
    db.commit()
    db.refresh(doc)
    
    # Update ChromaDB metadata
    try:
        from chromadb import HttpClient
        
        # Initialize Chroma client
        chroma_host = os.getenv("CHROMA_HOST", "chroma")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
        client = HttpClient(host=chroma_host, port=chroma_port)
        collection = client.get_or_create_collection("documents")
        
        # Update metadata in ChromaDB
        chroma_metadata = {
            "sensitivity": doc.sensitivity_level,
            "department": doc.department,
            "tags": ",".join(doc.tags) if doc.tags else "",
            "updated_at": datetime.utcnow().isoformat()
        }
        
        collection.update(
            ids=[document_id],
            metadatas=[chroma_metadata]
        )
    except Exception as e:
        # Log error but don't fail the request
        import logging
        logging.error(f"Failed to update ChromaDB metadata: {str(e)}")
    
    # Convert to response model
    return {
        "id": str(doc.id),
        "document_id": doc.document_id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "sensitivity_level": doc.sensitivity_level,
        "department": doc.department,
        "tags": doc.tags,
        "version": doc.version,
        "description": doc.description,
        "created_by": str(doc.created_by) if doc.created_by else None,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "indexed_at": doc.indexed_at
    }

@router.put("/metadata/{document_id}/tags", response_model=List[str])
async def update_document_tags(
    document_id: str,
    tags_update: TagsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_document_access(permission=Permission.DOCUMENT_WRITE))
):
    """
    Update tags for a specific document.
    
    Args:
        document_id: Document ID
        tags_update: Tags update data
        db: Database session
        current_user: Current authenticated user with DOCUMENT_WRITE permission
        
    Returns:
        List[str]: Updated tags
        
    Raises:
        HTTPException: If document not found or tags invalid
    """
    # Find document metadata
    doc = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    # Validate tags
    if not isinstance(tags_update.tags, list):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Tags must be a list"
        )
    
    # Sanitize tags
    sanitized_tags = [tag[:100] for tag in tags_update.tags[:20]]  # Limit to 20 tags, 100 chars each
    
    # Update tags
    doc.tags = sanitized_tags
    doc.updated_at = datetime.utcnow()
    
    # Save changes
    db.commit()
    
    # Update ChromaDB metadata
    try:
        from chromadb import HttpClient
        
        # Initialize Chroma client
        chroma_host = os.getenv("CHROMA_HOST", "chroma")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
        client = HttpClient(host=chroma_host, port=chroma_port)
        collection = client.get_or_create_collection("documents")
        
        # Update tags in ChromaDB
        collection.update(
            ids=[document_id],
            metadatas=[{"tags": ",".join(sanitized_tags)}]
        )
    except Exception as e:
        # Log error but don't fail the request
        import logging
        logging.error(f"Failed to update ChromaDB tags: {str(e)}")
    
    return doc.tags

@router.put("/metadata/{document_id}/sensitivity", response_model=str)
async def update_document_sensitivity(
    document_id: str,
    sensitivity_update: SensitivityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_document_access(permission=Permission.DOCUMENT_WRITE))
):
    """
    Update sensitivity level for a specific document.
    
    Args:
        document_id: Document ID
        sensitivity_update: Sensitivity update data
        db: Database session
        current_user: Current authenticated user with DOCUMENT_WRITE permission
        
    Returns:
        str: Updated sensitivity level
        
    Raises:
        HTTPException: If document not found or sensitivity invalid
    """
    # Find document metadata
    doc = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    # Validate sensitivity level
    if sensitivity_update.sensitivity_level not in [s.value for s in DocumentSensitivity]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid sensitivity level: {sensitivity_update.sensitivity_level}"
        )
    
    # Update sensitivity level
    doc.sensitivity_level = sensitivity_update.sensitivity_level
    doc.updated_at = datetime.utcnow()
    
    # Save changes
    db.commit()
    
    # Update ChromaDB metadata
    try:
        from chromadb import HttpClient
        
        # Initialize Chroma client
        chroma_host = os.getenv("CHROMA_HOST", "chroma")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
        client = HttpClient(host=chroma_host, port=chroma_port)
        collection = client.get_or_create_collection("documents")
        
        # Update sensitivity in ChromaDB
        collection.update(
            ids=[document_id],
            metadatas=[{"sensitivity": sensitivity_update.sensitivity_level}]
        )
    except Exception as e:
        # Log error but don't fail the request
        import logging
        logging.error(f"Failed to update ChromaDB sensitivity: {str(e)}")
    
    return doc.sensitivity_level

@router.put("/metadata/{document_id}/department", response_model=str)
async def update_document_department(
    document_id: str,
    department_update: DepartmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_document_access(permission=Permission.DOCUMENT_WRITE))
):
    """
    Update department for a specific document.
    
    Args:
        document_id: Document ID
        department_update: Department update data
        db: Database session
        current_user: Current authenticated user with DOCUMENT_WRITE permission
        
    Returns:
        str: Updated department
        
    Raises:
        HTTPException: If document not found or department invalid
    """
    # Find document metadata
    doc = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    # Validate department
    if department_update.department not in [d.value for d in Department]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid department: {department_update.department}"
        )
    
    # Update department
    doc.department = department_update.department
    doc.updated_at = datetime.utcnow()
    
    # Save changes
    db.commit()
    
    # Update ChromaDB metadata
    try:
        from chromadb import HttpClient
        
        # Initialize Chroma client
        chroma_host = os.getenv("CHROMA_HOST", "chroma")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
        client = HttpClient(host=chroma_host, port=chroma_port)
        collection = client.get_or_create_collection("documents")
        
        # Update department in ChromaDB
        collection.update(
            ids=[document_id],
            metadatas=[{"department": department_update.department}]
        )
    except Exception as e:
        # Log error but don't fail the request
        import logging
        logging.error(f"Failed to update ChromaDB department: {str(e)}")
    
    return doc.department

@router.put("/metadata/{document_id}/access", response_model=Dict[str, List[str]])
async def update_document_access_permissions(
    document_id: str,
    access_update: AccessPermissionsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_document_access(permission=Permission.DOCUMENT_WRITE))
):
    """
    Update access permissions for a specific document.
    
    Args:
        document_id: Document ID
        access_update: Access permissions update data
        db: Database session
        current_user: Current authenticated user with DOCUMENT_WRITE permission
        
    Returns:
        Dict[str, List[str]]: Updated access permissions
        
    Raises:
        HTTPException: If document not found
    """
    # Find document metadata
    doc = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    # Get current access permissions
    current_permissions = doc.access_permissions or {"users": [], "roles": []}
    
    # Update access permissions
    if access_update.users is not None:
        current_permissions["users"] = access_update.users
    if access_update.roles is not None:
        current_permissions["roles"] = access_update.roles
    
    # Update document
    doc.access_permissions = current_permissions
    doc.updated_at = datetime.utcnow()
    
    # Save changes
    db.commit()
    
    return doc.access_permissions


class ManualTaggingRequest(BaseModel):
    """Manual metadata tagging request model."""
    sensitivity_level: Optional[str] = None
    department: Optional[str] = None
    tags: Optional[List[str]] = None
    version: Optional[str] = None
    description: Optional[str] = None
    access_permissions: Optional[Dict[str, List[str]]] = None
    custom_fields: Optional[Dict[str, Any]] = None

@router.post("/metadata/{document_id}/manual-tagging", response_model=DocumentMetadataResponse)
async def apply_manual_metadata_tags(
    document_id: str,
    tagging_request: ManualTaggingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_document_access(permission=Permission.DOCUMENT_WRITE))
):
    """
    Apply manual metadata tags to a document.
    
    Args:
        document_id: Document ID
        tagging_request: Manual tagging request data
        db: Database session
        current_user: Current authenticated user with DOCUMENT_WRITE permission
        
    Returns:
        DocumentMetadataResponse: Updated document metadata
        
    Raises:
        HTTPException: If document not found or tagging fails
    """
    # Find document metadata
    doc = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    # Create metadata extractor
    metadata_extractor = MetadataExtractor(db)
    
    # Convert request to dictionary
    metadata_updates = tagging_request.dict(exclude_unset=True, exclude_none=True)
    
    # Apply manual tags
    success = metadata_extractor.apply_manual_tags(document_id, metadata_updates)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to apply metadata tags"
        )
    
    # Refresh document from database
    db.refresh(doc)
    
    # Update ChromaDB metadata if needed
    try:
        from chromadb import HttpClient
        
        # Initialize Chroma client
        chroma_host = os.getenv("CHROMA_HOST", "chroma")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
        client = HttpClient(host=chroma_host, port=chroma_port)
        collection = client.get_or_create_collection("documents")
        
        # Update metadata in ChromaDB
        chroma_metadata = {
            "sensitivity": doc.sensitivity_level,
            "department": doc.department,
            "tags": ",".join(doc.tags) if doc.tags else "",
            "updated_at": datetime.utcnow().isoformat()
        }
        
        collection.update(
            ids=[document_id],
            metadatas=[chroma_metadata]
        )
    except Exception as e:
        # Log error but don't fail the request
        import logging
        logging.error(f"Failed to update ChromaDB metadata: {str(e)}")
    
    # Convert to response model
    return {
        "id": str(doc.id),
        "document_id": doc.document_id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "sensitivity_level": doc.sensitivity_level,
        "department": doc.department,
        "tags": doc.tags,
        "version": doc.version,
        "description": doc.description,
        "created_by": str(doc.created_by) if doc.created_by else None,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "indexed_at": doc.indexed_at
    }

@router.post("/metadata/{document_id}/manual-tagging", response_model=DocumentMetadataResponse)
async def apply_manual_metadata_tags(
    document_id: str,
    tagging_request: ManualTaggingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_document_access(permission=Permission.DOCUMENT_WRITE))
):
    """
    Apply manual metadata tags to a document.
    
    Args:
        document_id: Document ID
        tagging_request: Manual tagging request data
        db: Database session
        current_user: Current authenticated user with DOCUMENT_WRITE permission
        
    Returns:
        DocumentMetadataResponse: Updated document metadata
        
    Raises:
        HTTPException: If document not found or tagging fails
    """
    # Find document metadata
    doc = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    # Create metadata extractor
    metadata_extractor = MetadataExtractor(db)
    
    # Convert request to dictionary
    metadata_updates = tagging_request.dict(exclude_unset=True, exclude_none=True)
    
    # Apply manual tags
    success = metadata_extractor.apply_manual_tags(document_id, metadata_updates)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to apply metadata tags"
        )
    
    # Refresh document from database
    db.refresh(doc)
    
    # Update ChromaDB metadata if needed
    try:
        from chromadb import HttpClient
        
        # Initialize Chroma client
        chroma_host = os.getenv("CHROMA_HOST", "chroma")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
        client = HttpClient(host=chroma_host, port=chroma_port)
        collection = client.get_or_create_collection("documents")
        
        # Update metadata in ChromaDB
        chroma_metadata = {
            "sensitivity": doc.sensitivity_level,
            "department": doc.department,
            "tags": ",".join(doc.tags) if doc.tags else "",
            "updated_at": datetime.utcnow().isoformat()
        }
        
        collection.update(
            ids=[document_id],
            metadatas=[chroma_metadata]
        )
    except Exception as e:
        # Log error but don't fail the request
        import logging
        logging.error(f"Failed to update ChromaDB metadata: {str(e)}")
    
    # Convert to response model
    return {
        "id": str(doc.id),
        "document_id": doc.document_id,
        "filename": doc.filename,
        "file_type": doc.file_type,
        "file_size": doc.file_size,
        "sensitivity_level": doc.sensitivity_level,
        "department": doc.department,
        "tags": doc.tags,
        "version": doc.version,
        "description": doc.description,
        "created_by": str(doc.created_by) if doc.created_by else None,
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "indexed_at": doc.indexed_at
    }

@router.delete("/metadata/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(permission_checker.require_document_access(permission=Permission.DOCUMENT_DELETE))
):
    """
    Delete a document and its metadata.
    
    Args:
        document_id: Document ID
        db: Database session
        current_user: Current authenticated user with DOCUMENT_DELETE permission
        
    Raises:
        HTTPException: If document not found
    """
    # Find document metadata
    doc = db.query(DocumentMetadata).filter(DocumentMetadata.document_id == document_id).first()
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    # Delete from SQLite
    try:
        conn = sqlite3.connect(os.getenv("DB_PATH", "/data/notebooklm.db"), check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM documents WHERE id = ?", (document_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        # Log error but continue
        import logging
        logging.error(f"Failed to delete document from SQLite: {str(e)}")
    
    # Delete from ChromaDB
    try:
        from chromadb import HttpClient
        
        # Initialize Chroma client
        chroma_host = os.getenv("CHROMA_HOST", "chroma")
        chroma_port = int(os.getenv("CHROMA_PORT", "8000"))
        client = HttpClient(host=chroma_host, port=chroma_port)
        collection = client.get_or_create_collection("documents")
        
        # Delete from ChromaDB
        collection.delete(ids=[document_id])
    except Exception as e:
        # Log error but continue
        import logging
        logging.error(f"Failed to delete document from ChromaDB: {str(e)}")
    
    # Delete metadata from database
    db.delete(doc)
    db.commit()
    
    return None