# 🚀 High-Availability Qwen 2.5 3B Platform on Kubernetes

A production-ready Ansible playbook and Kubernetes architecture designed for **Docker Desktop on Windows** (with 2 worker nodes). This platform deploys a scalable **Qwen 2.5 3B** LLM inference service, **Keycloak OIDC Authentication**, an **OpenAI-Compatible API Gateway**, and a **Token Management Web Portal**.

---

## 🏗️ Architecture Overview

```mermaid
flowchart TD
    subgraph Clients["Clients & Users"]
        Browser["🌐 Web Browser / Portal"]
        APIClient["💻 OpenAI SDK / cURL / Apps"]
    end

    subgraph IngressLayer["Ingress & Routing"]
        Ingress["🔀 NGINX Ingress / NodePorts (30080, 30090, 30100)"]
    end

    subgraph Node1["Kubernetes Worker Node 1"]
        GW1["🛡️ API Gateway & Portal (Pod 1)"]
        KC1["🔐 Keycloak SSO (Pod 1)"]
        PG1["💾 PostgreSQL HA (Pod 1)"]
        QW1["⚡ Qwen 2.5 3B (Pod 1 - Active)"]
    end

    subgraph Node2["Kubernetes Worker Node 2"]
        GW2["🛡️ API Gateway & Portal (Pod 2)"]
        KC2["🔐 Keycloak SSO (Pod 2)"]
        PG2["💾 PostgreSQL HA (Pod 2)"]
        QW2["⚡ Qwen 2.5 3B (Auto-scaled Pods 2-6)"]
    end

    subgraph Scaling["Autoscaling Engine"]
        HPA["📈 HorizontalPodAutoscaler (HPA)<br/>Min: 1 Pod &bull; Max: 6 Pods"]
        Metrics["📊 Kubernetes Metrics Server"]
    end

    Browser -->|HTTP UI / SSO| Ingress
    APIClient -->|Bearer API Key| Ingress

    Ingress --> GW1
    Ingress --> GW2
    Ingress --> KC1
    Ingress --> KC2

    GW1 -->|Validate Auth & Deduct Tokens| PG1
    GW2 -->|Validate Auth & Deduct Tokens| PG2
    GW1 -->|OIDC Token Exchange| KC1
    GW2 -->|OIDC Token Exchange| KC2

    GW1 -->|Forward /v1/chat/completions| QW1
    GW2 -->|Forward /v1/chat/completions| QW2

    Metrics -->|CPU & Load Signals| HPA
    HPA -->|Spawns New Pods When in Use| QW1
    HPA -->|Spawns New Pods When in Use| QW2
```

---

## 🌟 Key Features

1. **Qwen 2.5 3B Dynamic Autoscaling (1 to 6 Pods)**:
   - Starts at **1 replica** to conserve resources.
   - Automatically detects active inference load and spawns up to **6 replicas** when existing instances are in use.
   - Exposes standard **OpenAI-compatible endpoints** (`/v1/chat/completions`, `/v1/models`).

2. **Full Redundancy & High Availability**:
   - Deployed across **2 Kubernetes worker nodes**.
   - **PostgreSQL Database**: Redundant 2-replica StatefulSet with persistent storage.
   - **Keycloak OIDC Server**: Redundant 2-replica deployment with pod anti-affinity.
   - **API Gateway & Web Portal**: Redundant 2-replica deployment with pod anti-affinity.

3. **Keycloak Authentication & Pre-provisioned Accounts**:
   - Realm: `llm-platform` with OIDC client `token-portal`.
   - **Every user is automatically granted 100,000 initial tokens**.
   - Pre-configured accounts:
     - 👑 **Admin**: `admin` / `AdminPass123!` (Role: `admin`, Pre-seeded Key: `sk-admin-master-key-2026`)
     - 👤 **User 1**: `user1` / `User1Pass123!` (Role: `user`, Pre-seeded Key: `sk-user1-secret-key-2026`)
     - 👤 **User 2**: `user2` / `User2Pass123!` (Role: `user`, Pre-seeded Key: `sk-user2-secret-key-2026`)
     - 👤 **User 3**: `user3` / `User3Pass123!` (Role: `user`, Pre-seeded Key: `sk-user3-secret-key-2026`)

4. **Token Management & Interactive Web Chat Portal**:
   - **Interactive Qwen 2.5 3B Chat Field**: Chat in real-time directly on the web portal with markdown formatting, syntax highlighting, conversation history, and quick prompts.
   - **User Dashboard**: View real-time remaining tokens, monthly quota progress, API keys (reveal, copy, regenerate), and endpoint URLs.
   - **Live Token Metering**: Real-time atomic token deduction in PostgreSQL per request and immediate updates to balance cards.
   - **Admin Console**: View all user balances, grant extra tokens (e.g. +50,000) to any user, configure monthly recurring quotas, and reset balances.

---

## 📁 Repository Structure

