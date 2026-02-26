"""
INFINITE CONTEXT ORCHESTRATOR
Master system that intelligently combines all 4 context tiers
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json

from config import SystemConfig, TokenCounter, SYSTEM_PROMPT_TEMPLATE
from tier1_active_context import ActiveContextWindow, Message
from tier2_compressed_memory import CompressedMemoryManager
from tier3_vector_retrieval import VectorRetrievalSystem, Document
from tier4_persistent_memory import PersistentMemorySystem


@dataclass
class ContextBudget:
    """Token budget allocation across tiers"""
    tier1_active: int
    tier2_compressed: int
    tier3_retrieval: int
    tier4_persistent: int
    system_prompt: int
    
    @property
    def total(self) -> int:
        return (self.tier1_active + self.tier2_compressed + 
                self.tier3_retrieval + self.tier4_persistent + 
                self.system_prompt)


class InfiniteContextOrchestrator:
    """
    Master orchestrator for the 4-tier infinite context system
    
    Responsibilities:
    - Route queries to appropriate tiers
    - Allocate token budget intelligently
    - Combine context from all tiers
    - Optimize for relevance + recency
    - Track performance metrics
    """
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.token_counter = TokenCounter(config.primary_llm)
        
        # Initialize all tiers
        self.tier1 = ActiveContextWindow(config)
        self.tier2 = CompressedMemoryManager(config)
        self.tier3 = VectorRetrievalSystem(config)
        self.tier4 = PersistentMemorySystem(config)
        
        # Performance tracking
        self.total_queries = 0
        self.total_tokens_used = 0
        self.tier_usage_stats = {
            "tier1": 0, "tier2": 0, "tier3": 0, "tier4": 0
        }
        
        # Session tracking
        self.session_start = datetime.now()
        self.message_count = 0
    
    async def process_message(self, role: str, content: str,
                       importance_score: float = 0.5,
                       metadata: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Process a new message through the system
        
        Args:
            role: Message role (user, assistant)
            content: Message content
            importance_score: Importance rating (0-1)
            metadata: Optional metadata
        
        Returns:
            Processing result with context information
        """
        self.message_count += 1
        
        # Add to Tier 1 (Active Context)
        message = await self.tier1.add_message(
            role=role,
            content=content,
            metadata=metadata,
            importance_score=importance_score
        )
        
        # Extract entities for Tier 4 (Persistent Memory)
        entities = []
        if self.config.enable_entity_memory:
            entities = await self.tier4.extract_and_store_entities(content, metadata)
        
        # Check if compression needed
        if (self.message_count % self.config.memory_consolidation_interval == 0 and
            self.config.enable_short_term_memory):
            await self._consolidate_memory()
        
        return {
            "message_id": message.metadata.get("id", "unknown"),
            "tokens": message.tokens,
            "entities_extracted": len(entities) if self.config.enable_entity_memory else 0,
            "tier1_utilization": self.tier1.get_window_stats()["utilization"]
        }
    
    async def generate_context(self, query: str,
                        max_tokens: Optional[int] = None) -> Dict[str, Any]:
        """
        Generate complete context for LLM by intelligently combining all tiers
        
        Args:
            query: Current user query
            max_tokens: Maximum total tokens (defaults to config)
        
        Returns:
            Dictionary with formatted context and metadata
        """
        if max_tokens is None:
            max_tokens = self.config.token_budget_per_request
        
        # Calculate token budget allocation
        budget = self._allocate_token_budget(max_tokens, query)
        
        # Collect context from each tier
        contexts = {}
        
        # TIER 1: Active Context (always included)
        tier1_context = self.tier1.get_context_for_llm(include_key_points=True)
        contexts["tier1"] = tier1_context
        self.tier_usage_stats["tier1"] += 1
        
        # TIER 2: Compressed Memory (if available)
        if self.config.enable_short_term_memory and budget.tier2_compressed > 0:
            tier2_context = self.tier2.get_context_summary(budget.tier2_compressed)
            if tier2_context:
                contexts["tier2"] = tier2_context
                self.tier_usage_stats["tier2"] += 1
        
        # TIER 3: Vector Retrieval (query-driven)
        if budget.tier3_retrieval > 0:
            retrieval_results = await self.tier3.retrieve(
                query=query,
                top_k=10,
                strategy=self.config.retrieval_strategy
            )
            if retrieval_results:
                tier3_context = self.tier3.get_context_for_llm(
                    retrieval_results,
                    max_tokens=budget.tier3_retrieval
                )
                contexts["tier3"] = tier3_context
                self.tier_usage_stats["tier3"] += 1
        
        # TIER 4: Persistent Memory (entity-driven)
        if self.config.enable_long_term_memory and budget.tier4_persistent > 0:
            tier4_context = self.tier4.get_context_for_llm(
                query=query,
                max_tokens=budget.tier4_persistent
            )
            if tier4_context:
                contexts["tier4"] = tier4_context
                self.tier_usage_stats["tier4"] += 1
        
        # Build system prompt with context summary
        context_summary = self._build_context_summary(contexts, budget)
        system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
            context_summary=context_summary,
            task_description=query
        )
        
        # Count total tokens
        total_tokens = sum(
            self.token_counter.count(str(ctx)) 
            for ctx in contexts.values()
        ) + self.token_counter.count(system_prompt)
        
        self.total_queries += 1
        self.total_tokens_used += total_tokens
        
        return {
            "system_prompt": system_prompt,
            "contexts": contexts,
            "budget": budget,
            "total_tokens": total_tokens,
            "budget_utilization": f"{(total_tokens / max_tokens * 100):.1f}%"
        }
    
    def _allocate_token_budget(self, max_tokens: int, query: str) -> ContextBudget:
        """
        Intelligently allocate token budget across tiers
        
        Strategy:
        - Reserve tokens for system prompt
        - Prioritize Tier 1 (active context)
        - Allocate remaining based on query type and tier weights
        """
        # Reserve for system prompt
        system_prompt_tokens = 500
        available = max_tokens - system_prompt_tokens
        
        # Get tier configurations
        tier1_config = self.config.tier_configs[self.config.tier_configs.keys().__iter__().__next__()]
        
        # Base allocation (proportional to tier capacity and priority)
        tier_weights = {
            "tier1": 0.35,  # 35% - Active context is most important
            "tier2": 0.20,  # 20% - Compressed memory
            "tier3": 0.30,  # 30% - Retrieval (query-dependent)
            "tier4": 0.15   # 15% - Persistent memory
        }
        
        # Adjust based on query characteristics
        query_lower = query.lower()
        
        # If query asks about history, boost Tier 2
        if any(word in query_lower for word in ['history', 'earlier', 'before', 'previous']):
            tier_weights["tier2"] += 0.10
            tier_weights["tier1"] -= 0.05
            tier_weights["tier3"] -= 0.05
        
        # If query is knowledge-seeking, boost Tier 3
        if any(word in query_lower for word in ['what', 'how', 'why', 'explain', 'tell me about']):
            tier_weights["tier3"] += 0.10
            tier_weights["tier1"] -= 0.10
        
        # If query mentions entities, boost Tier 4
        entities = self.tier4.get_relevant_entities(query, top_k=3)
        if entities:
            tier_weights["tier4"] += 0.10
            tier_weights["tier2"] -= 0.05
            tier_weights["tier3"] -= 0.05
        
        # Normalize weights
        total_weight = sum(tier_weights.values())
        tier_weights = {k: v / total_weight for k, v in tier_weights.items()}
        
        # Calculate allocations
        return ContextBudget(
            tier1_active=int(available * tier_weights["tier1"]),
            tier2_compressed=int(available * tier_weights["tier2"]),
            tier3_retrieval=int(available * tier_weights["tier3"]),
            tier4_persistent=int(available * tier_weights["tier4"]),
            system_prompt=system_prompt_tokens
        )
    
    def _build_context_summary(self, contexts: Dict[str, Any],
                              budget: ContextBudget) -> str:
        """Build summary of available context for system prompt"""
        summary_parts = []
        
        tier_descriptions = {
            "tier1": f"ACTIVE CONTEXT ({budget.tier1_active} tokens allocated)",
            "tier2": f"COMPRESSED MEMORY ({budget.tier2_compressed} tokens allocated)",
            "tier3": f"RETRIEVED KNOWLEDGE ({budget.tier3_retrieval} tokens allocated)",
            "tier4": f"PERSISTENT MEMORY ({budget.tier4_persistent} tokens allocated)"
        }
        
        for tier_name, description in tier_descriptions.items():
            if tier_name in contexts and contexts[tier_name]:
                summary_parts.append(f"✓ {description} - Available")
            else:
                summary_parts.append(f"✗ {description} - Not used")
        
        return '\n'.join(summary_parts)
    
    async def _consolidate_memory(self):
        """Consolidate active context into compressed memory"""
        # Export messages from Tier 1
        messages = self.tier1.export_for_compression()
        
        if len(messages) > 5:  # Only compress if we have enough messages
            # Create hierarchical summary
            await self.tier2.create_hierarchical_summary(
                messages,
                use_llm=True
            )
            
            # Clear old messages from Tier 1, keeping recent ones
            self.tier1.clear_old_messages(keep_recent=5)
    
    async def add_knowledge_document(self, content: str, metadata: Optional[Dict] = None):
        """Add a document to the knowledge base (Tier 3)"""
        import uuid
        
        doc = Document(
            doc_id=str(uuid.uuid4()),
            content=content,
            metadata=metadata or {},
            source=metadata.get("source", "user_provided") if metadata else "user_provided"
        )
        
        await self.tier3.add_documents([doc], generate_embeddings=True)
    
    def set_user_preference(self, key: str, value: Any, confidence: float = 1.0):
        """Set a user preference in Tier 4"""
        self.tier4.add_user_preference(key, value, confidence)
    
    def get_system_stats(self) -> Dict[str, Any]:
        """Get comprehensive system statistics"""
        session_duration = (datetime.now() - self.session_start).total_seconds()
        
        return {
            "session_duration_seconds": round(session_duration, 2),
            "total_queries": self.total_queries,
            "total_messages": self.message_count,
            "total_tokens_used": self.total_tokens_used,
            "avg_tokens_per_query": round(self.total_tokens_used / max(self.total_queries, 1)),
            
            "tier_usage": self.tier_usage_stats,
            
            "tier1_stats": self.tier1.get_window_stats(),
            "tier2_stats": self.tier2.get_stats(),
            "tier3_stats": self.tier3.get_stats(),
            "tier4_stats": self.tier4.get_stats(),
            
            "configuration": {
                "max_llm_context": self.config.max_llm_context,
                "total_tier_capacity": self.config.get_total_context_capacity(),
                "embedding_model": self.config.embedding_model,
                "retrieval_strategy": self.config.retrieval_strategy
            }
        }
    
    def export_session(self, filepath: str):
        """Export entire session including all tiers"""
        export_data = {
            "session_start": self.session_start.isoformat(),
            "session_stats": self.get_system_stats(),
            "tier1_messages": self.tier1.export_for_compression(),
            "tier2_memories": [m.to_dict() for m in self.tier2.compressed_memories],
            "tier4_memory": {
                "entities": [e.to_dict() for e in self.tier4.entity_graph.entities.values()],
                "relationships": [r.to_dict() for r in self.tier4.entity_graph.relationships.values()],
                "preferences": self.tier4.user_preferences
            }
        }
        
        with open(filepath, 'w') as f:
            json.dump(export_data, f, indent=2)
        
        print(f"Session exported to: {filepath}")


