# Development Guide

Local development setup for the Voice Gateway service.

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) package manager
- Access to Riva and NIM services (local or remote)

## Setup

### 1. Clone and Install Dependencies

```bash
cd services/voice-gateway
uv sync
```

### 2. Generate Proto Files

```bash
uv run python -m grpc_tools.protoc \
  -I../../proto \
  --python_out=src \
  --grpc_python_out=src \
  ../../proto/voice_workflow.proto
```

### 3. Configure Environment

```bash
# Point to your Riva/NIM services
export RIVA_URI="localhost:50051"           # Or remote Riva
export LLM_SERVICE_URL="http://localhost:8000/v1"  # Or remote NIM

# Optional configuration
export LOG_LEVEL="DEBUG"
export SHUTDOWN_GRACE_PERIOD="5"
```

### 4. Run Locally

```bash
uv run python src/main.py
```

## Project Structure

```
services/voice-gateway/
├── Dockerfile          # Multi-stage, security-hardened
├── pyproject.toml      # Dependencies (uv)
├── uv.lock             # Locked dependencies
├── src/
│   ├── main.py         # gRPC server, graceful shutdown
│   ├── clients/
│   │   ├── asr.py      # Riva ASR client
│   │   ├── llm.py      # NIM LLM client
│   │   └── tts.py      # Riva TTS client
│   ├── voice_workflow_pb2.py      # Generated proto
│   └── voice_workflow_pb2_grpc.py # Generated proto
└── tests/
    ├── test_mic_client.py    # Interactive test
    └── test_*.py             # Other tests
```

## Code Patterns

### Async Streaming

All clients use async generators for streaming:

```python
async def transcribe_stream(self, audio_gen) -> AsyncGenerator[str, None]:
    async for chunk in audio_gen:
        # Process and yield results
        yield transcript, is_final
```

### Configuration from Environment

```python
# Read from ConfigMap env vars
self.temperature = float(os.getenv("LLM_TEMPERATURE", "0.5"))
self.system_prompt = os.getenv("LLM_SYSTEM_PROMPT", None)
```

### Graceful Shutdown

```python
async def graceful_shutdown(sig_name: str):
    await server.stop(grace=SHUTDOWN_GRACE_PERIOD)
    shutdown_event.set()

for sig in (signal.SIGTERM, signal.SIGINT):
    loop.add_signal_handler(sig, lambda: asyncio.create_task(graceful_shutdown(...)))
```

## Testing

### Unit Tests

```bash
cd services/voice-gateway
uv run pytest tests/
```

### Interactive Test (Microphone)

```bash
# Requires port-forward to gateway
uv run python tests/test_mic_client.py
```

## Building

### Local Build

```bash
./scripts/build_gateway.sh
```

### Push to Registry

```bash
export REGISTRY=docker.io/yourname
./scripts/build_gateway.sh
```

## Debugging

### Enable Debug Logs

```bash
export LOG_LEVEL="DEBUG"
uv run python src/main.py
```

### Test Individual Components

```bash
# Test ASR
uv run python tests/test_asr.py

# Test LLM
uv run python tests/test_llm.py

# Test TTS
uv run python tests/test_tts.py
```

