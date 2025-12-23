# Voice-to-Voice Hindi Workflow - Implementation Status

## Current Architecture & Thought Process
This project implements a scalable, low-latency Voice-to-Voice AI pipeline for Hindi, designed to run on Kubernetes.

### Core Philosophy
1.  **Central Orchestrator (Gateway)**: A single entry point (Gateway) manages the complexity. Clients don't talk to ASR/TTS directly. This allows us to handle state (interruption, turn-taking) on the server side.
2.  **Streaming First**: Everything is gRPC streams. We don't wait for full audio to start processing.
3.  **Strict Contracts**: We use Protobuf (`.proto`) to define exact data structures before writing code.
4.  **Modern Python**: We use `uv` for dependency management and `asyncio` for high-concurrency handling in the Gateway.

## Folder Structure Mapping

```text
voice-voice-workflow/
├── docs/                       # Documentation
│   └── architecture/           # Mermaid diagrams & visual designs
│       └── high_level_diagram.mermaid
├── helm/                       # Infrastructure as Code (Helm Charts)
│   └── voice-workflow/         # The main application chart
│       ├── Chart.yaml          # Chart metadata
│       ├── values.yaml         # Default configuration (image tags, replicas)
│       └── templates/          # K8s manifests (Deployments, Services, Ingress)
├── proto/                      # Interface Definitions (The Contract)
│   └── voice_workflow.proto    # gRPC service definition (Client <-> Gateway)
├── services/                   # Microservices Source Code
│   └── voice-gateway/          # The Orchestrator Service
│       ├── Dockerfile          # Container build definition
│       ├── pyproject.toml      # Python dependencies (managed by uv)
│       ├── uv.lock             # Exact dependency versions
│       ├── src/                # Application Source Code
│       │   ├── main.py         # Entry point & gRPC Server implementation
│       │   ├── voice_workflow_pb2.py       # Generated gRPC code (do not edit)
│       │   └── voice_workflow_pb2_grpc.py  # Generated gRPC stubs (do not edit)
│       └── tests/              # Test Scripts
│           └── test_client.py  # Standalone script to simulate a user client
└── PLAN.md                     # High-level project plan & checklist
```

## Setup Instructions for Future Context

### 1. Prerequisites
- **uv**: Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Protobuf Compiler**: Required if modifying `.proto` files.

### 2. Development Workflow
To work on the `voice-gateway`:
```bash
cd services/voice-gateway
uv sync                     # Install dependencies
uv run python src/main.py   # Run the server locally
```

### 3. Testing
To verify the gateway is responding:
```bash
# In a separate terminal
cd services/voice-gateway
uv run python tests/test_client.py
```

### 4. Code Generation
If `proto/voice_workflow.proto` is modified, regenerate the Python code:
```bash
# From services/voice-gateway directory
uv run python -m grpc_tools.protoc -I../../proto --python_out=./src --grpc_python_out=./src voice_workflow.proto
```

## Next Implementation Logic (Roadmap)
The current `main.py` is a skeleton. The next immediate tasks for the LLM are:
1.  **Connect ASR**: Use `nvidia-riva-client` to forward audio chunks from `StreamAudio` to a Riva server.
2.  **Connect LLM**: Take the final transcript from ASR and send it to an LLM (e.g., via OpenAI-compatible API or local NIM).
3.  **Connect TTS**: Take the LLM text stream and send it to Riva TTS, then stream audio back to the user.

