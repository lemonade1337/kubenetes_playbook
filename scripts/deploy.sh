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

EXTRA_ARGS=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --env)
            ENV_NAME="$2"
            shift 2
            case "$ENV_NAME" in
                macos|mac)
                    EXTRA_ARGS+=("-e" "@vars/macos.yml")
                    ;;
                linux)
                    EXTRA_ARGS+=("-e" "@vars/linux.yml")
                    ;;
                aws|eks)
                    EXTRA_ARGS+=("-e" "@vars/aws-eks.yml")
                    ;;
                azure|aks)
                    EXTRA_ARGS+=("-e" "@vars/azure-aks.yml")
                    ;;
                *)
                    if [ -f "vars/${ENV_NAME}.yml" ]; then
                        EXTRA_ARGS+=("-e" "@vars/${ENV_NAME}.yml")
                    else
                        echo "⚠️  Warning: Unknown environment '$ENV_NAME'. Passing as-is."
                    fi
                    ;;
            esac
            ;;
        *)
            EXTRA_ARGS+=("$1")
            shift
            ;;
    esac
done

# Run the playbook
ansible-playbook -i inventory.ini playbook.yml "${EXTRA_ARGS[@]}"

echo "==================================================================="
echo "✅ Deployment Complete!"
echo "👉 Run './scripts/port_forward.sh' to access the services on localhost"
echo "🌐 Web Portal & Chat: http://localhost:8000"
echo "==================================================================="
