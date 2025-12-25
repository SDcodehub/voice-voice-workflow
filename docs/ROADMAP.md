# Project Roadmap

## Completed Phases

### Phase 1: Architecture & Design ✅

- [x] Define High-Level Architecture
- [x] Define API Interfaces (Protobuf definitions)

### Phase 2: Core Components ✅

- [x] Gateway Skeleton (gRPC server)
- [x] ASR Integration (Riva client)
- [x] LLM Integration (NIM/OpenAI client)
- [x] TTS Integration (Riva client)
- [x] End-to-End Logic (pipeline wired)

### Phase 3: Kubernetes Deployment ✅

- [x] NIM Operator Setup
- [x] Deploy LLM NIM (`meta/llama-3.1-8b-instruct`)
- [x] Deploy Riva (Parakeet ASR + FastPitch TTS)
- [x] Containerize Gateway (`docker.io/sagdesai/voice-gateway`)
- [x] Gateway Helm Chart
- [x] E2E Test Verified

### Phase 3.5: Production Hardening ✅ (2025-12-24)

- [x] Resource Management (CPU/Memory requests & limits)
- [x] Health Probes (liveness & readiness)
- [x] ConfigMap (runtime-tunable parameters)
- [x] Pod Disruption Budget

### Phase 3.6: Security & Reliability ✅ (2025-12-24)

- [x] Graceful Shutdown (SIGTERM handling)
- [x] Non-root Container (UID 1000)
- [x] Security Context (read-only FS, drop capabilities)
- [x] Secret Management (Helm templates + existing secrets)
- [x] Voice-optimized System Prompt (no markdown for TTS)

---

## Current Phase

### Phase 4: Optimization & Scalability 🚧

- [ ] Latency Tuning (measure E2E, optimize buffers)
- [ ] Ingress (expose gRPC externally with HTTP/2)
- [ ] Horizontal Pod Autoscaling (HPA)
- [ ] Load Testing (Locust/K6)

---

## Planned Phases

### Phase 5: Observability 🚧 (2025-12-25)

- [x] Prometheus Metrics
  - ASR latency histogram (`voice_gateway_asr_latency_seconds`)
  - LLM time-to-first-token (`voice_gateway_llm_ttft_seconds`)
  - LLM total generation time (`voice_gateway_llm_total_seconds`)
  - TTS synthesis time (`voice_gateway_tts_latency_seconds`)
  - E2E latency (`voice_gateway_e2e_latency_seconds`)
  - Request counts, error rates
- [x] DCGM GPU Metrics Integration
  - GPU utilization, memory, temperature, power
  - Pre-built dashboard (ID: 12239)
- [x] Grafana Dashboards
  - Custom Voice Gateway dashboard
  - Latency breakdown panels (ASR/LLM/TTS)
- [ ] OpenTelemetry Tracing
  - Span tracking across ASR→LLM→TTS
  - Distributed trace context
- [ ] Alerting (PagerDuty/Slack)

### Phase 6: Production Readiness 📋

- [ ] TLS for gRPC
- [ ] API Authentication
- [ ] Multi-language (Hindi ASR/TTS)
- [ ] CI/CD Pipelines
- [ ] Disaster Recovery

---

## Known Issues & Future Improvements

### Issue 1: Echo/Feedback Loop (Speaker Mode)

**Problem**: When using speakers (not headphones), the microphone picks up TTS output, causing ASR to process the assistant's own voice, creating an infinite loop.

**Impact**: Users must use headphones for testing.

**Solutions** (Future):
| Solution | Complexity | Description |
|----------|------------|-------------|
| Headphones | None | Physical isolation (current workaround) |
| Mic mute during TTS | Low | Simple but prevents interruption |
| Platform AEC | Medium | Use iOS/Android/WebRTC echo cancellation |
| Riva reference signal | Medium | Send TTS audio as reference to ASR |

**Tech Solution**: Integrate WebRTC AudioProcessing or platform-native AEC (AVAudioSession on iOS, AudioManager on Android). Mobile platforms handle this automatically in voice/communication mode.

### Issue 2: No Barge-in/Interruption Support

**Problem**: Users cannot interrupt the assistant while TTS is speaking. The system completes the full turn (ASR→LLM→TTS) before listening again.

**Impact**: Poor UX for long responses; users must wait.

**Solutions** (Future):
| Solution | Complexity | Description |
|----------|------------|-------------|
| Client-side interrupt | Low | Detect voice during TTS, send cancel signal |
| Full-duplex streaming | High | Separate input/output streams, always listening |
| VAD during TTS | Medium | Server-side voice activity detection |

**Tech Solution**: Add `CANCEL_TTS` message to proto, implement client-side VAD to detect user speech during playback, gateway cancels TTS stream on interrupt signal.

### Issue 3: Half-Duplex Architecture

**Problem**: Current architecture is request-response (half-duplex). For natural conversation, need full-duplex where system can listen while speaking.

**Impact**: Less natural conversation flow.

**Solution** (Future): Implement state machine in gateway:
```
IDLE → LISTENING → PROCESSING → SPEAKING → (interrupt?) → LISTENING
```

**Tech Solution**: Refactor gateway to maintain conversation state, process incoming audio even during TTS output, use AEC to filter speaker audio.

---

## What We Have Today

### Working Components ✅

| Component | Status | Notes |
|-----------|--------|-------|
| ASR Streaming | ✅ Working | Riva Parakeet, 16kHz, en-US |
| LLM Generation | ✅ Working | Llama 3.1 8B via NIM |
| TTS Streaming | ✅ Working | FastPitch + HiFiGAN |
| Gateway | ✅ Working | Python async gRPC |
| K8s Deployment | ✅ Working | Helm chart, all best practices |
| Security | ✅ Working | Non-root, read-only FS, secrets |
| Mac Client | ✅ Working | PyAudio test client |

### Production Features ✅

| Feature | Status | Details |
|---------|--------|---------|
| Resource Limits | ✅ | 50m/500m CPU, 128Mi/512Mi memory |
| Health Probes | ✅ | TCP socket liveness/readiness |
| Graceful Shutdown | ✅ | 10s grace period, SIGTERM handling |
| ConfigMap | ✅ | Runtime tunable (temp, prompt, etc.) |
| PDB | ✅ | Blocks voluntary disruptions |
| Secrets | ✅ | Helm template + existing secret ref |

### Not Yet Implemented ❌

| Feature | Priority | Notes |
|---------|----------|-------|
| Echo Cancellation | High | Required for speaker mode |
| Barge-in | High | Required for natural UX |
| Observability | Medium | Prometheus + OTEL |
| Load Testing | Medium | Locust/K6 |
| TLS | Medium | Security for external access |
| Multi-language | Low | Hindi models available |

---

## Version History

| Version | Date | Highlights |
|---------|------|------------|
| 0.1.0 | 2025-12-23 | Initial E2E working |
| 0.2.0 | 2025-12-24 | Production hardening, security |
| 0.3.0 | TBD | Observability |
| 1.0.0 | TBD | Production release |

