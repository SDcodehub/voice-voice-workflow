# Observability Guide

Monitoring latency, GPU usage, and performance for the Voice-to-Voice pipeline.

## Quick Start

```bash
# 1. Deploy voice-gateway (already has metrics enabled)
./scripts/deploy_gateway.sh

# 2. Setup observability (creates ServiceMonitor)
./scripts/setup_observability.sh

# 3. Start port-forwards on server
kubectl port-forward -n prometheus svc/kube-prometheus-stack-grafana 3000:80 --address 0.0.0.0 &
kubectl port-forward -n prometheus svc/kube-prometheus-stack-prometheus 9090:9090 --address 0.0.0.0 &

# 4. Access dashboards
#    - Direct (on server): http://localhost:3000
#    - Remote (from Mac): SSH tunnel then http://localhost:3001
#    - Login: admin / prom-operator
```

### Remote Access (from Mac)

```bash
# On Mac - create SSH tunnel (use different local ports if 3000/9090 are busy)
ssh -L 3001:localhost:3000 -L 9091:localhost:9090 user@server-ip

# Then open in browser:
#   Grafana:    http://localhost:3001
#   Prometheus: http://localhost:9091
```

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              Kubernetes Cluster                               │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                    Voice Workflow Namespace                             │ │
│  │                                                                         │ │
│  │  ┌─────────────────────┐      ┌─────────────────────┐                  │ │
│  │  │   Voice Gateway     │      │    Riva (Triton)    │                  │ │
│  │  │   :50051 (gRPC)     │      │    :50051 (gRPC)    │                  │ │
│  │  │   :8080 (metrics)   │      │    :8002 (metrics)  │                  │ │
│  │  └─────────────────────┘      └─────────────────────┘                  │ │
│  │             │                           │                               │ │
│  │             └───────────────────────────┘                               │ │
│  │                         │                                               │ │
│  └─────────────────────────┼───────────────────────────────────────────────┘ │
│                            │                                                 │
│  ┌─────────────────────────┼───────────────────────────────────────────────┐ │
│  │  Prometheus Namespace   │                                               │ │
│  │  (kube-prometheus-stack)│                                               │ │
│  │                         ▼                                               │ │
│  │  ┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐       │ │
│  │  │   Prometheus    │◄──│  DCGM Exporter  │   │    Grafana      │       │ │
│  │  │   :9090         │   │  (GPU metrics)  │   │    :3000        │       │ │
│  │  └────────┬────────┘   └─────────────────┘   └────────┬────────┘       │ │
│  │           │                                           │                │ │
│  │           └───────────────────────────────────────────┘                │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────────────┘
```

## Metrics Available

### Voice Gateway Metrics (port 8080)

| Metric | Type | Description |
|--------|------|-------------|
| `voice_gateway_asr_latency_seconds` | Histogram | ASR transcription latency |
| `voice_gateway_llm_ttft_seconds` | Histogram | LLM Time to First Token |
| `voice_gateway_llm_total_seconds` | Histogram | LLM total generation time |
| `voice_gateway_llm_tokens_total` | Histogram | Tokens generated per response |
| `voice_gateway_tts_latency_seconds` | Histogram | TTS synthesis latency |
| `voice_gateway_tts_characters_total` | Histogram | Characters per TTS call |
| `voice_gateway_e2e_latency_seconds` | Histogram | End-to-end latency |
| `voice_gateway_requests_total` | Counter | Total requests (by status) |
| `voice_gateway_active_streams` | Gauge | Current active streams |
| `voice_gateway_*_errors_total` | Counters | Error counts by type |

### GPU Metrics (DCGM Exporter)

Since **DCGM is already integrated** in your cluster, these metrics are available:

| Metric | Description |
|--------|-------------|
| `DCGM_FI_DEV_GPU_UTIL` | GPU utilization (%) |
| `DCGM_FI_DEV_MEM_COPY_UTIL` | Memory copy utilization (%) |
| `DCGM_FI_DEV_FB_USED` | Framebuffer memory used (MB) |
| `DCGM_FI_DEV_FB_FREE` | Framebuffer memory free (MB) |
| `DCGM_FI_DEV_POWER_USAGE` | Power usage (W) |
| `DCGM_FI_DEV_GPU_TEMP` | GPU temperature (°C) |
| `DCGM_FI_PROF_GR_ENGINE_ACTIVE` | Graphics engine active time |
| `DCGM_FI_PROF_SM_ACTIVE` | SM active time |

### Riva/Triton Metrics (port 8002)

Riva exposes Triton metrics automatically:

| Metric | Description |
|--------|-------------|
| `nv_inference_request_success` | Successful inference requests |
| `nv_inference_request_failure` | Failed inference requests |
| `nv_inference_exec_count` | Inference execution count |
| `nv_inference_request_duration_us` | Request duration (microseconds) |
| `nv_inference_queue_duration_us` | Queue wait time (microseconds) |
| `nv_gpu_utilization` | GPU utilization from Triton |

---

## Setup Instructions

### Prerequisites

Your cluster should have:
- **kube-prometheus-stack** deployed in `prometheus` namespace
- **DCGM Exporter** (from GPU Operator) for GPU metrics
- **Voice Gateway** deployed in `voice-workflow` namespace

### 1. Verify Prometheus Stack is Running

```bash
# Check Prometheus pods
kubectl get pods -n prometheus | grep -E "prometheus|grafana"

