"""
Simplified agents using LangChain and existing libraries.
"""

from langchain_core.tools import tool
from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage
from typing import Dict, Any, List
import chromadb

@tool
def search_documents(query: str, user_id: str = None) -> List[Dict]:
    """Search documents using existing ChromaDB collection."""
    # Use existing collection from main.py
    from ..main import collection, get_embedding
    import asyncio
    
    async def _search():
        query_embedding = await get_embedding(query)
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5,
            include=["documents", "metadatas", "distances"]
        )
        
        return [
            {
                "content": doc[:200] + "...",
                "filename": meta.get("filename", "Unknown"),
                "relevance": 1 - dist
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0], 
                results["distances"][0]
            )
        ]
    
    return asyncio.run(_search())

@tool  
def analyze_data(data: str, analysis_type: str = "summary") -> Dict[str, Any]:
    """Analyze data using pandas."""
    import pandas as pd
    import json
    
    try:
        # Try to parse as JSON
        parsed_data = json.loads(data)
        df = pd.DataFrame(parsed_data)
        
        if analysis_type == "summary":
            return {
                "shape": df.shape,
                "columns": list(df.columns),
                "numeric_summary": df.describe().to_dict() if len(df.select_dtypes(include=['number']).columns) > 0 else {},
                "missing_values": df.isnull().sum().to_dict()
            }
    except:
        return {"error": "Could not analyze data"}

class SimpleAgentCoordinator:
    """Simplified agent coordinator using LangChain tools."""
    
    def __init__(self, ollama_host: str, model_name: str):
        self.llm = ChatOllama(base_url=ollama_host, model=model_name)
        self.tools = [search_documents, analyze_data]
    
    async def process_query(self, query: str, user_id: str) -> Dict[str, Any]:
        """Process query using available tools."""
        # Determine which tools to use
        tools_to_use = []
        
        if any(word in query.lower() for word in ["search", "find", "document"]):
            docs = search_documents.invoke({"query": query, "user_id": user_id})
            context = "\n".join([f"Document: {doc['filename']}\n{doc['content']}" for doc in docs])
        else:
            context = "No documents searched."
        
        # Generate response
        prompt = f"""Query: {query}
        
Context: {context}

Provide a helpful response based on the available information."""
        
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        
        return {
            "response": response.content,
            "sources": docs if 'docs' in locals() else [],
            "agent_used": "simple_coordinator"
        }