import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
import grpc
from src.main import VoiceGatewayServicer
import voice_workflow_pb2

class TestVoiceGatewayServicer(unittest.IsolatedAsyncioTestCase):
    
    async def asyncSetUp(self):
        # Patch the clients
        self.patcher_asr = patch('src.main.ASRClient')
        self.patcher_llm = patch('src.main.LLMClient')
        self.patcher_tts = patch('src.main.TTSClient')
        self.patcher_auth = patch('src.main.riva.client.Auth')
        
        self.MockASR = self.patcher_asr.start()
        self.MockLLM = self.patcher_llm.start()
        self.MockTTS = self.patcher_tts.start()
        self.MockAuth = self.patcher_auth.start()

        self.servicer = VoiceGatewayServicer()
        
        # Setup Mocks
        self.mock_asr = self.MockASR.return_value
        self.mock_llm = self.MockLLM.return_value
        self.mock_tts = self.MockTTS.return_value

    async def asyncTearDown(self):
        self.patcher_asr.stop()
        self.patcher_llm.stop()
        self.patcher_tts.stop()
        self.patcher_auth.stop()

    async def test_stream_audio_flow(self):
        """
        Test the full pipeline: Audio -> ASR -> LLM -> TTS -> Audio
        """
        
        # 1. Mock ASR Stream
        # It yields (transcript, is_final)
        async def mock_asr_stream(audio_gen):
            # Consume the audio generator to prevent pending task errors
            async for _ in audio_gen:
                pass
            yield ("Hello", True)
        self.mock_asr.transcribe_stream.side_effect = mock_asr_stream

        # 2. Mock LLM Stream
        # It yields text chunks
        async def mock_llm_stream(text):
            yield "Namaste"
            yield "."
        self.mock_llm.generate_response.side_effect = mock_llm_stream

        # 3. Mock TTS Stream
        # It yields audio bytes
        async def mock_tts_stream(text):
            yield b'\xDE\xAD'
            yield b'\xBE\xEF'
        self.mock_tts.synthesize_stream.side_effect = mock_tts_stream

        # 4. Create Input Stream (Client requests)
        async def request_iterator():
            # Send Config
            yield voice_workflow_pb2.ClientMessage(
                config=voice_workflow_pb2.VoiceConfig(language_code="hi-IN")
            )
            # Send Audio
            yield voice_workflow_pb2.ClientMessage(
                audio_chunk=b'\x01\x02\x03'
            )
            await asyncio.sleep(0.1) 
        
        # 5. Run the Servicer Method
        responses = []
        async for response in self.servicer.StreamAudio(request_iterator(), None):
            responses.append(response)

        # 6. Verify Results
        
        # Check if we got LISTENING event at start
        self.assertEqual(responses[0].event.type, voice_workflow_pb2.LISTENING)
        
        # Check for Transcript
        transcript_msgs = [r for r in responses if r.transcript_chunk]
        self.assertTrue(len(transcript_msgs) > 0)
        self.assertEqual(transcript_msgs[0].transcript_chunk, "Hello")

        # Check for LLM Response
        llm_msgs = [r for r in responses if r.llm_response_chunk]
        self.assertTrue(len(llm_msgs) > 0)
        full_text = "".join([r.llm_response_chunk for r in llm_msgs])
        self.assertEqual(full_text, "Namaste.")

        # Check for Audio Response (TTS)
        audio_msgs = [r for r in responses if r.audio_chunk]
        self.assertTrue(len(audio_msgs) > 0)
        self.assertEqual(audio_msgs[0].audio_chunk, b'\xDE\xAD')
        
        # Verify calls
        self.mock_asr.transcribe_stream.assert_called()
        self.mock_llm.generate_response.assert_called_with("Hello")
        self.mock_tts.synthesize_stream.assert_called_with("Namaste.")

if __name__ == '__main__':
    unittest.main()

