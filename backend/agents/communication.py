"""
Agent communication system for message routing and coordination.
"""

import asyncio
import logging
from typing import Dict, List, Optional, Callable, Any
from datetime import datetime
import json

from .models import AgentMessage, MessageType

logger = logging.getLogger(__name__)

class AgentCommunicationBus:
    """Central communication bus for agent-to-agent messaging."""
    
    def __init__(self):
        """Initialize communication bus."""
        self.subscribers: Dict[str, List[Callable]] = {}
        self.message_history: List[AgentMessage] = []
        self.message_queue = asyncio.Queue()
        self.is_running = False
        
    async def start(self):
        """Start the communication bus."""
        self.is_running = True
        logger.info("Agent communication bus started")
        
        # Start message processing loop
        asyncio.create_task(self._message_processing_loop())
    
    async def stop(self):
        """Stop the communication bus."""
        self.is_running = False
        logger.info("Agent communication bus stopped")
    
    async def send_message(self, message: AgentMessage) -> bool:
        """Send a message through the communication bus."""
        try:
            # Add to message queue
            await self.message_queue.put(message)
            
            # Store in history
            self.message_history.append(message)
            
            # Limit history size
            if len(self.message_history) > 1000:
                self.message_history = self.message_history[-500:]
            
            logger.debug(f"Message queued: {message.sender_id} -> {message.recipient_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return False
    
    async def subscribe(self, agent_id: str, callback: Callable[[AgentMessage], None]):
        """Subscribe an agent to receive messages."""
        if agent_id not in self.subscribers:
            self.subscribers[agent_id] = []
        
        self.subscribers[agent_id].append(callback)
        logger.debug(f"Agent {agent_id} subscribed to communication bus")
    
    async def unsubscribe(self, agent_id: str, callback: Optional[Callable] = None):
        """Unsubscribe an agent from receiving messages."""
        if agent_id in self.subscribers:
            if callback:
                try:
                    self.subscribers[agent_id].remove(callback)
                except ValueError:
                    pass
            else:
                # Remove all callbacks for this agent
                self.subscribers[agent_id] = []
            
            logger.debug(f"Agent {agent_id} unsubscribed from communication bus")
    
    async def broadcast_message(self, message: AgentMessage, exclude_sender: bool = True) -> int:
        """Broadcast a message to all subscribed agents."""
        delivered_count = 0
        
        for agent_id, callbacks in self.subscribers.items():
            # Skip sender if requested
            if exclude_sender and agent_id == message.sender_id:
                continue
            
            # Create a copy of the message for each recipient
            broadcast_message = AgentMessage(
                sender_id=message.sender_id,
                recipient_id=agent_id,
                message_type=message.message_type,
                content=message.content,
                correlation_id=message.correlation_id,
                timestamp=message.timestamp,
                requires_response=message.requires_response
            )
            
            # Send to all callbacks for this agent
            for callback in callbacks:
                try:
                    await callback(broadcast_message)
                    delivered_count += 1
                except Exception as e:
                    logger.error(f"Error delivering broadcast message to {agent_id}: {str(e)}")
        
        logger.debug(f"Broadcast message delivered to {delivered_count} recipients")
        return delivered_count
    
    async def _message_processing_loop(self):
        """Process messages from the queue."""
        while self.is_running:
            try:
                # Wait for message with timeout
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                await self._deliver_message(message)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in message processing loop: {str(e)}")
    
    async def _deliver_message(self, message: AgentMessage):
        """Deliver a message to its recipient."""
        recipient_id = message.recipient_id
        
        if recipient_id not in self.subscribers:
            logger.warning(f"No subscribers found for recipient: {recipient_id}")
            return
        
        # Deliver to all callbacks for the recipient
        callbacks = self.subscribers[recipient_id]
        for callback in callbacks:
            try:
                await callback(message)
                logger.debug(f"Message delivered: {message.sender_id} -> {recipient_id}")
            except Exception as e:
                logger.error(f"Error delivering message to {recipient_id}: {str(e)}")
    
    def get_message_history(self, agent_id: Optional[str] = None, 
                           limit: int = 100) -> List[AgentMessage]:
        """Get message history, optionally filtered by agent."""
        if agent_id:
            filtered_messages = [
                msg for msg in self.message_history
                if msg.sender_id == agent_id or msg.recipient_id == agent_id
            ]
            return filtered_messages[-limit:]
        else:
            return self.message_history[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get communication bus statistics."""
        return {
            "total_messages": len(self.message_history),
            "active_subscribers": len(self.subscribers),
            "queue_size": self.message_queue.qsize(),
            "is_running": self.is_running,
            "message_types": self._get_message_type_stats()
        }
    
    def _get_message_type_stats(self) -> Dict[str, int]:
        """Get statistics on message types."""
        type_counts = {}
        for message in self.message_history:
            msg_type = message.message_type.value
            type_counts[msg_type] = type_counts.get(msg_type, 0) + 1
        return type_counts


class MessageRouter:
    """Router for intelligent message routing based on content and context."""
    
    def __init__(self, communication_bus: AgentCommunicationBus):
        """Initialize message router."""
        self.communication_bus = communication_bus
        self.routing_rules: List[Dict[str, Any]] = []
    
    def add_routing_rule(self, rule: Dict[str, Any]):
        """Add a routing rule for message routing."""
        self.routing_rules.append(rule)
        logger.debug(f"Added routing rule: {rule}")
    
    async def route_message(self, message: AgentMessage) -> bool:
        """Route a message based on routing rules."""
        # Apply routing rules
        for rule in self.routing_rules:
            if await self._matches_rule(message, rule):
                return await self._apply_rule(message, rule)
        
        # Default routing - direct delivery
        return await self.communication_bus.send_message(message)
    
    async def _matches_rule(self, message: AgentMessage, rule: Dict[str, Any]) -> bool:
        """Check if a message matches a routing rule."""
        # Check message type
        if "message_type" in rule:
            if message.message_type.value != rule["message_type"]:
                return False
        
        # Check sender
        if "sender_pattern" in rule:
            if rule["sender_pattern"] not in message.sender_id:
                return False
        
        # Check content keywords
        if "content_keywords" in rule:
            content_str = json.dumps(message.content).lower()
            for keyword in rule["content_keywords"]:
                if keyword.lower() in content_str:
                    return True
            return False
        
        return True
    
    async def _apply_rule(self, message: AgentMessage, rule: Dict[str, Any]) -> bool:
        """Apply a routing rule to a message."""
        action = rule.get("action", "forward")
        
        if action == "forward":
            # Forward to specified recipients
            recipients = rule.get("recipients", [message.recipient_id])
            success_count = 0
            
            for recipient in recipients:
                forwarded_message = AgentMessage(
                    sender_id=message.sender_id,
                    recipient_id=recipient,
                    message_type=message.message_type,
                    content=message.content,
                    correlation_id=message.correlation_id,
                    timestamp=message.timestamp,
                    requires_response=message.requires_response
                )
                
                if await self.communication_bus.send_message(forwarded_message):
                    success_count += 1
            
            return success_count > 0
        
        elif action == "broadcast":
            # Broadcast to all agents
            return await self.communication_bus.broadcast_message(message) > 0
        
        elif action == "drop":
            # Drop the message
            logger.debug(f"Message dropped by routing rule: {message.message_id}")
            return True
        
        else:
            logger.warning(f"Unknown routing action: {action}")
            return False