import asyncio
import logging
import grpc
import os
import signal
import riva.client
from concurrent import futures
from typing import AsyncGenerator

# Generated proto imports
import voice_workflow_pb2
import voice_workflow_pb2_grpc

from clients.asr import ASRClient
from clients.llm import LLMClient
from clients.tts import TTSClient

# Configure logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Graceful shutdown configuration
SHUTDOWN_GRACE_PERIOD = int(os.getenv("SHUTDOWN_GRACE_PERIOD", "10"))  # seconds

class VoiceGatewayServicer(voice_workflow_pb2_grpc.VoiceGatewayServicer):
    """Implementation of the Voice Gateway Service."""

    def __init__(self):
        # Load configuration from environment variables
        self.riva_uri = os.getenv("RIVA_URI", "localhost:50051")
        self.nim_url = os.getenv("LLM_SERVICE_URL", "http://localhost:8000/v1")
        
        logger.info(f"Connecting to Riva at {self.riva_uri}")
        logger.info(f"Connecting to NIM at {self.nim_url}")

        # Initialize Riva Auth
        # In production, might need SSL options
        self.auth = riva.client.Auth(uri=self.riva_uri)

        # Initialize Clients (LLM and TTS can be shared or lightweight)
        self.llm_client = LLMClient(base_url=self.nim_url)
        # TTSClient might need lang config too, checking later. 
        # For now, we move ASRClient creation to per-session.

    async def StreamAudio(self, request_iterator, context):
        """
        Bidirectional streaming RPC.
        """
        # Queue to decouple input request stream from processing logic
        # We can also just use an async generator adapter.
        
        # We need a way to pass audio chunks to ASR. 
        # Since ASRClient takes an async generator, we can create one that yields from request_iterator.
        # BUT, request_iterator also contains Config and Text.
        
        input_queue = asyncio.Queue()
        
        async def input_processor():
            """Reads from gRPC stream and pushes to input_queue."""
            try:
                async for request in request_iterator:
                    await input_queue.put(request)
            finally:
                await input_queue.put(None) # Sentinel

        # Start input processing in background
        input_task = asyncio.create_task(input_processor())

        try:
            # 1. Wait for Config (first message)
            first_msg = await input_queue.get()
            if not first_msg or not first_msg.HasField('config'):
                logger.warning("First message was not config.")
                # We can proceed or error out. Proceeding for robustness.
            else:
                logger.info(f"Session started: {first_msg.config}")
                # Initialize ASR Client with session language
                language = first_msg.config.language_code if first_msg.config.language_code else "en-US"
                sample_rate = first_msg.config.sample_rate if first_msg.config.sample_rate else 16000
                asr_client = ASRClient(auth=self.auth, language_code=language, sample_rate=sample_rate)
                
                # Initialize TTS Client with matching language and sample rate for client playback
                tts_client = TTSClient(auth=self.auth, language_code=language, sample_rate=sample_rate)
                
                yield voice_workflow_pb2.ServerMessage(
                    event=voice_workflow_pb2.ServerEvent(
                        type=voice_workflow_pb2.LISTENING,
                        message="Ready"
                    )
                )

            # 2. Define audio source generator for ASR
            async def audio_source_gen():
                # If the first message wasn't config and was audio, yield it
                if first_msg and first_msg.HasField('audio_chunk'):
                    yield first_msg.audio_chunk
                
                while True:
                    msg = await input_queue.get()
                    if msg is None:
                        logger.info("End of input stream received.")
                        break
                    if msg.HasField('audio_chunk'):
                        # logger.debug(f"Received audio chunk: {len(msg.audio_chunk)} bytes")
                        yield msg.audio_chunk
                    elif msg.HasField('text_input'):
                        # TODO: Handle text input (bypass ASR)
                        # For now, we focus on voice-to-voice
                        pass
            
            # 3. Process Pipeline: ASR -> LLM -> TTS
            # We iterate over ASR results. This drives the whole loop.
            
            asr_stream = asr_client.transcribe_stream(audio_source_gen())
            
            async for transcript, is_final in asr_stream:
                if not is_final:
                    # Send interim transcript
                    yield voice_workflow_pb2.ServerMessage(transcript_chunk=transcript)
                else:
                    logger.info(f"Final ASR: {transcript}")
                    yield voice_workflow_pb2.ServerMessage(transcript_chunk=transcript)
                    yield voice_workflow_pb2.ServerMessage(
                        event=voice_workflow_pb2.ServerEvent(type=voice_workflow_pb2.PROCESSING)
                    )

                    # Send to LLM
                    llm_stream = self.llm_client.generate_response(transcript)
                    
                    # Buffer for TTS
                    sentence_buffer = ""
                    
                    async for text_chunk in llm_stream:
                        yield voice_workflow_pb2.ServerMessage(llm_response_chunk=text_chunk)
                        
                        sentence_buffer += text_chunk
                        # Simple sentence splitting
                        if any(p in text_chunk for p in ['.', '?', '!', '।', '\n']):
                            # Speak what we have
                            to_speak = sentence_buffer.strip()
                            if to_speak:
                                yield voice_workflow_pb2.ServerMessage(
                                    event=voice_workflow_pb2.ServerEvent(type=voice_workflow_pb2.SPEAKING)
                                )
                                logger.info(f"Speaking: {to_speak}")
                                tts_stream = tts_client.synthesize_stream(to_speak)
                                async for audio_chunk in tts_stream:
                                    yield voice_workflow_pb2.ServerMessage(audio_chunk=audio_chunk)
                            sentence_buffer = ""
                    
                    # Process remaining buffer
                    if sentence_buffer.strip():
                        to_speak = sentence_buffer.strip()
                        logger.info(f"Speaking (Final): {to_speak}")
                        tts_stream = tts_client.synthesize_stream(to_speak)
                        async for audio_chunk in tts_stream:
                            yield voice_workflow_pb2.ServerMessage(audio_chunk=audio_chunk)

                    yield voice_workflow_pb2.ServerMessage(
                        event=voice_workflow_pb2.ServerEvent(type=voice_workflow_pb2.LISTENING)
                    )

        except Exception as e:
            logger.error(f"Error in StreamAudio: {e}", exc_info=True)
            yield voice_workflow_pb2.ServerMessage(
                event=voice_workflow_pb2.ServerEvent(
                    type=voice_workflow_pb2.ERROR,
                    message=str(e)
                )
            )
        finally:
            input_task.cancel()
            yield voice_workflow_pb2.ServerMessage(
                event=voice_workflow_pb2.ServerEvent(type=voice_workflow_pb2.END_OF_TURN)
            )

