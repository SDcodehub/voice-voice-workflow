"""NVIDIA Riva TTS Client for Hindi Speech Synthesis."""

import asyncio
from typing import AsyncIterator, Optional, List
from dataclasses import dataclass
import time

import grpc
import numpy as np
import structlog

# Riva TTS imports
try:
    import riva.client
    from riva.client import SpeechSynthesisService
    import riva.client.proto.riva_tts_pb2 as riva_tts
    import riva.client.proto.riva_tts_pb2_grpc as riva_tts_grpc
    RIVA_AVAILABLE = True
except ImportError:
    RIVA_AVAILABLE = False
    riva_tts = None
    riva_tts_grpc = None

from config import get_settings

logger = structlog.get_logger()
settings = get_settings()


@dataclass
class SynthesisResult:
    """TTS synthesis result."""
    audio_data: bytes
    sample_rate: int
    duration_ms: float
    latency_ms: float
    language: str


class RivaTTSClient:
    """
    NVIDIA Riva TTS Client optimized for Hindi language.
    
    Features:
    - Streaming audio synthesis
    - Connection pooling for high throughput
    - Support for multiple voices
    - SSML support
    """
    
    def __init__(self):
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[riva_tts_grpc.RivaSpeechSynthesisStub] = None
        
    async def connect(self):
        """Establish connection to Riva TTS server."""
        if not RIVA_AVAILABLE:
            logger.warning("Riva client not available, using mock mode")
            return
            
        try:
            # Create gRPC channel with optimized settings
            options = [
                ('grpc.max_send_message_length', settings.grpc_max_message_size),
                ('grpc.max_receive_message_length', settings.grpc_max_message_size),
                ('grpc.keepalive_time_ms', 10000),
                ('grpc.keepalive_timeout_ms', 5000),
                ('grpc.keepalive_permit_without_calls', True),
                ('grpc.http2.max_pings_without_data', 0),
            ]
            
            if settings.riva_use_ssl and settings.riva_ssl_cert:
                with open(settings.riva_ssl_cert, 'rb') as f:
                    creds = grpc.ssl_channel_credentials(f.read())
                self._channel = grpc.aio.secure_channel(
                    settings.riva_server_url, creds, options=options
                )
            else:
                self._channel = grpc.aio.insecure_channel(
                    settings.riva_server_url, options=options
                )
            
            self._stub = riva_tts_grpc.RivaSpeechSynthesisStub(self._channel)
            
            logger.info("Connected to Riva TTS server",
                       url=settings.riva_server_url)
            
        except Exception as e:
            logger.error("Failed to connect to Riva TTS", error=str(e))
            raise
    
    async def close(self):
        """Close the connection."""
        if self._channel:
            await self._channel.close()
            logger.info("Riva TTS connection closed")
    
    def _generate_mock_audio(self, text: str, sample_rate: int = 22050) -> bytes:
        """Generate mock audio for development."""
        # Generate silence with appropriate duration
        # Estimate ~100ms per character for Hindi
        duration_seconds = len(text) * 0.1
        num_samples = int(sample_rate * duration_seconds)
        
        # Generate silent audio (16-bit PCM)
        audio = np.zeros(num_samples, dtype=np.int16)
        return audio.tobytes()
    
    async def synthesize(
        self,
        text: str,
        language: str = None,
        voice_name: str = None,
        sample_rate: int = None
    ) -> SynthesisResult:
        """
        Synthesize speech from text (batch/offline synthesis).
        
        Args:
            text: Text to synthesize (Hindi or English)
            language: Language code (default: hi-IN)
            voice_name: Voice name (default: language default)
            sample_rate: Output sample rate (default: 22050)
            
        Returns:
            SynthesisResult with audio data and metadata
        """
        start_time = time.time()
        
        language = language or settings.tts_language_code
        sample_rate = sample_rate or settings.tts_sample_rate
        
        if not RIVA_AVAILABLE or not self._stub:
            # Mock response for development
            logger.warning("Using mock TTS response")
            audio_data = self._generate_mock_audio(text, sample_rate)
            duration_ms = len(audio_data) / (sample_rate * 2) * 1000  # 16-bit = 2 bytes
            
            return SynthesisResult(
                audio_data=audio_data,
                sample_rate=sample_rate,
                duration_ms=duration_ms,
                latency_ms=(time.time() - start_time) * 1000,
                language=language
            )
        
        try:
            request = riva_tts.SynthesizeSpeechRequest(
                text=text,
                language_code=language,
                encoding=riva_tts.AudioEncoding.LINEAR_PCM,
                sample_rate_hz=sample_rate,
            )
            
            if voice_name or settings.tts_voice_name:
                request.voice_name = voice_name or settings.tts_voice_name
            
            response = await self._stub.Synthesize(request)
            
            latency_ms = (time.time() - start_time) * 1000
            duration_ms = len(response.audio) / (sample_rate * 2) * 1000
            
            return SynthesisResult(
                audio_data=response.audio,
                sample_rate=sample_rate,
                duration_ms=duration_ms,
                latency_ms=latency_ms,
                language=language
            )
            
        except grpc.RpcError as e:
            logger.error("Riva TTS error",
                        code=e.code(),
                        details=e.details())
            raise
    
    async def synthesize_streaming(
        self,
        text: str,
        language: str = None,
        voice_name: str = None,
        sample_rate: int = None
    ) -> AsyncIterator[bytes]:
        """
        Stream synthesized audio chunks.
        
        Yields audio chunks as they are generated for low-latency playback.
        
        Args:
            text: Text to synthesize
            language: Language code (default: hi-IN)
            voice_name: Voice name (default: language default)
            sample_rate: Output sample rate (default: 22050)
            
        Yields:
            Audio data chunks (PCM bytes)
        """
        language = language or settings.tts_language_code
        sample_rate = sample_rate or settings.tts_sample_rate
        
        if not RIVA_AVAILABLE or not self._stub:
            logger.warning("Using mock streaming TTS")
            # Mock streaming - yield chunks
            audio_data = self._generate_mock_audio(text, sample_rate)
            chunk_size = settings.streaming_chunk_size
            
            for i in range(0, len(audio_data), chunk_size):
                yield audio_data[i:i + chunk_size]
                await asyncio.sleep(0.01)  # Simulate streaming delay
            return
        
        try:
            request = riva_tts.SynthesizeSpeechRequest(
                text=text,
                language_code=language,
                encoding=riva_tts.AudioEncoding.LINEAR_PCM,
                sample_rate_hz=sample_rate,
            )
            
            if voice_name or settings.tts_voice_name:
                request.voice_name = voice_name or settings.tts_voice_name
            
            async for response in self._stub.SynthesizeOnline(request):
                if response.audio:
                    yield response.audio
                    
        except grpc.RpcError as e:
            logger.error("Streaming TTS error",
                        code=e.code(),
                        details=e.details())
            raise
    
    async def get_voices(self, language: str = None) -> List[dict]:
        """Get available voices for a language."""
        if not RIVA_AVAILABLE or not self._stub:
            return [
                {"name": "hi-IN-female-1", "language": "hi-IN", "gender": "female"},
                {"name": "hi-IN-male-1", "language": "hi-IN", "gender": "male"},
            ]
        
        # Note: Riva doesn't have a direct API for listing voices
        # This would need to be configured or fetched from model config
        return []


class TTSConnectionPool:
    """Connection pool for Riva TTS clients."""
    
    def __init__(self, pool_size: int = None):
        self.pool_size = pool_size or settings.grpc_pool_size
        self._clients: List[RivaTTSClient] = []
        self._available: asyncio.Queue = asyncio.Queue()
        self._initialized = False
    
    async def initialize(self):
        """Initialize the connection pool."""
        if self._initialized:
            return
            
        for _ in range(self.pool_size):
            client = RivaTTSClient()
            await client.connect()
            self._clients.append(client)
            await self._available.put(client)
        
        self._initialized = True
        logger.info("TTS connection pool initialized", size=self.pool_size)
    
    async def close(self):
        """Close all connections in the pool."""
        for client in self._clients:
            await client.close()
        self._clients.clear()
        self._initialized = False
    
    async def acquire(self) -> RivaTTSClient:
        """Acquire a client from the pool."""
        return await self._available.get()
    
    async def release(self, client: RivaTTSClient):
        """Release a client back to the pool."""
        await self._available.put(client)


# Global connection pool
tts_pool = TTSConnectionPool()

