"""ASR Service - NVIDIA Riva Hindi Speech Recognition."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import structlog

from config import get_settings
from asr_client import asr_pool, TranscriptionResult

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

# Prometheus metrics
ASR_REQUESTS = Counter(
    'asr_requests_total',
    'Total ASR requests',
    ['language', 'status']
)
ASR_LATENCY = Histogram(
    'asr_latency_seconds',
    'ASR processing latency',
    ['language'],
    buckets=[0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0]
)
ASR_AUDIO_DURATION = Histogram(
    'asr_audio_duration_seconds',
    'Duration of audio processed',
    buckets=[1, 2, 5, 10, 30, 60, 120]
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting ASR Service",
                host=settings.service_host,
                port=settings.http_port,
                riva_server=settings.riva_server_url)
    
    # Initialize ASR connection pool
    await asr_pool.initialize()
    
    yield
    
    # Shutdown
    logger.info("Shutting down ASR Service")
    await asr_pool.close()


app = FastAPI(
    title="ASR Service",
    description="NVIDIA Riva ASR service for Hindi speech recognition",
    version="1.0.0",
    lifespan=lifespan
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": settings.service_name
    }


@app.get("/ready")
async def readiness_check():
    """Readiness check."""
    try:
        # Try to acquire and release a client
        client = await asyncio.wait_for(asr_pool.acquire(), timeout=5.0)
        await asr_pool.release(client)
        return {"status": "ready"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST
    )


@app.post("/transcribe")
async def transcribe_audio(request: Request):
    """
    Transcribe audio to text.
    
    Expects:
    - Body: Raw PCM audio bytes (16-bit, mono, 16kHz)
    - Headers:
        - X-Language: Language code (default: hi-IN)
        - X-Sample-Rate: Sample rate (default: 16000)
        - X-Session-ID: Optional session ID for tracking
    
    Returns:
        JSON with transcript and metadata
    """
    # Get headers
    language = request.headers.get("X-Language", settings.asr_language_code)
    sample_rate = int(request.headers.get("X-Sample-Rate", settings.asr_sample_rate))
    session_id = request.headers.get("X-Session-ID", "unknown")
    
    # Read audio data
    audio_data = await request.body()
    
    if not audio_data:
        ASR_REQUESTS.labels(language=language, status="error").inc()
        raise HTTPException(status_code=400, detail="No audio data provided")
    
    # Calculate audio duration for metrics
    # 16-bit mono = 2 bytes per sample
    audio_duration = len(audio_data) / (sample_rate * 2)
    ASR_AUDIO_DURATION.observe(audio_duration)
    
    logger.info("Transcription request",
                session_id=session_id,
                language=language,
                audio_bytes=len(audio_data),
                audio_duration=audio_duration)
    
    try:
        # Acquire client from pool
        client = await asr_pool.acquire()
        
        try:
            # Perform transcription
            with ASR_LATENCY.labels(language=language).time():
                result = await client.transcribe(
                    audio_data=audio_data,
                    language=language,
                    sample_rate=sample_rate
                )
            
            ASR_REQUESTS.labels(language=language, status="success").inc()
            
            logger.info("Transcription complete",
                       session_id=session_id,
                       transcript_length=len(result.transcript),
                       confidence=result.confidence,
                       latency_ms=result.latency_ms)
            
            return {
                "transcript": result.transcript,
                "is_final": result.is_final,
                "confidence": result.confidence,
                "language": result.language,
                "latency_ms": result.latency_ms,
                "words": result.words
            }
            
        finally:
            await asr_pool.release(client)
            
    except Exception as e:
        ASR_REQUESTS.labels(language=language, status="error").inc()
        logger.error("Transcription failed",
                    session_id=session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/transcribe/json")
async def transcribe_audio_json(
    audio_base64: str,
    language: str = None,
    sample_rate: int = None
):
    """
    Transcribe base64-encoded audio.
    
    Args:
        audio_base64: Base64 encoded PCM audio
        language: Language code (default: hi-IN)
        sample_rate: Sample rate (default: 16000)
    """
    import base64
    
    language = language or settings.asr_language_code
    sample_rate = sample_rate or settings.asr_sample_rate
    
    try:
        audio_data = base64.b64decode(audio_base64)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid base64 audio")
    
    try:
        client = await asr_pool.acquire()
        try:
            result = await client.transcribe(
                audio_data=audio_data,
                language=language,
                sample_rate=sample_rate
            )
            
            return {
                "transcript": result.transcript,
                "confidence": result.confidence,
                "language": result.language
            }
        finally:
            await asr_pool.release(client)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "ASR Service",
        "version": "1.0.0",
        "language": settings.asr_language_code,
        "sample_rate": settings.asr_sample_rate,
        "riva_server": settings.riva_server_url
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=settings.service_host,
        port=settings.http_port,
        reload=settings.debug
    )

