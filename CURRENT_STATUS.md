# Voice-to-Voice Hindi Workflow - Implementation Status

## Project Overview
This project implements a scalable, low-latency Voice-to-Voice AI pipeline for Hindi using NVIDIA Riva and NIMs on Kubernetes. It follows a "Central Gateway" architecture with gRPC streaming.

### Core Philosophy
1.  **Central Orchestrator (Gateway)**: A single entry point (Gateway) manages the complexity. Clients don't talk to ASR/TTS directly. This allows us to handle state (interruption, turn-taking) on the server side.
2.  **Streaming First**: Everything is gRPC streams. We don't wait for full audio to start processing.
3.  **Strict Contracts**: We use Protobuf (`.proto`) to define exact data structures before writing code.
4.  **Modern Python**: We use `uv` for dependency management and `asyncio` for high-concurrency handling in the Gateway.

## Current Progress (Phase 2: Core Components)
- [x] **Architecture**: Defined in `docs/architecture` and `proto/`.
- [x] **Gateway Skeleton**: Basic gRPC server set up in `services/voice-gateway`.
- [x] **ASR Integration**: Implemented `ASRClient` in `src/clients/asr.py`.
    - Verified with unit tests (`tests/test_asr.py`).
- [x] **LLM Integration**: Implemented `LLMClient` in `src/clients/llm.py`.
    - Verified with unit tests (`tests/test_llm.py`).
- [x] **TTS Integration**: Implemented `TTSClient` in `src/clients/tts.py`.
    - Verified with unit tests (`tests/test_tts.py`).
- [x] **End-to-End Logic**: Wired up ASR -> LLM -> TTS pipeline in `src/main.py`.
    - Verified with integration tests (`tests/test_gateway.py`).

## Folder Structure Mapping

```text
voice-voice-workflow/
├── CURRENT_STATUS.md           # <-- YOU ARE HERE
├── docs/                       # Documentation
│   └── architecture/           # Mermaid diagrams & visual designs
├── helm/                       # Infrastructure as Code (Helm Charts)
│   └── voice-workflow/         # The main application chart
├── proto/                      # Interface Definitions (The Contract)
│   └── voice_workflow.proto    # gRPC service definition
├── services/                   # Microservices Source Code
│   └── voice-gateway/          # The Orchestrator Service
│       ├── Dockerfile          # Container build definition
│       ├── pyproject.toml      # Dependencies
│       ├── uv.lock             # Exact dependency versions
│       ├── src/                # Application Source Code
│       │   ├── main.py         # Entry point & gRPC Server implementation
│       │   ├── clients/        # External Service Wrappers
│       │   │   ├── asr.py      # Riva ASR Client
│       │   │   ├── llm.py      # NIM LLM Client
│       │   │   └── tts.py      # Riva TTS Client
│       │   ├── voice_workflow_pb2.py       # Generated gRPC code
│       │   └── voice_workflow_pb2_grpc.py  # Generated gRPC stubs
│       └── tests/              # Test Scripts
│           ├── test_client.py  # Standalone script to simulate a user client
│           ├── test_gateway.py # Integration test for the full pipeline
│           ├── test_asr.py     # Unit test for ASR
│           ├── test_llm.py     # Unit test for LLM
│           └── test_tts.py     # Unit test for TTS
└── PLAN.md                     # High-level project plan & checklist
```

## Setup Instructions

### 1. Prerequisites
- **uv**: Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)

### 2. Development Workflow
To work on the `voice-gateway`:
```bash
cd services/voice-gateway
uv sync                     # Install dependencies
uv run python src/main.py   # Run the server locally
```

### 3. Testing
To verify components:
```bash
cd services/voice-gateway
export PYTHONPATH=$PYTHONPATH:./src:.

# Run all unit tests
uv run python -m unittest discover tests

# Run key integration test
uv run python -m unittest tests/test_gateway.py
```

## Next Immediate Steps (Phase 3: Deployment)
The project is ready for deployment. The code logic is complete and tested.
1.  **Containerize**: Build the Docker image for the gateway.
2.  **Helm Charts**: Complete the `helm/voice-workflow` chart.
    -   Add dependencies (Riva, Redis if needed).
    -   Create ConfigMaps for environment variables (`Riva URI`, `NIM URL`).
    -   Configure Ingress for gRPC.
3.  **Deploy**: Apply to the K8s cluster.
