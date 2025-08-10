"""
Base agent class using LangChain and LlamaIndex.
"""

from langchain_core.runnables import Runnable
from langchain_core.messages import HumanMessage, AIMessage
from llama_index.core.agent import ReActAgent
from llama_index.core.tools import FunctionTool
from typing import Dict, Any, Optional, List
from datetime import datetime

from .models import AgentTask, AgentResult, AgentPersonality, AgentStatus, AgentType

logger = logging.getLogger(__name__)

class BaseAgent(Runnable):
    """Base agent using LangChain Runnable interface."""
    
    def __init__(self, agent_id: str, agent_type: AgentType, personality: AgentPersonality, llm):
        """Initialize base agent with LLM."""
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.personality = personality
        self.llm = llm
        self.status = AgentStatus(agent_id=agent_id, agent_type=agent_type)
        self.tools = self._create_tools()
        
    def _create_tools(self) -> List[FunctionTool]:
        """Create tools for this agent."""
        return []
    
    def invoke(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process input using LangChain interface."""
        task = AgentTask(**input_data)
        return self.process_task(task)
    
    def process_task(self, task: AgentTask) -> AgentResult:
        """Process a task - to be implemented by subclasses."""
        return AgentResult(
            task_id=task.task_id,
            agent_id=self.agent_id,
            success=True,
            result_data={"message": "Base agent processed task"}
        )
    
    async def start(self):
        """Start the agent."""
        self.is_running = True
        self.status.is_active = True
        logger.info(f"Agent {self.agent_id} ({self.agent_type}) started")
        
        # Start message processing loop
        asyncio.create_task(self._message_processing_loop())
    
    async def stop(self):
        """Stop the agent."""
        self.is_running = False
        self.status.is_active = False
        logger.info(f"Agent {self.agent_id} ({self.agent_type}) stopped")
    
    async def send_message(self, message: AgentMessage):
        """Send a message to another agent."""
        await self.message_queue.put(message)
    
    async def _message_processing_loop(self):
        """Process incoming messages."""
        while self.is_running:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._handle_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error processing message in agent {self.agent_id}: {str(e)}")
    
    async def _handle_message(self, message: AgentMessage):
        """Handle incoming message."""
        logger.debug(f"Agent {self.agent_id} received message: {message.message_type}")
        
        # Update last activity
        self.status.last_activity = datetime.utcnow()
        
        # Handle different message types
        if message.message_type.value == "task_request":
            await self._handle_task_request(message)
        elif message.message_type.value == "coordination":
            await self._handle_coordination_message(message)
        else:
            logger.warning(f"Unknown message type: {message.message_type}")
    
    async def _handle_task_request(self, message: AgentMessage):
        """Handle task request message."""
        try:
            task_data = message.content.get("task")
            if not task_data:
                logger.error("Task request message missing task data")
                return
            
            task = AgentTask(**task_data)
            
            # Check if we can handle this task
            if not await self.can_handle_task(task):
                logger.warning(f"Agent {self.agent_id} cannot handle task {task.task_id}")
                return
            
            # Add task to current tasks
            self.status.current_tasks.append(task.task_id)
            
            # Process the task
            result = await self.process_task(task)
            
            # Update status
            self.status.current_tasks.remove(task.task_id)
            self.status.completed_tasks += 1
            
            if not result.success:
                self.status.error_count += 1
            
            # Send result back (this would be handled by the communication bus)
            logger.info(f"Agent {self.agent_id} completed task {task.task_id}")
            
        except Exception as e:
            logger.error(f"Error handling task request in agent {self.agent_id}: {str(e)}")
            self.status.error_count += 1
    
    async def _handle_coordination_message(self, message: AgentMessage):
        """Handle coordination message."""
        # Base implementation - can be overridden by specialized agents
        logger.debug(f"Agent {self.agent_id} received coordination message")
    
    def get_status(self) -> AgentStatus:
        """Get current agent status."""
        return self.status
    
    def update_performance_metrics(self, metrics: Dict[str, float]):
        """Update performance metrics."""
        self.status.performance_metrics.update(metrics)