# Voice-to-Voice Hindi Workflow - Implementation Status

## Project Overview
This project implements a scalable, low-latency Voice-to-Voice AI pipeline for Hindi using NVIDIA Riva and NIMs on Kubernetes. It follows a "Central Gateway" architecture with gRPC streaming.

### Core Philosophy
1.  **Central Orchestrator (Gateway)**: A single entry point (Gateway) manages the complexity. Clients don't talk to ASR/TTS directly. This allows us to handle state (interruption, turn-taking) on the server side.
2.  **Streaming First**: Everything is gRPC streams. We don't wait for full audio to start processing.
3.  **Strict Contracts**: We use Protobuf (`.proto`) to define exact data structures before writing code.
4.  **Modern Python**: We use `uv` for dependency management and `asyncio` for high-concurrency handling in the Gateway.

## Current Progress (Phase 3: Kubernetes Deployment)
- [x] **Architecture**: Defined in `docs/architecture` and `proto/`.
- [x] **Gateway Skeleton**: Basic gRPC server set up in `services/voice-gateway`.
- [x] **ASR/TTS Integration**: Wired up in Gateway.
- [x] **Kubernetes Infrastructure**:
    - [x] **Storage**: `local-storage` PV/PVCs configured and bound on `node001`.
    - [x] **Secrets**: Automated secret creation (`ngc-api`, `modelpullsecret`, `riva-model-deploy-key`) via `deploy_riva.sh`.
    - [x] **Riva Deployment**: Riva Server deployed via Helm and verified.
        - **Status**: Running.
        - **Health Check**: `HTTP 200 OK` on `/v2/health/ready`.
    - [x] **LLM NIM**: NIM (Llama 3 8B) deployed and running.
- [x] **Gateway Deployment**:
    - [x] **Container**: Image built and pushed to `docker.io/sagdesai/voice-gateway`.
    - [x] **Helm**: Chart updated to connect to existing Riva and NIM services.
    - [x] **Deploy**: Gateway pod deployed (`voice-gateway` release).
    - [x] **E2E Test**: Verified connectivity and basic flow using internal test client.

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
To test with your microphone:
1.  **SSH Tunnel**: `ssh -L 50051:localhost:50051 sagdesai@10.41.88.111`
2.  **Setup Client**: Download `services/voice-gateway/tests/setup_mac_client.sh` and run it.
3.  **Run**: `uv run test_mic_client.py`

## Next Immediate Steps (Phase 4: Optimization)
1.  **Latency Tuning**: Measure E2E latency and optimize buffer sizes.
2.  **Ingress**: Expose the gRPC gateway to the outside world using an Ingress Controller (Traefik/Nginx) with HTTP/2 support.
3.  **Client**: Develop a web or CLI client to interact with the deployed gateway.
