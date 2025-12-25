#!/bin/bash
# =============================================================================
# Setup Observability for Voice Gateway
# =============================================================================
# This script:
#   1. Verifies Prometheus & Grafana are running
#   2. Creates ServiceMonitor for voice-gateway
#   3. Verifies metrics are being scraped
#   4. Provides Grafana dashboard import instructions
#
# Prerequisites:
#   - kube-prometheus-stack deployed
#   - Voice Gateway deployed in voice-workflow namespace
# =============================================================================

set -e

NAMESPACE="voice-workflow"
PROMETHEUS_NS="prometheus"

echo "============================================================"
echo "🔍 OBSERVABILITY SETUP FOR VOICE GATEWAY"
echo "============================================================"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Check Prometheus Stack
# -----------------------------------------------------------------------------
echo "📍 Step 1: Checking Prometheus Stack..."
echo ""

# Check Prometheus pods
PROM_PODS=$(kubectl get pods -n $PROMETHEUS_NS -l app.kubernetes.io/name=prometheus 2>/dev/null | grep -c Running || echo "0")
if [ "$PROM_PODS" -gt 0 ]; then
    echo "   ✅ Prometheus is running ($PROM_PODS pods)"
else
    echo "   ❌ Prometheus not found in namespace '$PROMETHEUS_NS'"
    echo "   Run: helm install prometheus prometheus-community/kube-prometheus-stack -n prometheus"
    exit 1
fi

# Check Grafana
GRAFANA_PODS=$(kubectl get pods -n $PROMETHEUS_NS -l app.kubernetes.io/name=grafana 2>/dev/null | grep -c Running || echo "0")
if [ "$GRAFANA_PODS" -gt 0 ]; then
    echo "   ✅ Grafana is running"
else
    echo "   ⚠️  Grafana not found (optional but recommended)"
fi

# Check DCGM Exporter
DCGM_PODS=$(kubectl get pods -n gpu-operator -l app=nvidia-dcgm-exporter 2>/dev/null | grep -c Running || echo "0")
if [ "$DCGM_PODS" -gt 0 ]; then
    echo "   ✅ DCGM Exporter is running (GPU metrics available)"
else
    echo "   ⚠️  DCGM Exporter not found (GPU metrics won't be available)"
fi

echo ""

# -----------------------------------------------------------------------------
# Step 2: Check Voice Gateway
# -----------------------------------------------------------------------------
echo "📍 Step 2: Checking Voice Gateway..."
echo ""

# Check if voice-gateway is running
GW_PODS=$(kubectl get pods -n $NAMESPACE -l app=voice-gateway 2>/dev/null | grep -c Running || echo "0")
if [ "$GW_PODS" -gt 0 ]; then
    echo "   ✅ Voice Gateway is running ($GW_PODS pods)"
else
    echo "   ❌ Voice Gateway not found in namespace '$NAMESPACE'"
    echo "   Run: ./scripts/deploy_gateway.sh"
    exit 1
fi

# Check if metrics port is exposed
METRICS_PORT=$(kubectl get svc -n $NAMESPACE voice-gateway-gateway -o jsonpath='{.spec.ports[?(@.name=="metrics")].port}' 2>/dev/null || echo "")
if [ -n "$METRICS_PORT" ]; then
    echo "   ✅ Metrics port exposed: $METRICS_PORT"
else
    echo "   ❌ Metrics port not exposed in service"
    echo "   Redeploy with: ./scripts/deploy_gateway.sh"
    exit 1
fi

echo ""

# -----------------------------------------------------------------------------
# Step 3: Create/Update ServiceMonitor
# -----------------------------------------------------------------------------
echo "📍 Step 3: Creating ServiceMonitor..."
echo ""

# Apply ServiceMonitor
kubectl apply -f k8s/observability/voice-gateway-servicemonitor.yaml

echo "   ✅ ServiceMonitor created in '$PROMETHEUS_NS' namespace"
echo ""

# -----------------------------------------------------------------------------
# Step 4: Verify ServiceMonitor
# -----------------------------------------------------------------------------
echo "📍 Step 4: Verifying ServiceMonitor..."
echo ""

sleep 3

# List ServiceMonitors
echo "   ServiceMonitors for voice-gateway:"
kubectl get servicemonitors -A | grep -E "NAME|voice" || echo "   None found"
echo ""

# -----------------------------------------------------------------------------
# Step 5: Test Metrics Endpoint
# -----------------------------------------------------------------------------
echo "📍 Step 5: Testing Metrics Endpoint..."
echo ""

# Port-forward and test
echo "   Starting port-forward to test metrics..."
kubectl port-forward -n $NAMESPACE svc/voice-gateway-gateway 8080:8080 &
PF_PID=$!
sleep 3

# Test metrics endpoint
if curl -s http://localhost:8080/metrics | head -20 > /dev/null 2>&1; then
    echo "   ✅ Metrics endpoint is working!"
    echo ""
    echo "   Sample metrics:"
    curl -s http://localhost:8080/metrics | grep -E "^voice_gateway" | head -5
else
    echo "   ❌ Cannot reach metrics endpoint"
fi

# Cleanup port-forward
kill $PF_PID 2>/dev/null || true

echo ""

# -----------------------------------------------------------------------------
# Step 6: Instructions
# -----------------------------------------------------------------------------
echo "============================================================"
echo "📊 NEXT STEPS"
echo "============================================================"
echo ""
echo "1. Wait ~30 seconds for Prometheus to discover the target"
echo ""
echo "2. Verify in Prometheus UI:"
echo "   kubectl port-forward -n prometheus svc/kube-prometheus-stack-prometheus 9090:9090"
echo "   Open: http://localhost:9090/targets"
echo "   Look for: voice-gateway-monitor"
echo ""
echo "3. Import Grafana Dashboards:"
echo "   kubectl port-forward -n prometheus svc/kube-prometheus-stack-grafana 3000:80"
echo "   Open: http://localhost:3000 (admin/admin123 or prom-operator)"
echo ""
echo "   a) GPU Metrics: Import Dashboard ID 12239"
echo "   b) Voice Gateway: Import from helm/voice-workflow/dashboards/voice-gateway-dashboard.json"
echo ""
echo "4. Test PromQL queries in Prometheus:"
echo "   - voice_gateway_e2e_latency_seconds_bucket"
echo "   - voice_gateway_requests_total"
echo "   - DCGM_FI_DEV_GPU_UTIL"
echo ""
echo "============================================================"
echo "✅ SETUP COMPLETE"
echo "============================================================"