# Expected output:
# kube-prometheus-stack-grafana-xxx              3/3     Running
# prometheus-kube-prometheus-stack-prometheus-0  2/2     Running
```

### 2. Verify DCGM Exporter is Running

```bash
# Check DCGM exporter pods (from GPU Operator)
kubectl get pods -n gpu-operator -l app=nvidia-dcgm-exporter

# Verify DCGM ServiceMonitor exists
kubectl get servicemonitors -n gpu-operator | grep dcgm
```

DCGM should already be configured. The ServiceMonitor was created with label `release: kube-prometheus-stack`.

### 3. Create ServiceMonitor for Voice Gateway

**Option A: Using the setup script (recommended)**
```bash
./scripts/setup_observability.sh
```

**Option B: Manual apply**
```bash
kubectl apply -f k8s/observability/voice-gateway-servicemonitor.yaml
```

**Option C: Via Helm** (ServiceMonitor is enabled by default)
```bash
./scripts/deploy_gateway.sh
```

### 4. Verify ServiceMonitor is Discovered

```bash
# List all ServiceMonitors
kubectl get servicemonitors -A | grep -E "voice|dcgm"

# Check Prometheus targets
kubectl port-forward -n prometheus svc/kube-prometheus-stack-prometheus 9090:9090
# Open http://localhost:9090/targets and look for voice-gateway-monitor
```

### 5. Access Grafana and Prometheus

#### Option A: Direct Access (on server)

```bash
# Start port-forwards on server (bind to 0.0.0.0 for remote access)
kubectl port-forward -n prometheus svc/kube-prometheus-stack-grafana 3000:80 --address 0.0.0.0 &
kubectl port-forward -n prometheus svc/kube-prometheus-stack-prometheus 9090:9090 --address 0.0.0.0 &
```

#### Option B: Remote Access from Mac via SSH Tunnel

If accessing the server remotely (e.g., from Mac), use SSH tunneling:

**Step 1: Start port-forwards on server**
```bash
# On server (run these in background or separate terminal)
kubectl port-forward -n prometheus svc/kube-prometheus-stack-grafana 3000:80 --address 0.0.0.0 &
kubectl port-forward -n prometheus svc/kube-prometheus-stack-prometheus 9090:9090 --address 0.0.0.0 &
```

**Step 2: Create SSH tunnel from Mac**
```bash
# On Mac terminal - tunnel both Grafana and Prometheus
ssh -L 3001:localhost:3000 -L 9091:localhost:9090 user@server-ip

