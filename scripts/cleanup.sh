#!/usr/bin/env bash
set -e

NAMESPACE="${1:-llm-platform}"

echo "⚠️  Deleting namespace '$NAMESPACE' and all associated resources..."
kubectl delete namespace "$NAMESPACE" --ignore-not-found=true

echo "✅ Cleanup complete."
