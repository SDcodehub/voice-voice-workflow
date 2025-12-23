# Voice-to-Voice Workflow - Implementation Status

## Project Overview
This project implements a scalable, low-latency Voice-to-Voice AI pipeline using NVIDIA Riva and NIMs on Kubernetes. It follows a "Central Gateway" architecture with gRPC streaming.

### Core Philosophy
1.  **Central Orchestrator (Gateway)**: A single entry point (Gateway) manages the complexity. Clients don't talk to ASR/TTS directly. This allows us to handle state (interruption, turn-taking) on the server side.
2.  **Streaming First**: Everything is gRPC streams. We don't wait for full audio to start processing.
3.  **Strict Contracts**: We use Protobuf (`.proto`) to define exact data structures before writing code.
4.  **Modern Python**: We use `uv` for dependency management and `asyncio` for high-concurrency handling in the Gateway.

## Current Progress (Phase 3: Kubernetes Deployment) ✅ COMPLETE

- [x] **Architecture**: Defined in `docs/architecture` and `proto/`.
- [x] **Gateway Skeleton**: Basic gRPC server set up in `services/voice-gateway`.
- [x] **ASR/TTS Integration**: Wired up in Gateway.
- [x] **Kubernetes Infrastructure**:
    - [x] **Storage**: `local-storage` PV/PVCs configured and bound on `node001`.
    - [x] **Secrets**: Automated secret creation (`ngc-api`, `modelpullsecret`, `riva-model-deploy-key`) via `deploy_riva.sh`.
    - [x] **Riva Deployment**: Riva Server deployed via Helm and verified.
        - **ASR Model**: `parakeet-0.6b-en-US-asr-streaming-throughput`
        - **TTS Model**: `fastpitch_hifigan_ensemble-English-US`
        - **Health Check**: `HTTP 200 OK` on `/v2/health/ready`.
    - [x] **LLM NIM**: NIM (Llama 3.1 8B Instruct) deployed and running.
        - **Model**: `meta/llama-3.1-8b-instruct`
- [x] **Gateway Deployment**:
    - [x] **Container**: Image built and pushed to `docker.io/sagdesai/voice-gateway`.
    - [x] **Helm**: Chart updated to connect to existing Riva and NIM services.
    - [x] **Deploy**: Gateway pod deployed (`voice-gateway` release).
    - [x] **E2E Test**: ✅ **FULLY VERIFIED** - Voice-to-Voice working from Mac client!

### E2E Test Results (2025-12-23)
- **ASR**: Streaming transcription working (en-US, 16kHz)
- **LLM**: Llama 3.1 8B responding with streaming text
- **TTS**: Audio synthesis and playback working on Mac speakers
- **Client**: Mac microphone → Server → Mac speakers pipeline complete

## Folder Structure Mapping

```text
voice-voice-workflow/
├── CURRENT_STATUS.md           # <-- YOU ARE HERE
├── docs/                       # Documentation
│   └── architecture/           # Mermaid diagrams & visual designs
├── helm/                       # Infrastructure as Code (Helm Charts)
│   ├── voice-workflow/         # The main application chart
│   └── riva-api/               # Local Riva Helm Chart
├── k8s/
│   └── infra/                  # Infrastructure manifests (PVCs, NIMs)
├── proto/                      # Interface Definitions (The Contract)
│   └── voice_workflow.proto    # gRPC service definition
├── scripts/
│   ├── deploy_infra.sh         # Script to deploy base infra
│   ├── deploy_riva.sh          # Script to deploy Riva (with secrets)
│   ├── build_gateway.sh        # Build & Push Gateway Image
│   └── deploy_gateway.sh       # Deploy Gateway using Helm
├── services/                   # Microservices Source Code
│   └── voice-gateway/          # The Orchestrator Service
│       ├── Dockerfile          # Container build definition
│       ├── src/                # Application Source Code
│       └── tests/              # Test Scripts
│           └── setup_mac_client.sh # Easy setup for local Mac client
└── PLAN.md                     # High-level project plan & checklist
```

## Setup Instructions

### 1. Prerequisites
- **uv**: Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Kubernetes**: Cluster with NVIDIA GPU support.
- **NGC API Key**: Exported as `NGC_API_KEY`.

### 2. Development Workflow
To work on the `voice-gateway`:
```bash
cd services/voice-gateway
uv sync                     # Install dependencies
uv run python src/main.py   # Run the server locally
```

### 3. Deployment
```bash
# 1. Deploy Infrastructure (NIM, PVCs)
./scripts/deploy_infra.sh

# 2. Deploy Riva (ASR/TTS)
export NGC_API_KEY=...
./scripts/deploy_riva.sh

# 3. Deploy Gateway
./scripts/build_gateway.sh
./scripts/deploy_gateway.sh
```

### 4. Client Testing (Mac/Local)

**On the Server** (headnode):
```bash
# Start port-forward (bind to 0.0.0.0 for SSH tunnel access)
kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0
```

**On your Mac**:
```bash
# 1. SSH Tunnel to the server
ssh -L 50051:localhost:50051 sagdesai@10.41.88.111

# 2. In a new terminal, set up the client
mkdir -p voice-client && cd voice-client

# Copy required files from server
scp sagdesai@10.41.88.111:~/voice-voice-workflow/proto/voice_workflow.proto .
scp sagdesai@10.41.88.111:~/voice-voice-workflow/services/voice-gateway/tests/test_mic_client.py .

# Initialize uv project and install dependencies
uv init --app --no-workspace --name voice-client .
uv add grpcio grpcio-tools pyaudio

# Generate proto code
uv run python -m grpc_tools.protoc -I. --python_out=. --grpc_python_out=. voice_workflow.proto

# 3. Run the client
uv run test_mic_client.py
```

**Note**: If `pyaudio` fails to install, run: `brew install portaudio`

## Technical Notes

### Key Configuration Values
| Component | Setting | Value |
|-----------|---------|-------|
| ASR | Language | `en-US` |
| ASR | Sample Rate | `16000` Hz |
| LLM | Model | `meta/llama-3.1-8b-instruct` |
| TTS | Voice | Default (empty string) |
| TTS | Sample Rate | `16000` Hz |

### Fixes Applied (2025-12-23)
1. **ASR Async Bug**: Fixed blocking `await` in executor that prevented streaming results
2. **LLM Model Name**: Changed from `meta/llama3-8b-instruct` to `meta/llama-3.1-8b-instruct`
3. **TTS Voice Name**: Changed from `en-US-Standard-A` to empty string (use default)
4. **Port Forwarding**: Added `--address 0.0.0.0` for SSH tunnel access

## Next Immediate Steps (Phase 4: Optimization)
1.  **Latency Tuning**: Measure E2E latency and optimize buffer sizes.
2.  **Ingress**: Expose the gRPC gateway to the outside world using an Ingress Controller (Traefik/Nginx) with HTTP/2 support.
3.  **Client**: Develop a web or CLI client to interact with the deployed gateway.
4.  **Multi-language**: Add Hindi ASR/TTS models for Hindi voice workflow.

## setup on mac instructions
Quick Reference for Tomorrow
On Server (headnode):
kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0
On Mac (Terminal 1 - SSH tunnel):
ssh -L 50051:localhost:50051 sagdesai@10.41.88.111
On Mac (Terminal 2 - run client):
cd ~/Desktop/voice-clientuv run test_mic_client.py