# Example:
ssh -L 3001:localhost:3000 -L 9091:localhost:9090 sagdesai@10.41.88.111
```

> **Note**: Use different local ports (3001, 9091) if 3000/9090 are already in use on your Mac.

**Step 3: Access dashboards in Mac browser**

| Service | URL | Credentials |
|---------|-----|-------------|
| Grafana | http://localhost:3001 | `admin` / `prom-operator` |
| Prometheus | http://localhost:9091 | (none required) |

#### Grafana Credentials

```bash
# Get Grafana admin password
kubectl get secret -n prometheus kube-prometheus-stack-grafana \
  -o jsonpath='{.data.admin-password}' | base64 -d
# Default: prom-operator
```

### 6. Import Dashboards

#### Dashboard A: NVIDIA DCGM (GPU Metrics) - ID: 12239

1. In Grafana: **☰ Menu** → **Dashboards** → **New** → **Import**
2. Enter Dashboard ID: **`12239`**
3. Click **Load**
4. Select **Prometheus** as data source
5. Click **Import**

This provides:
- GPU utilization
- GPU memory usage  
- Power consumption
- Temperature
- Per-GPU breakdown

#### Dashboard B: Voice Gateway Performance

**Option 1: Import JSON file**

1. Copy dashboard JSON from server to Mac:
   ```bash
   scp user@server:~/voice-voice-workflow/helm/voice-workflow/dashboards/voice-gateway-dashboard.json ~/Desktop/
   ```
2. In Grafana: **☰ Menu** → **Dashboards** → **New** → **Import**
3. Click **Upload dashboard JSON file**
4. Select the downloaded file
5. Select **Prometheus** as data source
6. Click **Import**

**Option 2: Paste JSON directly**

1. In Grafana: **☰ Menu** → **Dashboards** → **New** → **Import**
2. Copy contents from `helm/voice-workflow/dashboards/voice-gateway-dashboard.json`
3. Paste into the **Import via dashboard JSON model** text area
4. Click **Load**
5. Select **Prometheus** as data source
6. Click **Import**

**Option 3: Create manually** with these panels:

**Panel 1: E2E Latency (P50, P95, P99)**
```promql
# P50
histogram_quantile(0.5, sum(rate(voice_gateway_e2e_latency_seconds_bucket[5m])) by (le))

# P95
histogram_quantile(0.95, sum(rate(voice_gateway_e2e_latency_seconds_bucket[5m])) by (le))

# P99
histogram_quantile(0.99, sum(rate(voice_gateway_e2e_latency_seconds_bucket[5m])) by (le))
```

**Panel 2: Component Latency Breakdown**
```promql
# ASR P95
histogram_quantile(0.95, sum(rate(voice_gateway_asr_latency_seconds_bucket[5m])) by (le))

# LLM TTFT P95
histogram_quantile(0.95, sum(rate(voice_gateway_llm_ttft_seconds_bucket[5m])) by (le))

# TTS P95
histogram_quantile(0.95, sum(rate(voice_gateway_tts_latency_seconds_bucket[5m])) by (le))
```

**Panel 3: Request Rate & Errors**
```promql
# Request rate
sum(rate(voice_gateway_requests_total[5m])) by (status)

