#!/usr/bin/env bash
set -e

echo "==================================================================="
echo "🚀 Starting Deployment of Qwen 2.5 3B Platform on Kubernetes"
echo "==================================================================="

# Check for Ansible
if ! command -v ansible-playbook &> /dev/null; then
    echo "❌ Error: ansible-playbook is not installed or not in PATH."
    exit 1
fi

# Ensure ~/.kube/config is available (auto-detect Windows Docker Desktop if in WSL)
if [ ! -f "$HOME/.kube/config" ] && [ -z "$KUBECONFIG" ]; then
    WIN_KUBECONFIG=$(ls -d /mnt/c/Users/*/.kube/config 2>/dev/null | head -n 1 || true)
    if [ -n "$WIN_KUBECONFIG" ] && [ -f "$WIN_KUBECONFIG" ]; then
        echo "🔗 Linking Windows Docker Desktop kubeconfig from $WIN_KUBECONFIG..."
        mkdir -p "$HOME/.kube"
        ln -sf "$WIN_KUBECONFIG" "$HOME/.kube/config"
    fi
fi

# Run the playbook
ansible-playbook -i inventory.ini playbook.yml "$@"

echo "==================================================================="
echo "✅ Deployment Complete! Visit http://localhost:30080 or http://localhost/"
echo "==================================================================="
