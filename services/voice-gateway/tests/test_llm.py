import unittest
from unittest.mock import MagicMock, patch, AsyncMock
import asyncio
from src.clients.llm import LLMClient

class TestLLMClient(unittest.IsolatedAsyncioTestCase):
    
    def setUp(self):
        # We need to mock AsyncOpenAI to avoid making real network calls
        self.patcher = patch('src.clients.llm.AsyncOpenAI')
        self.MockAsyncOpenAI = self.patcher.start()
        self.mock_client_instance = self.MockAsyncOpenAI.return_value
        
        self.client = LLMClient(base_url="http://mock-nim:8000/v1")

    def tearDown(self):
        self.patcher.stop()

    async def test_generate_response_stream(self):
        # Prepare the mock stream data
        # The openai client returns an async iterator of chunks
        
        # Create mock chunks
        chunk1 = MagicMock()
        chunk1.choices = [MagicMock()]
        chunk1.choices[0].delta.content = "Namaste"
        
        chunk2 = MagicMock()
        chunk2.choices = [MagicMock()]
        chunk2.choices[0].delta.content = " World"
        
        chunk3 = MagicMock()
        chunk3.choices = [MagicMock()]
        chunk3.choices[0].delta.content = "" # Empty chunk at end

        # Mock the completions.create method to return an async generator
        async def mock_stream_generator():
            yield chunk1
            yield chunk2
            yield chunk3

        # create needs to be an awaitable that returns the generator
        async def mock_create(*args, **kwargs):
            return mock_stream_generator()

        self.mock_client_instance.chat.completions.create.side_effect = mock_create

        # Run the method
        response_text = ""
        async for chunk in self.client.generate_response("Hello", system_prompt="Speak Hindi"):
            response_text += chunk
        
        # Verify
        self.assertEqual(response_text, "Namaste World")
        
        # Verify arguments passed to client
        self.mock_client_instance.chat.completions.create.assert_called_once()
        call_kwargs = self.mock_client_instance.chat.completions.create.call_args.kwargs
        self.assertEqual(call_kwargs['model'], "meta/llama3-8b-instruct")
        self.assertEqual(call_kwargs['messages'][0]['role'], "system")
        self.assertEqual(call_kwargs['messages'][1]['content'], "Hello")

if __name__ == '__main__':
    unittest.main()

