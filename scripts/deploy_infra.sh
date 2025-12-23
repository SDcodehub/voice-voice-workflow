#!/bin/bash
set -e

# Configuration
NAMESPACE="voice-workflow"
NODE_HOSTNAME="node001"
LOCAL_PATH="/mnt/nim-models/voice-workflow"

echo "=== Voice-to-Voice Workflow Infrastructure Deployment ==="

# 1. Prerequisites Check
if [ -z "$NGC_API_KEY" ]; then
    echo "❌ Error: NGC_API_KEY environment variable is not set."
    echo "Please export it: export NGC_API_KEY='nvapi-...'"
    exit 1
fi

echo "✅ NGC_API_KEY found"

# 2. Node Preparation (Warning only)
echo "⚠️  Ensure directory exists on $NODE_HOSTNAME: $LOCAL_PATH"
echo "Run this on the node if not done:"
echo "sudo mkdir -p $LOCAL_PATH && sudo chmod 777 $LOCAL_PATH"
echo "Press Enter to continue..."
read

# 3. Deploy Namespace & Storage
echo "🚀 Deploying Namespace & Storage..."
kubectl apply -f k8s/infra/00-namespace-pvc.yaml

# 4. Create Secrets
echo "🔑 Creating Secrets..."
# NGC API Secret
kubectl create secret generic ngc-api \
    --from-literal=NGC_API_KEY=$NGC_API_KEY \
    -n $NAMESPACE \
    --dry-run=client -o yaml | kubectl apply -f -

# Image Pull Secret
kubectl create secret docker-registry nvcrimagepullsecret \
    --docker-server=nvcr.io \
    --docker-username='$oauthtoken' \
    --docker-password=$NGC_API_KEY \
    -n $NAMESPACE \
    --dry-run=client -o yaml | kubectl apply -f -

# 5. Deploy NIM
echo "🤖 Deploying LLM NIM..."
kubectl apply -f k8s/infra/nim-llm.yaml

# 6. Monitor
echo "✅ Deployment initiated."
echo "Waiting for NIM to be ready (this can take 5-15 mins)..."
kubectl -n $NAMESPACE rollout status deployment/meta-llama3-8b-instruct --timeout=1200s

echo "🎉 NIM is Ready!"
echo "Service URL: http://meta-llama3-8b-instruct.$NAMESPACE.svc.cluster.local:8000/v1"
