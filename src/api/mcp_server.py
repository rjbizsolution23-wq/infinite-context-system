"""
ICS MCP SERVER (v3.0 - Elite Edition)
Exposes Infinite Context System capabilities via Model Context Protocol
"""

import os
from typing import Optional, Dict, Any
from mcp.server.fastmcp import FastMCP

from src.agents.orchestrator import InfiniteContextOrchestrator
from src.lib.config import SystemConfig

# Initialize MCP Server
mcp = FastMCP("InfiniteContextSystem")

# Initialize ICS Orchestrator
config = SystemConfig()
orchestrator = InfiniteContextOrchestrator(config)

@mcp.tool()
async def generate_context(query: str, max_tokens: Optional[int] = None) -> str:
    """
    Generate rich context for a query using all 4 tiers + Self-RAG + Reranking.
    Use this before answering complex questions to get the most relevant history and knowledge.
    """
    result = await orchestrator.generate_context(query, max_tokens=max_tokens)
    return result["system_prompt"]

@mcp.tool()
async def ingest_knowledge(content: str, source: str = "mcp_ingest", topic: Optional[str] = None) -> str:
    """
    Add text-based knowledge to the Tier 3 Vector Database.
    """
    metadata = {"source": source}
    if topic:
        metadata["topic"] = topic
    await orchestrator.add_knowledge_document(content, metadata)
    return f"Successfully ingested knowledge from {source}"

@mcp.tool()
async def ingest_image(image_path: str, caption: str, source: str = "mcp_vision") -> str:
    """
    Add visual knowledge (images/charts) to the system using CLIP perception.
    Requires the absolute path to the image file.
    """
    metadata = {"source": source}
    await orchestrator.add_image_knowledge(image_path, caption, metadata)
    return f"Successfully ingested image: {os.path.basename(image_path)}"

@mcp.tool()
async def sync_swarm() -> str:
    """
    Synchronize local memory with the Redis distributed backbone.
    Call this to ensure you have the latest context from other agents in the swarm.
    """
    if not config.use_redis:
        return "Redis is not enabled in configuration. Sync skipped."
    
    await orchestrator.sync_distributed_memory()
    return "Successfully synchronized memory with Redis swarm."

@mcp.tool()
async def get_system_status() -> Dict[str, Any]:
    """
    Get detailed statistics and health of the Infinite Context System.
    """
    return orchestrator.get_system_stats()

@mcp.tool()
async def set_user_preference(key: str, value: Any, confidence: float = 1.0) -> str:
    """
    Store a user preference or fact in Tier 4 Persistent Memory.
    """
    orchestrator.set_user_preference(key, value, confidence)
    return f"Stored preference: {key} = {value}"

if __name__ == "__main__":
    mcp.run()
