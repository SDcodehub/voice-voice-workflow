import unittest
from unittest.mock import MagicMock, patch
import asyncio
from src.clients.tts import TTSClient
import riva.client

class TestTTSClient(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        self.mock_auth = MagicMock(spec=riva.client.Auth)
        # Patch the SpeechSynthesisService
        with patch('riva.client.SpeechSynthesisService') as MockService:
            self.client = TTSClient(self.mock_auth)
            self.mock_service_instance = MockService.return_value
    
    async def test_synthesize_stream_flow(self):
        # Prepare mock responses from Riva
        mock_response1 = MagicMock()
        mock_response1.audio = b'\x01\x02'
        
        mock_response2 = MagicMock()
        mock_response2.audio = b'\x03\x04'

        # The service returns a synchronous generator
        def mock_generator(*args, **kwargs):
            yield mock_response1
            yield mock_response2

        self.mock_service_instance.synthesize_online.side_effect = mock_generator

        # Run the method
        audio_chunks = []
        async for chunk in self.client.synthesize_stream("Namaste World"):
            audio_chunks.append(chunk)
            
        # Verify
        self.assertEqual(len(audio_chunks), 2)
        self.assertEqual(audio_chunks[0], b'\x01\x02')
        self.assertEqual(audio_chunks[1], b'\x03\x04')
        
        # Verify arguments
        self.mock_service_instance.synthesize_online.assert_called_once()
        call_kwargs = self.mock_service_instance.synthesize_online.call_args.kwargs
        self.assertEqual(call_kwargs['text'], "Namaste World")
        self.assertEqual(call_kwargs['language_code'], "hi-IN")

if __name__ == '__main__':
    unittest.main()

