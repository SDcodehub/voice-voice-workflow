#!/bin/bash
set -e

NAMESPACE="voice-workflow"
RELEASE_NAME="voice-gateway"
CHART_PATH="voice-voice-workflow/helm/voice-workflow"

echo "=== Deploying Voice Gateway ==="

# 1. Deploy Gateway
echo "🚀 Installing Gateway Helm Chart..."

# Ensure dependencies are up to date
helm repo add nvidia https://helm.ngc.nvidia.com/nvidia || true
helm dependency update $CHART_PATH

helm upgrade --install $RELEASE_NAME $CHART_PATH \
    --namespace $NAMESPACE \
    --wait --timeout 5m

echo "✅ Gateway Deployment Initiated."
echo "Monitor with: kubectl logs -n $NAMESPACE -l app=voice-gateway -f"

