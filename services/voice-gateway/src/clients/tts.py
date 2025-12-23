import logging
import riva.client
from typing import AsyncGenerator, Generator
import asyncio
import queue

logger = logging.getLogger(__name__)

class TTSClient:
    def __init__(self, auth: riva.client.Auth, language_code: str = "hi-IN", sample_rate: int = 44100):
        self.auth = auth
        self.language_code = language_code
        self.sample_rate = sample_rate
        self.tts_service = riva.client.SpeechSynthesisService(self.auth)
        
        logger.info(f"Initializing TTS Client: Language={self.language_code}, SampleRate={self.sample_rate}")

    async def synthesize_stream(self, text: str) -> AsyncGenerator[bytes, None]:
        """
        Synthesize text to speech streaming audio.
        
        Args:
            text: The text to synthesize (e.g., a sentence from the LLM)
            
        Yields:
            bytes: Audio chunks (linear PCM)
        """
        # Riva's synthesize_online is a blocking call that returns a generator.
        # We need to run this in a thread to avoid blocking the asyncio event loop.
        
        loop = asyncio.get_running_loop()
        result_queue = asyncio.Queue()

        def run_riva_synthesis():
            try:
                responses = self.tts_service.synthesize_online(
                    text=text,
                    language_code=self.language_code,
                    encoding=riva.client.AudioEncoding.LINEAR_PCM,
                    sample_rate_hz=self.sample_rate,
                    voice_name=f"{self.language_code}-Standard-A" # Assuming standard voice exists, or let Riva pick default
                )
                
                for response in responses:
                    if response.audio:
                        asyncio.run_coroutine_threadsafe(
                            result_queue.put(response.audio), loop
                        )
            except Exception as e:
                logger.error(f"Error in Riva TTS synthesis: {e}")
                # Propagate error via queue or log
                asyncio.run_coroutine_threadsafe(result_queue.put(e), loop)
            finally:
                asyncio.run_coroutine_threadsafe(result_queue.put(None), loop)

        # Start the synthesis in a separate thread
        await loop.run_in_executor(None, run_riva_synthesis)

        # Yield results back to the caller
        while True:
            item = await result_queue.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            yield item

