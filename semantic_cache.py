"""
SEMANTIC CACHE
High-performance similarity-based context caching
"""

import json
import logging
from typing import Optional, Dict, Any, List
import numpy as np
from openai import AsyncOpenAI

class SemanticCache:
    """
    Caches LLM context payloads based on semantic similarity of queries.
    Reduces latency and token costs for repeated/similar questions.
    """
    
    def __init__(self, config):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        self.cache: Dict[str, Dict[str, Any]] = {} # In-memory storage for demo
        self.embeddings: Dict[str, List[float]] = {}
        
    async def get(self, query: str) -> Optional[Dict[str, Any]]:
        """Retrieve a cached result if a semantically similar query exists."""
        if not self.cache:
            return None
            
        try:
            query_emb = await self._generate_embedding(query)
            
            # Find most similar query in cache
            best_score = -1.0
            best_match = None
            
            for cached_query, cached_emb in self.embeddings.items():
                score = self._cosine_similarity(np.array(query_emb), np.array(cached_emb))
                if score > best_score:
                    best_score = score
                    best_match = cached_query
            
            # Threshold check (e.g., 0.95 for direct semantic hit)
            if best_match and best_score > 0.95:
                self.logger.info(f"Semantic Cache Hit! Score: {best_score:.4f}")
                return self.cache[best_match]
                
        except Exception as e:
            self.logger.error(f"Cache retrieval error: {e}")
            
        return None
        
    async def set(self, query: str, data: Dict[str, Any]):
        """Store a result in the semantic cache."""
        try:
            query_emb = await self._generate_embedding(query)
            self.cache[query] = data
            self.embeddings[query] = query_emb
        except Exception as e:
            self.logger.error(f"Cache storage error: {e}")

    async def _generate_embedding(self, text: str):
        response = await self.client.embeddings.create(
            input=[text.replace("\n", " ")],
            model=self.config.embedding_model
        )
        return response.data[0].embedding

    def _cosine_similarity(self, a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
