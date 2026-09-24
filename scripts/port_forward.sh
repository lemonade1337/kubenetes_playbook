#!/usr/bin/env bash
# Port-forwarding helper for Docker Desktop multi-node clusters
set -e

NAMESPACE="llm-platform"

echo "==================================================================="
echo "🌐 Starting Port Forwarding for Qwen 2.5 3B AI Platform"
echo "==================================================================="
echo "• Web Portal & Chat: http://localhost:8000  (or http://localhost:30080)"
echo "• Keycloak Console:  http://localhost:8080/auth (or http://localhost:30090/auth)"
echo "• Qwen LLM Engine:   http://localhost:11434"
echo "==================================================================="
echo "Press Ctrl+C to stop port forwarding."

# Start background port forwards
kubectl port-forward -n "$NAMESPACE" svc/api-gateway-service 8000:8000 30080:8000 &
PID_GW=$!

kubectl port-forward -n "$NAMESPACE" svc/keycloak-service 8080:8080 30090:8080 &
PID_KC=$!

kubectl port-forward -n "$NAMESPACE" svc/qwen-llm-service 11434:11434 30100:11434 &
PID_QW=$!

trap "kill $PID_GW $PID_KC $PID_QW 2>/dev/null; exit" SIGINT SIGTERM

wait
