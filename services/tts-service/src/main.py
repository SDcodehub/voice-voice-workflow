"""TTS Service - NVIDIA Riva Hindi Text-to-Speech."""

import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import structlog

from config import get_settings
from tts_client import tts_pool
from metrics import TTS_REQUESTS, TTS_LATENCY, TTS_AUDIO_DURATION, TTS_TEXT_LENGTH

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


class SynthesizeRequest(BaseModel):
    """Request body for synthesis."""
    text: str
    language: str = "hi-IN"
    voice_name: Optional[str] = None
    sample_rate: Optional[int] = None
    session_id: Optional[str] = None


class SynthesizeResponse(BaseModel):
    """Response body for synthesis metadata."""
    sample_rate: int
    duration_ms: float
    latency_ms: float
    language: str
    text_length: int


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info("Starting TTS Service",
                host=settings.service_host,
                port=settings.http_port,
                riva_server=settings.riva_server_url)
    
    # Initialize TTS connection pool
    await tts_pool.initialize()
    
    yield
    
    # Shutdown
    logger.info("Shutting down TTS Service")
    await tts_pool.close()


app = FastAPI(
    title="TTS Service",
    description="NVIDIA Riva TTS service for Hindi speech synthesis",
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
        client = await asyncio.wait_for(tts_pool.acquire(), timeout=5.0)
        await tts_pool.release(client)
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


@app.post("/synthesize")
async def synthesize(request: SynthesizeRequest):
    """
    Synthesize text to speech (streaming).
    
    Returns audio stream for low-latency playback.
    
    Args:
        request: Synthesis request with text and options
        
    Returns:
        Streaming audio response (PCM bytes)
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="No text provided")
    
    TTS_TEXT_LENGTH.observe(len(request.text))
    
    logger.info("Synthesis request",
                session_id=request.session_id,
                language=request.language,
                text_length=len(request.text))
    
    async def audio_generator():
        try:
            client = await tts_pool.acquire()
            try:
                async for chunk in client.synthesize_streaming(
                    text=request.text,
                    language=request.language,
                    voice_name=request.voice_name,
                    sample_rate=request.sample_rate
                ):
                    yield chunk
                    
                TTS_REQUESTS.labels(
                    language=request.language,
                    status="success"
                ).inc()
                
            finally:
                await tts_pool.release(client)
                
        except Exception as e:
            TTS_REQUESTS.labels(
                language=request.language,
                status="error"
            ).inc()
            logger.error("Synthesis failed",
                        session_id=request.session_id,
                        error=str(e))
            raise
    
    return StreamingResponse(
        audio_generator(),
        media_type="audio/raw",
        headers={
            "X-Sample-Rate": str(request.sample_rate or settings.tts_sample_rate),
            "X-Audio-Encoding": "LINEAR_PCM",
            "X-Audio-Channels": "1"
        }
    )


@app.post("/synthesize/full")
async def synthesize_full(request: SynthesizeRequest):
    """
    Synthesize text to speech (non-streaming).
    
    Returns complete audio after synthesis.
    
    Args:
        request: Synthesis request with text and options
        
    Returns:
        Audio response with metadata headers
    """
    if not request.text or not request.text.strip():
        raise HTTPException(status_code=400, detail="No text provided")
    
    TTS_TEXT_LENGTH.observe(len(request.text))
    
    logger.info("Full synthesis request",
                session_id=request.session_id,
                language=request.language,
                text_length=len(request.text))
    
    try:
        client = await tts_pool.acquire()
        try:
            with TTS_LATENCY.labels(language=request.language).time():
                result = await client.synthesize(
                    text=request.text,
                    language=request.language,
                    voice_name=request.voice_name,
                    sample_rate=request.sample_rate
                )
            
            TTS_REQUESTS.labels(language=request.language, status="success").inc()
            TTS_AUDIO_DURATION.observe(result.duration_ms / 1000)
            
            logger.info("Synthesis complete",
                       session_id=request.session_id,
                       duration_ms=result.duration_ms,
                       latency_ms=result.latency_ms)
            
            return Response(
                content=result.audio_data,
                media_type="audio/raw",
                headers={
                    "X-Sample-Rate": str(result.sample_rate),
                    "X-Duration-Ms": str(result.duration_ms),
                    "X-Latency-Ms": str(result.latency_ms),
                    "X-Audio-Encoding": "LINEAR_PCM",
                    "X-Audio-Channels": "1"
                }
            )
            
        finally:
            await tts_pool.release(client)
            
    except Exception as e:
        TTS_REQUESTS.labels(language=request.language, status="error").inc()
        logger.error("Synthesis failed",
                    session_id=request.session_id,
                    error=str(e))
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/voices")
async def list_voices(language: str = None):
    """List available voices."""
    try:
        client = await tts_pool.acquire()
        try:
            voices = await client.get_voices(language)
            return {"voices": voices}
        finally:
            await tts_pool.release(client)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "TTS Service",
        "version": "1.0.0",
        "language": settings.tts_language_code,
        "sample_rate": settings.tts_sample_rate,
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