async def serve():
    """
    Start the gRPC server with graceful shutdown support.
    
    Graceful shutdown flow:
    1. SIGTERM/SIGINT received (from Kubernetes or Ctrl+C)
    2. Server stops accepting NEW connections
    3. Waits up to SHUTDOWN_GRACE_PERIOD seconds for existing requests to complete
    4. Forcefully terminates remaining connections
    5. Exit cleanly
    """
    port = os.getenv("GRPC_PORT", "50051")
    max_workers = int(os.getenv("GRPC_MAX_WORKERS", "10"))
    
    server = grpc.aio.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            # Maximum time to wait for in-flight RPCs to complete during shutdown
            ('grpc.max_connection_idle_ms', 60000),
        ]
    )
    voice_workflow_pb2_grpc.add_VoiceGatewayServicer_to_server(VoiceGatewayServicer(), server)
    
    server.add_insecure_port('[::]:' + port)
    
    # Graceful shutdown handler
    shutdown_event = asyncio.Event()
    
    async def graceful_shutdown(sig_name: str):
        """Handle shutdown signal gracefully."""
        logger.info(f"Received {sig_name}, initiating graceful shutdown...")
        logger.info(f"Waiting up to {SHUTDOWN_GRACE_PERIOD}s for active requests to complete...")
        
        # Stop accepting new requests, wait for existing ones
        # grace parameter: time to wait for RPCs to complete
        await server.stop(grace=SHUTDOWN_GRACE_PERIOD)
        
        logger.info("Graceful shutdown complete.")
        shutdown_event.set()
    
    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(
            sig,
            lambda s=sig: asyncio.create_task(graceful_shutdown(s.name))
        )
    
    logger.info(f"Starting Voice Gateway on port {port}")
    logger.info(f"Max workers: {max_workers}, Shutdown grace period: {SHUTDOWN_GRACE_PERIOD}s")
    
    await server.start()
    
    # Wait for shutdown signal or server termination
    await shutdown_event.wait()


def main():
    """Entry point with proper signal handling."""
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, exiting...")
    except Exception as e:
        logger.error(f"Server crashed: {e}", exc_info=True)
        raise


if __name__ == '__main__':
    main()
