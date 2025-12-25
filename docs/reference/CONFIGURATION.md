# Configuration Reference

Complete reference for all configuration options.

## Configuration Methods

| Method | Location | Requires Rebuild | Use Case |
|--------|----------|------------------|----------|
| ConfigMap | `values.yaml` → `config.*` | No | Runtime tuning |
| Environment | Deployment env vars | No | Service discovery |
| Secrets | K8s Secret → envFrom | No | Credentials |
| Code | Source files | Yes | Logic changes |

## ConfigMap Values

### ASR Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `ASR_LANGUAGE` | `en-US` | Language code (en-US, hi-IN) |
| `ASR_SAMPLE_RATE` | `16000` | Audio sample rate in Hz |

### LLM Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `LLM_MODEL` | `meta/llama-3.1-8b-instruct` | Model identifier |
| `LLM_TEMPERATURE` | `0.6` | Response randomness (0.0-1.0) |
| `LLM_MAX_TOKENS` | `2048` | Maximum response length |
| `LLM_SYSTEM_PROMPT` | (see below) | System instructions |

**Default System Prompt** (optimized for voice):
```
You are an intelligent voice assistant powered by Llama 3.1...
- NEVER use markdown formatting
- Be conversational
- Provide detail when asked
```

### TTS Configuration

| Key | Default | Description |
|-----|---------|-------------|
| `TTS_VOICE` | `""` | Voice name (empty = default) |
| `TTS_SAMPLE_RATE` | `16000` | Output sample rate in Hz |

## Environment Variables

### Service Discovery

| Variable | Default | Description |
|----------|---------|-------------|
| `RIVA_URI` | `riva-api:50051` | Riva gRPC endpoint |
| `LLM_SERVICE_URL` | `http://meta-llama3-8b-instruct:8000/v1` | NIM endpoint |

### Runtime Settings

| Variable | Default | Description |
|----------|---------|-------------|
| `GRPC_PORT` | `50051` | Gateway listen port |
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `SHUTDOWN_GRACE_PERIOD` | `10` | Seconds to wait for requests on shutdown |
| `GRPC_MAX_WORKERS` | `10` | Thread pool size |

## Helm Values Reference

### Gateway Configuration

```yaml
gateway:
  image: docker.io/sagdesai/voice-gateway:latest
  imagePullPolicy: Always
  replicas: 1
  
  service:
    type: ClusterIP
    port: 50051
  
  resources:
    requests:
      memory: "128Mi"
      cpu: "50m"
    limits:
      memory: "512Mi"
      cpu: "500m"
  
  pdb:
    enabled: true
    minAvailable: 1
  
  shutdownGracePeriod: "10"
  terminationGracePeriodSeconds: 30
  logLevel: "INFO"
  
  securityContext:
    enabled: true
    runAsUser: 1000
    runAsGroup: 1000
    fsGroup: 1000
  
  secrets:
    create: false
    existingSecret: ""
```

### Runtime Config

```yaml
config:
  asr:
    language: "en-US"
    sampleRate: "16000"
  
  llm:
    model: "meta/llama-3.1-8b-instruct"
    temperature: "0.6"
    maxTokens: "2048"
    systemPrompt: |
      You are a voice assistant...
  
  tts:
    voice: ""
    sampleRate: "16000"
```

## Resource Recommendations

### By Workload

| Scenario | CPU Request | CPU Limit | Memory Request | Memory Limit |
|----------|-------------|-----------|----------------|--------------|
| Development | 50m | 500m | 128Mi | 512Mi |
| Production (low) | 100m | 1000m | 256Mi | 1Gi |
| Production (high) | 500m | 2000m | 512Mi | 2Gi |

### Scaling Guidelines

| Concurrent Users | Replicas | CPU per Pod | Memory per Pod |
|------------------|----------|-------------|----------------|
| 1-10 | 1 | 500m | 512Mi |
| 10-50 | 2-3 | 1000m | 1Gi |
| 50-100 | 3-5 | 2000m | 2Gi |

## Health Probe Configuration

```yaml
# In deployment template
livenessProbe:
  tcpSocket:
    port: grpc
  initialDelaySeconds: 15
  periodSeconds: 30
  timeoutSeconds: 5
  failureThreshold: 3

readinessProbe:
  tcpSocket:
    port: grpc
  initialDelaySeconds: 5
  periodSeconds: 10
  timeoutSeconds: 3
  failureThreshold: 3
```

## Changing Configuration

### Runtime Changes (No Rebuild)

1. Edit `helm/voice-workflow/values.yaml`
2. Deploy: `./scripts/deploy_gateway.sh`
3. Restart pods: `kubectl rollout restart deployment/voice-gateway-gateway -n voice-workflow`

### Viewing Current Config

```bash
# ConfigMap
kubectl get configmap voice-gateway-config -n voice-workflow -o yaml

# Environment in pod
kubectl exec -n voice-workflow -l app=voice-gateway -- env | grep -E "LLM|ASR|TTS"
```

