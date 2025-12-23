#!/bin/bash
set -e

IMAGE_NAME="voice-gateway"
TAG="latest"
# If running on local k8s (e.g. standard cluster), we usually need to push to a registry.
# Or if using containerd directly on the node, we can import it.
# For this environment, we will assume local build is sufficient or we can push to a local registry if available.
# To keep it simple, we'll build and tag.

echo "=== Building Voice Gateway ==="

# Navigate to service directory
cd "$(dirname "$0")/../services/voice-gateway"

# Build Docker Image
echo "🐳 Building Docker image..."
# Check for podman if docker is missing
if command -v docker >/dev/null 2>&1; then
    CMD=docker
elif command -v podman >/dev/null 2>&1; then
    CMD=podman
else
    echo "❌ No docker or podman found."
    exit 1
fi

$CMD build -t $IMAGE_NAME:$TAG .

echo "✅ Build Complete: $IMAGE_NAME:$TAG"

# Check if we have a registry
if [ -n "$REGISTRY" ]; then
    echo "Pushing to registry: $REGISTRY"
    $CMD tag $IMAGE_NAME:$TAG $REGISTRY/$IMAGE_NAME:$TAG
    $CMD push $REGISTRY/$IMAGE_NAME:$TAG
else
    echo "⚠️  No REGISTRY env var set. Image is only local."
    echo "If you are using a multi-node cluster, you MUST push this image to a registry."
    echo "Example: export REGISTRY=localhost:5000"
fi

