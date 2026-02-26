"""
ULTIMATE INFINITE CONTEXT SYSTEM - Core Configuration
Implements 4-tier hybrid context architecture with intelligent routing
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
from pathlib import Path

# ============================================================================
# SYSTEM CONFIGURATION
# ============================================================================

@dataclass
class ContextTierConfig:
    """Configuration for each context tier"""
    max_tokens: int
    priority_weight: float
    enabled: bool = True

class ContextTier(Enum):
    """Four-tier context hierarchy"""
    ACTIVE = "active"           # Tier 1: Current window
    COMPRESSED = "compressed"   # Tier 2: Summarized memory
    RETRIEVAL = "retrieval"     # Tier 3: Vector search
    PERSISTENT = "persistent"   # Tier 4: Long-term storage

@dataclass
class SystemConfig:
    """Master configuration for infinite context system"""
    
    # API Keys
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    cohere_api_key: str = os.getenv("COHERE_API_KEY", "")
    
    # LLM Configuration
    primary_llm: str = "gpt-4-turbo-2024-04-09"
    fallback_llm: str = "claude-3-5-sonnet-20240620"
    llm_provider: str = "openai"
    max_llm_context: int = 128000
    
    # Storage Paths
    storage_root: Path = Path("./storage")
    tier1_db_path: Path = Path("./storage/tier1_active.jsonl")
    
    # Embedding Configuration
    embedding_model: str = "text-embedding-3-large"
    embedding_dimensions: int = 3072
    embedding_batch_size: int = 100
    
    # Context Tier Configuration
    tier_configs: Dict[ContextTier, ContextTierConfig] = None
    
    # Vector Database (Qdrant)
    vector_db_type: str = "qdrant"
    vector_db_url: str = os.getenv("QDRANT_URL", "http://localhost:6333")
    vector_db_api_key: str = os.getenv("QDRANT_API_KEY", "")
    collection_name: str = "infinite_context"
    
    # Feature Flags
    enable_semantic_cache: bool = True
    enable_self_rag: bool = True
    self_rag_threshold: float = 0.7
    
    # Memory Configuration
    enable_short_term_memory: bool = True
    enable_long_term_memory: bool = True
    enable_entity_memory: bool = True
    memory_consolidation_interval: int = 10
    
    # Retrieval Configuration
    retrieval_top_k: int = 20
    retrieval_strategy: str = "hybrid"
    rerank_enabled: bool = True
    rerank_top_n: int = 5
    
    # Compression Configuration
    compression_enabled: bool = True
    compression_ratio: float = 0.5
    summary_model: str = "gpt-4o-mini"
    
    # Graph Memory (Neo4j)
    neo4j_uri: str = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user: str = os.getenv("NEO4J_USER", "neo4j")
    neo4j_password: str = os.getenv("NEO4J_PASSWORD", "")
    
    # Performance & Async
    enable_caching: bool = True
    cache_ttl: int = 3600
    parallel_retrieval: bool = True
    max_workers: int = 10
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    
    # Cost Optimization
    token_budget_per_request: int = 100000
    enable_token_tracking: bool = True
    
    def __post_init__(self):
        """Initialize configurations and create storage"""
        os.makedirs(self.storage_root, exist_ok=True)
        self._setup_logging()
        
        if self.tier_configs is None:
            self.tier_configs = {
                ContextTier.ACTIVE: ContextTierConfig(max_tokens=32000, priority_weight=1.0),
                ContextTier.COMPRESSED: ContextTierConfig(max_tokens=50000, priority_weight=0.7),
                ContextTier.RETRIEVAL: ContextTierConfig(max_tokens=40000, priority_weight=0.5),
                ContextTier.PERSISTENT: ContextTierConfig(max_tokens=6000, priority_weight=0.3)
            }
            
    def _setup_logging(self):
        """Configure structured logging"""
        logging.basicConfig(
            level=getattr(logging, self.log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            force=True
        )
    
    def get_total_context_capacity(self) -> int:
        """Calculate total context capacity across all tiers"""
        return sum(
            tier.max_tokens 
            for tier in self.tier_configs.values() 
            if tier.enabled
        )
    
    def validate(self) -> bool:
        """Validate configuration"""
        total = self.get_total_context_capacity()
        if total > self.max_llm_context:
            print(f"Warning: Total tier capacity ({total}) exceeds LLM max ({self.max_llm_context})")
            return False
        
        if not self.openai_api_key:
            print("Error: OPENAI_API_KEY not set")
            return False
            
        return True


# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

SYSTEM_PROMPT_TEMPLATE = """You are an AI assistant with INFINITE CONTEXT capabilities across four memory tiers:

**TIER 1 - ACTIVE CONTEXT**: Recent conversation and immediate task context
**TIER 2 - COMPRESSED MEMORY**: Hierarchical summaries of past interactions  
**TIER 3 - RETRIEVAL**: Semantic search across all stored knowledge
**TIER 4 - PERSISTENT**: Long-term entity memory and user preferences

You have access to the following context:

{context_summary}

**Instructions:**
1. Synthesize information across all context tiers
2. Prioritize recent/relevant information over older data
3. Cite sources when referencing retrieved information
4. Track entities and relationships mentioned
5. Update memory after each interaction

**Current Task:** {task_description}
"""

COMPRESSION_PROMPT = """Compress the following conversation history into a dense summary preserving:
1. Key facts and decisions
2. Important entities and relationships  
3. User preferences and patterns
4. Critical context for future interactions

Conversation:
{conversation}

Provide a compressed summary (target {target_tokens} tokens):"""

ENTITY_EXTRACTION_PROMPT = """Extract structured entities from the following text:

Text: {text}

Return a JSON with:
{{
  "entities": [
    {{"name": "entity_name", "type": "PERSON|ORG|CONCEPT|EVENT", "attributes": {{}}}},
  ],
  "relationships": [
    {{"from": "entity1", "to": "entity2", "type": "relationship_type"}},
  ]
}}
"""

# ============================================================================
# TOKEN COUNTING UTILITIES
# ============================================================================

import tiktoken

class TokenCounter:
    """Accurate token counting for different models"""
    
    def __init__(self, model: str = "gpt-4"):
        try:
            self.encoding = tiktoken.encoding_for_model(model)
        except KeyError:
            self.encoding = tiktoken.get_encoding("cl100k_base")
    
    def count(self, text: str) -> int:
        """Count tokens in text"""
        return len(self.encoding.encode(text))
    
    def truncate(self, text: str, max_tokens: int) -> str:
        """Truncate text to max tokens"""
        tokens = self.encoding.encode(text)
        if len(tokens) <= max_tokens:
            return text
        return self.encoding.decode(tokens[:max_tokens])


# ============================================================================
# EXPORT DEFAULT CONFIG
# ============================================================================

# Create default configuration
DEFAULT_CONFIG = SystemConfig()

if __name__ == "__main__":
    config = SystemConfig()
    print("=" * 70)
    print("ULTIMATE INFINITE CONTEXT SYSTEM - Configuration")
    print("=" * 70)
    print(f"\nTotal Context Capacity: {config.get_total_context_capacity():,} tokens")
    print(f"LLM Max Context: {config.max_llm_context:,} tokens")
    print(f"\nTier Configuration:")
    for tier, tier_config in config.tier_configs.items():
        print(f"  {tier.value.upper():12} | {tier_config.max_tokens:6,} tokens | Priority: {tier_config.priority_weight:.1f}")
    print(f"\nConfiguration Valid: {config.validate()}")
    print("=" * 70)
