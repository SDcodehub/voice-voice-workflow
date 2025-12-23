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

# 2. Create Secrets Manually
# The Helm chart might not create all necessary secrets, or might create them incorrectly.
# We manually create them to ensure reliability.

echo "🔑 Creating Secrets..."

# Image Pull Secret (for pulling containers)
kubectl create secret docker-registry nvcr.io-secret \
    --docker-server=nvcr.io \
    --docker-username='$oauthtoken' \
    --docker-password=$NGC_API_KEY \
    -n $NAMESPACE \
    --dry-run=client -o yaml | kubectl apply -f -

# Model Pull Secret (for init container to download models)
kubectl create secret generic modelpullsecret \
    --from-literal=apikey=$NGC_API_KEY \
    -n $NAMESPACE \
    --dry-run=client -o yaml | kubectl apply -f -

# Model Deploy Key (for decrypting models)
# The chart expects this to be base64 encoded if passed via values, but creating it manually avoids chart issues.
# We create it with the RAW value 'tlt_encode' which kubectl will encode.
kubectl create secret generic riva-model-deploy-key \
    --from-literal=key=tlt_encode \
    -n $NAMESPACE \
    --dry-run=client -o yaml | kubectl apply -f -


# 3. Deploy Riva
echo "🚀 Installing Riva Helm Chart from $CHART_PATH..."

# We pass dummy/empty values for the secrets in the Helm command because we already created them.
# This prevents the chart from trying to create malformed secrets.
# We still set modelRepoGenerator.modelDeployKey to satisfy any required checks, but point to our existing secret.

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
