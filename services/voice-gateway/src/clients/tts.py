import logging
import riva.client
from typing import AsyncGenerator, Generator
import asyncio
import queue

from metrics import METRICS, Timer

logger = logging.getLogger(__name__)

class TTSClient:
    def __init__(self, auth: riva.client.Auth, language_code: str = "en-US", sample_rate: int = 16000):
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
            
        Metrics collected:
        - tts_latency: Time to synthesize text
        - tts_characters: Number of characters synthesized
        """
        # Riva's synthesize_online is a blocking call that returns a generator.
        # We need to run this in a thread to avoid blocking the asyncio event loop.
        
        loop = asyncio.get_running_loop()
        result_queue = asyncio.Queue()
        
        # Timer for TTS latency
        tts_timer = Timer()
        text_length = len(text)

        def run_riva_synthesis():
            try:
                tts_timer.start()
                
                # Voice name format for Riva TTS models varies by deployment
                # For fastpitch_hifigan models, use "English-US" format or empty string for default
                responses = self.tts_service.synthesize_online(
                    text=text,
                    language_code=self.language_code,
                    encoding=riva.client.AudioEncoding.LINEAR_PCM,
                    sample_rate_hz=self.sample_rate,
                    voice_name=""  # Let Riva use the default voice for the language
                )
                
                first_chunk = True
                for response in responses:
                    if response.audio:
                        # Record time to first audio chunk
                        if first_chunk:
                            tts_timer.stop()
                            METRICS.tts_latency.labels(language=self.language_code).observe(tts_timer.duration)
                            METRICS.tts_characters.labels(language=self.language_code).observe(text_length)
                            logger.debug(f"TTS latency: {tts_timer.duration:.3f}s for {text_length} chars")
                            first_chunk = False
                        
                        asyncio.run_coroutine_threadsafe(
                            result_queue.put(response.audio), loop
                        )
            except Exception as e:
                logger.error(f"Error in Riva TTS synthesis: {e}")
                METRICS.tts_errors.labels(error_type=type(e).__name__).inc()
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
                METRICS.tts_errors.labels(error_type=type(item).__name__).inc()
                raise item
            yield item

