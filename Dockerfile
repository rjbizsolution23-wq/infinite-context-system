# 🛡️ SUPREME PRODUCTION DOCKERFILE
# Multi-stage build for maximum security and minimum footprint
# Architecture: ICS v4.0 Elite

# --- Phase 1: Dependency Builder ---
FROM python:3.12-slim AS builder

WORKDIR /build

# Install system build dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python requirements
COPY requirements.txt .
RUN pip install --user --no-cache-dir -r requirements.txt

# --- Phase 2: Production Runner ---
FROM python:3.12-slim AS runner

WORKDIR /app

# Non-root user for security
RUN groupadd -g 1001 icsgroup && \
    useradd -u 1001 -g icsgroup -s /bin/sh icsuser

# Copy installed packages from builder
COPY --from=builder /root/.local /home/icsuser/.local
ENV PATH=/home/icsuser/.local/bin:$PATH

# Copy application source code
COPY --chown=icsuser:icsgroup . .

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV APP_ENV=production
ENV LOG_LEVEL=INFO

# Expose ports for API and Monitoring
EXPOSE 8000
EXPOSE 9090

USER icsuser

# Healthcheck for orchestration stability
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

# Start the Supreme Engine
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
