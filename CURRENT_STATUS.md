# Voice-to-Voice Workflow - Implementation Status

## Project Overview
This project implements a scalable, low-latency Voice-to-Voice AI pipeline using NVIDIA Riva and NIMs on Kubernetes. It follows a "Central Gateway" architecture with gRPC streaming.

### Core Philosophy
1.  **Central Orchestrator (Gateway)**: A single entry point (Gateway) manages the complexity. Clients don't talk to ASR/TTS directly. This allows us to handle state (interruption, turn-taking) on the server side.
2.  **Streaming First**: Everything is gRPC streams. We don't wait for full audio to start processing.
3.  **Strict Contracts**: We use Protobuf (`.proto`) to define exact data structures before writing code.
4.  **Modern Python**: We use `uv` for dependency management and `asyncio` for high-concurrency handling in the Gateway.

---

## Current Progress

### Phase 3: Kubernetes Deployment ✅ COMPLETE

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

### Phase 3.5: Production Hardening ✅ COMPLETE (2025-12-24)

Implemented Kubernetes best practices for production readiness:

- [x] **Resource Management**
    - [x] CPU/Memory requests and limits configured
    - [x] Based on observed usage: ~1m CPU, ~56Mi memory at idle
    - [x] Requests: `50m` CPU, `128Mi` memory
    - [x] Limits: `500m` CPU, `512Mi` memory

- [x] **Health Probes**
    - [x] **Liveness Probe**: TCP socket check on gRPC port (restarts unhealthy pods)
    - [x] **Readiness Probe**: TCP socket check on gRPC port (removes from service if not ready)
    - [x] Configuration: `initialDelaySeconds: 15`, `periodSeconds: 30`

- [x] **ConfigMap for Runtime Configuration**
    - [x] Tunable parameters without container rebuild
    - [x] ASR: language, sample rate
    - [x] LLM: model, temperature, max tokens, system prompt
    - [x] TTS: voice, sample rate
    - [x] Usage: Edit `values.yaml` → `./scripts/deploy_gateway.sh`

- [x] **Pod Disruption Budget (PDB)**
    - [x] Protects against voluntary disruptions (node drains, cluster upgrades)
    - [x] Configured with `minAvailable: 1`
    - [x] Tested: Drain blocked with "Cannot evict pod as it would violate the pod's disruption budget"

---

## Helm Chart Features

### Generated Kubernetes Resources

| Resource | Name | Purpose |
|----------|------|---------|
| Deployment | `voice-gateway-gateway` | Gateway pod specification |
| Service | `voice-gateway-gateway` | ClusterIP service for gRPC |
| ConfigMap | `voice-gateway-config` | Runtime configuration |
| PDB | `voice-gateway-gateway-pdb` | Disruption protection |

### Configuration Hierarchy

```
values.yaml
├── config.*           → ConfigMap (runtime tunable)
│   ├── asr.*          → ASR settings
│   ├── llm.*          → LLM settings (temperature, system prompt)
│   └── tts.*          → TTS settings
├── gateway.*          → Deployment settings
│   ├── resources.*    → CPU/Memory limits
│   ├── pdb.*          → Pod Disruption Budget
│   └── env.*          → Service discovery
└── riva.*/nim.*       → External dependencies (disabled, deployed separately)
```

---

## E2E Test Results

### Initial Test (2025-12-23)
- **ASR**: Streaming transcription working (en-US, 16kHz)
- **LLM**: Llama 3.1 8B responding with streaming text
- **TTS**: Audio synthesis and playback working on Mac speakers
- **Client**: Mac microphone → Server → Mac speakers pipeline complete

### Production Hardening Test (2025-12-24)
- **Resource Limits**: Verified pod running within limits
- **Health Probes**: Pod marked Ready after probes pass
- **ConfigMap**: LLM temperature and system prompt applied correctly
- **PDB**: Node drain blocked as expected

---

## Folder Structure Mapping

```text
voice-voice-workflow/
├── CURRENT_STATUS.md           # <-- YOU ARE HERE
├── PLAN.md                     # High-level project plan & checklist
├── docs/                       # Documentation
│   └── architecture/           # Mermaid diagrams & visual designs
├── helm/                       # Infrastructure as Code (Helm Charts)
│   ├── voice-workflow/         # The main application chart
│   │   ├── Chart.yaml          # Chart metadata
│   │   ├── values.yaml         # Configuration values (WELL DOCUMENTED)
│   │   └── templates/
│   │       ├── deployment-gateway.yaml  # Gateway deployment
│   │       ├── service.yaml             # ClusterIP service
│   │       ├── configmap.yaml           # Runtime config
│   │       └── pdb.yaml                 # Pod Disruption Budget
│   └── riva-api/               # Local Riva Helm Chart
├── k8s/
│   └── infra/                  # Infrastructure manifests
│       ├── 00-namespace-pvc.yaml  # Namespace, PV, PVC
│       ├── nim-llm.yaml           # NIM LLM deployment
│       └── riva-values.yaml       # Riva Helm values
├── proto/                      # Interface Definitions (The Contract)
│   └── voice_workflow.proto    # gRPC service definition
├── scripts/
│   ├── deploy_infra.sh         # Deploy base infra (namespace, NIM)
│   ├── deploy_riva.sh          # Deploy Riva (with secrets)
│   ├── build_gateway.sh        # Build & push Gateway image
│   └── deploy_gateway.sh       # Deploy Gateway using Helm
└── services/                   # Microservices Source Code
    └── voice-gateway/          # The Orchestrator Service
        ├── Dockerfile          # Container build definition
        ├── pyproject.toml      # Python dependencies (uv)
        ├── src/
        │   ├── main.py         # gRPC server entry point
        │   └── clients/
        │       ├── asr.py      # Riva ASR client
        │       ├── llm.py      # NIM LLM client (reads ConfigMap env vars)
        │       └── tts.py      # Riva TTS client
        └── tests/
            ├── test_mic_client.py    # Interactive mic test
            └── setup_mac_client.sh   # Mac client setup script
```

