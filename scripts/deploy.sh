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

# Run the playbook
ansible-playbook -i inventory.ini playbook.yml "$@"

echo "==================================================================="
echo "✅ Deployment Complete! Visit http://localhost:30080 or http://localhost/"
echo "==================================================================="
