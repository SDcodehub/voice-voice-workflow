"""LLM Service - Conversational AI for Hindi."""

from contextlib import asynccontextmanager
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import structlog

from config import get_settings
from llm_client import llm_client
from metrics import LLM_REQUESTS, LLM_LATENCY, LLM_TOKENS

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()
settings = get_settings()


class GenerateRequest(BaseModel):
    """Request body for generation."""
    messages: List[Dict[str, str]]
    language: str = "hi-IN"
    session_id: Optional[str] = None
    stream: bool = False
    max_tokens: Optional[int] = None
    temperature: Optional[float] = None


class GenerateResponse(BaseModel):
    """Response body for generation."""
    text: str
    tokens_generated: int
    latency_ms: float
    finish_reason: str
    cached: bool


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting LLM Service",
                host=settings.service_host,
                port=settings.http_port,
                backend=settings.llm_backend)
    
    # Initialize LLM client
    await llm_client.initialize()
    
    yield
    
    # Shutdown
    logger.info("Shutting down LLM Service")
    await llm_client.close()


app = FastAPI(
    title="LLM Service",
    description="LLM service for Hindi conversational AI",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.service_name,
        "backend": settings.llm_backend
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check."""
    return {"status": "ready"}


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/generate", response_model=GenerateResponse)
async def generate(request: GenerateRequest):
    """
    Generate a response (non-streaming).
    
    Args:
        request: Generation request with messages and options
        
    Returns:
        GenerateResponse with generated text
    """
    logger.info("Generation request",
                session_id=request.session_id,
                language=request.language,
                message_count=len(request.messages))
    
    try:
        with LLM_LATENCY.labels(language=request.language).time():
            result = await llm_client.generate(
                conversation_history=request.messages,
                language=request.language,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            )
        
        LLM_REQUESTS.labels(
            language=request.language,
            status="success",
            cached=str(result.cached)
        ).inc()
        
        LLM_TOKENS.labels(language=request.language).inc(result.tokens_generated)
        
        logger.info("Generation complete",
                   session_id=request.session_id,
                   tokens=result.tokens_generated,
                   latency_ms=result.latency_ms,
                   cached=result.cached)
        
        return GenerateResponse(
            text=result.text,
            tokens_generated=result.tokens_generated,
            latency_ms=result.latency_ms,
            finish_reason=result.finish_reason,
            cached=result.cached
        )
        
    except Exception as e:
        LLM_REQUESTS.labels(
            language=request.language,
            status="error",
            cached="false"
        ).inc()
        logger.error("Generation failed",
                    session_id=request.session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate/stream")
async def generate_stream(request: GenerateRequest):
    """
    Generate a streaming response.
    
    Returns tokens as they are generated for low-latency response.
    """
    logger.info("Streaming generation request",
                session_id=request.session_id,
                language=request.language)
    
    async def stream_generator():
        try:
            async for token in llm_client.generate_stream(
                conversation_history=request.messages,
                language=request.language,
                max_tokens=request.max_tokens,
                temperature=request.temperature
            ):
                yield token
                
            LLM_REQUESTS.labels(
                language=request.language,
                status="success",
                cached="false"
            ).inc()
            
        except Exception as e:
            LLM_REQUESTS.labels(
                language=request.language,
                status="error",
                cached="false"
            ).inc()
            logger.error("Streaming generation failed", error=str(e))
            yield f"\n[ERROR: {str(e)}]"
    
    return StreamingResponse(
        stream_generator(),
        media_type="text/plain"
    )


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "LLM Service",
        "version": "1.0.0",
        "backend": settings.llm_backend,
        "model": settings.nim_model if settings.llm_backend == "nvidia_nim" else settings.openai_model,
        "supported_languages": ["hi-IN", "en-US"]
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.service_host,
        port=settings.http_port,
        reload=settings.debug
    )

