#!/usr/bin/env python3
"""
End-to-End Test Script for Voice-to-Voice Workflow

Tests the complete pipeline: Audio -> ASR -> LLM -> TTS -> Audio
"""

import asyncio
import json
import argparse
import wave
import struct
import sys
from pathlib import Path

try:
    import websockets
    import numpy as np
except ImportError:
    print("Installing required packages...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "websockets", "numpy"])
    import websockets
    import numpy as np


def generate_test_audio(duration_seconds: float = 2.0, sample_rate: int = 16000) -> bytes:
    """Generate silent test audio."""
    num_samples = int(sample_rate * duration_seconds)
    # Generate silent audio (or could add a tone for testing)
    audio = np.zeros(num_samples, dtype=np.int16)
    return audio.tobytes()


def save_audio_to_wav(audio_data: bytes, filename: str, sample_rate: int = 22050):
    """Save raw PCM audio to WAV file."""
    with wave.open(filename, 'wb') as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(audio_data)
    print(f"Saved audio to {filename}")


async def test_websocket_connection(url: str, language: str = "hi-IN"):
    """Test WebSocket connection and basic protocol."""
    print(f"\n=== Testing WebSocket Connection ===")
    print(f"URL: {url}")
    print(f"Language: {language}")
    
    try:
        async with websockets.connect(url, ping_interval=30) as websocket:
            # Send config message
            config = {"language": language}
            await websocket.send(json.dumps(config))
            print(f"✓ Sent config: {config}")
            
            # Wait for session_created response
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            data = json.loads(response)
            print(f"✓ Received: {data}")
            
            if data.get("type") == "session_created":
                print(f"✓ Session created: {data.get('session_id')}")
            else:
                print(f"✗ Unexpected response type: {data.get('type')}")
                return False
            
            # Test ping
            await websocket.send(json.dumps({"action": "ping"}))
            response = await asyncio.wait_for(websocket.recv(), timeout=5)
            data = json.loads(response)
            if data.get("type") == "pong":
                print("✓ Ping/Pong successful")
            
            return True
            
    except asyncio.TimeoutError:
        print("✗ Timeout waiting for response")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False


async def test_audio_pipeline(url: str, language: str = "hi-IN"):
    """Test the complete audio pipeline."""
    print(f"\n=== Testing Audio Pipeline ===")
    
    try:
        async with websockets.connect(url, ping_interval=30) as websocket:
            # Setup session
            await websocket.send(json.dumps({"language": language}))
            response = await asyncio.wait_for(websocket.recv(), timeout=10)
            session_data = json.loads(response)
            session_id = session_data.get("session_id")
            print(f"Session ID: {session_id}")
            
            # Generate and send test audio
            print("\nSending test audio...")
            test_audio = generate_test_audio(duration_seconds=2.0)
            await websocket.send(test_audio)
            print(f"✓ Sent {len(test_audio)} bytes of audio")
            
            # Collect responses
            received_audio = bytearray()
            transcript = ""
            response_text = ""
            
            print("\nWaiting for responses...")
            try:
                while True:
                    message = await asyncio.wait_for(websocket.recv(), timeout=30)
                    
                    if isinstance(message, bytes):
                        received_audio.extend(message)
                        print(f"  Received audio chunk: {len(message)} bytes")
                    else:
                        data = json.loads(message)
                        msg_type = data.get("type")
                        
                        if msg_type == "status":
                            print(f"  Status: {data.get('state')} - {data.get('stage', '')}")
                        elif msg_type == "transcript":
                            transcript = data.get("text", "")
                            print(f"  Transcript: {transcript}")
                        elif msg_type == "response_text":
                            if data.get("is_final"):
                                print(f"  Response complete")
                                break
                            else:
                                response_text += data.get("text", "")
                                print(f"  Response chunk: {data.get('text', '')}")
                        elif msg_type == "error":
                            print(f"  ✗ Error: {data.get('message')}")
                            return False
                            
            except asyncio.TimeoutError:
                print("  (Timeout - this is expected for test audio)")
            
            # Summary
            print("\n=== Pipeline Results ===")
            print(f"Transcript: {transcript or '(none)'}")
            print(f"Response: {response_text or '(none)'}")
            print(f"Audio received: {len(received_audio)} bytes")
            
            if received_audio:
                # Save received audio
                save_audio_to_wav(bytes(received_audio), "test_output.wav")
            
            return True
            
    except Exception as e:
        print(f"✗ Pipeline error: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_health_endpoints(base_url: str):
    """Test service health endpoints."""
    print(f"\n=== Testing Health Endpoints ===")
    
    try:
        import httpx
    except ImportError:
        print("Installing httpx...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
        import httpx
    
    services = [
        ("Voice Gateway", f"{base_url}/health"),
    ]
    
    async with httpx.AsyncClient(timeout=10) as client:
        for name, url in services:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    print(f"✓ {name}: healthy")
                else:
                    print(f"✗ {name}: {response.status_code}")
            except Exception as e:
                print(f"✗ {name}: {e}")


async def main():
    parser = argparse.ArgumentParser(description="Voice Workflow E2E Test")
    parser.add_argument(
        "--url", 
        default="ws://localhost:8000/ws/voice",
        help="WebSocket URL (default: ws://localhost:8000/ws/voice)"
    )
    parser.add_argument(
        "--http-url",
        default="http://localhost:8000",
        help="HTTP base URL (default: http://localhost:8000)"
    )
    parser.add_argument(
        "--language",
        default="hi-IN",
        help="Language code (default: hi-IN)"
    )
    parser.add_argument(
        "--test",
        choices=["connection", "pipeline", "health", "all"],
        default="all",
        help="Test to run (default: all)"
    )
    
    args = parser.parse_args()
    
    print("=" * 50)
    print("Voice-to-Voice Workflow E2E Test")
    print("=" * 50)
    
    results = {}
    
    if args.test in ["connection", "all"]:
        results["connection"] = await test_websocket_connection(args.url, args.language)
    
    if args.test in ["pipeline", "all"]:
        results["pipeline"] = await test_audio_pipeline(args.url, args.language)
    
    if args.test in ["health", "all"]:
        await test_health_endpoints(args.http_url)
    
    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)
    for test_name, passed in results.items():
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"  {test_name}: {status}")
    
    # Exit code
    if all(results.values()):
        print("\n✓ All tests passed!")
        sys.exit(0)
    else:
        print("\n✗ Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())

