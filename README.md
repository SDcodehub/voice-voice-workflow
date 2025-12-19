# Voice-to-Voice Workflow for Hindi

A highly scalable, low-latency voice-to-voice conversational AI system using NVIDIA Riva for ASR/TTS and LLM for intelligent responses.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                              KUBERNETES CLUSTER                                          │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                         INGRESS (NGINX / Traefik)                                │    │
│  │                    WebSocket + gRPC-Web Support                                  │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                        │                                                 │
│                                        ▼                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                      VOICE GATEWAY SERVICE                                       │    │
│  │              (WebSocket Server + Session Management)                             │    │
│  │                    Replicas: 3-10 (HPA)                                          │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                        │                                                 │
│                    ┌───────────────────┼───────────────────┐                            │
│                    │                   │                   │                            │
│                    ▼                   ▼                   ▼                            │
│  ┌─────────────────────┐  ┌─────────────────────┐  ┌─────────────────────┐             │
│  │   ASR SERVICE       │  │   LLM SERVICE       │  │   TTS SERVICE       │             │
│  │   (Riva Hindi)      │  │   (NIM/vLLM)        │  │   (Riva Hindi)      │             │
│  │                     │  │                     │  │                     │             │
│  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │  │ ┌─────────────────┐ │             │
│  │ │ gRPC Client     │ │  │ │ Inference       │ │  │ │ gRPC Client     │ │             │
│  │ │ Streaming ASR   │ │  │ │ Streaming LLM   │ │  │ │ Streaming TTS   │ │             │
│  │ └─────────────────┘ │  │ └─────────────────┘ │  │ └─────────────────┘ │             │
│  │   Replicas: 2-8     │  │   Replicas: 2-6     │  │   Replicas: 2-8     │             │
│  └──────────┬──────────┘  └──────────┬──────────┘  └──────────┬──────────┘             │
│             │                        │                        │                         │
│             │            ┌───────────┴───────────┐            │                         │
│             │            │                       │            │                         │
│             ▼            ▼                       ▼            ▼                         │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                           GPU NODE POOL                                          │    │
│  │  ┌───────────────────────────────────────────────────────────────────────────┐  │    │
│  │  │                    NVIDIA RIVA SERVER (Hindi Models)                       │  │    │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐ │  │    │
│  │  │  │ ASR Model       │  │ TTS Model       │  │ Punctuation Model          │ │  │    │
│  │  │  │ hi-IN Conformer │  │ hi-IN FastPitch │  │ (Optional)                 │ │  │    │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────────────────┘ │  │    │
│  │  └───────────────────────────────────────────────────────────────────────────┘  │    │
│  │                                                                                  │    │
│  │  ┌───────────────────────────────────────────────────────────────────────────┐  │    │
│  │  │                    LLM INFERENCE SERVER                                    │  │    │
│  │  │  ┌─────────────────────────────────────────────────────────────────────┐  │  │    │
│  │  │  │ NVIDIA NIM / vLLM / TensorRT-LLM                                    │  │  │    │
│  │  │  │ Model: Llama-3.1-8B / Mistral-7B-Instruct (Hindi capable)           │  │  │    │
│  │  │  └─────────────────────────────────────────────────────────────────────┘  │  │    │
│  │  └───────────────────────────────────────────────────────────────────────────┘  │    │
│  └──────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────────────┐    │
│  │                           SUPPORTING SERVICES                                    │    │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌───────────────────────┐   │    │
│  │  │   Redis     │  │ Prometheus  │  │  Grafana    │  │ OpenTelemetry         │   │    │
│  │  │ (Sessions)  │  │ (Metrics)   │  │ (Dashboard) │  │ Collector             │   │    │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └───────────────────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────────────────┘    │
│                                                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```

## Data Flow (Low Latency Pipeline)

```
┌──────────┐    Audio     ┌──────────────┐   gRPC    ┌──────────┐   gRPC    ┌──────────┐
│  Client  │─────────────▶│ Voice        │──────────▶│  Riva    │─────────▶│   ASR    │
│ (Browser │  WebSocket   │ Gateway      │ Streaming │  Server  │ Streaming│ Service  │
│  /App)   │              │              │           │          │          │          │
└──────────┘              └──────────────┘           └──────────┘          └────┬─────┘
     ▲                                                                          │
     │                                                                          │ Text
     │                                                                          ▼
     │                    ┌──────────────┐           ┌──────────┐          ┌──────────┐
     │    Audio          │ Voice        │   gRPC    │  Riva    │  Text    │   LLM    │
     └───────────────────│ Gateway      │◀──────────│  Server  │◀─────────│ Service  │
          WebSocket      │              │ Streaming │          │ Streaming│          │
                         └──────────────┘           └──────────┘          └──────────┘
