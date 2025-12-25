import logging
import riva.client
from typing import AsyncGenerator
import asyncio
import queue

from metrics import METRICS, Timer

logger = logging.getLogger(__name__)

class ASRClient:
    def __init__(self, auth: riva.client.Auth, language_code: str = "en-US", sample_rate: int = 16000):
        self.auth = auth
        self.language_code = language_code
        self.sample_rate = sample_rate
        self.asr_service = riva.client.ASRService(self.auth)
        
        logger.info(f"Initializing ASR Client: Language={self.language_code}, SampleRate={self.sample_rate}")
        
        # Configuration for streaming recognition
        self.config = riva.client.StreamingRecognitionConfig(
            config=riva.client.RecognitionConfig(
                encoding=riva.client.AudioEncoding.LINEAR_PCM,
                language_code=self.language_code,
                max_alternatives=1,
                enable_automatic_punctuation=False,
                verbatim_transcripts=True,
                sample_rate_hertz=self.sample_rate, 
            ),
            interim_results=True,
        )

    async def transcribe_stream(self, audio_generator: AsyncGenerator[bytes, None]) -> AsyncGenerator[str, None]:
        """
        Consumes an audio generator and yields transcript results.
        Uses a thread-safe queue to bridge asyncio generator and Riva's blocking iterator.
        
        Metrics collected:
        - asr_latency: Time from first audio chunk to final transcript
        """
        # Create a queue to buffer audio chunks for the Riva client
        audio_queue = queue.Queue()
        
        # Flag to signal the end of the stream
        stream_closed = False
        
        # Timer for ASR latency (start on first audio, stop on final transcript)
        asr_timer = Timer()
        first_audio_received = False

        def audio_chunk_iterator():
            nonlocal first_audio_received
            while True:
                try:
                    chunk = audio_queue.get(timeout=1.0) # Wait for audio
                    if chunk is None: # Sentinel for end of stream
                        return
                    # Start timer on first audio chunk
                    if not first_audio_received:
                        asr_timer.start()
                        first_audio_received = True
                    yield chunk
                except queue.Empty:
                    if stream_closed:
                        return
                    continue

        async def fill_queue():
            nonlocal stream_closed
            try:
                async for chunk in audio_generator:
                    audio_queue.put(chunk)
            finally:
                stream_closed = True
                audio_queue.put(None)

        # Start filling the queue in the background
        fill_task = asyncio.create_task(fill_queue())

        try:
            # Riva client's streaming_recognize is a blocking call that accepts an iterator
            # We run it in a separate thread/executor to avoid blocking the async loop if needed,
            # but for simplicity, we'll iterate over the responses.
            # Ideally, we should wrap the blocking generator in an async wrapper.
            
            # NOTE: In a true async production setup, we would run this blocking call in an executor.
            # For this implementation, we will assume the Riva client call iterates quickly enough or use to_thread.
            
            responses = self.asr_service.streaming_response_generator(
                audio_chunks=audio_chunk_iterator(),
                streaming_config=self.config
            )

            # We iterate the blocking generator in a non-blocking way
            # This is a bit tricky with Riva's synchronous client.
            # A common pattern is to run the consumption in a separate thread and put results in an async queue.
            
            loop = asyncio.get_running_loop()
            result_queue = asyncio.Queue()

            def consume_riva_responses():
                try:
                    for response in responses:
                        if not response.results:
                            continue
                        for result in response.results:
                            # We only care about the first alternative
                            if not result.alternatives:
                                continue
                            transcript = result.alternatives[0].transcript
                            is_final = result.is_final
                            if transcript:
                                logger.debug(f"ASR Result: '{transcript}' (final={is_final})")
                                asyncio.run_coroutine_threadsafe(
                                    result_queue.put((transcript, is_final)), loop
                                )
                except Exception as e:
                    logger.error(f"Error in Riva consumption: {e}")
                    # Record error metric
                    METRICS.asr_errors.labels(error_type=type(e).__name__).inc()
                finally:
                    asyncio.run_coroutine_threadsafe(result_queue.put(None), loop)

            # Start the consumer in a background thread (don't await - run concurrently!)
            consumer_future = loop.run_in_executor(None, consume_riva_responses)

            # Yield results as they come from the background thread
            while True:
                item = await result_queue.get()
                if item is None:
                    break
                transcript, is_final = item
                
                # Record ASR latency on final transcript
                if is_final and first_audio_received:
                    asr_timer.stop()
                    METRICS.asr_latency.labels(language=self.language_code).observe(asr_timer.duration)
                    logger.debug(f"ASR latency: {asr_timer.duration:.3f}s")
                
                yield transcript, is_final
            
            # Wait for the consumer to finish cleanly
            await consumer_future

        except Exception as e:
            logger.error(f"Error during transcription: {e}")
            METRICS.asr_errors.labels(error_type=type(e).__name__).inc()
            raise e
        finally:
            # ensure background task is cleaned up
            fill_task.cancel()