---

## Setup Instructions

### 1. Prerequisites
- **uv**: Python package manager (`curl -LsSf https://astral.sh/uv/install.sh | sh`)
- **Kubernetes**: Cluster with NVIDIA GPU support
- **NGC API Key**: Exported as `NGC_API_KEY`
- **Helm**: v3.x installed

### 2. Deployment (Full Stack)

```bash
# 1. Deploy Infrastructure (Namespace, PVCs, NIM)
export NGC_API_KEY='nvapi-...'
./scripts/deploy_infra.sh

# 2. Deploy Riva (ASR/TTS) - Takes 20-40 minutes first time
./scripts/deploy_riva.sh

# 3. Build and Deploy Gateway
./scripts/build_gateway.sh
./scripts/deploy_gateway.sh
```

### 3. Configuration Changes (No Rebuild Required)

Edit `helm/voice-workflow/values.yaml`:

```yaml
config:
  llm:
    temperature: "0.7"                    # More creative responses
    systemPrompt: "You are a Hindi-speaking assistant. Respond in Hindi."
```

Then redeploy:
```bash
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
# Terminal 1: SSH Tunnel
ssh -L 50051:localhost:50051 sagdesai@10.41.88.111

# Terminal 2: Run client
cd ~/Desktop/voice-client
uv run test_mic_client.py
```

---

## Technical Reference

### Key Configuration Values

| Component | Setting | Value | ConfigMap Key |
|-----------|---------|-------|---------------|
| ASR | Language | `en-US` | `ASR_LANGUAGE` |
| ASR | Sample Rate | `16000` Hz | `ASR_SAMPLE_RATE` |
| LLM | Model | `meta/llama-3.1-8b-instruct` | `LLM_MODEL` |
| LLM | Temperature | `0.5` | `LLM_TEMPERATURE` |
| LLM | Max Tokens | `1024` | `LLM_MAX_TOKENS` |
| LLM | System Prompt | (configurable) | `LLM_SYSTEM_PROMPT` |
| TTS | Voice | Default | `TTS_VOICE` |
| TTS | Sample Rate | `16000` Hz | `TTS_SAMPLE_RATE` |

### Resource Allocation

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit | GPU |
|-----------|-------------|-----------|----------------|--------------|-----|
| Gateway | 50m | 500m | 128Mi | 512Mi | - |
| NIM LLM | - | - | - | - | 1 |
| Riva | - | - | - | - | 1 |

### Health Check Configuration

| Probe | Type | Port | Initial Delay | Period | Timeout | Failure Threshold |
|-------|------|------|---------------|--------|---------|-------------------|
| Liveness | TCP Socket | 50051 | 15s | 30s | 5s | 3 |
| Readiness | TCP Socket | 50051 | 5s | 10s | 3s | 3 |

### Kubernetes Commands Reference

```bash
# Check all pods
kubectl get pods -n voice-workflow -o wide

# Check resource usage
kubectl top pods -n voice-workflow

# Check PDB status
kubectl get pdb -n voice-workflow

# View ConfigMap
kubectl get configmap voice-gateway-config -n voice-workflow -o yaml

# View gateway logs
kubectl logs -n voice-workflow -l app=voice-gateway -f

# Describe gateway pod (see resources, probes, events)
kubectl describe pod -n voice-workflow -l app=voice-gateway
```

---

## Fixes Applied

### 2025-12-23
1. **ASR Async Bug**: Fixed blocking `await` in executor that prevented streaming results
2. **LLM Model Name**: Changed from `meta/llama3-8b-instruct` to `meta/llama-3.1-8b-instruct`
3. **TTS Voice Name**: Changed from `en-US-Standard-A` to empty string (use default)
4. **Port Forwarding**: Added `--address 0.0.0.0` for SSH tunnel access

### 2025-12-24
1. **Resource Limits**: Added CPU/memory requests and limits to gateway deployment
2. **Health Probes**: Added liveness and readiness probes (TCP socket)
3. **ConfigMap**: Created ConfigMap for runtime-tunable LLM parameters
4. **PDB**: Added Pod Disruption Budget for voluntary disruption protection
5. **LLM Client**: Updated to read temperature, max_tokens, system_prompt from env vars

---

## Next Steps (Phase 4: Optimization & Observability)

### Immediate
1. **Latency Tuning**: Measure E2E latency and optimize buffer sizes
2. **Ingress**: Expose gRPC gateway externally (Traefik/Nginx with HTTP/2)

### Future (Planned)
1. **Load Testing**: Locust/K6 for performance benchmarking
2. **Observability**: 
   - Prometheus metrics (latency histograms, request counts)
   - OpenTelemetry tracing (span tracking across ASR→LLM→TTS)
   - Grafana dashboards
3. **Multi-language**: Add Hindi ASR/TTS models
4. **Security**: TLS for gRPC, authentication

---

## Quick Reference

### Start Server (Headnode)
```bash
kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0
```

### Connect from Mac
```bash
# Terminal 1: SSH tunnel
ssh -L 50051:localhost:50051 sagdesai@10.41.88.111

# Terminal 2: Run client
cd ~/Desktop/voice-client
uv run test_mic_client.py
```
