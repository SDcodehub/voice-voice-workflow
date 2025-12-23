import asyncio
import logging
import grpc
import struct
import math
import sys

# Import generated protos
import voice_workflow_pb2
import voice_workflow_pb2_grpc

# Configuration
CHUNK_SIZE = 4096
RATE = 16000
FREQUENCY = 440.0  # Hz (A4)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def generate_sine_wave(duration_seconds):
    """Generates a sine wave audio chunk."""
    num_samples = int(duration_seconds * RATE)
    audio = []
    for x in range(num_samples):
        value = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * FREQUENCY * x / RATE))
        audio.append(struct.pack('<h', value))
    return b''.join(audio)

async def run():
    logger.info(f"🎵 Generating Sine Wave Audio Test...")

    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = voice_workflow_pb2_grpc.VoiceGatewayStub(channel)

        async def request_generator():
            # 1. Send Config
            logger.info("Sending Config...")
            yield voice_workflow_pb2.ClientMessage(
                config=voice_workflow_pb2.VoiceConfig(
                    language_code="en-US", 
                    session_id="mac-client-sine",
                    sample_rate=RATE
                )
            )
            
            # 2. Send Sine Wave Audio (3 seconds)
            audio_data = generate_sine_wave(3.0)
            
            # Split into chunks
            for i in range(0, len(audio_data), CHUNK_SIZE):
                chunk = audio_data[i:i+CHUNK_SIZE]
                # print(".", end="", flush=True)
                yield voice_workflow_pb2.ClientMessage(audio_chunk=chunk)
                await asyncio.sleep(0.01) # Simulate real-time streaming

            logger.info("\nFinished sending audio.")

        try:
            async for response in stub.StreamAudio(request_generator()):
                if response.HasField('transcript_chunk'):
                    print(f"\r🗣️  ASR: {response.transcript_chunk}", end='', flush=True)
                elif response.HasField('event'):
                    logger.info(f"Event: {response.event.type}")

        except Exception as e:
            logger.error(f"Error: {e}")

if __name__ == '__main__':
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass

