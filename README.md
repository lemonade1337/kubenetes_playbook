# High-Availability Qwen 2.5 3B Platform on Kubernetes

A production-ready Ansible playbook and Kubernetes architecture for deploying a scalable **Qwen 2.5 3B** LLM inference service, **Keycloak Authentication**, an **OpenAI-Compatible API Gateway**, and a **Token Management Web Portal**.

Supports deployment across **macOS**, **Linux**, **Windows (WSL2 / Docker Desktop)**, **AWS EKS**, and **Azure AKS**.

---

## Architecture Overview

```mermaid
flowchart TD
    %% =========================================================================
    %% Modern Blue, White, and Slate-Grey Style Palette
    %% =========================================================================
    classDef clientBox fill:#f0f7ff,stroke:#2563eb,stroke-width:1.5px,color:#0f172a
    classDef ingressBox fill:#1e293b,stroke:#0f172a,stroke-width:2px,color:#ffffff
    classDef gatewayBox fill:#dbeafe,stroke:#1d4ed8,stroke-width:2px,color:#1e3a8a
    classDef authBox fill:#e2e8f0,stroke:#475569,stroke-width:1.5px,color:#0f172a
    classDef dbBox fill:#f1f5f9,stroke:#64748b,stroke-width:1.5px,color:#1e293b
    classDef llmBox fill:#bfdbfe,stroke:#2563eb,stroke-width:2px,color:#1e3a8a
    classDef promBox fill:#eff6ff,stroke:#2563eb,stroke-width:1.5px,color:#1e40af
    classDef jaegerBox fill:#e0f2fe,stroke:#0284c7,stroke-width:1.5px,color:#0369a1
    classDef grafanaBox fill:#ffffff,stroke:#1d4ed8,stroke-width:1.5px,color:#0f172a
    classDef scaleBox fill:#f8fafc,stroke:#94a3b8,stroke-width:1.5px,color:#334155

    %% -------------------------------------------------------------------------
    %% Clients & External Actors
    %% -------------------------------------------------------------------------
    subgraph Clients["👥 Clients & Users"]
        Browser["🖥️ Web Browser / Portal UI"]:::clientBox
        APIClient["⚡ OpenAI SDK / cURL / Apps"]:::clientBox
        AdminOps["📊 SRE / DevOps / Admins"]:::clientBox
    end

    %% -------------------------------------------------------------------------
    %% Ingress & Edge Routing
    %% -------------------------------------------------------------------------
    subgraph IngressLayer["🌐 Ingress & Routing Layer"]
        Ingress["🔀 NGINX Ingress Controller / NodePorts<br/>(Ports: 30080 &bull; 30090 &bull; 30100 &bull; 30085 &bull; 30086 &bull; 30091)"]:::ingressBox
    end

    %% -------------------------------------------------------------------------
    %% Core Kubernetes Cluster
    %% -------------------------------------------------------------------------
    subgraph Cluster["☸️ Kubernetes Cluster (llm-platform namespace)"]
        subgraph Node1["Worker Node 1"]
            GW1["API Gateway & Portal<br/>(Pod 1 &bull; FastAPI + OTel)"]:::gatewayBox
            KC1["Keycloak IAM<br/>(Pod 1 &bull; Auth Server)"]:::authBox
            PG1[("PostgreSQL HA<br/>(Pod 1 &bull; Primary + Exporter)")]:::dbBox
            QW1["Qwen 2.5 3B Engine<br/>(Pod 1 &bull; Active Inference)"]:::llmBox
        end

        subgraph Node2["Worker Node 2"]
            GW2["API Gateway & Portal<br/>(Pod 2 &bull; FastAPI + OTel)"]:::gatewayBox
            KC2["Keycloak IAM<br/>(Pod 2 &bull; Auth Server)"]:::authBox
            PG2[("PostgreSQL HA<br/>(Pod 2 &bull; Standby + Exporter)")]:::dbBox
            QW2["Qwen 2.5 3B Engine<br/>(Pods 2–6 &bull; Autoscaled Replicas)"]:::llmBox
        end

        %% Observability Stack
        subgraph ObservabilityLayer["📈 Full Observability & Telemetry Stack"]
            Prometheus["📊 Prometheus Server<br/>(Scrapes Metrics :9090)"]:::promBox
            Jaeger["🔍 Jaeger Tracing<br/>(OTLP Ingestion :4318 / UI :16686)"]:::jaegerBox
            Grafana["📈 Grafana Visualizer<br/>(Platform Dashboards :3000)"]:::grafanaBox
        end

        %% Autoscaling Subsystem
        subgraph ScalingLayer["⚡ Dynamic Autoscaling Engine"]
            HPA["HorizontalPodAutoscaler (HPA)<br/>Min: 1 Pod &bull; Max: 6 Pods (80% CPU Target)"]:::scaleBox
            MetricsSrv["Kubernetes Metrics Server"]:::scaleBox
        end
    end

    %% -------------------------------------------------------------------------
    %% Traffic & Communication Flow
    %% -------------------------------------------------------------------------
    Browser -->|HTTP Web UI| Ingress
    APIClient -->|Bearer API Key| Ingress
    AdminOps -->|Dashboards & Traces| Ingress

    Ingress -->|Route / & /v1/*| GW1
    Ingress -->|Route / & /v1/*| GW2
    Ingress -->|Route /auth/*| KC1
    Ingress -->|Route /auth/*| KC2
    Ingress -.->|Route :30085| Grafana
    Ingress -.->|Route :30086| Jaeger
    Ingress -.->|Route :30091| Prometheus

    GW1 -->|Token Validation & Ledger| PG1
    GW2 -->|Token Validation & Ledger| PG2
    GW1 -->|OIDC / OAuth2 Validation| KC1
    GW2 -->|OIDC / OAuth2 Validation| KC2

    GW1 -->|Forward /v1/chat/completions| QW1
    GW2 -->|Forward /v1/chat/completions| QW2

    %% Observability Connections
    GW1 -.->|OTLP Traces| Jaeger
    GW2 -.->|OTLP Traces| Jaeger
    Prometheus -.->|Scrape /metrics| GW1
    Prometheus -.->|Scrape /metrics| GW2
    Prometheus -.->|Scrape /auth/metrics| KC1
    Prometheus -.->|Scrape /auth/metrics| KC2
    Prometheus -.->|Scrape Port 9187| PG1
    Prometheus -.->|Scrape Port 9187| PG2
    Grafana -->|PromQL Queries| Prometheus
    Grafana -->|Trace Queries| Jaeger

    %% Autoscaling Connections
    MetricsSrv -->|CPU Utilization Signals| HPA
    HPA ==>|Scale Inference Replicas| QW1
    HPA ==>|Scale Inference Replicas| QW2
```

---

## Key Features

1. **Qwen 2.5 3B Dynamic Autoscaling (1 to 6 Pods)**:
   - Starts at **1 replica** to conserve resources.
   - Automatically detects active inference load and spawns up to **6 replicas** when existing instances are in use.
   - Exposes standard **OpenAI-compatible endpoints** (`/v1/chat/completions`, `/v1/models`).

2. **Full Redundancy & High Availability**:
   - Deployed across **2 Kubernetes worker nodes** (or single-node development environments).
   - **PostgreSQL Database**: Redundant 2-replica StatefulSet with persistent storage and postgres-exporter metrics sidecar.
   - **Keycloak Server**: Redundant 2-replica deployment with pod anti-affinity.
   - **API Gateway & Web Portal**: Redundant 2-replica deployment with pod anti-affinity.

3. **Keycloak Authentication & Pre-provisioned Accounts**:
   - Realm: `llm-platform` with client `token-portal`.
   - **Every user is automatically granted 100,000 initial tokens**.
   - Pre-configured accounts:
     - **Admin**: `admin` / `AdminPass123!` (Role: `admin`, Pre-seeded Key: `sk-admin-master-key-2026`)
     - **User 1**: `user1` / `User1Pass123!` (Role: `user`, Pre-seeded Key: `sk-user1-secret-key-2026`)
     - **User 2**: `user2` / `User2Pass123!` (Role: `user`, Pre-seeded Key: `sk-user2-secret-key-2026`)
     - **User 3**: `user3` / `User3Pass123!` (Role: `user`, Pre-seeded Key: `sk-user3-secret-key-2026`)

4. **Token Management & Interactive Web Chat Portal**:
   - **Interactive Qwen 2.5 3B Chat Field**: Chat in real-time directly on the web portal with markdown formatting, syntax highlighting, conversation history, and quick prompts.
   - **User Dashboard**: View real-time remaining tokens, monthly quota progress, API keys (reveal, copy, regenerate), and endpoint URLs.
   - **Live Token Metering**: Real-time atomic token deduction in PostgreSQL per request and immediate updates to balance cards.
   - **Admin Console**: View all user balances, grant extra tokens (e.g. +50,000) to any user, configure monthly recurring quotas, and reset balances.

5. **Complete Observability Stack (Prometheus, Grafana, Jaeger)**:
   - **Prometheus (1 Pod)**: Automatically scrapes metrics from PostgreSQL (via postgres-exporter sidecar on port 9187), Keycloak (built-in metrics at `/auth/metrics`), and API Gateway (`/metrics`).
   - **Jaeger Distributed Tracing (1 Pod)**: Integrated into the API Gateway via OpenTelemetry (FastAPI, HTTPX outbound client, and SQLAlchemy engine), providing distributed trace graphs with token counts, user metadata, and backend latencies.
   - **Grafana Visualization (1 Pod)**: Pre-provisioned with Prometheus & Jaeger data sources and auto-loaded dashboards for Platform Overview, PostgreSQL Performance, and Keycloak Auth metrics.

---

## Repository Structure

```
.
├── ansible.cfg                          # Ansible configuration
├── inventory.ini                        # Inventory targeting Kubernetes
├── playbook.yml                         # Master deployment playbook
├── site.yml                             # Playbook entrypoint alias
├── group_vars/
│   └── all.yml                          # Global configuration variables
├── vars/                                # Environment-specific variable overlays
│   ├── macos.yml                        # Settings for macOS (Docker Desktop/Minikube/Kind)
│   ├── linux.yml                        # Settings for Linux (k3s/MicroK8s/Minikube/Kind)
│   ├── aws-eks.yml                      # Settings for AWS EKS (gp3 storage, ECR, ALB)
│   └── azure-aks.yml                    # Settings for Azure AKS (managed-csi storage, ACR)
├── roles/
│   ├── prerequisites/                   # Namespace and Metrics Server
│   ├── postgres/                        # PostgreSQL HA StatefulSet (2 replicas + exporter)
│   ├── keycloak/                        # Keycloak HA Server (2 replicas)
│   ├── observability/                   # Prometheus, Grafana, & Jaeger Tracing (1 pod each)
│   ├── qwen_llm/                        # Qwen 2.5 3B Service & HPA (1 to 6 replicas)
│   ├── api_gateway_portal/              # FastAPI Portal, Token Metering, UI, & Tracing (2 replicas)
│   └── ingress/                         # Ingress rules and NodePort routing
├── scripts/
│   ├── deploy.sh                        # One-click multi-environment deployment script
│   ├── port_forward.sh                  # Port-forwarding helper script
│   ├── test_api.py                      # Automated test suite
│   ├── load_test_autoscale.py           # Concurrency autoscaling load tester
│   └── cleanup.sh                       # Teardown script
└── README.md
```

---

## Deployment Guides (macOS, Linux, Windows, AWS, Azure)

### General Prerequisites
- **Python 3** (3.9+) with `ansible` and `kubernetes` packages installed:
  ```bash
  pip install ansible kubernetes
  ansible-galaxy collection install kubernetes.core
  ```
