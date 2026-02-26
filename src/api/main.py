from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uvicorn
import logging
import os
from datetime import datetime

from src.lib.config import SystemConfig
from src.agents.orchestrator import InfiniteContextOrchestrator

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Infinite Context System API", version="1.0.0")

# Global instances
config = SystemConfig()
orchestrator = InfiniteContextOrchestrator(config)

class MessageRequest(BaseModel):
    role: str
    content: str
    importance_score: Optional[float] = 0.5
    metadata: Optional[Dict[str, Any]] = None

class ContextRequest(BaseModel):
    query: str
    max_tokens: Optional[int] = None

class KnowledgeRequest(BaseModel):
    content: str
    metadata: Optional[Dict[str, Any]] = None

@app.on_event("startup")
async def startup_event():
    # Load state from disk if applicable
    await orchestrator.tier1.load_from_disk()
    logger.info("System initialized and state loaded.")

@app.on_event("shutdown")
async def shutdown_event():
    await orchestrator.tier4.close()
    logger.info("System shut down.")

@app.post("/chat")
async def chat(request: MessageRequest):
    """Process a new message and return system acknowledgment"""
    try:
        result = await orchestrator.process_message(
            role=request.role,
            content=request.content,
            importance_score=request.importance_score,
            metadata=request.metadata
        )
        return result
    except Exception as e:
        logger.error(f"Error processing message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/context")
async def get_context(request: ContextRequest):
    """Generate context for a query across all tiers"""
    try:
        result = await orchestrator.generate_context(
            query=request.query,
            max_tokens=request.max_tokens
        )
        return result
    except Exception as e:
        logger.error(f"Error generating context: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/knowledge")
async def add_knowledge(request: KnowledgeRequest):
    """Add a document to Tier 3 (Vector Retrieval)"""
    try:
        await orchestrator.add_knowledge_document(
            content=request.content,
            metadata=request.metadata
        )
        return {"status": "success", "message": "Document added to knowledge base"}
    except Exception as e:
        logger.error(f"Error adding knowledge: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """Get system-wide performance and utilization stats"""
    return orchestrator.get_system_stats()

@app.post("/reset")
async def reset_session():
    """Reset the current active context (Tier 1)"""
    # Orchestrator would need a reset method if we want to clear everything
    # For now, just clear Tier 1 in memory
    orchestrator.tier1.messages.clear()
    orchestrator.tier1.current_tokens = 0
    return {"status": "success", "message": "Active context reset"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
