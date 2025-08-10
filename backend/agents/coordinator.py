"""
Multi-agent coordinator using LangGraph for orchestration.
"""

from typing import Dict, Any, List
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, AIMessage
from langchain_ollama import ChatOllama
import asyncio

class AgentState(Dict):
    """State shared between agents."""
    query: str
    user_id: str
    documents: List[Dict]
    analysis_results: Dict
    final_response: str
    
class MultiAgentCoordinator:
    """Coordinates multiple specialized agents using LangGraph."""
    
    def __init__(self, ollama_host: str, model_name: str):
        self.llm = ChatOllama(base_url=ollama_host, model=model_name)
        self.workflow = self._build_workflow()
    
    def _build_workflow(self) -> StateGraph:
        """Build the multi-agent workflow graph."""
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("document_search", self._document_search_agent)
        workflow.add_node("analysis", self._analysis_agent)
        workflow.add_node("synthesis", self._synthesis_agent)
        
        # Add edges
        workflow.add_edge("document_search", "analysis")
        workflow.add_edge("analysis", "synthesis")
        workflow.add_edge("synthesis", END)
        
        # Set entry point
        workflow.set_entry_point("document_search")
        
        return workflow.compile()
    
    async def process_query(self, query: str, user_id: str) -> Dict[str, Any]:
        """Process a query through the multi-agent workflow."""
        initial_state = AgentState(
            query=query,
            user_id=user_id,
            documents=[],
            analysis_results={},
            final_response=""
        )
        
        result = await self.workflow.ainvoke(initial_state)
        return result
    
    async def _document_search_agent(self, state: AgentState) -> AgentState:
        """Document search agent using existing ChromaDB."""
        # Use existing document search logic
        from ..main import collection, get_embedding
        
        query_embedding = await get_embedding(state["query"])
        results = collection.query(
            query_embeddings=[query_embedding],
            n_results=5,
            include=["documents", "metadatas", "distances"]
        )
        
        state["documents"] = [
            {
                "content": doc,
                "metadata": meta,
                "distance": dist
            }
            for doc, meta, dist in zip(
                results["documents"][0],
                results["metadatas"][0], 
                results["distances"][0]
            )
        ]
        
        return state
    
    async def _analysis_agent(self, state: AgentState) -> AgentState:
        """Analysis agent for data processing."""
        if not state["documents"]:
            state["analysis_results"] = {"message": "No documents found"}
            return state
        
        # Simple analysis - count documents, extract key themes
        state["analysis_results"] = {
            "document_count": len(state["documents"]),
            "avg_relevance": sum(1 - doc["distance"] for doc in state["documents"]) / len(state["documents"]),
            "key_themes": [doc["metadata"].get("filename", "Unknown") for doc in state["documents"][:3]]
        }
        
        return state
    
    async def _synthesis_agent(self, state: AgentState) -> AgentState:
        """Synthesis agent to generate final response."""
        context = "\n".join([doc["content"][:200] for doc in state["documents"]])
        
        prompt = f"""Based on the following documents, answer the query: {state['query']}

Documents:
{context}

Analysis: {state['analysis_results']}

Provide a comprehensive answer with citations."""
        
        response = await self.llm.ainvoke([HumanMessage(content=prompt)])
        state["final_response"] = response.content
        
        return state