# Error rate
sum(rate(voice_gateway_asr_errors_total[5m])) + 
sum(rate(voice_gateway_llm_errors_total[5m])) + 
sum(rate(voice_gateway_tts_errors_total[5m]))
```

**Panel 4: Active Streams**
```promql
voice_gateway_active_streams
```

**Panel 5: GPU Utilization (from DCGM)**
```promql
DCGM_FI_DEV_GPU_UTIL{gpu="0"}
```

**Panel 6: GPU Memory Usage**
```promql
DCGM_FI_DEV_FB_USED{gpu="0"} / (DCGM_FI_DEV_FB_USED{gpu="0"} + DCGM_FI_DEV_FB_FREE{gpu="0"}) * 100
```

---

## Creating Custom Grafana Dashboard

### Step-by-Step:

1. **Open Grafana** → **Create** → **Dashboard**

2. **Add Panel: E2E Latency**
   - Visualization: Time series
   - Query A: `histogram_quantile(0.5, sum(rate(voice_gateway_e2e_latency_seconds_bucket[5m])) by (le))`
   - Legend: P50
   - Query B: P95 (same with 0.95)
   - Query C: P99 (same with 0.99)
   - Unit: seconds

3. **Add Panel: Latency Waterfall**
   - Visualization: Bar gauge or Stat
   - Show P95 for ASR, LLM TTFT, TTS
   - Unit: seconds

4. **Add Panel: Request Rate**
   - Visualization: Time series
   - Query: `sum(rate(voice_gateway_requests_total[1m])) by (status)`
   - Unit: requests/sec

5. **Add Panel: GPU Stats**
   - Visualization: Gauge
   - Query: `DCGM_FI_DEV_GPU_UTIL`
   - Unit: percent

6. **Save Dashboard**
   - Export JSON for version control

---

## Alerting Examples

### Prometheus Alerting Rules

```yaml
# voice-gateway-alerts.yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: voice-gateway-alerts
  namespace: voice-workflow
spec:
  groups:
    - name: voice-gateway
      rules:
        # High E2E latency alert
        - alert: VoiceGatewayHighLatency
          expr: histogram_quantile(0.95, sum(rate(voice_gateway_e2e_latency_seconds_bucket[5m])) by (le)) > 3
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "Voice Gateway P95 latency is high"
            description: "P95 E2E latency is {{ $value }}s (threshold: 3s)"
        
        # High error rate alert
        - alert: VoiceGatewayHighErrorRate
          expr: |
            (sum(rate(voice_gateway_requests_total{status="error"}[5m])) / 
             sum(rate(voice_gateway_requests_total[5m]))) > 0.05
          for: 5m
          labels:
            severity: critical
          annotations:
            summary: "Voice Gateway error rate > 5%"
            description: "Error rate is {{ $value | humanizePercentage }}"
        
        # GPU memory exhaustion
        - alert: GPUMemoryHigh
          expr: |
            (DCGM_FI_DEV_FB_USED / (DCGM_FI_DEV_FB_USED + DCGM_FI_DEV_FB_FREE)) > 0.9
          for: 5m
          labels:
            severity: warning
          annotations:
            summary: "GPU memory usage > 90%"
            description: "GPU {{ $labels.gpu }} memory at {{ $value | humanizePercentage }}"
```

---

## Debugging Tips

### Check if metrics are being collected

```bash
# Port-forward to gateway
kubectl port-forward -n voice-workflow svc/voice-gateway-gateway 8080:8080

# View raw metrics
curl http://localhost:8080/metrics

# Check specific metric
curl http://localhost:8080/metrics | grep voice_gateway_e2e_latency
```

### Check Prometheus targets

```bash
# Port-forward to Prometheus
kubectl port-forward -n prometheus svc/kube-prometheus-stack-prometheus 9090:9090

# Open browser: http://localhost:9090/targets
# Look for voice-gateway-monitor and dcgm-exporter targets
```

### Verify DCGM metrics

```bash
# Direct query to DCGM exporter
kubectl exec -n gpu-operator $(kubectl get pods -n gpu-operator -l app=nvidia-dcgm-exporter -o jsonpath='{.items[0].metadata.name}') -- wget -qO- localhost:9400/metrics | head -50
```

---

## Performance Impact

The metrics implementation is designed for **zero latency impact**:

| Component | Overhead | Notes |
|-----------|----------|-------|
| Timer measurements | ~1μs | `time.perf_counter()` |
| Histogram observation | ~5μs | Lock-free in-memory |
| Metrics HTTP server | 0 | Separate thread, separate port |
| Prometheus scrape | 0 | Doesn't affect gRPC |

Total overhead per request: **< 20μs** (negligible vs 500ms+ E2E latency)

