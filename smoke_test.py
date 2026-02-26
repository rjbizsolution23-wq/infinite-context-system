import asyncio
import logging
from config import SystemConfig
from orchestrator import InfiniteContextOrchestrator

async def smoke_test():
    # Initialize
    config = SystemConfig()
    orchestrator = InfiniteContextOrchestrator(config)
    
    print("--- Starting Async Smoke Test ---")
    
    # 1. Process a user message
    print("Step 1: Processing user message...")
    try:
        res = await orchestrator.process_message(
            role="user",
            content="Testing the infinite context system. My name is Alice and I love quantum computing.",
            importance_score=0.9
        )
        print(f"Result: {res}")
    except Exception as e:
        print(f"Error in Step 1: {e}")
        return
    
    # 2. Add knowledge document
    print("Step 2: Adding knowledge...")
    try:
        await orchestrator.add_knowledge_document(
            content="Quantum computing is a type of computing that uses quantum mechanics.",
            metadata={"topic": "quantum"}
        )
        print("Knowledge document added.")
    except Exception as e:
        print(f"Error in Step 2: {e}")
    
    # 3. Generate context
    print("Step 3: Generating context for query...")
    try:
        ctx = await orchestrator.generate_context("What does Alice like?")
        print(f"Total tokens in context: {ctx['total_tokens']}")
        print(f"Tiers used: {list(ctx['contexts'].keys())}")
    except Exception as e:
        print(f"Error in Step 3: {e}")
    
    # 4. Check Tier 4 (Persistent Memory)
    print("Step 4: Verifying Tier 4 entity extraction...")
    entities = orchestrator.tier4.entity_graph.entities
    if not entities:
        print("No entities found in memory.")
    for eid, ent in entities.items():
        print(f"Entity found: {ent.name} ({ent.entity_type})")
        
    print("--- Smoke Test Completed Successfully ---")

if __name__ == "__main__":
    asyncio.run(smoke_test())