# ============================================================================
# COMPLETE USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    print("=" * 70)
    print("INFINITE CONTEXT ORCHESTRATOR - Complete Demo")
    print("=" * 70)
    
    # Initialize system
    config = SystemConfig()
    orchestrator = InfiniteContextOrchestrator(config)
    
    # Set system message
    orchestrator.tier1.set_system_message(
        "You are an AI assistant with infinite context capabilities."
    )
    
    # Simulate conversation
    print("\n[1] Processing user message...")
    result = orchestrator.process_message(
        role="user",
        content="I'm working on a machine learning project using PyTorch.",
        importance_score=0.7
    )
    print(f"    Tokens: {result['tokens']}, Entities: {result['entities_extracted']}")
    
    print("\n[2] Adding assistant response...")
    orchestrator.process_message(
        role="assistant",
        content="Great! I'll help you with your PyTorch ML project. What specifically are you building?",
        importance_score=0.5
    )
    
    print("\n[3] Adding knowledge document...")
    orchestrator.add_knowledge_document(
        content="PyTorch is a deep learning framework that provides tensor computation with GPU acceleration.",
        metadata={"source": "documentation", "topic": "pytorch"}
    )
    
    print("\n[4] Setting user preference...")
    orchestrator.set_user_preference("ml.framework", "PyTorch", confidence=0.9)
    
    print("\n[5] Generating context for query...")
    query = "What should I know about PyTorch for my project?"
    context_data = orchestrator.generate_context(query, max_tokens=100000)
    
    print(f"\n    Generated context:")
    print(f"    - Total tokens: {context_data['total_tokens']}")
    print(f"    - Budget utilization: {context_data['budget_utilization']}")
    print(f"    - Tiers used: {', '.join(context_data['contexts'].keys())}")
    
    # Show comprehensive stats
    print("\n" + "=" * 70)
    print("SYSTEM STATISTICS")
    print("=" * 70)
    
    stats = orchestrator.get_system_stats()
    
    print(f"\nSession Overview:")
    print(f"  Duration: {stats['session_duration_seconds']}s")
    print(f"  Total Queries: {stats['total_queries']}")
    print(f"  Total Messages: {stats['total_messages']}")
    print(f"  Total Tokens Used: {stats['total_tokens_used']:,}")
    
    print(f"\nTier Usage:")
    for tier, count in stats['tier_usage'].items():
        print(f"  {tier}: {count} times")
    
    print(f"\nTier 1 (Active Context):")
    for key, value in stats['tier1_stats'].items():
        print(f"  {key}: {value}")
    
    print(f"\nTier 2 (Compressed Memory):")
    for key, value in stats['tier2_stats'].items():
        print(f"  {key}: {value}")
    
    print(f"\nTier 3 (Vector Retrieval):")
    for key, value in stats['tier3_stats'].items():
        print(f"  {key}: {value}")
    
    print(f"\nTier 4 (Persistent Memory):")
    for key, value in stats['tier4_stats'].items():
        print(f"  {key}: {value}")
    
    print("\n" + "=" * 70)
    print("System successfully demonstrated all 4 tiers!")
    print("=" * 70)
