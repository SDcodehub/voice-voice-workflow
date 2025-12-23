import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from src.clients.asr import ASRClient
import riva.client

class TestASRClient(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        self.mock_auth = MagicMock(spec=riva.client.Auth)
        # Patch the ASRService within the module context or class init
        with patch('riva.client.ASRService') as MockService:
            self.client = ASRClient(self.mock_auth)
            self.mock_service_instance = MockService.return_value
    
    async def test_transcribe_stream_flow(self):
        # Mock the streaming_response_generator
        # It needs to return an iterator of mock responses
        
        mock_response = MagicMock()
        mock_result = MagicMock()
        mock_result.is_final = True
        mock_alternative = MagicMock()
        mock_alternative.transcript = "नमस्ते"
        mock_result.alternatives = [mock_alternative]
        mock_response.results = [mock_result]
        
        # Configure the mock service to return our mock response when iterated
        # interacting with the threaded logic requires careful mocking.
        # simpler approach: we mock the ASRService.streaming_response_generator
        # to simply return a list (iterator)
        
        self.client.asr_service.streaming_response_generator = MagicMock(return_value=[mock_response])
        
        # Create a dummy audio generator
        async def mock_audio_gen():
            yield b'\x00' * 160
            yield b'\x00' * 160
        
        # Collect results
        results = []
        async for transcript, is_final in self.client.transcribe_stream(mock_audio_gen()):
            results.append((transcript, is_final))
            
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0][0], "नमस्ते")
        self.assertTrue(results[0][1])

if __name__ == '__main__':
    unittest.main()

