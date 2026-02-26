# 🛳️ ICS v4.0 — ENTERPRISE DEPLOYMENT GUIDE
## RJ Business Solutions | Production-Grade Infrastructure

### 1. Docker Production
The repository features a multi-stage `Dockerfile` optimized for security and footprint.
```bash
docker build -t ics-elite:latest .
docker run -p 8000:8000 --env-file .env ics-elite:latest
```

### 2. Kubernetes Orchestration
Deployment manifests are located in `infrastructure/kubernetes/`.
- **Auto-Scaling**: HPA configured for CPU/Memory spikes during heavy retrieval.
- **Persistence**: PV/PVC bindings for Neo4j and Qdrant storage.

### 3. CI/CD Pipeline
- **Supreme Pipeline**: Triggered on `push` to `main`.
- **Logic**: Lint -> Type Check -> Unit Tests -> Security Scan -> Docker Registry Push.

---
*Deployment Integrity — RJ Business Solutions Standard.*