```

## Latency Optimization Strategies

1. **Streaming ASR**: Real-time transcription as user speaks
2. **Streaming LLM**: Token-by-token generation
3. **Streaming TTS**: Audio chunk generation in parallel with LLM
4. **Connection Pooling**: gRPC connection reuse
5. **GPU Inference**: All models on GPU for <100ms inference
6. **Edge Caching**: Common responses cached in Redis

## Project Structure

```
voice-voice-workflow/
├── README.md
├── architecture/
│   └── diagram.mermaid
├── services/
│   ├── voice-gateway/          # WebSocket gateway + orchestration
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── gateway.py
│   │       └── config.py
│   ├── asr-service/            # Riva ASR client
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── asr_client.py
│   │       └── config.py
│   ├── llm-service/            # LLM inference orchestrator
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── src/
│   │       ├── main.py
│   │       ├── llm_client.py
│   │       └── config.py
│   └── tts-service/            # Riva TTS client
│       ├── Dockerfile
│       ├── requirements.txt
│       └── src/
│           ├── main.py
│           ├── tts_client.py
│           └── config.py
├── k8s/
│   ├── base/
│   │   ├── namespace.yaml
│   │   ├── riva-server.yaml
│   │   ├── llm-server.yaml
│   │   ├── voice-gateway.yaml
│   │   ├── asr-service.yaml
│   │   ├── llm-service.yaml
│   │   ├── tts-service.yaml
│   │   ├── redis.yaml
│   │   └── ingress.yaml
│   └── overlays/
│       ├── dev/
│       └── prod/
├── helm/
│   └── voice-workflow/
│       ├── Chart.yaml
│       ├── values.yaml
│       ├── values-prod.yaml
│       └── templates/
│           ├── _helpers.tpl
│           ├── namespace.yaml
│           ├── riva-server.yaml
│           ├── llm-server.yaml
│           ├── voice-gateway.yaml
│           ├── asr-service.yaml
│           ├── llm-service.yaml
│           ├── tts-service.yaml
│           ├── redis.yaml
│           ├── ingress.yaml
│           ├── hpa.yaml
│           └── servicemonitor.yaml
├── proto/
│   └── voice_service.proto
└── scripts/
    ├── deploy.sh
    └── test-e2e.sh
```

## Quick Start

```bash
# 1. Deploy Riva Server (requires NGC API key)
export NGC_API_KEY=<your-key>
helm install riva-server helm/voice-workflow -f helm/voice-workflow/values.yaml

# 2. Deploy voice workflow services
kubectl apply -k k8s/overlays/prod/

# 3. Test the endpoint
python scripts/test-e2e.sh
```

## Prerequisites

- Kubernetes cluster with GPU nodes (A100/H100 recommended)
- NVIDIA GPU Operator installed
- NGC API key for Riva models
- Ingress controller (NGINX recommended)

## Hindi Language Support

- **ASR Model**: `riva-asr-hi-in-conformer` (Hindi Conformer)
- **TTS Model**: `riva-tts-hi-in-fastpitch` (Hindi FastPitch)
- **LLM**: Llama-3.1-8B-Instruct or Mistral-7B-Instruct (multilingual)

## Scaling

The system uses Horizontal Pod Autoscaler (HPA) based on:
- CPU/Memory utilization
- Custom metrics (requests per second, latency percentiles)
- GPU utilization for inference pods

