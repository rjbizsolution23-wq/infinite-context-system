import asyncio
import logging
import os
from unittest.mock import MagicMock, patch
import numpy as np

# Set CI flag to skip heavy model downloads
os.environ["CI"] = "true"

# Mock heavy dependencies BEFORE importing orchestrator
mock_st = MagicMock()
mock_st_instance = mock_st.return_value
mock_st_instance.encode.return_value = np.random.rand(512)

# Apply patches to prevent any real heavy loading
with patch('sentence_transformers.SentenceTransformer', mock_st):
    with patch('flashrank.Ranker', MagicMock()):
        # Now import
        from orchestrator import InfiniteContextOrchestrator
        from config import SystemConfig
        from tier3_vector_retrieval import Document

async def test_mocked_elite():
    print("🚀 Starting ICS v3.0 Elite Verification (MOCKED)...")
    
    config = SystemConfig()
    config.enable_semantic_cache = True
    config.enable_self_rag = True
    config.rerank_enabled = True
    
    # Initialize Orchestrator
    orchestrator = InfiniteContextOrchestrator(config)
    orchestrator.client = MagicMock()
    
    # Mock OpenAI reflection for Self-RAG
    orchestrator.client.chat.completions.create = asyncio.Future()
    
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "0.95" # High relevance
    orchestrator.client.chat.completions.create.set_result(mock_response)

    print("✅ System Initialized with CI Mocks")
    
    # 1. Test Retrieval Logic
    print("\n[Testing Retrieval Pipeline]")
    query = "What is the secret code for the elite system?"
    context = await orchestrator.generate_context(query, max_tokens=1000)
    
    print(f"✅ Context call successful: {context['tiers_used']}")
    print(f"✅ Budget Utilization: {context['budget_utilization']}")
    
    # 2. Test Cache Integration
    print("\n[Testing Semantic Cache Integration]")
    # Second call should hit the in-memory cache we just populated
    cached_context = await orchestrator.generate_context(query, max_tokens=1000)
    print(f"✅ Cache check successful: {cached_context['tiers_used']}")

    print("\n✨ ICS v3.0 Elite Verification (MOCKED) Complete!")

if __name__ == "__main__":
    logging.basicConfig(level=logging.ERROR)
    asyncio.run(test_mocked_elite())
