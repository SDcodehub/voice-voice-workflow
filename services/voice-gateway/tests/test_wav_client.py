import asyncio
import logging
import grpc
import wave
import sys

# Import generated protos
import voice_workflow_pb2
import voice_workflow_pb2_grpc

CHUNK_SIZE = 4096

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run():
    filename = "test.wav"
    try:
        wf = wave.open(filename, 'rb')
    except FileNotFoundError:
        logger.error(f"File '{filename}' not found. Please download a sample wav file.")
        return

    logger.info(f"📂 Playing {filename}...")

    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = voice_workflow_pb2_grpc.VoiceGatewayStub(channel)

        async def request_generator():
            # 1. Send Config
            logger.info("Sending Config...")
            yield voice_workflow_pb2.ClientMessage(
                config=voice_workflow_pb2.VoiceConfig(
                    language_code="en-US", 
                    session_id="mac-client-wav",
                    sample_rate=wf.getframerate() # Use actual sample rate from file
                )
            )
            
            # 2. Stream Audio
            data = wf.readframes(CHUNK_SIZE)
            while len(data) > 0:
                yield voice_workflow_pb2.ClientMessage(audio_chunk=data)
                data = wf.readframes(CHUNK_SIZE)
                await asyncio.sleep(0.01) # Simulate real-time streaming

            logger.info("\nFinished sending audio.")

        try:
            async for response in stub.StreamAudio(request_generator()):
                if response.HasField('transcript_chunk'):
                    print(f"\r🗣️  ASR: {response.transcript_chunk}", end='', flush=True)
                
                elif response.HasField('llm_response_chunk'):
                    print(f"🤖 LLM: {response.llm_response_chunk}", end='', flush=True)

        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            wf.close()

if __name__ == '__main__':
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass

