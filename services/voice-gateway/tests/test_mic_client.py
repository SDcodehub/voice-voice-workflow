import asyncio
import logging
import grpc
import pyaudio
import sys

# Import generated protos
import voice_workflow_pb2
import voice_workflow_pb2_grpc

# Configuration
CHUNK_SIZE = 4096 # Larger chunk size for network stability
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_audio_input_stream():
    p = pyaudio.PyAudio()
    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE,
                        input=True,
                        frames_per_buffer=CHUNK_SIZE)
        return p, stream
    except Exception as e:
        logger.error(f"Failed to open input stream: {e}")
        return None, None

def get_audio_output_stream():
    p = pyaudio.PyAudio()
    try:
        stream = p.open(format=FORMAT,
                        channels=CHANNELS,
                        rate=RATE, # 16k output to match input for simplicity, though TTS might be 22k/44k
                        output=True)
        return p, stream
    except Exception as e:
        logger.error(f"Failed to open output stream: {e}")
        return None, None

async def run():
    p_in, input_stream = get_audio_input_stream()
    p_out, output_stream = get_audio_output_stream()
    
    if not input_stream:
        logger.error("Could not initialize microphone. Check permissions!")
        return

    logger.info(f"🎤 Recording... (Press Ctrl+C to stop)")

    async with grpc.aio.insecure_channel('localhost:50051') as channel:
        stub = voice_workflow_pb2_grpc.VoiceGatewayStub(channel)

        async def request_generator():
            # 1. Send Config
            logger.info("Sending Config...")
            yield voice_workflow_pb2.ClientMessage(
                config=voice_workflow_pb2.VoiceConfig(
                    language_code="en-US", 
                    session_id="mac-client-debug",
                    sample_rate=RATE
                )
            )
            
            # 2. Stream Audio (Blocking Read in Executor)
            loop = asyncio.get_event_loop()
            while True:
                try:
                    # Read audio in a non-blocking way for asyncio
                    data = await loop.run_in_executor(None, input_stream.read, CHUNK_SIZE, False)
                    if not data:
                        break
                    
                    # Print dot to show capture is working
                    # print(".", end="", flush=True) 
                    
                    yield voice_workflow_pb2.ClientMessage(audio_chunk=data)
                except IOError as e:
                    logger.warning(f"Audio overflow: {e}")
                    continue

        try:
            async for response in stub.StreamAudio(request_generator()):
                if response.HasField('transcript_chunk'):
                    transcript = response.transcript_chunk
                    print(f"\r🗣️  ASR: {transcript}", end='', flush=True)
                    if not transcript.endswith('...'): # Final
                         print()
                
                elif response.HasField('llm_response_chunk'):
                    print(f"🤖 LLM: {response.llm_response_chunk}", end='', flush=True)
                
                elif response.HasField('audio_chunk'):
                    if output_stream:
                        output_stream.write(response.audio_chunk)
                
                elif response.HasField('event'):
                    # logger.info(f"Event: {response.event.type}")
                    pass

        except KeyboardInterrupt:
            pass
        except Exception as e:
            logger.error(f"Error: {e}")
        finally:
            if input_stream:
                input_stream.stop_stream()
                input_stream.close()
            if output_stream:
                output_stream.stop_stream()
                output_stream.close()
            if p_in: p_in.terminate()
            if p_out: p_out.terminate()

if __name__ == '__main__':
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
