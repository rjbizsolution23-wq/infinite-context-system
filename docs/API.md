# 🔌 ICS v4.0 ELITE — API SPECIFICATION
# RJ Business Solutions | Rick Jefferson
# Date: February 2026

## 1. Overview
The Infinite Context System (ICS) exposes a high-performance REST API and a FastMCP server for tool-augmented perception.

## 2. Authentication
All production endpoints require a Bearer Token provided in the `.env` configuration.
- Header: `Authorization: Bearer <YOUR_API_TOKEN>`

## 3. Core Endpoints

### `POST /v1/process`
Primary entry point for context-aware perception.
- **Request Body**:
```json
{
  "query": "Analyze the recursive logic in Tier 2.",
  "session_id": "elite-user-001",
  "enable_self_rag": true,
  "use_graph_memory": true
}
```
- **Response**: `200 OK` with `RetrievalResult` and `InfiniteContextResponse`.

### `GET /v1/memory/{session_id}`
Retrieve the current persistent state for a session.
- **Returns**: Hierarchical summary of Active, Compressed, and Graph memory.

### `POST /v1/ingest`
Asynchronous ingestion of large-scale document sets into Tier 3 (Vector) and Tier 4 (Graph).
- **Format**: Multipart/Form-Data or JSON metadata.

### `GET /health`
System status and dependency health check (Qdrant, Redis, Neo4j).

## 4. MCP Server Integration
ICS implements the **FastMCP** protocol, allowing it to be used as a backend for desktop Claude, IDEs, and other agentic environments.
- **Tools**: `query_memory`, `update_entity`, `summarize_long_context`.

## 5. Error Handling
ICS uses standardized RFC 7807 problem details for error responses.
- `401 Unauthorized`: Missing or invalid token.
- `422 Unprocessable Entity`: Validation error (Pydantic v2).
- `503 Service Unavailable`: Core dependency (e.g., Qdrant) is downstream.

---
© 2026 RJ Business Solutions. Pro version only.
