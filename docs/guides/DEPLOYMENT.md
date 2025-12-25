# Deployment Guide

Complete guide for deploying the Voice-to-Voice Workflow on Kubernetes.

## Prerequisites

- **Kubernetes**: Cluster with NVIDIA GPU support
- **Helm**: v3.x installed
- **NGC API Key**: Get from [NGC](https://ngc.nvidia.com/)
- **uv**: Python package manager (for building)

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Export NGC API Key
export NGC_API_KEY='nvapi-...'
```

## Deployment Steps

### Step 1: Deploy Infrastructure

Deploy namespace, PVCs, and LLM NIM:

```bash
./scripts/deploy_infra.sh
```

This creates:
- `voice-workflow` namespace
- Persistent volumes for model caching
- NGC secrets for image pulling
- LLM NIM deployment (Llama 3.1 8B)

**Wait time**: 5-15 minutes for NIM to download and start.

### Step 2: Deploy Riva (ASR/TTS)

```bash
./scripts/deploy_riva.sh
```

This deploys:
- Riva ASR (Parakeet 0.6B)
- Riva TTS (FastPitch + HiFiGAN)

**Wait time**: 20-40 minutes (first deployment downloads and optimizes models).

### Step 3: Build and Deploy Gateway

```bash
# Build container image
./scripts/build_gateway.sh

# Deploy to Kubernetes
./scripts/deploy_gateway.sh
```

### Step 4: Verify Deployment

```bash
# Check all pods
kubectl get pods -n voice-workflow

# Expected output:
# NAME                                       READY   STATUS    AGE
# meta-llama3-8b-instruct-xxx                1/1     Running   ...
# riva-api-xxx                               1/1     Running   ...
# tritongroup0-xxx                           1/1     Running   ...
# voice-gateway-gateway-xxx                  1/1     Running   ...

# Check gateway logs
kubectl logs -n voice-workflow -l app=voice-gateway
```

## Configuration

### Runtime Configuration (No Rebuild)

Edit `helm/voice-workflow/values.yaml`:

```yaml
config:
  llm:
    temperature: "0.7"
    systemPrompt: "You are a helpful assistant..."
```

Apply changes:
```bash
./scripts/deploy_gateway.sh
kubectl rollout restart deployment/voice-gateway-gateway -n voice-workflow
```

### Using Secrets

**Option A: Reference existing secret**
```bash
kubectl create secret generic gateway-secrets \
  --from-literal=LLM_API_KEY=your-key \
  -n voice-workflow

helm upgrade voice-gateway helm/voice-workflow \
  --set gateway.secrets.existingSecret=gateway-secrets \
  -n voice-workflow
```

**Option B: Helm-created secret (dev only)**
```yaml
gateway:
  secrets:
    create: true
    llmApiKey: "your-key"
```

## Kubernetes Resources

| Resource | Name | Purpose |
|----------|------|---------|
| Deployment | `voice-gateway-gateway` | Gateway pods |
| Service | `voice-gateway-gateway` | ClusterIP (50051) |
| ConfigMap | `voice-gateway-config` | Runtime config |
| PDB | `voice-gateway-gateway-pdb` | Disruption protection |
| Secret | `voice-gateway-secrets` | Credentials (optional) |

## Resource Requirements

| Component | CPU Request | CPU Limit | Memory Request | Memory Limit | GPU |
|-----------|-------------|-----------|----------------|--------------|-----|
| Gateway | 50m | 500m | 128Mi | 512Mi | - |
| LLM NIM | - | - | - | - | 1 |
| Riva | - | - | - | - | 1 |

## Health Checks

| Probe | Type | Port | Delay | Period |
|-------|------|------|-------|--------|
| Liveness | TCP | 50051 | 15s | 30s |
| Readiness | TCP | 50051 | 5s | 10s |

## Troubleshooting

### Pods not starting

```bash
# Check pod events
kubectl describe pod -n voice-workflow -l app=voice-gateway

# Check resource availability
kubectl top nodes
```

### Gateway can't connect to Riva/NIM

```bash
# Verify services exist
kubectl get svc -n voice-workflow

# Test connectivity from gateway pod
kubectl exec -n voice-workflow -l app=voice-gateway -- \
  python -c "import socket; s=socket.socket(); s.connect(('riva-api', 50051))"
```

### PDB blocking drains

```bash
# Check PDB status
kubectl get pdb -n voice-workflow

# If needed, scale up before drain
kubectl scale deployment/voice-gateway-gateway --replicas=2 -n voice-workflow
```

## Useful Commands

```bash
# View all resources
kubectl get all -n voice-workflow

# Watch pod logs
kubectl logs -n voice-workflow -l app=voice-gateway -f

# Check ConfigMap
kubectl get configmap voice-gateway-config -n voice-workflow -o yaml

# Restart gateway
kubectl rollout restart deployment/voice-gateway-gateway -n voice-workflow

# Scale gateway
kubectl scale deployment/voice-gateway-gateway --replicas=2 -n voice-workflow
```

