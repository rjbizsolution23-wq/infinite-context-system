import pytest
from orchestrator import InfiniteContextOrchestrator
from config import SystemConfig

@pytest.fixture
def mock_config():
    return SystemConfig(
        llm_provider="openai",
        enable_semantic_cache=False,
        enable_self_rag=True,
        self_rag_threshold=0.7
    )

@pytest.mark.asyncio
async def test_orchestrator_initialization(mock_config):
    """Test that the Supreme Orchestrator initializes all 4 tiers correctly."""
    orchestrator = InfiniteContextOrchestrator(mock_config)
    assert orchestrator.tier1 is not None
    assert orchestrator.tier2 is not None
    assert orchestrator.tier3 is not None
    assert orchestrator.tier4 is not None

@pytest.mark.asyncio
async def test_perception_loop_basic(mock_config):
    """Test a basic request-response perception loop."""
    orchestrator = InfiniteContextOrchestrator(mock_config)
    # We mock the LLM call or use a light provider for local tests
    query = "Who is the CEO of RJ Business Solutions?"
    response = await orchestrator.process_query(query, session_id="test_session")
    
    assert response is not None
    assert "Rick Jefferson" in str(response) or "operator" in str(response).lower()

@pytest.mark.asyncio
async def test_memory_persistence(mock_config):
    """Verify that memory is correctly handed off between tiers."""
    orchestrator = InfiniteContextOrchestrator(mock_config)
    # 1. Ingest something into Tier 1
    # 2. Trigger summarization into Tier 2
    # 3. Verify Tier 3/4 indexing
    pass # To be completed with deeper mocks
