# Voice-to-Voice Hindi Workflow - High Level Plan

## Phase 1: Architecture & Design (Current)
- [x] Define High-Level Architecture
- [ ] Define API Interfaces (Protobuf definitions for gRPC)
- [ ] Select specific Models (Riva Hindi models, LLM choice)

## Phase 2: Core Components Implementation (Proof of Concept)
- [ ] **ASR Service Setup**: Deploy NVIDIA Riva ASR with Hindi model on K8s (or mock for dev).
- [ ] **TTS Service Setup**: Deploy NVIDIA Riva TTS with Hindi model on K8s.
- [ ] **LLM Integration**: Set up a simple LLM connector (could be external API initially or local NIM).
- [ ] **Voice Gateway (Orchestrator)**:
    - Implement basic bi-directional streaming.
    - Handle ASR -> LLM -> TTS chaining.
    - Basic interruptibility (optional for POC).

## Phase 3: Kubernetes Deployment & Infrastructure
- [ ] Create Helm Charts for each component.
- [ ] Configure Ingress for WebSocket/gRPC support.
- [ ] Resource management (GPU requests/limits).
- [ ] Service Discovery setup.

## Phase 4: Optimization & Scalability
- [ ] Implement Low Latency optimizations (streaming improvements).
- [ ] Horizontal Pod Autoscaling (HPA) configuration.
- [ ] Load Testing (Locust/K6).

## Phase 5: Production Readiness
- [ ] Logging & Monitoring (Prometheus/Grafana/OTEL).
- [ ] Security (TLS, Auth).
- [ ] CI/CD Pipelines.

---

## Technical Stack
- **Orchestrator**: Python (FastAPI/AsyncIO) or Go.
- **Protocol**: gRPC (Internal), WebSocket (Client-Gateway).
- **AI Engine**: NVIDIA Riva (ASR/TTS), NVIDIA NIM (LLM).
- **Infra**: Kubernetes, Helm.