- **kubectl** installed and authenticated with your target cluster (`kubectl get nodes`).
- **Docker** or **Podman** installed (required for local image builds).

---

### 1. macOS Deployment (Docker Desktop, Minikube, Kind, OrbStack)

1. **Install tools via Homebrew**:
   ```bash
   brew install kubectl ansible helm
   ```

2. **Start a Kubernetes cluster**:
   - **Docker Desktop / OrbStack**: Enable Kubernetes in Settings.
   - **Minikube**:
     ```bash
     minikube start --cpus=4 --memory=8192 --nodes=2
     minikube addons enable ingress
     minikube addons enable metrics-server
     ```
   - **Kind**:
     ```bash
     kind create cluster --config - <<EOF
     kind: Cluster
     apiVersion: kind.x-k8s.io/v1alpha4
     nodes:
     - role: control-plane
     - role: worker
     - role: worker
     EOF
     ```

3. **Deploy the platform**:
   ```bash
   ./scripts/deploy.sh --env macos
   # Or directly with Ansible:
   ansible-playbook -i inventory.ini playbook.yml -e @vars/macos.yml
   ```

---

### 2. Linux Deployment (k3s, MicroK8s, Minikube, Kind, Bare-Metal)

1. **Install prerequisites (Ubuntu/Debian example)**:
   ```bash
   sudo apt-get update && sudo apt-get install -y docker.io python3-pip python3-venv
   pip3 install ansible kubernetes
   ansible-galaxy collection install kubernetes.core
   ```

2. **Set up cluster**:
   - **k3s**:
     ```bash
     curl -sfL https://get.k3s.io | sh -
     export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
     sudo chmod 644 /etc/rancher/k3s/k3s.yaml
     ```
   - **MicroK8s**:
     ```bash
     sudo snap install microk8s --classic
     sudo microk8s enable dns storage ingress metrics-server
     sudo snap alias microk8s.kubectl kubectl
     microk8s config > ~/.kube/config
     ```
   - **Minikube / Kind**:
     ```bash
     minikube start --driver=docker --cpus=4 --memory=8192 --nodes=2
     ```

3. **Deploy the platform**:
   ```bash
   ./scripts/deploy.sh --env linux
   # Or directly with Ansible:
   ansible-playbook -i inventory.ini playbook.yml -e @vars/linux.yml
   ```

---

### 3. Windows (Docker Desktop / WSL2)

1. Ensure **Docker Desktop** is running with **Kubernetes enabled** (2 worker nodes configured if using multi-node Kind/Docker Desktop).
2. From WSL2 or Windows bash:
   ```bash
   ./scripts/deploy.sh
   # Or:
   ansible-playbook -i inventory.ini playbook.yml
   ```

---

### 4. AWS EKS Deployment (Amazon Web Services)

1. **Prerequisites**:
   - Install AWS CLI (`aws`) and `eksctl`.
   - Configure AWS credentials: `aws configure`.

2. **Create an EKS cluster with 2+ worker nodes**:
   ```bash
   eksctl create cluster \
     --name qwen-platform \
     --region us-east-1 \
     --nodegroup-name standard-workers \
     --node-type t3.xlarge \
     --nodes 2 \
     --nodes-min 2 \
     --nodes-max 6 \
     --managed
   ```

3. **Install the Amazon EBS CSI driver** (for dynamic `gp3` storage provisioner):
   ```bash
   eksctl create addon --name aws-ebs-csi-driver --cluster qwen-platform --force
   ```

4. **Build and push the Qwen container image to Amazon ECR**:
   ```bash
   # Create ECR repository
   aws ecr create-repository --repository-name qwen-llm --region us-east-1

   # Authenticate Docker to ECR
   ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com

   # Build and push image
   docker build -t ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/qwen-llm:2.5-3b roles/qwen_llm/files
   docker push ${ACCOUNT_ID}.dkr.ecr.us-east-1.amazonaws.com/qwen-llm:2.5-3b
   ```

