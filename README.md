# Voice-to-Voice Workflow

A scalable, low-latency Voice-to-Voice AI pipeline using NVIDIA Riva and NIMs on Kubernetes.

[![Status](https://img.shields.io/badge/status-working-brightgreen)]()
[![K8s](https://img.shields.io/badge/kubernetes-ready-blue)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()

## Overview

This project implements a real-time voice conversation system where users can speak naturally and receive spoken AI responses. The architecture uses a Central Gateway pattern with gRPC streaming for low latency.

```
┌─────────┐     ┌─────────────┐     ┌──────────┐     ┌─────────┐     ┌─────────────┐
│  User   │────►│  ASR (Riva) │────►│  LLM     │────►│   TTS   │────►│    User     │
│ (Voice) │     │             │     │  (NIM)   │     │ (Riva)  │     │  (Speaker)  │
└─────────┘     └─────────────┘     └──────────┘     └─────────┘     └─────────────┘
                      ▲                   │                ▲
                      └───────────────────┴────────────────┘
                              Voice Gateway (Orchestrator)
```

### Key Features

- **Real-time Streaming**: gRPC bidirectional streaming for minimal latency
- **Production Ready**: Resource limits, health probes, PDB, graceful shutdown
- **Secure**: Non-root containers, read-only filesystem, secret management
- **Configurable**: Runtime-tunable LLM parameters via ConfigMap

### Tech Stack

| Component | Technology |
|-----------|------------|
| ASR | NVIDIA Riva (Parakeet) |
| LLM | NVIDIA NIM (Llama 3.1 8B) |
| TTS | NVIDIA Riva (FastPitch + HiFiGAN) |
| Gateway | Python + gRPC + asyncio |
| Orchestration | Kubernetes + Helm |

## Quick Start

### Prerequisites

- Kubernetes cluster with NVIDIA GPU
- Helm v3.x
- NGC API Key (`export NGC_API_KEY='nvapi-...'`)

### Deploy

```bash
# 1. Deploy infrastructure (NIM, Riva)
./scripts/deploy_infra.sh
./scripts/deploy_riva.sh    # Takes 20-40 min first time

# 2. Deploy gateway
./scripts/build_gateway.sh
./scripts/deploy_gateway.sh
```

### Test

```bash
# On server (headnode)
kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 50051:50051 --address 0.0.0.0

# On client (Mac)
ssh -L 50051:localhost:50051 user@server
cd voice-client && uv run test_mic_client.py
```

## Documentation

| Document | Description |
|----------|-------------|
| [Deployment Guide](docs/guides/DEPLOYMENT.md) | Full K8s deployment instructions |
| [Development Guide](docs/guides/DEVELOPMENT.md) | Local development setup |
| [Client Setup](docs/guides/CLIENT_SETUP.md) | Mac/mobile client configuration |
| [Observability Guide](docs/guides/OBSERVABILITY.md) | Prometheus, Grafana, GPU metrics |
| [Configuration Reference](docs/reference/CONFIGURATION.md) | All config options |
| [Security Guide](docs/reference/SECURITY.md) | Security features & best practices |
| [Roadmap](docs/ROADMAP.md) | Project phases & future plans |

## Project Structure

```
voice-voice-workflow/
├── README.md                 # This file
├── docs/                     # Documentation
│   ├── architecture/         # Architecture diagrams
│   ├── guides/               # How-to guides
│   ├── reference/            # Reference documentation
│   └── ROADMAP.md            # Project roadmap
├── helm/voice-workflow/      # Helm chart
├── k8s/infra/                # K8s manifests (NIM, PVCs)
├── proto/                    # gRPC protocol definitions
├── scripts/                  # Deployment scripts
└── services/voice-gateway/   # Gateway service source
```

## Current Status

✅ **Phase 3.6 Complete** - Production-ready deployment with:
- E2E voice-to-voice working
- Kubernetes best practices (resources, probes, PDB)
- Security hardening (non-root, read-only FS, secrets)
- Graceful shutdown

See [ROADMAP.md](docs/ROADMAP.md) for detailed progress and future plans.

## Contributing

1. Check [ROADMAP.md](docs/ROADMAP.md) for planned features
2. Follow existing code patterns
3. Test changes locally before submitting

## License

MIT License - See LICENSE file for details.

