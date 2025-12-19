#!/bin/bash
# Voice Workflow Deployment Script
set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=== Voice-to-Voice Workflow Deployment ===${NC}"

# Check prerequisites
check_prerequisites() {
    echo -e "${YELLOW}Checking prerequisites...${NC}"
    
    if ! command -v kubectl &> /dev/null; then
        echo -e "${RED}kubectl not found. Please install kubectl.${NC}"
        exit 1
    fi
    
    if ! command -v helm &> /dev/null; then
        echo -e "${RED}helm not found. Please install helm.${NC}"
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        echo -e "${RED}docker not found. Please install docker.${NC}"
        exit 1
    fi
    
    echo -e "${GREEN}All prerequisites met.${NC}"
}

# Build Docker images
build_images() {
    echo -e "${YELLOW}Building Docker images...${NC}"
    
    local REGISTRY=${DOCKER_REGISTRY:-""}
    local TAG=${IMAGE_TAG:-"latest"}
    
    # Build each service
    for service in voice-gateway asr-service llm-service tts-service; do
        echo "Building $service..."
        docker build -t ${REGISTRY}${service}:${TAG} ./services/${service}/
    done
    
    echo -e "${GREEN}Docker images built successfully.${NC}"
}

# Push Docker images
push_images() {
    echo -e "${YELLOW}Pushing Docker images...${NC}"
    
    local REGISTRY=${DOCKER_REGISTRY:-""}
    local TAG=${IMAGE_TAG:-"latest"}
    
    if [ -z "$REGISTRY" ]; then
        echo -e "${YELLOW}DOCKER_REGISTRY not set. Skipping push.${NC}"
        return
    fi
    
    for service in voice-gateway asr-service llm-service tts-service; do
        echo "Pushing $service..."
        docker push ${REGISTRY}${service}:${TAG}
    done
    
    echo -e "${GREEN}Docker images pushed successfully.${NC}"
}

# Deploy using Helm
deploy_helm() {
    echo -e "${YELLOW}Deploying with Helm...${NC}"
    
    local NAMESPACE=${NAMESPACE:-"voice-workflow"}
    local RELEASE_NAME=${RELEASE_NAME:-"voice-workflow"}
    local VALUES_FILE=${VALUES_FILE:-"helm/voice-workflow/values.yaml"}
    
    # Check if NGC API key is set
    if [ -z "$NGC_API_KEY" ]; then
        echo -e "${RED}NGC_API_KEY not set. Required for Riva and NIM.${NC}"
        echo "Please set NGC_API_KEY environment variable."
        exit 1
    fi
    
    # Add Bitnami repo for Redis
    helm repo add bitnami https://charts.bitnami.com/bitnami 2>/dev/null || true
    helm repo update
    
    # Create namespace if not exists
    kubectl create namespace ${NAMESPACE} --dry-run=client -o yaml | kubectl apply -f -
    
    # Deploy
    helm upgrade --install ${RELEASE_NAME} ./helm/voice-workflow \
        --namespace ${NAMESPACE} \
        --values ${VALUES_FILE} \
        --set ngc.apiKey=${NGC_API_KEY} \
        --set voiceGateway.image.repository=${DOCKER_REGISTRY:-""}voice-gateway \
        --set voiceGateway.image.tag=${IMAGE_TAG:-"latest"} \
        --set asrService.image.repository=${DOCKER_REGISTRY:-""}asr-service \
        --set asrService.image.tag=${IMAGE_TAG:-"latest"} \
        --set llmService.image.repository=${DOCKER_REGISTRY:-""}llm-service \
        --set llmService.image.tag=${IMAGE_TAG:-"latest"} \
        --set ttsService.image.repository=${DOCKER_REGISTRY:-""}tts-service \
        --set ttsService.image.tag=${IMAGE_TAG:-"latest"} \
        --wait --timeout 15m
    
    echo -e "${GREEN}Deployment completed successfully.${NC}"
}

# Deploy using Kustomize
deploy_kustomize() {
    echo -e "${YELLOW}Deploying with Kustomize...${NC}"
    
    local OVERLAY=${OVERLAY:-"base"}
    
    kubectl apply -k k8s/${OVERLAY}/
    
    echo -e "${GREEN}Deployment completed.${NC}"
}

# Get deployment status
status() {
    echo -e "${YELLOW}Getting deployment status...${NC}"
    
    local NAMESPACE=${NAMESPACE:-"voice-workflow"}
    
    echo ""
    echo "=== Pods ==="
    kubectl get pods -n ${NAMESPACE}
    
    echo ""
    echo "=== Services ==="
    kubectl get svc -n ${NAMESPACE}
    
    echo ""
    echo "=== Ingress ==="
    kubectl get ingress -n ${NAMESPACE}
    
    echo ""
    echo "=== HPA ==="
    kubectl get hpa -n ${NAMESPACE}
}

# Cleanup
cleanup() {
    echo -e "${YELLOW}Cleaning up deployment...${NC}"
    
    local NAMESPACE=${NAMESPACE:-"voice-workflow"}
    local RELEASE_NAME=${RELEASE_NAME:-"voice-workflow"}
    
    helm uninstall ${RELEASE_NAME} --namespace ${NAMESPACE} || true
    kubectl delete namespace ${NAMESPACE} || true
    
    echo -e "${GREEN}Cleanup completed.${NC}"
}

# Print usage
usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  build       Build Docker images"
    echo "  push        Push Docker images to registry"
    echo "  deploy      Deploy using Helm (default)"
    echo "  kustomize   Deploy using Kustomize"
    echo "  status      Get deployment status"
    echo "  cleanup     Remove deployment"
    echo "  all         Build, push, and deploy"
    echo ""
    echo "Environment variables:"
    echo "  NGC_API_KEY      - NVIDIA NGC API key (required)"
    echo "  DOCKER_REGISTRY  - Docker registry prefix (optional)"
    echo "  IMAGE_TAG        - Image tag (default: latest)"
    echo "  NAMESPACE        - Kubernetes namespace (default: voice-workflow)"
    echo "  RELEASE_NAME     - Helm release name (default: voice-workflow)"
    echo "  VALUES_FILE      - Helm values file (default: helm/voice-workflow/values.yaml)"
}

# Main
main() {
    check_prerequisites
    
    case "${1:-deploy}" in
        build)
            build_images
            ;;
        push)
            push_images
            ;;
        deploy)
            deploy_helm
            ;;
        kustomize)
            deploy_kustomize
            ;;
        status)
            status
            ;;
        cleanup)
            cleanup
            ;;
        all)
            build_images
            push_images
            deploy_helm
            status
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            echo -e "${RED}Unknown command: $1${NC}"
            usage
            exit 1
            ;;
    esac
}

main "$@"

