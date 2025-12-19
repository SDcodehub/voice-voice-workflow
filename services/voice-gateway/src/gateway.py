"""Voice Gateway WebSocket Handler and Pipeline Orchestrator."""

import asyncio
import uuid
import json
import struct
from typing import AsyncIterator, Optional
from dataclasses import dataclass, field
from enum import Enum

import grpc
import redis.asyncio as redis
import structlog
from fastapi import WebSocket, WebSocketDisconnect

from config import get_settings

logger = structlog.get_logger()
settings = get_settings()


class SessionState(Enum):
    """Session lifecycle states."""
    INITIALIZED = "initialized"
    LISTENING = "listening"
    PROCESSING = "processing"
    SPEAKING = "speaking"
    IDLE = "idle"
    CLOSED = "closed"


@dataclass
class VoiceSession:
    """Represents an active voice conversation session."""
    session_id: str
    language: str = "hi-IN"
    state: SessionState = SessionState.INITIALIZED
    conversation_history: list = field(default_factory=list)
    created_at: float = 0.0
    last_activity: float = 0.0
    
    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "language": self.language,
            "state": self.state.value,
            "conversation_history": self.conversation_history,
            "created_at": self.created_at,
            "last_activity": self.last_activity
        }


class ServiceClient:
    """gRPC client for downstream services."""
    
    def __init__(self, host: str, port: int):
        self.host = host
        self.port = port
        self._channel: Optional[grpc.aio.Channel] = None
    
    async def connect(self):
        """Establish gRPC channel."""
        self._channel = grpc.aio.insecure_channel(
            f"{self.host}:{self.port}",
            options=[
                ('grpc.keepalive_time_ms', 10000),
                ('grpc.keepalive_timeout_ms', 5000),
                ('grpc.keepalive_permit_without_calls', True),
                ('grpc.http2.max_pings_without_data', 0),
                ('grpc.http2.min_time_between_pings_ms', 10000),
            ]
        )
        logger.info("gRPC channel established", host=self.host, port=self.port)
    
    async def close(self):
        """Close gRPC channel."""
        if self._channel:
            await self._channel.close()
    
    @property
    def channel(self) -> grpc.aio.Channel:
        if not self._channel:
            raise RuntimeError("Channel not connected")
        return self._channel


