import asyncio
import logging
import grpc
import sys
import os

# Add src to path to import generated protos
sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

import voice_workflow_pb2
import voice_workflow_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run():
    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = voice_workflow_pb2_grpc.VoiceGatewayStub(channel)
        
        # Create a generator to stream requests
        async def request_generator():
            # 1. Send Config
            logger.info("Sending Config...")
            yield voice_workflow_pb2.ClientMessage(
                config=voice_workflow_pb2.VoiceConfig(
                    language_code="en-US",
                    session_id="test-session-123",
                    sample_rate=16000
                )
            )
            
            # 2. Send dummy audio chunks (simulated)
            for i in range(3):
                await asyncio.sleep(0.5)
                logger.info(f"Sending audio chunk {i+1}")
                yield voice_workflow_pb2.ClientMessage(
                    audio_chunk=b'\0' * 1024 # Dummy 1KB of silence
                )
        
        # Call the streaming RPC
        logger.info("Starting stream...")
        async for response in stub.StreamAudio(request_generator()):
            if response.HasField('event'):
                logger.info(f"Received Event: {response.event.type} - {response.event.message}")
            elif response.HasField('transcript_chunk'):
                logger.info(f"Transcript: {response.transcript_chunk}")

if __name__ == '__main__':
    asyncio.run(run())


