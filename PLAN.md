# Voice-to-Voice Workflow - High Level Plan

## Phase 1: Architecture & Design (✅ Done)
- [x] Define High-Level Architecture
- [x] Define API Interfaces (Protobuf definitions)

## Phase 2: Core Components Implementation (✅ Done)
- [x] **Gateway Skeleton**: Basic gRPC server.
- [x] **ASR Integration**: Riva Client connected.
- [x] **LLM Integration**: NIM (OpenAI) Client connected.
- [x] **TTS Integration**: Riva Client connected.
- [x] **End-to-End Logic**: Pipeline wired and tested.

## Phase 3: Kubernetes Deployment & Infrastructure (✅ Done)

### 3.1: AI Infrastructure (Layer 2)
- [x] **NIM Operator Setup**: Operator running.
- [x] **Deploy LLM NIM**: `meta/llama-3.1-8b-instruct` deployed via `k8s/infra/nim-llm.yaml`.
- [x] **Deploy Riva**: Helm chart with ASR (Parakeet) + TTS (FastPitch).

### 3.2: Application Deployment (Layer 3)
- [x] **Containerize Gateway**: Image at `docker.io/sagdesai/voice-gateway`.
- [x] **Gateway Helm Chart**: Complete `helm/voice-workflow`.
- [x] **Deploy Gateway**: Helm release `voice-gateway` in `voice-workflow` namespace.
- [x] **E2E Test**: Voice-to-Voice working from Mac client.

## Phase 3.5: Production Hardening (✅ Done - 2025-12-24)

### Kubernetes Best Practices
- [x] **Resource Management**: CPU/Memory requests and limits configured.
- [x] **Health Probes**: Liveness and readiness probes (TCP socket).
- [x] **ConfigMap**: Runtime-tunable parameters (LLM temperature, system prompt).
- [x] **Pod Disruption Budget**: Protection against voluntary disruptions.

### Documentation
- [x] **values.yaml**: Comprehensive inline documentation.
- [x] **CURRENT_STATUS.md**: Updated with all improvements and reference tables.

## Phase 4: Optimization & Scalability (🚧 Next)
- [ ] **Latency Tuning**: Measure E2E latency, optimize buffer sizes.
- [ ] **Ingress**: Expose gRPC gateway externally (HTTP/2 support).
- [ ] **Horizontal Pod Autoscaling (HPA)**: Scale gateway based on CPU/requests.
- [ ] **Load Testing**: Locust/K6 for performance benchmarking.

## Phase 5: Observability (📋 Planned)
- [ ] **Metrics**: Prometheus metrics (latency histograms, request counts).
- [ ] **Tracing**: OpenTelemetry spans across ASR→LLM→TTS pipeline.
- [ ] **Dashboards**: Grafana dashboards for monitoring.
- [ ] **Alerting**: PagerDuty/Slack alerts for SLA breaches.

## Phase 6: Production Readiness (📋 Planned)
- [ ] **Security**: TLS for gRPC, API authentication.
- [ ] **Multi-language**: Hindi ASR/TTS models.
- [ ] **CI/CD Pipelines**: Automated build, test, deploy.
- [ ] **Disaster Recovery**: Backup strategies, multi-region.
