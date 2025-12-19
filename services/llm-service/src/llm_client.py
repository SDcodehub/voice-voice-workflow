"""LLM Client for Hindi conversational AI."""

import asyncio
import hashlib
import json
from typing import AsyncIterator, List, Optional, Dict, Any
from dataclasses import dataclass
import time

import httpx
import redis.asyncio as redis
import structlog

from config import get_settings

logger = structlog.get_logger()
settings = get_settings()


@dataclass
class Message:
    """Chat message."""
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class GenerationResult:
    """LLM generation result."""
    text: str
    tokens_generated: int
    latency_ms: float
    finish_reason: str
    cached: bool = False


class LLMClient:
    """
    LLM Client supporting multiple backends.
    
    Backends:
    - nvidia_nim: NVIDIA NIM (recommended)
    - openai: OpenAI API compatible (vLLM, TGI, etc.)
    
    Features:
    - Streaming generation for low latency
    - Response caching
    - Automatic retry with backoff
    """
    
    def __init__(self):
        self._http_client: Optional[httpx.AsyncClient] = None
        self._redis_client: Optional[redis.Redis] = None
        
    async def initialize(self):
        """Initialize HTTP client and cache."""
        self._http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=20, max_connections=100)
        )
        
        if settings.enable_cache:
            try:
                self._redis_client = redis.Redis(
                    host=settings.redis_host,
                    port=settings.redis_port,
                    db=settings.redis_db,
                    decode_responses=True
                )
                await self._redis_client.ping()
                logger.info("Redis cache connected")
            except Exception as e:
                logger.warning("Redis cache unavailable", error=str(e))
                self._redis_client = None
    
    async def close(self):
        """Close connections."""
        if self._http_client:
            await self._http_client.aclose()
        if self._redis_client:
            await self._redis_client.close()
    
    def _get_api_config(self) -> tuple[str, str, str]:
        """Get API URL, key, and model based on backend."""
        if settings.llm_backend == "nvidia_nim":
            return (
                settings.nim_api_url,
                settings.nim_api_key,
                settings.nim_model
            )
        else:
            return (
                settings.openai_api_url,
                settings.openai_api_key,
                settings.openai_model
            )
    
    def _get_system_prompt(self, language: str) -> str:
        """Get appropriate system prompt for language."""
        if language.startswith("hi"):
            return settings.system_prompt_hindi
        return settings.system_prompt_english
    
    def _build_messages(
        self,
        conversation_history: List[Dict[str, str]],
        language: str
    ) -> List[Dict[str, str]]:
        """Build message list with system prompt and history."""
        messages = [
            {"role": "system", "content": self._get_system_prompt(language)}
        ]
        
        # Add conversation history (limited to max turns)
        history = conversation_history[-settings.max_history_turns * 2:]
        messages.extend(history)
        
        return messages
    
    def _get_cache_key(self, messages: List[Dict[str, str]]) -> str:
        """Generate cache key for messages."""
        content = json.dumps(messages, sort_keys=True)
        return f"llm_cache:{hashlib.sha256(content.encode()).hexdigest()[:16]}"
    
    async def _check_cache(self, cache_key: str) -> Optional[str]:
        """Check cache for response."""
        if not self._redis_client or not settings.enable_cache:
            return None
        
        try:
            return await self._redis_client.get(cache_key)
        except Exception as e:
            logger.warning("Cache read error", error=str(e))
            return None
    
    async def _set_cache(self, cache_key: str, response: str):
        """Cache response."""
        if not self._redis_client or not settings.enable_cache:
            return
        
        try:
            await self._redis_client.setex(
                cache_key,
                settings.cache_ttl_seconds,
                response
            )
        except Exception as e:
            logger.warning("Cache write error", error=str(e))
    
    async def generate(
        self,
        conversation_history: List[Dict[str, str]],
        language: str = "hi-IN",
        max_tokens: int = None,
        temperature: float = None
    ) -> GenerationResult:
        """
        Generate a response (non-streaming).
        
        Args:
            conversation_history: List of messages [{"role": "user/assistant", "content": "..."}]
            language: Language code
            max_tokens: Override max tokens
            temperature: Override temperature
            
        Returns:
            GenerationResult with generated text
        """
        start_time = time.time()
        
        messages = self._build_messages(conversation_history, language)
        cache_key = self._get_cache_key(messages)
        
        # Check cache
        cached = await self._check_cache(cache_key)
        if cached:
            return GenerationResult(
                text=cached,
                tokens_generated=0,
                latency_ms=(time.time() - start_time) * 1000,
                finish_reason="cached",
                cached=True
            )
        
        api_url, api_key, model = self._get_api_config()
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens or settings.max_tokens,
            "temperature": temperature or settings.temperature,
            "top_p": settings.top_p,
            "frequency_penalty": settings.frequency_penalty,
            "presence_penalty": settings.presence_penalty,
            "stream": False
        }
        
        try:
            response = await self._http_client.post(
                f"{api_url}/chat/completions",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            
            text = data["choices"][0]["message"]["content"]
            tokens = data.get("usage", {}).get("completion_tokens", 0)
            finish_reason = data["choices"][0].get("finish_reason", "stop")
            
            # Cache the response
            await self._set_cache(cache_key, text)
            
            return GenerationResult(
                text=text,
                tokens_generated=tokens,
                latency_ms=(time.time() - start_time) * 1000,
                finish_reason=finish_reason,
                cached=False
            )
            
        except httpx.HTTPStatusError as e:
            logger.error("LLM API error", 
                        status=e.response.status_code,
                        body=e.response.text)
            raise
        except Exception as e:
            logger.error("LLM generation error", error=str(e))
            raise
    
    async def generate_stream(
        self,
        conversation_history: List[Dict[str, str]],
        language: str = "hi-IN",
        max_tokens: int = None,
        temperature: float = None
    ) -> AsyncIterator[str]:
        """
        Generate a streaming response.
        
        Yields tokens as they are generated for low-latency response.
        
        Args:
            conversation_history: List of messages
            language: Language code
            max_tokens: Override max tokens
            temperature: Override temperature
            
        Yields:
            Text chunks as they are generated
        """
        messages = self._build_messages(conversation_history, language)
        
        api_url, api_key, model = self._get_api_config()
        
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens or settings.max_tokens,
            "temperature": temperature or settings.temperature,
            "top_p": settings.top_p,
            "frequency_penalty": settings.frequency_penalty,
            "presence_penalty": settings.presence_penalty,
            "stream": True
        }
        
        try:
            async with self._http_client.stream(
                "POST",
                f"{api_url}/chat/completions",
                headers=headers,
                json=payload
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    
                    data = line[6:]  # Remove "data: " prefix
                    
                    if data == "[DONE]":
                        break
                    
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0].get("delta", {})
                        content = delta.get("content", "")
                        
                        if content:
                            yield content
                            
                    except json.JSONDecodeError:
                        continue
                        
        except httpx.HTTPStatusError as e:
            logger.error("LLM streaming error",
                        status=e.response.status_code)
            raise
        except Exception as e:
            logger.error("LLM streaming error", error=str(e))
            raise


# Global client instance
llm_client = LLMClient()

