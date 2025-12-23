#!/bin/bash
set -e

NAMESPACE="voice-workflow"
RELEASE_NAME="riva-server"
CHART_PATH="voice-voice-workflow/helm/riva-api"

echo "=== Deploying NVIDIA Riva (ASR/TTS) from Local Chart ==="

# 1. Check Prerequisites
if [ -z "$NGC_API_KEY" ]; then
    echo "❌ Error: NGC_API_KEY environment variable is not set."
    exit 1
fi

if [ ! -d "$CHART_PATH" ]; then
    echo "❌ Error: Riva Chart not found at $CHART_PATH"
    echo "Please ensure you have placed the 'riva-api' folder in 'helm/'"
    exit 1
fi

# 2. Create Docker Registry Secret (if not exists)
# The chart also creates a secret if ngcCredentials.password is provided, but we can keep this for safety or remove if redundant.
# Based on the chart, 'imagepullsecret' is created if ngcCredentials.password is set.
echo "🔑 Ensuring Image Pull Secret..."
kubectl create secret docker-registry nvcr.io-secret \
    --docker-server=nvcr.io \
    --docker-username='$oauthtoken' \
    --docker-password=$NGC_API_KEY \
    -n $NAMESPACE \
    --dry-run=client -o yaml | kubectl apply -f -

# 3. Deploy Riva
echo "🚀 Installing Riva Helm Chart from $CHART_PATH..."

# Prepare keys as per documentation
# ngcCredentials.password should be the raw API Key
# modelDeployKey should be base64 encoded 'tlt_encode'
MODEL_DEPLOY_KEY=$(echo -n "tlt_encode" | base64 -w0)

helm upgrade --install $RELEASE_NAME $CHART_PATH \
    --namespace $NAMESPACE \
    --values voice-voice-workflow/k8s/infra/riva-values.yaml \
    --set ngcCredentials.password=$NGC_API_KEY \
    --set ngcCredentials.email="sagdesai@nvidia.com" \
    --set modelRepoGenerator.modelDeployKey=$MODEL_DEPLOY_KEY \
    --wait --timeout 30m

echo "✅ Riva Deployment Initiated."
echo "Note: The first deployment takes 20-40 minutes to download and optimize models."
echo "Monitor with: kubectl logs -n $NAMESPACE -l app.kubernetes.io/name=riva-api -f"