```
.
├── ansible.cfg                          # Ansible configuration
├── inventory.ini                        # Inventory targeting Kubernetes
├── playbook.yml                         # Master deployment playbook
├── site.yml                             # Playbook entrypoint alias
├── group_vars/
│   └── all.yml                          # Global configuration variables
├── roles/
│   ├── prerequisites/                   # Namespace and Metrics Server
│   ├── postgres/                        # PostgreSQL HA StatefulSet (2 replicas)
│   ├── keycloak/                        # Keycloak HA OIDC Server (2 replicas)
│   ├── qwen_llm/                        # Qwen 2.5 3B Service & HPA (1 to 6 replicas)
│   ├── api_gateway_portal/              # FastAPI Portal, Token Metering, & UI (2 replicas)
│   └── ingress/                         # Ingress rules and NodePort routing
├── scripts/
│   ├── deploy.sh                        # One-click deployment script
│   ├── test_api.py                      # Automated test suite
│   ├── load_test_autoscale.py           # Concurrency autoscaling load tester
│   └── cleanup.sh                       # Teardown script
└── README.md
```

---

## 🚀 Quickstart & Deployment

### 1. Prerequisites
- **Docker Desktop on Windows** with **Kubernetes enabled** (2 worker nodes configured).
- Python 3 with `ansible` and `kubernetes` packages installed.

Ensure your `KUBECONFIG` points to your Docker Desktop Kubernetes cluster:
```bash
# If running inside WSL2:
export KUBECONFIG=/mnt/c/Users/<YourWindowsUser>/.kube/config
# Or default:
kubectl get nodes
```

### 2. Deploy the Entire Platform
Run the deployment script or execute Ansible directly:

```bash
# Option A: One-click script
./scripts/deploy.sh

# Option B: Direct Ansible invocation
ansible-playbook -i inventory.ini playbook.yml
```

---

## 🌐 Web Portal & Service URLs

Once deployed, access the services via Ingress or direct NodePorts on Docker Desktop:

| Service | Ingress URL | Direct NodePort URL | Default Credentials |
| :--- | :--- | :--- | :--- |
| **Token Portal & Web UI** | `http://localhost/` | `http://localhost:30080` | Use any user below |
| **Keycloak Admin Console** | `http://localhost/auth` | `http://localhost:30090/auth` | `admin` / `KeycloakMasterAdmin2026!` |
| **OpenAI API Gateway** | `http://localhost/v1` | `http://localhost:30080/v1` | `Bearer <API_KEY>` |

---

## 🔑 Pre-Configured Users & Initial Balances

| Username | Password | Role | Initial Tokens | Pre-Seeded API Key |
| :--- | :--- | :--- | :--- | :--- |
| `admin` | `AdminPass123!` | Admin + User | 100,000 | `sk-admin-master-key-2026` |
| `user1` | `User1Pass123!` | Standard User | 100,000 | `sk-user1-secret-key-2026` |
| `user2` | `User2Pass123!` | Standard User | 100,000 | `sk-user2-secret-key-2026` |
| `user3` | `User3Pass123!` | Standard User | 100,000 | `sk-user3-secret-key-2026` |

---

## 💻 Making OpenAI API Requests

### 1. cURL
```bash
curl -X POST http://localhost:30080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer sk-user1-secret-key-2026" \
  -d '{
    "model": "qwen2.5:3b",
    "messages": [
      {"role": "system", "content": "You are a concise AI assistant."},
      {"role": "user", "content": "Explain Kubernetes in one sentence."}
    ],
    "temperature": 0.7
  }'
```

### 2. Python (Official OpenAI SDK)
```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:30080/v1",
    api_key="sk-user1-secret-key-2026"
)

response = client.chat.completions.create(
    model="qwen2.5:3b",
    messages=[
        {"role": "system", "content": "You are a fast AI assistant."},
        {"role": "user", "content": "Write a python fibonacci function."}
    ]
)

print(response.choices[0].message.content)
print(f"Total tokens used: {response.usage.total_tokens}")
```

### 3. Node.js (OpenAI SDK)
```javascript
import OpenAI from 'openai';

const openai = new OpenAI({
  baseURL: 'http://localhost:30080/v1',
  apiKey: 'sk-user1-secret-key-2026',
});

async function main() {
  const completion = await openai.chat.completions.create({
    model: 'qwen2.5:3b',
    messages: [{ role: 'user', content: 'Hello Qwen 2.5 3B!' }],
  });
  console.log(completion.choices[0].message.content);
}
main();
```

---

## 🧪 Testing & Autoscaling Verification

### 1. Automated Functional Test
Verify health, token deduction, and admin operations:
```bash
python3 scripts/test_api.py http://localhost:30080
```

### 2. Concurrency Autoscaling Demonstration (1 to 6 Pods)
To watch the cluster scale from 1 pod up to 6 pods under concurrent load:

1. In Terminal 1, watch the pods and HPA:
```bash
kubectl get hpa,pods -n llm-platform -w
```

2. In Terminal 2, launch concurrent requests:
```bash
python3 scripts/load_test_autoscale.py http://localhost:30080
```

You will observe the HPA detect the load on Pod 1 and scale the deployment to 2, 3, up to 6 pods across the 2 worker nodes!

---

## 🧹 Teardown

To clean up all deployed platform resources:
```bash
./scripts/cleanup.sh
```
