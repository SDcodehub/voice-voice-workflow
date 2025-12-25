# Security Reference

Security features and best practices for the Voice Gateway.

## Container Security

### Non-Root Execution

The gateway runs as an unprivileged user:

| Setting | Value | Purpose |
|---------|-------|---------|
| User | `appuser` (UID 1000) | Non-root execution |
| Group | `appgroup` (GID 1000) | Group permissions |

### Pod Security Context

```yaml
securityContext:
  runAsNonRoot: true      # Prevent root execution
  runAsUser: 1000         # Run as appuser
  runAsGroup: 1000        # Run as appgroup
  fsGroup: 1000           # File system group
```

### Container Security Context

```yaml
securityContext:
  allowPrivilegeEscalation: false  # No sudo/setuid
  readOnlyRootFilesystem: true     # Immutable container
  capabilities:
    drop:
      - ALL                         # No Linux capabilities
```

### Security Model

```
┌─────────────────────────────────────────────────────────────────┐
│                     Pod Security Context                         │
│  runAsNonRoot: true │ runAsUser: 1000 │ fsGroup: 1000           │
├─────────────────────────────────────────────────────────────────┤
│                  Container Security Context                      │
│  readOnlyRootFilesystem: true │ allowPrivilegeEscalation: false │
│  capabilities: drop ALL                                          │
├─────────────────────────────────────────────────────────────────┤
│                      Writable Volumes                            │
│  /tmp (emptyDir) │ /home/appuser/.cache (emptyDir)              │
└─────────────────────────────────────────────────────────────────┘
```

## Writable Volumes

The container filesystem is read-only, but these directories are writable:

| Path | Type | Purpose |
|------|------|---------|
| `/tmp` | emptyDir | Python/gRPC temp files |
| `/home/appuser/.cache` | emptyDir | Python cache |

**Why needed**: gRPC and Python libraries require temp file creation for streaming operations.

## Secret Management

### Option 1: Helm-Created Secret (Dev/Test)

```yaml
gateway:
  secrets:
    create: true
    llmApiKey: "your-api-key"
```

⚠️ **Not recommended for production** - secrets visible in values.yaml

### Option 2: Existing Secret (Production)

```bash
# Create secret manually
kubectl create secret generic gateway-secrets \
  --from-literal=LLM_API_KEY=your-key \
  -n voice-workflow

# Reference in values.yaml
gateway:
  secrets:
    create: false
    existingSecret: "gateway-secrets"
```

✅ **Recommended** - secrets not in version control

### Option 3: External Secrets Operator (Enterprise)

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: gateway-secrets
spec:
  secretStoreRef:
    name: vault-backend
    kind: SecretStore
  target:
    name: gateway-secrets
  data:
    - secretKey: LLM_API_KEY
      remoteRef:
        key: voice-workflow/llm
        property: api_key
```

### Secret Flow

```
Option 1: Helm-created               Option 2: Existing Secret
┌─────────────────┐                 ┌─────────────────┐
│   values.yaml   │                 │ External Tool   │
│ secrets.create  │                 │ (Vault, kubectl)│
└────────┬────────┘                 └────────┬────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────┐                 ┌─────────────────┐
│  secret.yaml    │                 │   K8s Secret    │
│  (template)     │                 │  "my-secret"    │
└────────┬────────┘                 └────────┬────────┘
         │                                   │
         ▼                                   ▼
┌─────────────────────────────────────────────────────┐
│                    Gateway Pod                       │
│              envFrom: secretRef                      │
└─────────────────────────────────────────────────────┘
```

## Network Security

### Current State

| Feature | Status | Notes |
|---------|--------|-------|
| TLS | ❌ Not implemented | Use Ingress TLS termination |
| mTLS | ❌ Not implemented | Consider service mesh |
| Authentication | ❌ Not implemented | Use API gateway |

### Recommendations

1. **Use Ingress with TLS** for external access
2. **Network Policies** to restrict pod-to-pod traffic
3. **Service Mesh** (Istio/Linkerd) for mTLS

## Best Practices

### Do

- ✅ Use existing secrets in production
- ✅ Keep container image updated
- ✅ Use read-only filesystem
- ✅ Drop all capabilities
- ✅ Run as non-root

### Don't

- ❌ Put secrets in values.yaml for production
- ❌ Run as root
- ❌ Allow privilege escalation
- ❌ Use `:latest` tag in production
- ❌ Expose gRPC without TLS externally

## Auditing

### Check Security Settings

```bash
# Verify non-root
kubectl exec -n voice-workflow -l app=voice-gateway -- id
# Expected: uid=1000(appuser) gid=1000(appgroup)

# Verify read-only filesystem
kubectl exec -n voice-workflow -l app=voice-gateway -- touch /test
# Expected: touch: cannot touch '/test': Read-only file system

# Verify capabilities dropped
kubectl exec -n voice-workflow -l app=voice-gateway -- cat /proc/1/status | grep Cap
# CapBnd should be 0000000000000000
```

### Pod Security Standards

The gateway is compatible with:
- **Restricted** Pod Security Standard (most secure)
- **Baseline** Pod Security Standard
- **Privileged** Pod Security Standard

```bash
# Check if namespace enforces standards
kubectl get ns voice-workflow -o yaml | grep pod-security
```

