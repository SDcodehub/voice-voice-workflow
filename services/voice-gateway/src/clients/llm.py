import logging
import os
from typing import AsyncGenerator
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

class LLMClient:
    def __init__(self, base_url: str = None, api_key: str = "dummy", model: str = "meta/llama-3.1-8b-instruct"):
        """
        Initialize the LLM Client for NVIDIA NIM.
        
        Args:
            base_url: The URL of the NIM service (e.g., "http://localhost:8000/v1")
            api_key: API Key (usually not needed for self-hosted NIMs inside K8s, but required by SDK)
            model: The specific model name running in the NIM
        """
        # If no URL is provided, try to find it in env vars, otherwise default to localhost
        self.base_url = base_url or os.getenv("LLM_SERVICE_URL", "http://localhost:8000/v1")
        self.api_key = api_key or os.getenv("LLM_API_KEY", "dummy")
        self.model = model or os.getenv("LLM_MODEL", "meta/llama-3.1-8b-instruct")
        
        logger.info(f"Initializing LLM Client: URL={self.base_url}, Model={self.model}")
        
        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key
        )

    async def generate_response(self, text_input: str, system_prompt: str = None) -> AsyncGenerator[str, None]:
        """
        Generate a streaming response from the LLM.
        
        Args:
            text_input: The user's input text (from ASR)
            system_prompt: Optional system instruction (e.g., "You are a helpful assistant speaking Hindi")
            
        Yields:
            str: Chunks of generated text
        """
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        messages.append({"role": "user", "content": text_input})

        try:
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                stream=True,
                temperature=0.5, # Adjust for creativity vs determinism
                max_tokens=1024
            )

            async for chunk in stream:
                content = chunk.choices[0].delta.content
                if content:
                    yield content

        except Exception as e:
            logger.error(f"Error generating LLM response: {e}")
            # In a production system, we might yield a fallback error message or re-raise
            raise e

