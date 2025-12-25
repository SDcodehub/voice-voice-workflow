import logging
import os
from typing import AsyncGenerator
from openai import AsyncOpenAI

from metrics import METRICS, Timer

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, base_url: str = None, api_key: str = "dummy", model: str = None):
        """
        Initialize the LLM Client for NVIDIA NIM.
        
        Args:
            base_url: The URL of the NIM service (e.g., "http://localhost:8000/v1")
            api_key: API Key (usually not needed for self-hosted NIMs inside K8s, but required by SDK)
            model: The specific model name running in the NIM
        """
        # Configuration from environment variables (set via ConfigMap)
        self.base_url = base_url or os.getenv("LLM_SERVICE_URL", "http://localhost:8000/v1")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "dummy")
        self.model = model or os.getenv("LLM_MODEL", "meta/llama-3.1-8b-instruct")
        
        # Tunable parameters from ConfigMap
        self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.5"))
        self.max_tokens = int(os.getenv("LLM_MAX_TOKENS", "1024"))
        self.default_system_prompt = os.getenv("LLM_SYSTEM_PROMPT", None)
        
        logger.info(f"Initializing LLM Client: URL={self.base_url}, Model={self.model}, Temp={self.temperature}")
        
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )

    async def generate_response(self, text_input: str, system_prompt: str = None) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from the LLM.
        
        Args:
            text_input: The user's input text (from ASR)
            system_prompt: Optional system instruction (overrides default from ConfigMap)
            
        Yields:
            str: Chunks of generated text
            
        Metrics collected:
        - llm_ttft: Time to first token
        - llm_total: Total generation time
        - llm_tokens: Number of tokens generated
        """
        messages = []
        
        # Use provided system_prompt, or fall back to ConfigMap default
        effective_prompt = system_prompt or self.default_system_prompt
        if effective_prompt:
            messages.append({"role": "system", "content": effective_prompt})
        
        messages.append({"role": "user", "content": text_input})
        
        # Timers for latency metrics
        total_timer = Timer()
        ttft_timer = Timer()
        first_token_received = False
        token_count = 0

        try:
            total_timer.start()
            ttft_timer.start()
            
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=self.temperature,
                max_tokens=self.max_tokens
            )

            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    # Record time to first token
                    if not first_token_received:
                        ttft_timer.stop()
                        METRICS.llm_ttft.labels(model=self.model).observe(ttft_timer.duration)
                        logger.debug(f"LLM TTFT: {ttft_timer.duration:.3f}s")
                        first_token_received = True
                    
                    token_count += 1
                    yield content
            
            # Record total generation metrics
            total_timer.stop()
            METRICS.llm_total.labels(model=self.model).observe(total_timer.duration)
            METRICS.llm_tokens.labels(model=self.model).observe(token_count)
            logger.debug(f"LLM total: {total_timer.duration:.3f}s, tokens: {token_count}")

        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            METRICS.llm_errors.labels(error_type=type(e).__name__).inc()
            # In a production system, we might yield a fallback error message or re-raise
            raise e