5. **Update [vars/aws-eks.yml](vars/aws-eks.yml)** with your ECR image URI and cluster settings:
   ```yaml
   k8s_storage_class: "gp3"
   qwen_build_local: false
   qwen_image: "<YOUR_ACCOUNT_ID>.dkr.ecr.us-east-1.amazonaws.com/qwen-llm:2.5-3b"
   ```

6. **Deploy the platform**:
   ```bash
   ./scripts/deploy.sh --env aws
   # Or:
   ansible-playbook -i inventory.ini playbook.yml -e @vars/aws-eks.yml
   ```

---

### 5. Azure AKS Deployment (Microsoft Azure)

1. **Prerequisites**:
   - Install Azure CLI (`az`).
   - Log in: `az login`.

2. **Create Resource Group and AKS Cluster**:
   ```bash
   az group create --name qwen-rg --location eastus

   az aks create \
     --resource-group qwen-rg \
     --name qwen-aks-cluster \
     --node-count 2 \
     --node-vm-size Standard_D4s_v5 \
     --enable-managed-identity \
     --generate-ssh-keys

   # Retrieve kubeconfig credentials
   az aks get-credentials --resource-group qwen-rg --name qwen-aks-cluster --overwrite-existing
   ```

3. **Build and push the Qwen container image to Azure Container Registry (ACR)**:
   ```bash
   # Create ACR registry
   az acr create --resource-group qwen-rg --name qwenregistry$RANDOM --sku Basic --admin-enabled true
   ACR_NAME=$(az acr list --resource-group qwen-rg --query "[0].name" -o tsv)

   # Attach ACR to AKS cluster for seamless image pulling
   az aks update --resource-group qwen-rg --name qwen-aks-cluster --attach-acr $ACR_NAME

   # Build and push image via ACR Tasks
   az acr build --registry $ACR_NAME --image qwen-llm:2.5-3b roles/qwen_llm/files
   ```

4. **Update [vars/azure-aks.yml](vars/azure-aks.yml)** with your ACR image URI:
   ```yaml
   k8s_storage_class: "managed-csi"
   qwen_build_local: false
   qwen_image: "<YOUR_ACR_NAME>.azurecr.io/qwen-llm:2.5-3b"
   ```

5. **Deploy the platform**:
   ```bash
   ./scripts/deploy.sh --env azure
   # Or:
   ansible-playbook -i inventory.ini playbook.yml -e @vars/azure-aks.yml
   ```

---

## Web Portal & Service URLs

Once deployed, access the services via Ingress, direct NodePorts, or Cloud LoadBalancers:

| Service | Ingress URL | Direct NodePort URL | Default Credentials |
| :--- | :--- | :--- | :--- |
| **Token Portal & Web UI** | `http://localhost/` | `http://localhost:30080` (or `http://localhost:8000`) | Use any user below |
| **Keycloak Admin Console** | `http://localhost/auth` | `http://localhost:30090/auth` (or `http://localhost:8080/auth`) | `admin` / `KeycloakMasterAdmin2026!` |
| **OpenAI API Gateway** | `http://localhost/v1` | `http://localhost:30080/v1` | `Bearer <API_KEY>` |
| **Grafana Dashboards** | `http://localhost:30085` | `http://localhost:30085` (or `http://localhost:3000`) | `admin` / `GrafanaMasterAdmin2026!` (or Anonymous Admin) |
| **Prometheus Metrics** | `http://localhost:30091` | `http://localhost:30091` (or `http://localhost:9090`) | N/A |
| **Jaeger Tracing UI** | `http://localhost:30086` | `http://localhost:30086` (or `http://localhost:16686`) | N/A |

> **Note for Port-Forwarding**: If NodePort or Ingress is not exposed on your host, run the helper script:
> ```bash
> ./scripts/port_forward.sh
> ```

---

## Pre-Configured Users & Initial Balances

