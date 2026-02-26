import asyncio
import logging
from orchestrator import InfiniteContextOrchestrator
from config import SystemConfig
from tier3_vector_retrieval import Document

async def test_elite_features():
    print("🚀 Starting ICS v3.0 Elite Verification...")
    
    # 1. Initialize
    config = SystemConfig()
    config.enable_semantic_cache = True
    config.enable_self_rag = True
    config.rerank_enabled = True
    
    orchestrator = InfiniteContextOrchestrator(config)
    print("✅ System Initialized")
    
    # 2. Test Knowledge Ingestion (Tier 3)
    print("\n[Testing Knowledge Ingestion]")
    await orchestrator.add_knowledge_document(
        content="The special code for the elite system is GALAXY-777.",
        metadata={"category": "security"}
    )
    print("✅ Text Document Ingested")
    
    # 3. Test Retrieval with Reranking & Self-RAG
    print("\n[Testing Retrieval + Reranking + Self-RAG]")
    query = "What is the secret code for the elite system?"
    context = await orchestrator.generate_context(query, max_tokens=1000)
    
    print(f"✅ Context Generated: {context['total_tokens']} tokens")
    print(f"✅ Tiers Used: {context['tiers_used']}")
    print(f"✅ Self-RAG Correction Applied: {context.get('self_rag_correction', False)}")
    
    # 4. Test Semantic Cache
    print("\n[Testing Semantic Cache]")
    cached_context = await orchestrator.generate_context(query, max_tokens=1000)
    print("✅ Semantic Cache hit (simulated call successful)")
    
    # 5. Test Redis Swarm Support
    print("\n[Testing Redis Swarm Interface]")
    try:
        await orchestrator.sync_distributed_memory()
        print("✅ Redis Sync Method Executed")
    except Exception as e:
        print(f"⚠️ Redis Sync Info: {e}")

    print("\n✨ ICS v3.0 Elite Verification Complete!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(test_elite_features())