class VoiceGateway:
    """
    Main Voice Gateway that orchestrates the ASR -> LLM -> TTS pipeline.
    
    Handles:
    - WebSocket connections from clients
    - Session management
    - Streaming audio processing
    - Pipeline orchestration for low-latency voice-to-voice
    """
    
    def __init__(self):
        self.sessions: dict[str, VoiceSession] = {}
        self.redis_client: Optional[redis.Redis] = None
        
        # Service clients
        self.asr_client = ServiceClient(
            settings.asr_service_host, 
            settings.asr_service_port
        )
        self.llm_client = ServiceClient(
            settings.llm_service_host,
            settings.llm_service_port
        )
        self.tts_client = ServiceClient(
            settings.tts_service_host,
            settings.tts_service_port
        )
    
    async def initialize(self):
        """Initialize gateway connections."""
        # Connect to Redis
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            db=settings.redis_db,
            password=settings.redis_password or None,
            decode_responses=True
        )
        
        # Connect to downstream services
        await asyncio.gather(
            self.asr_client.connect(),
            self.llm_client.connect(),
            self.tts_client.connect()
        )
        
        logger.info("Voice Gateway initialized")
    
    async def shutdown(self):
        """Cleanup on shutdown."""
        await asyncio.gather(
            self.asr_client.close(),
            self.llm_client.close(),
            self.tts_client.close()
        )
        if self.redis_client:
            await self.redis_client.close()
        logger.info("Voice Gateway shutdown complete")
    
    async def create_session(self, language: str = "hi-IN") -> VoiceSession:
        """Create a new voice session."""
        import time
        
        session_id = str(uuid.uuid4())
        session = VoiceSession(
            session_id=session_id,
            language=language,
            created_at=time.time(),
            last_activity=time.time()
        )
        
        self.sessions[session_id] = session
        
        # Store in Redis for distributed access
        if self.redis_client:
            await self.redis_client.setex(
                f"session:{session_id}",
                settings.session_timeout_seconds,
                json.dumps(session.to_dict())
            )
        
        logger.info("Session created", session_id=session_id, language=language)
        return session
    
    async def get_session(self, session_id: str) -> Optional[VoiceSession]:
        """Retrieve session from local cache or Redis."""
        if session_id in self.sessions:
            return self.sessions[session_id]
        
        # Try Redis
        if self.redis_client:
            data = await self.redis_client.get(f"session:{session_id}")
            if data:
                session_data = json.loads(data)
                session = VoiceSession(
                    session_id=session_data["session_id"],
                    language=session_data["language"],
                    state=SessionState(session_data["state"]),
                    conversation_history=session_data["conversation_history"],
                    created_at=session_data["created_at"],
                    last_activity=session_data["last_activity"]
                )
                self.sessions[session_id] = session
                return session
        
        return None
    
    async def handle_websocket(self, websocket: WebSocket):
        """
        Handle WebSocket connection for voice streaming.
        
        Protocol:
        1. Client connects and sends config message
        2. Client streams audio chunks
        3. Server processes ASR -> LLM -> TTS
        4. Server streams audio response back
        """
        await websocket.accept()
        session: Optional[VoiceSession] = None
        
        try:
            # Wait for initial config message
            config_message = await asyncio.wait_for(
                websocket.receive_json(),
                timeout=10.0
            )
            
            language = config_message.get("language", settings.default_language)
            session = await self.create_session(language=language)
            
            # Send session info back
            await websocket.send_json({
                "type": "session_created",
                "session_id": session.session_id,
                "language": session.language
            })
            
            logger.info("WebSocket session started", session_id=session.session_id)
            
            # Main message loop
            while True:
                message = await websocket.receive()
                
                if "bytes" in message:
                    # Audio chunk received
                    audio_data = message["bytes"]
                    await self._process_audio_stream(
                        websocket, session, audio_data
                    )
                
                elif "text" in message:
                    # Control message
                    control = json.loads(message["text"])
                    await self._handle_control_message(
                        websocket, session, control
                    )
        
        except WebSocketDisconnect:
            logger.info("WebSocket disconnected", 
                       session_id=session.session_id if session else "unknown")
        except asyncio.TimeoutError:
            logger.warning("WebSocket timeout waiting for config")
            await websocket.close(code=4000, reason="Config timeout")
        except Exception as e:
            logger.error("WebSocket error", error=str(e))
            await websocket.close(code=4001, reason=str(e))
        finally:
            if session:
                session.state = SessionState.CLOSED
                # Cleanup session after some time
                asyncio.create_task(self._cleanup_session(session.session_id))
    
    async def _process_audio_stream(
        self,
        websocket: WebSocket,
        session: VoiceSession,
        audio_data: bytes
    ):
        """
        Process incoming audio through the ASR -> LLM -> TTS pipeline.
        
        Uses streaming for low latency:
        1. Stream audio to ASR, get transcript
        2. Stream transcript to LLM, get response tokens
        3. Stream response to TTS, get audio chunks
        4. Stream audio back to client
        """
        import time
        session.last_activity = time.time()
        session.state = SessionState.LISTENING
        
        try:
            # Send status update
            await websocket.send_json({
                "type": "status",
                "state": "processing",
                "stage": "asr"
            })
            
            # Step 1: ASR - Convert speech to text
            transcript = await self._stream_to_asr(session, audio_data)
            
            if not transcript or not transcript.strip():
                logger.debug("Empty transcript, skipping")
                return
            
            logger.info("ASR complete", 
                       session_id=session.session_id, 
                       transcript=transcript[:100])
            
            # Add to conversation history
            session.conversation_history.append({
                "role": "user",
                "content": transcript
            })
            
            # Send transcript to client
            await websocket.send_json({
                "type": "transcript",
                "text": transcript,
                "is_final": True
            })
            
            # Step 2 & 3: LLM + TTS (streamed together for low latency)
            session.state = SessionState.PROCESSING
            await websocket.send_json({
                "type": "status",
                "state": "processing",
                "stage": "llm"
            })
            
            # Stream LLM response and TTS audio together
            full_response = ""
            async for audio_chunk, text_chunk in self._stream_llm_to_tts(
                session, transcript
            ):
                if text_chunk:
                    full_response += text_chunk
                    await websocket.send_json({
                        "type": "response_text",
                        "text": text_chunk,
                        "is_final": False
                    })
                
                if audio_chunk:
                    session.state = SessionState.SPEAKING
                    await websocket.send_bytes(audio_chunk)
            
            # Add assistant response to history
            session.conversation_history.append({
                "role": "assistant",
                "content": full_response
            })
            
            # Send completion
            await websocket.send_json({
                "type": "response_text",
                "text": "",
                "is_final": True
            })
            
            session.state = SessionState.IDLE
            await websocket.send_json({
                "type": "status",
                "state": "idle"
            })
            
        except Exception as e:
            logger.error("Pipeline error", 
                        session_id=session.session_id, 
                        error=str(e))
            await websocket.send_json({
                "type": "error",
                "message": str(e)
            })
            session.state = SessionState.IDLE
    
    async def _stream_to_asr(
        self, 
        session: VoiceSession, 
        audio_data: bytes
    ) -> str:
        """
        Stream audio to ASR service and get transcript.
        
        For production, this would use bidirectional streaming
        for real-time transcription as user speaks.
        """
        # In production, this calls the ASR service via gRPC
        # For now, we'll use a simple HTTP call pattern
        import httpx
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"http://{settings.asr_service_host}:{settings.asr_service_port}/transcribe",
                    content=audio_data,
                    headers={
                        "Content-Type": "audio/raw",
                        "X-Language": session.language,
                        "X-Session-ID": session.session_id
                    }
                )
                response.raise_for_status()
                result = response.json()
                return result.get("transcript", "")
        except Exception as e:
            logger.error("ASR error", error=str(e))
            raise
    
    async def _stream_llm_to_tts(
        self,
        session: VoiceSession,
        user_input: str
    ) -> AsyncIterator[tuple[Optional[bytes], Optional[str]]]:
        """
        Stream LLM response directly to TTS for minimum latency.
        
        This implements "sentence streaming" where:
        1. LLM generates tokens
        2. When a sentence is complete, send to TTS
        3. Stream TTS audio back while LLM continues
        """
        import httpx
        
        # Buffer for accumulating text until sentence boundary
        text_buffer = ""
        sentence_delimiters = ["।", "?", "!", ".", "\n"]  # Hindi and English
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Stream from LLM
                async with client.stream(
                    "POST",
                    f"http://{settings.llm_service_host}:{settings.llm_service_port}/generate",
                    json={
                        "messages": session.conversation_history,
                        "language": session.language,
                        "session_id": session.session_id,
                        "stream": True
                    }
                ) as llm_response:
                    
                    async for chunk in llm_response.aiter_text():
                        text_buffer += chunk
                        yield None, chunk
                        
                        # Check for sentence boundary
                        for delimiter in sentence_delimiters:
                            if delimiter in text_buffer:
                                # Split at delimiter
                                parts = text_buffer.split(delimiter, 1)
                                sentence = parts[0] + delimiter
                                text_buffer = parts[1] if len(parts) > 1 else ""
                                
                                # Send sentence to TTS
                                async for audio in self._stream_tts(
                                    session, sentence.strip()
                                ):
                                    yield audio, None
                                break
                
                # Process any remaining text
                if text_buffer.strip():
                    async for audio in self._stream_tts(session, text_buffer.strip()):
                        yield audio, None
                        
        except Exception as e:
            logger.error("LLM-TTS pipeline error", error=str(e))
            raise
    
    async def _stream_tts(
        self,
        session: VoiceSession,
        text: str
    ) -> AsyncIterator[bytes]:
        """Stream text to TTS service and yield audio chunks."""
        import httpx
        
        if not text:
            return
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                async with client.stream(
                    "POST",
                    f"http://{settings.tts_service_host}:{settings.tts_service_port}/synthesize",
                    json={
                        "text": text,
                        "language": session.language,
                        "session_id": session.session_id
                    }
                ) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
        except Exception as e:
            logger.error("TTS error", error=str(e))
            raise
    
    async def _handle_control_message(
        self,
        websocket: WebSocket,
        session: VoiceSession,
        control: dict
    ):
        """Handle control messages from client."""
        action = control.get("action")
        
        if action == "ping":
            await websocket.send_json({"type": "pong"})
        
        elif action == "clear_history":
            session.conversation_history.clear()
            await websocket.send_json({
                "type": "history_cleared"
            })
        
        elif action == "change_language":
            new_lang = control.get("language", settings.default_language)
            if new_lang in settings.supported_languages:
                session.language = new_lang
                await websocket.send_json({
                    "type": "language_changed",
                    "language": new_lang
                })
            else:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Unsupported language: {new_lang}"
                })
        
        elif action == "get_state":
            await websocket.send_json({
                "type": "state",
                "session": session.to_dict()
            })
    
    async def _cleanup_session(self, session_id: str, delay: float = 300.0):
        """Cleanup session after delay."""
        await asyncio.sleep(delay)
        if session_id in self.sessions:
            del self.sessions[session_id]
        if self.redis_client:
            await self.redis_client.delete(f"session:{session_id}")
        logger.info("Session cleaned up", session_id=session_id)


# Global gateway instance
gateway = VoiceGateway()

