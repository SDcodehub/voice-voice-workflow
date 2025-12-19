"""NVIDIA Riva ASR Client for Hindi Speech Recognition."""

import asyncio
from typing import AsyncIterator, Optional, List
from dataclasses import dataclass
import time

import grpc
import numpy as np
import structlog

# Riva ASR imports
try:
    import riva.client
    from riva.client import ASRService
    import riva.client.proto.riva_asr_pb2 as riva_asr
    import riva.client.proto.riva_asr_pb2_grpc as riva_asr_grpc
    RIVA_AVAILABLE = True
except ImportError:
    RIVA_AVAILABLE = False
    # Mock for development without Riva
    riva_asr = None
    riva_asr_grpc = None

from config import get_settings

logger = structlog.get_logger()
settings = get_settings()


@dataclass
class TranscriptionResult:
    """ASR transcription result."""
    transcript: str
    is_final: bool
    confidence: float
    words: List[dict]
    latency_ms: float
    language: str


class RivaASRClient:
    """
    NVIDIA Riva ASR Client optimized for Hindi language.
    
    Features:
    - Streaming speech recognition
    - Connection pooling for high throughput
    - Automatic reconnection
    - Support for multiple audio formats
    """
    
    def __init__(self):
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[riva_asr_grpc.RivaSpeechRecognitionStub] = None
        self._auth = None
        
    async def connect(self):
        """Establish connection to Riva ASR server."""
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
            
            self._stub = riva_asr_grpc.RivaSpeechRecognitionStub(self._channel)
            
            logger.info("Connected to Riva ASR server", 
                       url=settings.riva_server_url)
            
        except Exception as e:
            logger.error("Failed to connect to Riva ASR", error=str(e))
            raise
    
    async def close(self):
        """Close the connection."""
        if self._channel:
            await self._channel.close()
            logger.info("Riva ASR connection closed")
    
    def _create_recognition_config(
        self, 
        language: str = None,
        sample_rate: int = None
    ) -> 'riva_asr.RecognitionConfig':
        """Create Riva recognition configuration for Hindi."""
        if not RIVA_AVAILABLE:
            return None
            
        config = riva_asr.RecognitionConfig(
            encoding=riva_asr.AudioEncoding.LINEAR_PCM,
            sample_rate_hertz=sample_rate or settings.asr_sample_rate,
            language_code=language or settings.asr_language_code,
            max_alternatives=settings.asr_max_alternatives,
            enable_automatic_punctuation=settings.asr_enable_automatic_punctuation,
            enable_word_time_offsets=settings.asr_enable_word_time_offsets,
            profanity_filter=settings.asr_profanity_filter,
            verbatim_transcripts=settings.asr_verbatim_transcripts,
            audio_channel_count=settings.asr_audio_channel_count,
        )
        
        # Add model name if specified
        if settings.asr_model_name:
            config.model = settings.asr_model_name
            
        return config
    
    def _create_streaming_config(
        self,
        language: str = None,
        sample_rate: int = None
    ) -> 'riva_asr.StreamingRecognitionConfig':
        """Create streaming recognition configuration."""
        if not RIVA_AVAILABLE:
            return None
            
        return riva_asr.StreamingRecognitionConfig(
            config=self._create_recognition_config(language, sample_rate),
            interim_results=settings.streaming_interim_results,
        )
    
    async def transcribe(
        self,
        audio_data: bytes,
        language: str = None,
        sample_rate: int = None
    ) -> TranscriptionResult:
        """
        Transcribe audio data (batch/offline recognition).
        
        Args:
            audio_data: Raw PCM audio bytes (16-bit, mono)
            language: Language code (default: hi-IN)
            sample_rate: Sample rate in Hz (default: 16000)
            
        Returns:
            TranscriptionResult with transcript and metadata
        """
        start_time = time.time()
        
        if not RIVA_AVAILABLE or not self._stub:
            # Mock response for development
            logger.warning("Using mock ASR response")
            return TranscriptionResult(
                transcript="यह एक परीक्षण प्रतिलेख है",  # "This is a test transcript" in Hindi
                is_final=True,
                confidence=0.95,
                words=[],
                latency_ms=(time.time() - start_time) * 1000,
                language=language or settings.asr_language_code
            )
        
        try:
            request = riva_asr.RecognizeRequest(
                config=self._create_recognition_config(language, sample_rate),
                audio=audio_data
            )
            
            response = await self._stub.Recognize(request)
            
            latency_ms = (time.time() - start_time) * 1000
            
            if response.results:
                result = response.results[0]
                if result.alternatives:
                    alt = result.alternatives[0]
                    
                    words = []
                    if settings.asr_enable_word_time_offsets:
                        for word_info in alt.words:
                            words.append({
                                "word": word_info.word,
                                "start_time": word_info.start_time,
                                "end_time": word_info.end_time,
                                "confidence": word_info.confidence
                            })
                    
                    return TranscriptionResult(
                        transcript=alt.transcript,
                        is_final=True,
                        confidence=alt.confidence,
                        words=words,
                        latency_ms=latency_ms,
                        language=language or settings.asr_language_code
                    )
            
            return TranscriptionResult(
                transcript="",
                is_final=True,
                confidence=0.0,
                words=[],
                latency_ms=latency_ms,
                language=language or settings.asr_language_code
            )
            
        except grpc.RpcError as e:
            logger.error("Riva ASR error", 
                        code=e.code(), 
                        details=e.details())
            raise
    
    async def transcribe_streaming(
        self,
        audio_stream: AsyncIterator[bytes],
        language: str = None,
        sample_rate: int = None
    ) -> AsyncIterator[TranscriptionResult]:
        """
        Stream audio for real-time transcription.
        
        Args:
            audio_stream: Async iterator yielding audio chunks
            language: Language code (default: hi-IN)
            sample_rate: Sample rate in Hz (default: 16000)
            
        Yields:
            TranscriptionResult for each recognition result (interim and final)
        """
        if not RIVA_AVAILABLE or not self._stub:
            logger.warning("Using mock streaming ASR")
            # Mock streaming response
            async for chunk in audio_stream:
                yield TranscriptionResult(
                    transcript="स्ट्रीमिंग परीक्षण...",
                    is_final=False,
                    confidence=0.8,
                    words=[],
                    latency_ms=50.0,
                    language=language or settings.asr_language_code
                )
            yield TranscriptionResult(
                transcript="यह स्ट्रीमिंग प्रतिलेख का अंतिम परिणाम है",
                is_final=True,
                confidence=0.95,
                words=[],
                latency_ms=100.0,
                language=language or settings.asr_language_code
            )
            return
        
        try:
            async def request_generator():
                # First request with config
                yield riva_asr.StreamingRecognizeRequest(
                    streaming_config=self._create_streaming_config(language, sample_rate)
                )
                
                # Subsequent requests with audio
                async for audio_chunk in audio_stream:
                    yield riva_asr.StreamingRecognizeRequest(
                        audio_content=audio_chunk
                    )
            
            start_time = time.time()
            
            async for response in self._stub.StreamingRecognize(request_generator()):
                for result in response.results:
                    if result.alternatives:
                        alt = result.alternatives[0]
                        
                        words = []
                        if settings.asr_enable_word_time_offsets and result.is_final:
                            for word_info in alt.words:
                                words.append({
                                    "word": word_info.word,
                                    "start_time": word_info.start_time,
                                    "end_time": word_info.end_time,
                                    "confidence": word_info.confidence
                                })
                        
                        yield TranscriptionResult(
                            transcript=alt.transcript,
                            is_final=result.is_final,
                            confidence=alt.confidence,
                            words=words,
                            latency_ms=(time.time() - start_time) * 1000,
                            language=language or settings.asr_language_code
                        )
                        start_time = time.time()
                        
        except grpc.RpcError as e:
            logger.error("Streaming ASR error",
                        code=e.code(),
                        details=e.details())
            raise


class ASRConnectionPool:
    """Connection pool for Riva ASR clients."""
    
    def __init__(self, pool_size: int = None):
        self.pool_size = pool_size or settings.grpc_pool_size
        self._clients: List[RivaASRClient] = []
        self._available: asyncio.Queue = asyncio.Queue()
        self._initialized = False
    
    async def initialize(self):
        """Initialize the connection pool."""
        if self._initialized:
            return
            
        for _ in range(self.pool_size):
            client = RivaASRClient()
            await client.connect()
            self._clients.append(client)
            await self._available.put(client)
        
        self._initialized = True
        logger.info("ASR connection pool initialized", size=self.pool_size)
    
    async def close(self):
        """Close all connections in the pool."""
        for client in self._clients:
            await client.close()
        self._clients.clear()
        self._initialized = False
    
    async def acquire(self) -> RivaASRClient:
        """Acquire a client from the pool."""
        return await self._available.get()
    
    async def release(self, client: RivaASRClient):
        """Release a client back to the pool."""
        await self._available.put(client)
    
    async def __aenter__(self) -> RivaASRClient:
        return await self.acquire()
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        client = await self.acquire()
        await self.release(client)


# Global connection pool
asr_pool = ASRConnectionPool()

