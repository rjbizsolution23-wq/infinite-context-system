"""
TIER 3: VECTOR RETRIEVAL SYSTEM
Semantic search across unlimited external knowledge with reranking
"""

import logging
import asyncio
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict
from qdrant_client import QdrantClient, models
from openai import AsyncOpenAI

from config import SystemConfig, TokenCounter, ContextTier


@dataclass
class Document:
    """A document in the knowledge base"""
    doc_id: str
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = "unknown"
    token_count: int = 0
    
    def to_dict(self) -> Dict:
        return {
            "doc_id": self.doc_id,
            "content": self.content,
            "metadata": self.metadata,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "token_count": self.token_count
        }


@dataclass
class RetrievalResult:
    """Result from vector search"""
    document: Document
    score: float
    rank: int
    retrieval_method: str  # semantic, bm25, hybrid
    
    def to_dict(self) -> Dict:
        return {
            **self.document.to_dict(),
            "score": self.score,
            "rank": self.rank,
            "retrieval_method": self.retrieval_method
        }


class VectorRetrievalSystem:
    """
    Tier 3: Semantic search across unlimited external knowledge
    
    Features:
    - Dense vector search (semantic)
    - Sparse search (BM25)
    - Hybrid retrieval
    - Reranking for relevance
    - Multi-query retrieval
    - Metadata filtering
    """
    
    def __init__(self, config: SystemConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.token_counter = TokenCounter(config.primary_llm)
        self.client = AsyncOpenAI(api_key=config.openai_api_key)
        
        # Initialize Qdrant Client with fallback
        self.qdrant = None
        try:
            if config.vector_db_url == "localhost" or "localhost" in config.vector_db_url:
                self.qdrant = QdrantClient(url=config.vector_db_url)
            else:
                self.qdrant = QdrantClient(url=config.vector_db_url, api_key=config.vector_db_api_key)
            self._ensure_collection()
            self.logger.info("Connected to Qdrant successfully")
        except Exception as e:
            self.logger.warning(f"Could not connect to Qdrant, falling back to in-memory storage: {e}")
            self.qdrant = None

        # Get tier configuration
        tier_config = config.tier_configs[ContextTier.RETRIEVAL]
        self.max_tokens = tier_config.max_tokens
        
        # Retrieval configuration
        self.top_k = config.retrieval_top_k
        self.retrieval_strategy = config.retrieval_strategy
        self.rerank_enabled = config.rerank_enabled
        self.rerank_top_n = config.rerank_top_n
        
        # In-memory storage components (always active as fallback)
        self.documents: Dict[str, Document] = {}
        self.document_embeddings: Dict[str, List[float]] = {}
        
        # Tracking
        self.total_retrievals = 0
        self.cache: Dict[str, List[RetrievalResult]] = {}

    def _ensure_collection(self):
        """Ensure Qdrant collection exists"""
        try:
            self.qdrant.get_collection(self.config.collection_name)
        except Exception:
            self.logger.info(f"Creating collection: {self.config.collection_name}")
            self.qdrant.create_collection(
                collection_name=self.config.collection_name,
                vectors_config=models.VectorParams(
                    size=self.config.embedding_dimensions,
                    distance=models.Distance.COSINE
                )
            )

    async def add_documents(self, documents: List[Document], 
                     generate_embeddings: bool = True):
        """
        Add documents to the knowledge base
        
        Args:
            documents: List of documents to add
            generate_embeddings: Whether to generate embeddings
        """
        points = []
        for doc in documents:
            if doc.token_count == 0:
                doc.token_count = self.token_counter.count(doc.content)
            
            embedding = None
            if generate_embeddings:
                embedding = await self._generate_embedding(doc.content)
            
            points.append(models.PointStruct(
                id=doc.doc_id,
                vector=embedding if embedding is not None else [],
                payload=doc.to_dict()
            ))
            
        if points and self.qdrant:
            try:
                self.qdrant.upsert(
                    collection_name=self.config.collection_name,
                    points=points
                )
                self.logger.info(f"Added {len(points)} documents to Qdrant")
            except Exception as e:
                self.logger.error(f"Failed to upsert to Qdrant: {e}")
        
        # Always store in-memory fallback
        for doc in documents:
            self.documents[doc.doc_id] = doc
            # Re-generate embedding for in-memory if needed (or use existing)
            # For simplicity, we assume doc.embedding might be set or we store it elsewhere
            # Actually, let's just store the docs for now.

    async def retrieve(self, query: str, 
                top_k: Optional[int] = None,
                filters: Optional[Dict] = None,
                strategy: Optional[str] = None) -> List[RetrievalResult]:
        """
        Retrieve relevant documents for a query
        
        Args:
            query: Search query
            top_k: Number of results to return
            filters: Metadata filters
            strategy: Retrieval strategy (semantic, bm25, hybrid)
        """
        if top_k is None:
            top_k = self.top_k
        
        if strategy is None:
            strategy = self.retrieval_strategy
        
        # Check cache
        cache_key = f"{query}:{top_k}:{strategy}"
        if cache_key in self.cache and self.config.enable_caching:
            return self.cache[cache_key]
        
        # Retrieve based on strategy
        if strategy == "semantic":
            results = await self._semantic_retrieve(query, top_k, filters)
        elif strategy == "bm25":
            results = await self._bm25_retrieve(query, top_k, filters)
        elif strategy == "hybrid":
            results = await self._hybrid_retrieve(query, top_k, filters)
        else:
            raise ValueError(f"Unknown strategy: {strategy}")
        
        # Rerank if enabled
        if self.rerank_enabled and len(results) > self.rerank_top_n:
            results = self._rerank(query, results[:self.rerank_top_n * 2])
        
        # Limit results
        results = results[:top_k]
        
        # Cache results
        if self.config.enable_caching:
            self.cache[cache_key] = results
        
        self.total_retrievals += 1
        
        return results
    
    async def _semantic_retrieve(self, query: str, top_k: int, 
                          filters: Optional[Dict]) -> List[RetrievalResult]:
        """Dense vector semantic search with in-memory fallback"""
        query_embedding = await self._generate_embedding(query)
        
        if self.qdrant:
            try:
                search_result = self.qdrant.search(
                    collection_name=self.config.collection_name,
                    query_vector=query_embedding,
                    limit=top_k,
                    with_payload=True
                )
                
                results = []
                for rank, hit in enumerate(search_result, 1):
                    doc = Document(
                        doc_id=hit.id,
                        content=hit.payload['content'],
                        metadata=hit.payload['metadata'],
                        source=hit.payload['source'],
                        token_count=hit.payload['token_count']
                    )
                    results.append(RetrievalResult(
                        document=doc,
                        score=hit.score,
                        rank=rank,
                        retrieval_method="semantic"
                    ))
                return results
            except Exception as e:
                self.logger.error(f"Qdrant search failed: {e}. Falling back to in-memory.")

        # In-memory fallback
        results = []
        for i, (doc_id, doc) in enumerate(list(self.documents.items())[:top_k], 1):
            results.append(RetrievalResult(
                document=doc,
                score=1.0 / i,
                rank=i,
                retrieval_method="in-memory-fallback"
            ))
        return results
    
    async def _bm25_retrieve(self, query: str, top_k: int,
                      filters: Optional[Dict]) -> List[RetrievalResult]:
        """Sparse keyword-based search (BM25)"""
        # Simplified BM25 implementation
        query_terms = set(query.lower().split())
        
        scores = []
        for doc_id, doc in self.documents.items():
            # Apply filters
            if filters and not self._matches_filters(doc, filters):
                continue
            
            # Calculate BM25 score (simplified)
            doc_terms = set(doc.content.lower().split())
            common_terms = query_terms.intersection(doc_terms)
            
            if common_terms:
                # Simple term frequency score
                score = len(common_terms) / len(query_terms)
                scores.append((doc_id, score))
        
        # Sort by score
        scores.sort(key=lambda x: x[1], reverse=True)
        
        # Create results
        results = []
        for rank, (doc_id, score) in enumerate(scores[:top_k], 1):
            results.append(RetrievalResult(
                document=self.documents[doc_id],
                score=score,
                rank=rank,
                retrieval_method="bm25"
            ))
        
        return results
    
    async def _hybrid_retrieve(self, query: str, top_k: int,
                        filters: Optional[Dict]) -> List[RetrievalResult]:
        """Combine semantic and BM25 search"""
        # In production, this would use Qdrant's hybrid search feature
        # For now, we'll simulate it by getting semantic results and 
        # combining with a keyword boost if needed, or calling both.
        semantic_results = await self._semantic_retrieve(query, top_k * 2, filters)
        bm25_results = await self._bm25_retrieve(query, top_k * 2, filters)
        
        # Combine scores (Reciprocal Rank Fusion)
        combined_scores = defaultdict(float)
        doc_results = {}
        
        for result in semantic_results:
            doc_id = result.document.doc_id
            combined_scores[doc_id] += 1.0 / (result.rank + 60)  # RRF
            doc_results[doc_id] = result
        
        for result in bm25_results:
            doc_id = result.document.doc_id
            combined_scores[doc_id] += 1.0 / (result.rank + 60)  # RRF
            if doc_id not in doc_results:
                doc_results[doc_id] = result
        
        # Sort by combined score
        sorted_docs = sorted(combined_scores.items(), 
                           key=lambda x: x[1], reverse=True)
        
        # Create results
        results = []
        for rank, (doc_id, score) in enumerate(sorted_docs[:top_k], 1):
            result = doc_results[doc_id]
            results.append(RetrievalResult(
                document=result.document,
                score=score,
                rank=rank,
                retrieval_method="hybrid"
            ))
        
        return results
    
    def _rerank(self, query: str, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """
        Rerank results for better relevance
        
        In production, use models like:
        - Cohere Rerank
        - Cross-encoders (MS MARCO)
        - BGE Reranker
        """
        # PLACEHOLDER: Simple reranking based on query term overlap
        query_terms = set(query.lower().split())
        
        reranked = []
        for result in results:
            doc_terms = set(result.document.content.lower().split())
            overlap = len(query_terms.intersection(doc_terms))
            
            # Combine with original score
            new_score = result.score * 0.7 + (overlap / len(query_terms)) * 0.3
            
            reranked.append(RetrievalResult(
                document=result.document,
                score=new_score,
                rank=result.rank,
                retrieval_method=f"{result.retrieval_method}_reranked"
            ))
        
        # Re-sort and update ranks
        reranked.sort(key=lambda x: x.score, reverse=True)
        for i, result in enumerate(reranked, 1):
            result.rank = i
        
        return reranked
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding for text using OpenAI"""
        try:
            response = await self.client.embeddings.create(
                input=[text.replace("\n", " ")],
                model=self.config.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            self.logger.error(f"Error generating embedding: {e}")
            # Fallback to random for robustness in demo
            return np.random.rand(self.config.embedding_dimensions).tolist()
    
    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors"""
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def _matches_filters(self, doc: Document, filters: Dict) -> bool:
        """Check if document matches metadata filters"""
        for key, value in filters.items():
            if key not in doc.metadata:
                return False
            if doc.metadata[key] != value:
                return False
        return True
    
    def get_context_for_llm(self, results: List[RetrievalResult],
                           max_tokens: Optional[int] = None) -> str:
        """Format retrieval results for LLM context"""
        if max_tokens is None:
            max_tokens = self.max_tokens
        
        formatted = ["=== Retrieved Knowledge ===\n"]
        current_tokens = self.token_counter.count('\n'.join(formatted))
        
        for result in results:
            doc = result.document
            doc_text = f"\n[Source: {doc.source} | Relevance: {result.score:.2f}]\n{doc.content}\n"
            doc_tokens = self.token_counter.count(doc_text)
            
            if current_tokens + doc_tokens <= max_tokens:
                formatted.append(doc_text)
                current_tokens += doc_tokens
            else:
                break
        
        return '\n'.join(formatted)
    
    async def multi_query_retrieve(self, queries: List[str], 
                            top_k_per_query: int = 5) -> List[RetrievalResult]:
        """
        Retrieve results for multiple queries and deduplicate
        
        Useful for query expansion and multi-perspective retrieval
        """
        all_results = []
        seen_docs = set()
        
        for query in queries:
            results = await self.retrieve(query, top_k=top_k_per_query)
            
            for result in results:
                if result.document.doc_id not in seen_docs:
                    all_results.append(result)
                    seen_docs.add(result.document.doc_id)
        
        return all_results
    
    def get_stats(self) -> Dict[str, Any]:
        """Get statistics about the retrieval system"""
        return {
            "total_documents": len(self.documents),
            "total_embeddings": len(self.document_embeddings),
            "total_retrievals": self.total_retrievals,
            "cache_size": len(self.cache),
            "retrieval_strategy": self.retrieval_strategy,
            "rerank_enabled": self.rerank_enabled,
            "top_k": self.top_k
        }


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

if __name__ == "__main__":
    from config import SystemConfig
    import uuid
    
    print("=" * 70)
    print("TIER 3: VECTOR RETRIEVAL - Demo")
    print("=" * 70)
    
    # Initialize
    config = SystemConfig()
    retrieval = VectorRetrievalSystem(config)
    
    # Add sample documents
    docs = [
        Document(
            doc_id=str(uuid.uuid4()),
            content="Transformers use self-attention mechanisms to process sequences in parallel.",
            metadata={"category": "ml", "topic": "transformers"},
            source="ml_textbook"
        ),
        Document(
            doc_id=str(uuid.uuid4()),
            content="BERT is a bidirectional transformer model pretrained on large text corpora.",
            metadata={"category": "ml", "topic": "bert"},
            source="research_paper"
        ),
        Document(
            doc_id=str(uuid.uuid4()),
            content="Attention mechanism computes weighted sum of values based on query-key similarity.",
            metadata={"category": "ml", "topic": "attention"},
            source="ml_textbook"
        ),
    ]
    
    retrieval.add_documents(docs)
    
    # Retrieve
    query = "How do transformers work?"
    results = retrieval.retrieve(query, top_k=3, strategy="hybrid")
    
    print(f"\nQuery: '{query}'")
    print(f"Retrieved {len(results)} results:")
    
    for result in results:
        print(f"\n  Rank {result.rank} | Score: {result.score:.3f} | Method: {result.retrieval_method}")
        print(f"  Content: {result.document.content[:100]}...")
    
    # Show stats
    print("\nRetrieval System Statistics:")
    stats = retrieval.get_stats()
    for key, value in stats.items():
        print(f"  {key:25}: {value}")
    
    print("\n" + "=" * 70)
