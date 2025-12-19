"""Voice Gateway Service - Entry Point."""

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
from starlette.responses import Response
import structlog

from config import get_settings
from gateway import gateway

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
settings = get_settings()

# Prometheus metrics - use REGISTRY to avoid duplicate registration
from prometheus_client import REGISTRY

def get_or_create_counter(name, description, labels=None):
    """Get existing counter or create new one."""
    try:
        return Counter(name, description, labels or [])
    except ValueError:
        # Already registered, get from registry
        return REGISTRY._names_to_collectors.get(name + '_total') or \
               REGISTRY._names_to_collectors.get(name)

def get_or_create_histogram(name, description, labels=None, buckets=None):
    """Get existing histogram or create new one."""
    try:
        return Histogram(name, description, labels or [], buckets=buckets or [])
    except ValueError:
        return REGISTRY._names_to_collectors.get(name)

REQUEST_COUNT = get_or_create_counter(
    'voice_gateway_http_requests',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)
WEBSOCKET_CONNECTIONS = get_or_create_counter(
    'voice_gateway_ws_connections',
    'Total WebSocket connections'
)
WEBSOCKET_ACTIVE = get_or_create_counter(
    'voice_gateway_ws_active',
    'Active WebSocket connections'
)
PIPELINE_LATENCY = get_or_create_histogram(
    'voice_gateway_pipeline_latency_seconds',
    'Pipeline processing latency',
    ['stage'],
    [0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting Voice Gateway Service", 
                host=settings.service_host,
                port=settings.service_port)
    
    # Initialize gateway
    await gateway.initialize()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Voice Gateway Service")
    await gateway.shutdown()


app = FastAPI(
    title="Voice Gateway Service",
    description="WebSocket gateway for voice-to-voice Hindi conversations",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "version": "1.0.0"
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check - verifies downstream services."""
    try:
        # Check Redis connection
        if gateway.redis_client:
            await gateway.redis_client.ping()
        
        return {
            "status": "ready",
            "redis": "connected"
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.websocket("/ws/voice")
async def websocket_voice_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for voice streaming.
    
    Protocol:
    1. Connect to ws://host/ws/voice
    2. Send JSON config: {"language": "hi-IN"}
    3. Receive: {"type": "session_created", "session_id": "...", "language": "..."}
    4. Send binary audio chunks (16kHz, mono, 16-bit PCM)
    5. Receive JSON status updates and binary audio responses
    
    Message Types (Server -> Client):
    - session_created: Session initialized
    - status: Pipeline stage update
    - transcript: ASR result
    - response_text: LLM response text (streaming)
    - error: Error message
    - Binary: TTS audio chunks (16kHz PCM)
    
    Control Messages (Client -> Server):
    - {"action": "ping"} -> {"type": "pong"}
    - {"action": "clear_history"} -> {"type": "history_cleared"}
    - {"action": "change_language", "language": "en-US"} -> {"type": "language_changed"}
    - {"action": "get_state"} -> {"type": "state", "session": {...}}
    """
    WEBSOCKET_CONNECTIONS.inc()
    WEBSOCKET_ACTIVE.inc()
    
    try:
        await gateway.handle_websocket(websocket)
    finally:
        WEBSOCKET_ACTIVE.inc(-1)


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    session = await gateway.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session.to_dict()


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Voice Gateway",
        "version": "1.0.0",
        "endpoints": {
            "websocket": "/ws/voice",
            "health": "/health",
            "ready": "/ready",
            "metrics": "/metrics"
        },
        "supported_languages": settings.supported_languages,
        "default_language": settings.default_language
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.service_host,
        port=settings.service_port,
        reload=settings.debug,
        log_level="debug" if settings.debug else "info"
    )

