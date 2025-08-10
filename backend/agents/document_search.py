"""
Document search agent using LlamaIndex and ChromaDB.
"""

from llama_index.core.tools import FunctionTool
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.core import VectorStoreIndex
from typing import Dict, Any, List
import chromadb
from sqlalchemy.orm import Session

from .base import BaseAgent
from .models import AgentTask, AgentResult, AgentPersonality, AgentType

logger = logging.getLogger(__name__)

class DocumentSearchAgent(BaseAgent):
    """Document search agent using LlamaIndex."""
    
    def __init__(self, agent_id: str, chroma_client: chromadb.HttpClient, llm):
        """Initialize with LlamaIndex vector store."""
        personality = AgentPersonality(
            name="Document Search Specialist",
            description="Expert in finding and retrieving relevant documents",
            communication_style="precise",
            expertise_areas=["document_retrieval", "semantic_search"]
        )
        
        super().__init__(agent_id, AgentType.DOCUMENT_SEARCH, personality, llm)
        
        # Create LlamaIndex vector store
        collection = chroma_client.get_or_create_collection("documents")
        vector_store = ChromaVectorStore(chroma_collection=collection)
        self.index = VectorStoreIndex.from_vector_store(vector_store)
        
    def _create_tools(self) -> List[FunctionTool]:
        """Create search tools."""
        def search_documents(query: str) -> str:
            """Search documents using vector similarity."""
            query_engine = self.index.as_query_engine()
            response = query_engine.query(query)
            return str(response)
        
        return [FunctionTool.from_defaults(fn=search_documents)]
    
    def process_task(self, task: AgentTask) -> AgentResult:
        """Process document search using LlamaIndex."""
        try:
            query = task.input_data.get("query", "")
            if not query:
                return AgentResult(
                    task_id=task.task_id,
                    agent_id=self.agent_id,
                    success=False,
                    error_message="No query provided"
                )
            
            # Use LlamaIndex query engine
            query_engine = self.index.as_query_engine()
            response = query_engine.query(query)
            
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=True,
                result_data={
                    "response": str(response),
                    "sources": [node.metadata for node in response.source_nodes] if hasattr(response, 'source_nodes') else []
                }
            )
            
        except Exception as e:
            return AgentResult(
                task_id=task.task_id,
                agent_id=self.agent_id,
                success=False,
                error_message=str(e)
            )
    
    async def _semantic_search(self, query: str, top_k: int, 
                              accessible_doc_ids: List[str] = None,
                              filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Perform semantic search using ChromaDB."""
        try:
            # Build where clause for filtering
            where_clause = {}
            
            # Add accessibility filter
            if accessible_doc_ids:
                where_clause["$and"] = [{"id": {"$in": accessible_doc_ids}}]
            
            # Add custom filters
            if filters:
                if "sensitivity" in filters:
                    where_clause["sensitivity"] = filters["sensitivity"]
                if "department" in filters:
                    where_clause["department"] = filters["department"]
                if "file_type" in filters:
                    where_clause["file_type"] = filters["file_type"]
            
            # Perform search
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_clause if where_clause else None,
                include=["documents", "metadatas", "distances"]
            )
            
            # Format results
            formatted_results = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    formatted_results.append({
                        "id": doc_id,
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i],
                        "relevance_score": 1.0 - results["distances"][0][i]  # Convert distance to relevance
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"Error in semantic search: {str(e)}")
            return []
    
    async def _enhance_results_with_metadata(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Enhance search results with additional metadata."""
        enhanced_results = []
        
        for result in results:
            try:
                # Get additional metadata from database
                doc_id = result["id"]
                
                # Query document metadata
                from ..auth.database import DocumentMetadata
                doc_metadata = self.db_session.query(DocumentMetadata).filter(
                    DocumentMetadata.document_id == doc_id
                ).first()
                
                enhanced_result = result.copy()
                
                if doc_metadata:
                    enhanced_result["enhanced_metadata"] = {
                        "sensitivity_level": doc_metadata.sensitivity_level,
                        "department": doc_metadata.department,
                        "tags": doc_metadata.tags,
                        "version": doc_metadata.version,
                        "created_at": doc_metadata.created_at.isoformat() if doc_metadata.created_at else None,
                        "updated_at": doc_metadata.updated_at.isoformat() if doc_metadata.updated_at else None
                    }
                
                # Add snippet (first 200 characters)
                content = result.get("content", "")
                enhanced_result["snippet"] = content[:200] + "..." if len(content) > 200 else content
                
                enhanced_results.append(enhanced_result)
                
            except Exception as e:
                logger.warning(f"Error enhancing result for document {result.get('id')}: {str(e)}")
                enhanced_results.append(result)
        
        return enhanced_results
    
    def _calculate_confidence_score(self, results: List[Dict[str, Any]]) -> float:
        """Calculate confidence score based on search results quality."""
        if not results:
            return 0.0
        
        # Base confidence on relevance scores
        relevance_scores = [r.get("relevance_score", 0.0) for r in results]
        avg_relevance = sum(relevance_scores) / len(relevance_scores)
        
        # Adjust based on number of results
        result_count_factor = min(len(results) / 5.0, 1.0)  # Optimal around 5 results
        
        # Final confidence score
        confidence = avg_relevance * result_count_factor
        
        return min(confidence, 1.0)