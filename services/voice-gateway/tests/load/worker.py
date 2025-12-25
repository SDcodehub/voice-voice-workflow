"""
Voice Worker - Simulates a single virtual user making voice requests.

Each worker maintains its own gRPC channel and streams audio files
through the voice gateway, collecting timing metrics for each request.
"""

import asyncio
import time
import logging
from typing import Optional, AsyncGenerator, Callable
from dataclasses import dataclass

import grpc

# Import proto modules (will be available when running from correct directory)
try:
    import voice_workflow_pb2
    import voice_workflow_pb2_grpc
except ImportError:
    # Try relative import for when running as module
    import sys
    import os
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))
    import voice_workflow_pb2
    import voice_workflow_pb2_grpc

try:
    from .audio_pool import AudioFile
    from .collector import RequestResult
except ImportError:
    from audio_pool import AudioFile
    from collector import RequestResult

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """Configuration for a single worker."""
    worker_id: int
    target_url: str
    language_code: str = "en-US"
    sample_rate: int = 16000
    chunk_size: int = 4096
    chunk_delay: float = 0.01  # Seconds between chunks (simulates real-time)
    request_timeout: float = 60.0  # Seconds
    think_time: float = 1.0  # Seconds between requests


class VoiceWorker:
    """
    Simulates a single virtual user making voice requests.
    
    Each worker:
    1. Gets an audio file from the pool
    2. Opens a gRPC stream
    3. Sends audio chunks at realistic pace
    4. Captures response and timing metrics
    5. Reports results to collector
    
    Usage:
        worker = VoiceWorker(config, audio_pool, collector)
        await worker.start()  # Runs until stopped
        worker.stop()
    """
    
    def __init__(
        self,
        config: WorkerConfig,
        get_audio: Callable[[], AudioFile],
        on_result: Callable[[RequestResult], None],
    ):
        self.config = config
        self.get_audio = get_audio
        self.on_result = on_result
        
        self._running = False
        self._request_count = 0
        self._channel: Optional[grpc.aio.Channel] = None
        self._stub: Optional[voice_workflow_pb2_grpc.VoiceGatewayStub] = None
    
    async def start(self, max_requests: int = 0):
        """
        Start the worker loop.
        
        Args:
            max_requests: Maximum requests to make (0 = unlimited).
        """
        self._running = True
        
        # Create gRPC channel
        self._channel = grpc.aio.insecure_channel(self.config.target_url)
        self._stub = voice_workflow_pb2_grpc.VoiceGatewayStub(self._channel)
        
        logger.debug(f"Worker {self.config.worker_id} started")
        
        try:
            while self._running:
                # Check max requests
                if max_requests > 0 and self._request_count >= max_requests:
                    logger.debug(f"Worker {self.config.worker_id} reached max requests")
                    break
                
                # Make a request
                await self._make_request()
                self._request_count += 1
                
                # Think time between requests
                if self._running and self.config.think_time > 0:
                    await asyncio.sleep(self.config.think_time)
        
        finally:
            if self._channel:
                await self._channel.close()
            logger.debug(f"Worker {self.config.worker_id} stopped after {self._request_count} requests")
    
    def stop(self):
        """Signal the worker to stop after current request."""
        self._running = False
    
    async def _make_request(self):
        """Make a single voice request and collect metrics."""
        audio_file = self.get_audio()
        request_id = self._request_count
        
        result = RequestResult(
            worker_id=self.config.worker_id,
            request_id=request_id,
            audio_file=audio_file.name,
            start_time=time.time(),
            end_time=0,
        )
        
        # Timing trackers
        first_transcript_time: Optional[float] = None
        final_transcript_time: Optional[float] = None
        first_llm_token_time: Optional[float] = None
        last_llm_token_time: Optional[float] = None
        first_audio_time: Optional[float] = None
        
        transcript_buffer = ""
        response_buffer = ""
        
        try:
            # Create request generator
            async def request_generator() -> AsyncGenerator:
                # Send config first
                yield voice_workflow_pb2.ClientMessage(
                    config=voice_workflow_pb2.VoiceConfig(
                        language_code=self.config.language_code,
                        session_id=f"load-test-{self.config.worker_id}-{request_id}",
                        sample_rate=self.config.sample_rate,
                    )
                )
                
                # Stream audio chunks
                for chunk in audio_file.get_chunks(self.config.chunk_size):
                    yield voice_workflow_pb2.ClientMessage(audio_chunk=chunk)
                    
                    # Simulate real-time audio streaming
                    if self.config.chunk_delay > 0:
                        await asyncio.sleep(self.config.chunk_delay)
            
            # Make the streaming RPC call with timeout
            stream = self._stub.StreamAudio(
                request_generator(),
                timeout=self.config.request_timeout,
            )
            
            # Process responses
            async for response in stream:
                current_time = time.time()
                
                if response.HasField('transcript_chunk'):
                    if first_transcript_time is None:
                        first_transcript_time = current_time
                    transcript_buffer = response.transcript_chunk
                    
                    # Check if this looks like a final transcript
                    # (implementation may vary based on your proto)
                    if not transcript_buffer.endswith('...'):
                        final_transcript_time = current_time
                
                elif response.HasField('llm_response_chunk'):
                    if first_llm_token_time is None:
                        first_llm_token_time = current_time
                    last_llm_token_time = current_time
                    response_buffer += response.llm_response_chunk
                
                elif response.HasField('audio_chunk'):
                    if first_audio_time is None:
                        first_audio_time = current_time
                
                elif response.HasField('event'):
                    event_type = response.event.type
                    if event_type == voice_workflow_pb2.ERROR:
                        result.status = "error"
                        result.error_message = response.event.message
                    elif event_type == voice_workflow_pb2.END_OF_TURN:
                        break
            
            # Calculate latencies
            result.end_time = time.time()
            result.transcript = transcript_buffer
            result.response_text = response_buffer[:500]  # Truncate for storage
            
            # ASR latency: time from start to final transcript
            if final_transcript_time:
                result.asr_latency = final_transcript_time - result.start_time
            
            # LLM TTFT: time from final transcript to first LLM token
            if final_transcript_time and first_llm_token_time:
                result.llm_ttft = first_llm_token_time - final_transcript_time
            
            # LLM Total: time from final transcript to last LLM token
            if final_transcript_time and last_llm_token_time:
                result.llm_total = last_llm_token_time - final_transcript_time
            
            # TTS latency: time from first LLM token to first audio
            if first_llm_token_time and first_audio_time:
                result.tts_latency = first_audio_time - first_llm_token_time
            
            # E2E latency: time from final transcript to first audio
            if final_transcript_time and first_audio_time:
                result.e2e_latency = first_audio_time - final_transcript_time
            
            if result.status != "error":
                result.status = "success"
        
        except asyncio.TimeoutError:
            result.end_time = time.time()
            result.status = "timeout"
            result.error_message = f"Request timed out after {self.config.request_timeout}s"
            logger.warning(f"Worker {self.config.worker_id} request {request_id} timed out")
        
        except grpc.aio.AioRpcError as e:
            result.end_time = time.time()
            result.status = "error"
            result.error_message = f"gRPC error: {e.code()} - {e.details()}"
            logger.warning(f"Worker {self.config.worker_id} request {request_id} failed: {e}")
        
        except Exception as e:
            result.end_time = time.time()
            result.status = "error"
            result.error_message = str(e)
            logger.error(f"Worker {self.config.worker_id} request {request_id} error: {e}")
        
        # Report result
        self.on_result(result)
        
        logger.debug(
            f"Worker {self.config.worker_id} request {request_id}: "
            f"status={result.status}, e2e={result.e2e_latency or 0:.3f}s"
        )
    
    @property
    def request_count(self) -> int:
        """Number of requests completed."""
        return self._request_count

