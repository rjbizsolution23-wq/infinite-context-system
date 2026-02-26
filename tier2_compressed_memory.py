"""
TIER 2: COMPRESSED MEMORY SYSTEM
Hierarchical summarization and compression of historical context
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json
import hashlib

from config import SystemConfig, TokenCounter, ContextTier, COMPRESSION_PROMPT


@dataclass
class CompressedMemory:
    """A compressed summary of conversation history"""
    summary: str
    token_count: int
    original_message_count: int
    compression_ratio: float
    timestamp: datetime
    time_range: tuple[datetime, datetime]
    importance_score: float = 0.5
    memory_id: str = field(default_factory=lambda: hashlib.md5(
        str(datetime.now().timestamp()).encode()).hexdigest()[:12])
    
    def to_dict(self) -> Dict:
        return {
            "memory_id": self.memory_id,
            "summary": self.summary,
            "token_count": self.token_count,
            "original_message_count": self.original_message_count,
            "compression_ratio": self.compression_ratio,
            "timestamp": self.timestamp.isoformat(),
            "time_range": [self.time_range[0].isoformat(), self.time_range[1].isoformat()],
            "importance_score": self.importance_score
        }


class HierarchicalSummary:
    """
    Multi-level summary structure:
    - Level 1: Ultra-compressed (100 tokens) - High-level overview
    - Level 2: Mid-compressed (500 tokens) - Key details
    - Level 3: Detailed (2000 tokens) - Full context
    """
    
    def __init__(self, original_content: str, metadata: Optional[Dict] = None):
        self.original_content = original_content
        self.metadata = metadata or {}
        self.levels: Dict[int, CompressedMemory] = {}
        self.created_at = datetime.now()
    
    def add_level(self, level: int, compressed_memory: CompressedMemory):
        """Add a compression level"""
        self.levels[level] = compressed_memory
    
    def get_level(self, level: int) -> Optional[CompressedMemory]:
        """Get summary at specific compression level"""
        return self.levels.get(level)
    
    def get_adaptive(self, available_tokens: int) -> Optional[CompressedMemory]:
        """Get most detailed summary that fits in available tokens"""
        # Sort levels by detail (descending)
        sorted_levels = sorted(self.levels.items(), key=lambda x: x[0], reverse=True)
        
        for level, memory in sorted_levels:
            if memory.token_count <= available_tokens:
                return memory
        
        return None


class CompressedMemoryManager:
    """
    Tier 2: Manages compressed historical context
    
    Features:
    - Hierarchical multi-level compression
    - Adaptive summary retrieval
    - Progressive summarization as conversation grows
    - Semantic clustering of related memories
    """
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.token_counter = TokenCounter(config.primary_llm)
        
        # Get tier configuration
        tier_config = config.tier_configs[ContextTier.COMPRESSED]
        self.max_tokens = tier_config.max_tokens
        
        # Storage
        self.compressed_memories: List[CompressedMemory] = []
        self.hierarchical_summaries: List[HierarchicalSummary] = []
        
        # Compression levels (tokens per level)
        self.compression_levels = {
            1: 100,   # Ultra-compressed
            2: 500,   # Mid-compressed
            3: 2000   # Detailed
        }
        
        # LLM for compression (can use cheaper model)
        self.compression_model = config.summary_model
        
        # Tracking
        self.total_compressed_items = 0
        self.current_tokens = 0
    
    def compress_conversation(self, messages: List[Dict], 
                             target_level: int = 2,
                             use_llm: bool = True) -> CompressedMemory:
        """
        Compress a sequence of messages into a summary
        
        Args:
            messages: List of message dicts from Tier 1
            target_level: Compression level (1=ultra, 2=mid, 3=detailed)
            use_llm: Use LLM for compression (vs extractive)
        """
        if not messages:
            return None
        
        # Format messages for compression
        conversation_text = self._format_messages(messages)
        original_tokens = self.token_counter.count(conversation_text)
        target_tokens = self.compression_levels.get(target_level, 500)
        
        # Compress
        if use_llm:
            summary = self._llm_compress(conversation_text, target_tokens)
        else:
            summary = self._extractive_compress(conversation_text, target_tokens)
        
        # Create compressed memory
        time_range = (
            datetime.fromisoformat(messages[0].get('timestamp', datetime.now().isoformat())),
            datetime.fromisoformat(messages[-1].get('timestamp', datetime.now().isoformat()))
        )
        
        compressed = CompressedMemory(
            summary=summary,
            token_count=self.token_counter.count(summary),
            original_message_count=len(messages),
            compression_ratio=self.token_counter.count(summary) / original_tokens,
            timestamp=datetime.now(),
            time_range=time_range,
            importance_score=self._calculate_importance(messages)
        )
        
        # Store
        self.compressed_memories.append(compressed)
        self.current_tokens += compressed.token_count
        self.total_compressed_items += 1
        
        # Manage storage
        self._manage_storage()
        
        return compressed
    
    def create_hierarchical_summary(self, messages: List[Dict],
                                   use_llm: bool = True) -> HierarchicalSummary:
        """
        Create multi-level hierarchical summary
        
        Creates 3 compression levels automatically
        """
        conversation_text = self._format_messages(messages)
        summary = HierarchicalSummary(conversation_text)
        
        # Create each compression level
        for level, target_tokens in self.compression_levels.items():
            if use_llm:
                compressed_text = self._llm_compress(conversation_text, target_tokens)
            else:
                compressed_text = self._extractive_compress(conversation_text, target_tokens)
            
            time_range = (
                datetime.fromisoformat(messages[0].get('timestamp', datetime.now().isoformat())),
                datetime.fromisoformat(messages[-1].get('timestamp', datetime.now().isoformat()))
            )
            
            compressed = CompressedMemory(
                summary=compressed_text,
                token_count=self.token_counter.count(compressed_text),
                original_message_count=len(messages),
                compression_ratio=self.token_counter.count(compressed_text) / 
                                self.token_counter.count(conversation_text),
                timestamp=datetime.now(),
                time_range=time_range,
                importance_score=self._calculate_importance(messages)
            )
            
            summary.add_level(level, compressed)
        
        self.hierarchical_summaries.append(summary)
        return summary
    
    def _llm_compress(self, text: str, target_tokens: int) -> str:
        """
        Use LLM to compress text (placeholder - needs actual LLM call)
        
        In production, this would call OpenAI/Anthropic API:
        response = openai.ChatCompletion.create(
            model=self.compression_model,
            messages=[{"role": "user", "content": prompt}]
        )
        """
        # PLACEHOLDER: In real implementation, call LLM API
        # For now, use extractive compression
        return self._extractive_compress(text, target_tokens)
    
    def _extractive_compress(self, text: str, target_tokens: int) -> str:
        """
        Extractive compression - select most important sentences
        """
        # Split into sentences
        sentences = text.split('. ')
        
        # Score sentences (simple heuristic - can be improved)
        scored = []
        keywords = ['important', 'key', 'remember', 'note', 'decision', 
                   'prefer', 'need', 'must', 'critical', 'essential']
        
        for sent in sentences:
            score = sum(1 for kw in keywords if kw in sent.lower())
            # Boost user messages
            if sent.startswith('User:') or sent.startswith('user:'):
                score += 2
            scored.append((sent, score))
        
        # Sort by score and select top sentences
        sorted_sentences = sorted(scored, key=lambda x: x[1], reverse=True)
        
        # Build compressed text
        compressed = []
        current_tokens = 0
        
        for sent, score in sorted_sentences:
            sent_tokens = self.token_counter.count(sent)
            if current_tokens + sent_tokens <= target_tokens:
                compressed.append(sent)
                current_tokens += sent_tokens
            else:
                break
        
        return '. '.join(compressed) + '.'
    
    def _format_messages(self, messages: List[Dict]) -> str:
        """Format messages for compression"""
        formatted = []
        for msg in messages:
            role = msg.get('role', 'unknown').capitalize()
            content = msg.get('content', '')
            formatted.append(f"{role}: {content}")
        return '\n\n'.join(formatted)
    
    def _calculate_importance(self, messages: List[Dict]) -> float:
        """Calculate importance score for a message sequence"""
        # Average importance scores if available
        scores = [msg.get('importance_score', 0.5) for msg in messages]
        if not scores:
            return 0.5
        
        # Weight recent messages higher
        weighted_sum = sum(score * (i + 1) for i, score in enumerate(scores))
        weight_total = sum(i + 1 for i in range(len(scores)))
        
        return weighted_sum / weight_total if weight_total > 0 else 0.5
    
    def _manage_storage(self):
        """Manage storage to stay within token budget"""
        while self.current_tokens > self.max_tokens and self.compressed_memories:
            # Remove oldest, least important memory
            sorted_memories = sorted(
                self.compressed_memories,
                key=lambda m: (m.importance_score, m.timestamp)
            )
            
            removed = sorted_memories[0]
            self.compressed_memories.remove(removed)
            self.current_tokens -= removed.token_count
    
    def get_relevant_memories(self, query: Optional[str] = None,
                             max_tokens: Optional[int] = None,
                             top_k: int = 5) -> List[CompressedMemory]:
        """
        Retrieve relevant compressed memories
        
        Args:
            query: Optional query for relevance scoring
            max_tokens: Maximum tokens to return
            top_k: Number of memories to return
        """
        if max_tokens is None:
            max_tokens = self.max_tokens // 2
        
        # Sort by importance and recency
        sorted_memories = sorted(
            self.compressed_memories,
            key=lambda m: (m.importance_score, m.timestamp),
            reverse=True
        )
        
        # Select memories that fit in budget
        selected = []
        current_tokens = 0
        
        for memory in sorted_memories[:top_k]:
            if current_tokens + memory.token_count <= max_tokens:
                selected.append(memory)
                current_tokens += memory.token_count
            else:
                break
        
        return selected
    
    def get_context_summary(self, available_tokens: int) -> str:
        """Get formatted context summary for LLM"""
        memories = self.get_relevant_memories(max_tokens=available_tokens)
        
        if not memories:
            return ""
        
        formatted = ["=== Historical Context ===\n"]
        for i, memory in enumerate(memories, 1):
            time_str = memory.time_range[0].strftime("%Y-%m-%d %H:%M")
            formatted.append(f"\n[Memory {i} | {time_str} | {memory.original_message_count} messages]")
            formatted.append(memory.summary)
        
        return '\n'.join(formatted)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about compressed memory"""
        total_original_messages = sum(m.original_message_count for m in self.compressed_memories)
        avg_compression = (sum(m.compression_ratio for m in self.compressed_memories) / 
                          len(self.compressed_memories)) if self.compressed_memories else 0
        
        return {
            "total_memories": len(self.compressed_memories),
            "hierarchical_summaries": len(self.hierarchical_summaries),
            "current_tokens": self.current_tokens,
            "max_tokens": self.max_tokens,
            "utilization": f"{(self.current_tokens / self.max_tokens * 100):.1f}%",
            "original_messages_compressed": total_original_messages,
            "average_compression_ratio": f"{avg_compression:.2%}",
            "total_items_processed": self.total_compressed_items
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    from config import SystemConfig
    
    print("=" * 70)
    print("TIER 2: COMPRESSED MEMORY - Demo")
    print("=" * 70)
    
    # Initialize
    config = SystemConfig()
    memory_manager = CompressedMemoryManager(config)
    
    # Simulate messages to compress
    messages = [
        {"role": "user", "content": "I need help building a transformer model for NLP.", 
         "timestamp": datetime.now().isoformat(), "importance_score": 0.8},
        {"role": "assistant", "content": "I'll help you with that. Let's start with the architecture...",
         "timestamp": datetime.now().isoformat(), "importance_score": 0.6},
        {"role": "user", "content": "Important: I need multi-head attention with 8 heads.",
         "timestamp": datetime.now().isoformat(), "importance_score": 0.9},
    ]
    
    # Compress conversation
    compressed = memory_manager.compress_conversation(messages, target_level=2, use_llm=False)
    
    print("\nCompression Result:")
    print(f"  Original messages: {compressed.original_message_count}")
    print(f"  Compressed tokens: {compressed.token_count}")
    print(f"  Compression ratio: {compressed.compression_ratio:.2%}")
    print(f"  Importance score: {compressed.importance_score:.2f}")
    
    # Create hierarchical summary
    hierarchical = memory_manager.create_hierarchical_summary(messages, use_llm=False)
    
    print("\nHierarchical Summary:")
    for level in [1, 2, 3]:
        mem = hierarchical.get_level(level)
        if mem:
            print(f"  Level {level}: {mem.token_count} tokens (ratio: {mem.compression_ratio:.2%})")
    
    # Show stats
    print("\nMemory Manager Statistics:")
    stats = memory_manager.get_stats()
    for key, value in stats.items():
        print(f"  {key:30}: {value}")
    
    print("\n" + "=" * 70)
