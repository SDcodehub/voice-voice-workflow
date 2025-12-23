# Voice-to-Voice Hindi Workflow - High Level Plan

## Phase 1: Architecture & Design (✅ Done)
- [x] Define High-Level Architecture
- [x] Define API Interfaces (Protobuf definitions)

## Phase 2: Core Components Implementation (✅ Done)
- [x] **Gateway Skeleton**: Basic gRPC server.
- [x] **ASR Integration**: Riva Client connected.
- [x] **LLM Integration**: NIM (OpenAI) Client connected.
- [x] **TTS Integration**: Riva Client connected.
- [x] **End-to-End Logic**: Pipeline wired and tested.

## Phase 3: Kubernetes Deployment & Infrastructure (🚀 Current)
### 3.1: AI Infrastructure (Layer 2)
- [ ] **NIM Operator Setup**: Ensure Operator is running.
- [ ] **Deploy LLM NIM**: Apply `k8s/infra/nim-llm.yaml`.
- [ ] **Deploy Riva**: Install Riva Chart with `k8s/infra/riva-values.yaml`.

### 3.2: Application Deployment (Layer 3)
- [ ] **Containerize Gateway**: Build Docker image.
- [ ] **Gateway Helm Chart**: Complete `helm/voice-workflow`.
- [ ] **Deploy Gateway**: Install chart connecting to Layer 2 services.

## Phase 4: Optimization & Scalability
- [ ] Implement Low Latency optimizations (streaming improvements).
- [ ] Horizontal Pod Autoscaling (HPA) configuration.
- [ ] Load Testing (Locust/K6).

## Phase 5: Production Readiness
- [ ] Logging & Monitoring (Prometheus/Grafana/OTEL).
- [ ] Security (TLS, Auth).
- [ ] CI/CD Pipelines.
