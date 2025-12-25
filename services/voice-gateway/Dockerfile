# =============================================================================
# Voice Gateway Dockerfile
# =============================================================================
# Multi-stage build with security best practices:
# - Non-root user (UID 1000)
# - Minimal image (python:slim)
# - Dependency caching with uv
# =============================================================================

FROM python:3.10-slim AS builder

WORKDIR /app

# Install uv for fast dependency management
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

# Copy project definition first (for layer caching)
COPY pyproject.toml uv.lock ./

# Install dependencies (cached if pyproject.toml unchanged)
RUN uv sync --frozen --no-install-project

# =============================================================================
# Production image
# =============================================================================
FROM python:3.10-slim

# Labels for container metadata
LABEL maintainer="sagdesai"
LABEL description="Voice-to-Voice Gateway Service"
LABEL version="1.0.0"

WORKDIR /app

# Create non-root user for security
# Using UID 1000 which is standard for container workloads
RUN groupadd --gid 1000 appgroup && \
    useradd --uid 1000 --gid appgroup --shell /bin/bash --create-home appuser

# Copy virtual environment from builder
COPY --from=builder /app/.venv /app/.venv

# Copy source code
COPY --chown=appuser:appgroup src/ src/

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH" \
    # Python optimizations
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    # Application defaults (can be overridden)
    GRPC_PORT=50051 \
    METRICS_PORT=8080 \
    LOG_LEVEL=INFO \
    SHUTDOWN_GRACE_PERIOD=10

# Switch to non-root user
USER appuser

# Expose gRPC port and metrics port
EXPOSE 50051 8080

# Health check (optional, K8s probes are preferred)
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import socket; s=socket.socket(); s.connect(('localhost', 50051)); s.close()" || exit 1

# Run the application
CMD ["python", "src/main.py"]
