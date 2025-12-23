import asyncio
import logging
import grpc
from concurrent import futures

# Generated proto imports
import voice_workflow_pb2
import voice_workflow_pb2_grpc

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoiceGatewayServicer(voice_workflow_pb2_grpc.VoiceGatewayServicer):
    """Implementation of the Voice Gateway Service."""
    
    async def StreamAudio(self, request_iterator, context):
        """
        Bidirectional streaming RPC.
        Receives audio/config from client.
        Sends ASR/LLM/TTS results back to client.
        """
        async for request in request_iterator:
            # TODO: logic to route audio to ASR, text to LLM, etc.
            if request.HasField('config'):
                logger.info(f"Received config: {request.config}")
                yield voice_workflow_pb2.ServerMessage(
                    event=voice_workflow_pb2.ServerEvent(
                        type=voice_workflow_pb2.LISTENING,
                        message="Session started"
                    )
                )
            elif request.HasField('audio_chunk'):
                # logger.debug(f"Received audio chunk of size {len(request.audio_chunk)}")
                # For now, just acknowledge receiving audio
                pass
            elif request.HasField('text_input'):
                logger.info(f"Received text: {request.text_input}")
                
            
        # End of stream
        yield voice_workflow_pb2.ServerMessage(
            event=voice_workflow_pb2.ServerEvent(
                type=voice_workflow_pb2.END_OF_TURN
            )
        )

async def serve():
    port = '50051'
    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))
    voice_workflow_pb2_grpc.add_VoiceGatewayServicer_to_server(VoiceGatewayServicer(), server)
    
    server.add_insecure_port('[::]:' + port)
    logger.info(f"Starting Voice Gateway on port {port}")
    await server.start()
    await server.wait_for_termination()

if __name__ == '__main__':
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass
