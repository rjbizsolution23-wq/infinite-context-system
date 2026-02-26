"""
TIER 1: ACTIVE CONTEXT WINDOW MANAGER
Manages the immediate conversation window with sliding window + key points retention
"""

import json
import logging
import asyncio
import aiofiles
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from collections import deque

from src.lib.config import SystemConfig, TokenCounter, ContextTier


@dataclass
class Message:
    """Represents a single message in the conversation"""
    role: str  # system, user, assistant
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    tokens: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance_score: float = 0.5  # 0-1, higher = more important
    
    def to_dict(self) -> Dict:
        return {
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "tokens": self.tokens,
            "metadata": self.metadata,
            "importance_score": self.importance_score
        }


@dataclass
class KeyPoint:
    """Important information extracted from conversation"""
    content: str
    source_message_idx: int
    extraction_time: datetime
    relevance_score: float
    category: str  # fact, decision, preference, question, etc.


class ActiveContextWindow:
    """
    Tier 1: Manages active conversation window with intelligent retention
    
    Features:
    - Sliding window with configurable size
    - Key point extraction and preservation
    - Importance-based message retention
    - Token-aware management
    """
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.token_counter = TokenCounter(config.primary_llm)
        
        # Get tier configuration
        tier_config = config.tier_configs[ContextTier.ACTIVE]
        self.max_tokens = tier_config.max_tokens
        
        # Message storage
        self.messages: deque[Message] = deque(maxlen=1000)
        self.key_points: List[KeyPoint] = []
        
        # System message (always kept)
        self.system_message: Optional[Message] = None
        
        # Tracking
        self.current_tokens = 0
        self.total_messages_processed = 0
        
        # Persistence
        self.persistence_path = config.tier1_db_path
        
    async def load_from_disk(self):
        """Load messages from disk if available"""
        if not self.persistence_path.exists():
            return
        
        try:
            async with aiofiles.open(self.persistence_path, mode='r') as f:
                async for line in f:
                    data = json.loads(line)
                    msg = Message(
                        role=data['role'],
                        content=data['content'],
                        timestamp=datetime.fromisoformat(data['timestamp']),
                        tokens=data['tokens'],
                        metadata=data['metadata'],
                        importance_score=data['importance_score']
                    )
                    if msg.role == "system":
                        self.system_message = msg
                    else:
                        self.messages.append(msg)
                        self.current_tokens += msg.tokens
            self.logger.info(f"Loaded {len(self.messages)} messages from Tier 1 storage")
        except Exception as e:
            self.logger.error(f"Error loading Tier 1 messages: {e}")

    async def _save_to_disk(self):
        """Save all current messages to disk"""
        try:
            async with aiofiles.open(self.persistence_path, mode='w') as f:
                if self.system_message:
                    await f.write(json.dumps(self.system_message.to_dict()) + '\n')
                for msg in self.messages:
                    await f.write(json.dumps(msg.to_dict()) + '\n')
        except Exception as e:
            self.logger.error(f"Error saving Tier 1 messages: {e}")

    async def add_message(self, role: str, content: str, 
                   metadata: Optional[Dict] = None,
                   importance_score: float = 0.5) -> Message:
        """
        Add a new message to the active window
        
        Args:
            role: Message role (system, user, assistant)
            content: Message content
            metadata: Optional metadata
            importance_score: Importance rating (0-1)
        """
        # Count tokens
        tokens = self.token_counter.count(content)
        
        # Create message
        message = Message(
            role=role,
            content=content,
            tokens=tokens,
            metadata=metadata or {},
            importance_score=importance_score
        )
        
        # Handle system message separately
        if role == "system":
            self.system_message = message
            return message
        
        # Add to messages
        self.messages.append(message)
        self.current_tokens += tokens
        self.total_messages_processed += 1
        
        # Manage window size
        self._manage_window_size()
        
        # Extract key points if needed
        if self.total_messages_processed % 5 == 0:
            await self._extract_key_points()
        
        # Persistent save
        await self._save_to_disk()
        
        return message
    
    def _manage_window_size(self):
        """Ensure window stays within token budget"""
        # Remove oldest messages if over budget
        while self.current_tokens > self.max_tokens and len(self.messages) > 1:
            removed = self.messages.popleft()
            self.current_tokens -= removed.tokens
            
            # Try to extract key point before removal if important
            if removed.importance_score > 0.7:
                self._extract_key_point_from_message(removed, len(self.messages))
    
    async def _extract_key_points(self):
        """Extract key information from recent messages using LLM"""
        # In production, this would call LLM. For now, using heuristic.
        # TODO: Implement Async LLM call here
        recent_messages = list(self.messages)[-5:]
        
        for idx, msg in enumerate(recent_messages):
            # Check for indicators of important information
            indicators = [
                "important:", "note:", "remember:", 
                "key point:", "decision:", "preference:",
                "don't forget:", "crucial:"
            ]
            
            content_lower = msg.content.lower()
            for indicator in indicators:
                if indicator in content_lower:
                    # Extract the key point
                    key_point = KeyPoint(
                        content=msg.content,
                        source_message_idx=len(self.messages) - len(recent_messages) + idx,
                        extraction_time=datetime.now(),
                        relevance_score=0.8,
                        category="important"
                    )
                    self.key_points.append(key_point)
                    break
    
    def _extract_key_point_from_message(self, message: Message, position: int):
        """Extract key point from a specific message before removal"""
        key_point = KeyPoint(
            content=message.content[:500],  # First 500 chars
            source_message_idx=position,
            extraction_time=datetime.now(),
            relevance_score=message.importance_score,
            category="preserved"
        )
        self.key_points.append(key_point)
    
    def get_context_for_llm(self, include_key_points: bool = True) -> List[Dict]:
        """
        Get formatted context for LLM API call
        
        Returns:
            List of message dicts in OpenAI format
        """
        context = []
        
        # Add system message
        if self.system_message:
            context.append({
                "role": "system",
                "content": self.system_message.content
            })
        
        # Add key points as system context if enabled
        if include_key_points and self.key_points:
            key_points_text = self._format_key_points()
            context.append({
                "role": "system",
                "content": f"Key points from earlier conversation:\n{key_points_text}"
            })
        
        # Add recent messages
        for msg in self.messages:
            context.append({
                "role": msg.role,
                "content": msg.content
            })
        
        return context
    
    def _format_key_points(self) -> str:
        """Format key points for injection into context"""
        if not self.key_points:
            return ""
        
        # Group by category
        by_category: Dict[str, List[KeyPoint]] = {}
        for kp in self.key_points[-10:]:  # Last 10 key points
            by_category.setdefault(kp.category, []).append(kp)
        
        formatted = []
        for category, points in by_category.items():
            formatted.append(f"\n[{category.upper()}]")
            for point in points:
                formatted.append(f"- {point.content[:200]}")
        
        return "\n".join(formatted)
    
    def get_window_stats(self) -> Dict[str, Any]:
        """Get statistics about the current window"""
        return {
            "total_messages": len(self.messages),
            "current_tokens": self.current_tokens,
            "max_tokens": self.max_tokens,
            "utilization": f"{(self.current_tokens / self.max_tokens * 100):.1f}%",
            "key_points": len(self.key_points),
            "total_processed": self.total_messages_processed,
            "has_system_message": self.system_message is not None
        }
    
    def export_for_compression(self) -> List[Dict]:
        """Export messages for compression to Tier 2"""
        return [msg.to_dict() for msg in self.messages]
    
    def clear_old_messages(self, keep_recent: int = 5):
        """Clear old messages, keeping only recent N"""
        if len(self.messages) <= keep_recent:
            return
        
        # Extract key points from messages being removed
        messages_to_remove = list(self.messages)[:-keep_recent]
        for idx, msg in enumerate(messages_to_remove):
            if msg.importance_score > 0.6:
                self._extract_key_point_from_message(msg, idx)
        
        # Keep only recent messages
        recent = list(self.messages)[-keep_recent:]
        self.messages.clear()
        self.messages.extend(recent)
        
        # Recalculate tokens
        self.current_tokens = sum(msg.tokens for msg in self.messages)
    
    def set_system_message(self, content: str):
        """Set or update the system message"""
        tokens = self.token_counter.count(content)
        self.system_message = Message(
            role="system",
            content=content,
            tokens=tokens
        )
    
    async def sync_from_redis(self):
        """Pull latest messages from Redis for Agent Swarm sync."""
        if not self.redis:
            return
            
        try:
            raw_messages = self.redis.lrange("ics:tier1:messages", 0, -1)
            if not raw_messages:
                return
                
            self.messages.clear()
            self.current_tokens = 0
            
            for raw in raw_messages:
                data = json.loads(raw)
                msg = Message(
                    role=data['role'],
                    content=data['content'],
                    timestamp=datetime.fromisoformat(data['timestamp']),
                    tokens=data['tokens'],
                    metadata=data['metadata'],
                    importance_score=data['importance_score']
                )
                self.messages.append(msg)
                self.current_tokens += msg.tokens
            
            self.logger.info(f"Synced {len(self.messages)} messages from Redis")
        except Exception as e:
            self.logger.error(f"Error syncing Tier 1 from Redis: {e}")

    def boost_message_importance(self, message_idx: int, new_score: float):
        """Increase importance score of a specific message"""
        if 0 <= message_idx < len(self.messages):
            self.messages[message_idx].importance_score = min(1.0, new_score)


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    from config import SystemConfig
    
    print("=" * 70)
    print("TIER 1: ACTIVE CONTEXT WINDOW - Demo")
    print("=" * 70)
    
    # Initialize
    config = SystemConfig()
    window = ActiveContextWindow(config)
    
    # Set system message
    window.set_system_message(
        "You are a helpful AI assistant with infinite context capabilities."
    )
    
    # Simulate conversation
    window.add_message("user", "Hello! I'm working on a machine learning project.", 
                      importance_score=0.6)
    window.add_message("assistant", "Great! I'd be happy to help. What kind of ML project?",
                      importance_score=0.5)
    window.add_message("user", "Important: I need to build a transformer model for NLP.",
                      importance_score=0.9)
    window.add_message("assistant", "Perfect! Let me help you with transformer architecture...",
                      importance_score=0.5)
    
    # Show stats
    print("\nWindow Statistics:")
    stats = window.get_window_stats()
    for key, value in stats.items():
        print(f"  {key:20}: {value}")
    
    # Show context
    print("\nContext for LLM:")
    context = window.get_context_for_llm()
    print(f"  Total messages: {len(context)}")
    print(f"  Includes key points: {any('Key points' in msg.get('content', '') for msg in context)}")
    
    print("\n" + "=" * 70)
