"""
Enhanced document processing using Docling and LlamaIndex.
"""

from docling.document_converter import DocumentConverter
from llama_index.core import Document, VectorStoreIndex
from llama_index.core.node_parser import SentenceSplitter
from typing import List, Dict, Any
import tempfile
import os

class EnhancedDocumentProcessor:
    """Enhanced document processor using Docling and LlamaIndex."""
    
    def __init__(self):
        self.converter = DocumentConverter()
        self.node_parser = SentenceSplitter(chunk_size=512, chunk_overlap=50)
    
    async def process_document(self, file_path: str, content: bytes) -> Dict[str, Any]:
        """Process document with enhanced extraction."""
        # Save content to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file_path)[1]) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        
        try:
            # Use Docling for advanced parsing
            result = self.converter.convert(tmp_path)
            
            # Extract structured content
            structured_content = {
                "text": result.document.export_to_markdown(),
                "tables": [table.export_to_dict() for table in result.document.tables],
                "images": len(result.document.pictures),
                "metadata": result.document.meta.dict() if result.document.meta else {}
            }
            
            # Create LlamaIndex document
            doc = Document(text=structured_content["text"])
            
            # Parse into nodes/chunks
            nodes = self.node_parser.get_nodes_from_documents([doc])
            
            return {
                "structured_content": structured_content,
                "chunks": [{"text": node.text, "metadata": node.metadata} for node in nodes],
                "processing_success": True
            }
            
        except Exception as e:
            # Fallback to basic processing
            return {
                "structured_content": {"text": content.decode('utf-8', errors='ignore')},
                "chunks": [{"text": content.decode('utf-8', errors='ignore')[:1000]}],
                "processing_success": False,
                "error": str(e)
            }
        finally:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)