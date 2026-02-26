# 🎓 Mastering the Infinite Context System (MCP)

This guide provides a deep-dive into maximizing the **Infinite Context System (ICS)** through the Model Context Protocol.

---

## 🚀 Why Use the MCP Wrapper?

The MCP server (`mcp_server.py`) transforms your local ICS engine into a set of standard tools that any modern AI agent can understand. This enables:
1.  **Cross-App Intelligence**: Use the same memory across Claude Desktop, IDE extensions, and custom scripts.
2.  **Autonomous Memory Management**: Let the agent decide when to "remember" a relationship or retrieval context.
3.  **Low Latency**: Directly call tools without overhead of a full REST API if running locally.

---

## 🛠️ Tool Mastery

### 1. `ingest_knowledge`
Use this to feed raw data into the system. ICS will embed the text and store it in **Tier 3 (Vector Retrieval)**.
- **Tip**: Group related information using the `topic` argument. This helps the Vector DB focus search results later.
- **Example Usage**: *"Ingest the latest Q3 financial results under the topic 'earnings'."*

### 2. `query_memory`
This is the heart of the system. It gathers context from all 4 tiers and returns a formatted string for the LLM.
- **Optimization**: Use `max_tokens` (default 4000) to ensure you don't overwhelm your current prompt.
- **Strategy**: Call this at the start of complex research tasks to "prime" the agent's knowledge of the specific query.

### 3. `remember_relationship`
Manually inject facts into the **Tier 4 (Persistent Graph)**.
- **Tip**: Use this for identity-defining information. 
- **Example**: *"Remember that 'Project Aether' is led by 'Sarah' and uses 'Rust' as the primary language."*

---

## 📈 Optimization Strategies

### Tuning the Token Budget
In `config.py`, you can adjust how much each tier contributes to the final context.
- **For Creative Writing**: Increase Tier 2 (Compressed) weight for better narrative continuity.
- **For Technical Q&A**: Increase Tier 3 (Vector) weight for higher-density factual retrieval.
- **For Personal Assistants**: Prioritize Tier 4 Higher to ensure user preferences are always top-of-mind.

### Hybrid Search Performance
The system uses `hybrid` search by default. This combines the semantic "feeling" of vectors with the keyword precision of BM25.
- **Best Practice**: If you are searching for specific variable names or code snippets, ensure your keyword overlap is high in the query.

---

## 🧗 Scaling to Production

When you are ready to move beyond the local in-memory fallbacks:

1.  **Vector DB**: Set `QDRANT_URL` and `QDRANT_API_KEY`. ICS will automatically migrate from local storage to Qdrant's high-speed clusters.
2.  **Graph DB**: Set `NEO4J_URI` and `NEO4J_PASSWORD`. This unlocks complex path-finding and relationship analysis that the local graph can't handle.

---
**Infinite Context System - Documentation v2.0**