| Username | Password | Role | Initial Tokens | Pre-Seeded API Key |
| :--- | :--- | :--- | :--- | :--- |
| `admin` | `AdminPass123!` | Admin + User | 100,000 | `sk-admin-master-key-2026` |
| `user1` | `User1Pass123!` | Standard User | 100,000 | `sk-user1-secret-key-2026` |
| `user2` | `User2Pass123!` | Standard User | 100,000 | `sk-user2-secret-key-2026` |
| `user3` | `User3Pass123!` | Standard User | 100,000 | `sk-user3-secret-key-2026` |

---

## How to Add a New User

New users can be added at runtime through the **Keycloak Admin Console**, declaratively via **Ansible**, or via **Self-Registration**.

### Method 1: Keycloak Admin Console (Recommended for Runtime Management)

1. Open the Keycloak Admin Console at `http://localhost:30090/auth` (or `http://localhost/auth`).
2. Log in with the Master Admin credentials:
   - **Username**: `admin`
   - **Password**: `KeycloakMasterAdmin2026!`
3. In the top-left realm dropdown, switch from `master` to the **`llm-platform`** realm.
4. In the left sidebar, click **Manage > Users**, then click the **Add user** button.
5. Enter the user details:
   - **Username**: e.g., `janedoe`
   - **Email**: `janedoe@example.com`
   - **First name**: `Jane`
   - **Last name**: `Doe`
   - Ensure **Enabled** is switched to **ON**.
   - Click **Create**.
6. Switch to the **Credentials** tab:
   - Click **Set password**.
   - Enter and confirm the password (e.g. `JaneSecurePass123!`).
   - Toggle **Temporary** to **OFF** so the user is not prompted to reset it immediately.
   - Click **Save**.
7. Switch to the **Role mapping** tab:
   - Click **Assign role**.
   - Filter by realm roles and assign **`user`** (for standard access) or **`admin`** (for admin portal controls).
8. **Automatic Provisioning**:
   - The user can now immediately log in at the Token Portal (`http://localhost:8000` or `http://localhost/`).
   - Upon first login, the platform automatically provisions a **100,000 initial token balance**, a monthly quota, and generates an active OpenAI-compatible API key (`sk-...`).

---

### Method 2: Declarative Pre-Provisioning via Ansible

You can add users directly into the infrastructure configuration so they are provisioned upon deployment:

1. Open [group_vars/all.yml](group_vars/all.yml).
2. Locate the `initial_users` list and append your new user entry:
   ```yaml
   initial_users:
     - username: "janedoe"
       email: "janedoe@example.com"
       password: "JaneSecurePass123!"
       first_name: "Jane"
       last_name: "Doe"
       is_admin: false          # Set to true for admin rights
       initial_tokens: 100000   # Initial token allocation
       monthly_quota: 100000    # Recurring monthly quota
   ```
3. Re-apply the authentication and realm configuration:
   ```bash
   ansible-playbook -i inventory.ini playbook.yml --tags auth
   ```

---

### Method 3: Self-Registration via Web Portal

1. On the Token Portal login screen (`http://localhost/login`), click the **Register** link to be redirected to the Keycloak registration page.
2. Complete the registration form (username, email, password).
3. Upon first login, the Token Portal automatically allocates **100,000 free tokens** and generates an API key.

---

### Method 4: Managing Token Balances & Quotas as an Administrator

1. Log in to the Token Portal with an admin account (e.g., `admin` / `AdminPass123!`).
2. Click **Admin Console** in the top navigation bar (or navigate to `http://localhost/admin`).
3. You can:
   - View all registered users and their current remaining token balances.
   - Click **Add Tokens** (e.g., grant +50,000 or +100,000 tokens to any user).
   - Set custom recurring **Monthly Quotas**.
   - **Reset Balances** for individual users or all users across the platform.

---

## Making OpenAI API Requests

### 1. cURL
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
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
    base_url="http://localhost:8000/v1",
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
  baseURL: 'http://localhost:8000/v1',
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

## Teardown

To clean up all deployed platform resources:
```bash
./scripts/cleanup.sh
```
