# mini-neo4j-agent-backend (Neo4j + FastAPI + Prometheus + Grafana)

(Note): AWS demo: https://github.com/TeleViaBox/mini-neo4j-agent-backend/blob/main/AWS_README.md 


A minimal, production-shaped backend MVP inspired by **mem0-style graph memory**: a FastAPI service that writes/searches “memories” in **Neo4j**, exposes **Prometheus** metrics, and ships with a ready-to-use **Grafana** dashboard.

This repo is intentionally small but end-to-end:
- **Graph memory store:** Neo4j (nodes + relationships)
- **API layer:** FastAPI (health/readiness + memory write/search)
- **Observability:** Prometheus scrape + Grafana dashboard provisioning (auto-load)


<img width="2974" height="994" alt="image" src="https://github.com/user-attachments/assets/f302411c-7d54-4c58-b2bf-dd079dcaa83f" />


<img width="1372" height="744" alt="image" src="https://github.com/user-attachments/assets/c8b605e0-eaee-4155-a7c0-ae3ee475b859" />


---

## Architecture

Services (Docker Compose):

- `api` (FastAPI)  
  - REST endpoints: `/v1/health`, `/v1/ready`, `/v1/memories`, `/v1/memories/search`  
  - Metrics: `/metrics` (Prometheus format)
- `neo4j` (Neo4j 5)
  - Graph model: `(:User)-[:HAS_MEMORY]->(:Memory)`
  - Indexes/constraints on startup (unique IDs + full-text index for `Memory.text`)
- `prometheus`
  - Scrapes `api:8000/metrics` every 5s
- `grafana`
  - Provisioned data source + dashboard (RPS / p95 latency / 5xx rate)

Ports (default):
- API: `8000`
- Grafana: `3000`
- Prometheus: `9090`
- Neo4j Browser: `7474` (Bolt: `7687`)

---

## Quickstart (Local or on a Linux host)

### 1) Start everything
```bash
docker compose up -d --build
docker compose ps
```

### 2) Verify API
```bash
curl -s http://localhost:8000/v1/health
curl -s http://localhost:8000/v1/ready
```

### 3) Open UIs
- Grafana: `http://localhost:3000`  (default: `admin / admin`)
- Prometheus: `http://localhost:9090`
- Neo4j Browser: `http://localhost:7474`

> If running on a remote host, replace `localhost` with the host IP/hostname and the same ports.

---

## API

### Create a memory
```bash
curl -s -X POST http://127.0.0.1:8000/v1/memories \
  -H "Content-Type: application/json" \
  -d '{"user_id":"u1","text":"I like coffee and graph memory in Neo4j."}'
```

Example response:
```json
{
  "id": "166eb801-7f98-4be2-b235-782cda24e8ae",
  "user_id": "u1",
  "text": "I like coffee and graph memory in Neo4j.",
  "created_at": "2026-01-23T20:36:40.538073+00:00"
}
```

### Search memories
```bash
curl -s "http://127.0.0.1:8000/v1/memories/search?user_id=u1&q=coffee&limit=10"
```

Example response:
```json
{
  "results": [
    {
      "id": "166eb801-7f98-4be2-b235-782cda24e8ae",
      "text": "I like coffee and graph memory in Neo4j.",
      "created_at": "2026-01-23T20:36:40.538073+00:00",
      "score": 0.13076457381248474
    }
  ]
}
```

---

## Observability

### Prometheus target check
Prometheus should show the `api` scrape target as **UP** at:

- UI: `http://localhost:9090/targets`

Expected:
- 1 / 1 target **up**
- Scrape URL: `http://api:8000/metrics`

You can also verify via API:
```bash
curl -s http://localhost:9090/api/v1/targets | head
```

### Generate some traffic (for graphs)
```bash
for i in $(seq 1 30); do curl -s http://localhost:8000/v1/health >/dev/null; done
for i in $(seq 1 10); do curl -s http://localhost:8000/v1/ready  >/dev/null; done
```

### PromQL queries (copy/paste)
**RPS**
```promql
sum(rate(http_requests_total[1m]))
```

**RPS by route**
```promql
sum by (route) (rate(http_requests_total[1m]))
```

**p95 latency (seconds)**
```promql
histogram_quantile(
  0.95,
  sum by (le, route) (rate(http_request_duration_seconds_bucket[5m]))
)
```

**5xx rate**
```promql
sum(rate(http_requests_total{http_status=~"5.."}[1m]))
```

### Grafana dashboard
- URL: `http://localhost:3000`
- Dashboard: **API Overview (mini-mem0)**

Panels included:
- Request Rate (RPS)
- Latency p95 (seconds)
- 5xx Error Rate

---

## What was validated (smoke test checklist)

✅ Services start successfully:
- `neo4j` healthy  
- `api` healthy  
- `prometheus` running  
- `grafana` running  

✅ API functional:
- `GET /v1/health` → `200 {"ok": true}`
- `GET /v1/ready` → `200 {"ready": true}`
- `POST /v1/memories` → returns `id` + timestamps
- `GET /v1/memories/search` → returns scored results

✅ Observability works:
- Prometheus target `api:8000/metrics` is **UP**
- Grafana dashboard renders and updates after traffic generation

---

## Notes

- Neo4j schema setup occurs during API startup:
  - Unique constraints on `User.id` and `Memory.id`
  - Full-text index for `Memory.text` used by `/v1/memories/search`
- This is an MVP scaffolding intended to be extended with:
  - Auth (API keys/JWT)
  - Rate limiting
  - Multi-tenancy
  - Background jobs / ingestion pipelines
  - Load testing scripts (`k6`) and production checks

---

## Repo layout
```
mini-mem0-backend/
├─ app/                      # FastAPI service (Dockerfile + code)
├─ observability/            # Prometheus + Grafana provisioning
├─ docker-compose.yml
├─ Makefile
└─ .github/workflows/ci.yml
```


























# AWS Deployment Notes (mini-neo4j-agent-backend)

This document captures the AWS-side work to run the open-core repo in a production-like setup and prepare for “production-ready checks” (health/ready, observability, and in-VPC load testing without NAT).

Repo: `https://github.com/TeleViaBox/mini-neo4j-agent-backend.git`  
Region: `us-east-2`  
AWS Account: `927709485885`  
IAM principal used from local machine: `arn:aws:iam::927709485885:user/cli-admin`

<img width="850" height="549" alt="image" src="https://github.com/user-attachments/assets/d66ca8d9-159a-40d0-9c90-f3db4ecb55e9" />

<img width="386" height="471" alt="image" src="https://github.com/user-attachments/assets/643ec103-9b97-4f69-8940-933dee2155ba" />

<img width="781" height="319" alt="image" src="https://github.com/user-attachments/assets/0d5015db-c2e6-4636-a00e-d290c668a505" />


---

## 1) What is running in AWS right now

### Service EC2 (“app host”)
- Instance ID: `i-0bae753ec2745d904`
- AZ: `us-east-2a`
- Instance type: `t3.small`
- AMI: `ami-0503ed50b531cc445` (Ubuntu 22.04)
- Public IP: `18.189.141.50`
- Private IP: `172.31.2.115`
- Subnet (default VPC): `subnet-0c870148356774936`
- Security Group: `sg-0c8ef898d357f1150` (`mini-neo4j-sg`)
- Key pair name: `mini-neo4j-ec2-key` (local file: `~/Downloads/mini-neo4j-ec2-key.pem`)

### Containers (Docker Compose on the service EC2)
Verified on the instance:
- `api` (`mini-neo4j-agent-backend-api`) — `:8000` (healthy)
- `neo4j` (`neo4j:5`) — `:7474` (browser), `:7687` (bolt) (healthy)
- `prometheus` (`prom/prometheus`) — `:9090`
- `grafana` (`grafana/grafana`) — `:3000`

### API checks
From the service EC2:
- `curl -s http://localhost:8000/v1/health` → `{"ok":true}`
- `curl -s http://localhost:8000/v1/ready`  → `{"ready":true}`

---

## 2) Goal / Operating model

- **Open-core**: source lives on GitHub; local and AWS deployments are driven from the repo.
- **Production-ready checks on AWS**:
  - Health/ready endpoints
  - Metrics (`/metrics`) scraped by Prometheus
  - Dashboards in Grafana
  - **Load testing from inside AWS** (no NAT gateway, traffic stays in the VPC)

---

## 3) Local prerequisites (Mac)

### Install AWS CLI v2 (GUI-free)
Downloaded installer and installed via:
```bash
cd ~/Downloads
curl "https://awscli.amazonaws.com/AWSCLIV2.pkg" -o AWSCLIV2.pkg
sudo installer -pkg AWSCLIV2.pkg -target /
aws --version
which aws
```

### Configure AWS CLI credentials
1) Ensure region config is valid:
```bash
cp ~/.aws/config ~/.aws/config.bak.$(date +%Y%m%d%H%M%S) 2>/dev/null || true
cat > ~/.aws/config <<'EOF'
[default]
region = us-east-2
output = json
EOF
chmod 600 ~/.aws/config
unset AWS_REGION AWS_DEFAULT_REGION
aws configure get region
```

2) Validate identity:
```bash
export AWS_PAGER=""
aws sts get-caller-identity
```

> NOTE: a prior mistake was accidentally writing shell commands into `~/.aws/credentials` / `~/.aws/config`,
> which caused errors like:
> `Provided region_name 'cat ~/.aws/credentials 2>/dev/null' doesn't match a supported format.`
> Fix was rewriting `~/.aws/config` correctly (above).

---

## 4) IAM permissions (required)

Initially, EC2 API calls failed with `UnauthorizedOperation` (e.g., `ec2:CreateKeyPair`, `ec2:DescribeVpcs`, `ec2:CreateSecurityGroup`).
Resolution: add/attach the required IAM permissions to `cli-admin` (via IAM console or policy attachment),
then retry the AWS CLI commands successfully.

---

## 5) Provisioning: service EC2 (AWS CLI from Mac)

> All commands below run on **Mac**.

### 5.1 Set variables
```bash
export AWS_PAGER=""
REGION=us-east-2
KEY_NAME="mini-neo4j-ec2-key"
SG_NAME="mini-neo4j-sg"
TAG_NAME="mini-neo4j-agent-backend"
INSTANCE_TYPE="t3.small"
REPO_URL="https://github.com/TeleViaBox/mini-neo4j-agent-backend.git"
```

### 5.2 Find Ubuntu 22.04 AMI (without SSM Parameter Store)
SSM parameter lookup was not used; instead AMI was discovered via `describe-images`:
```bash
AMI_ID=$(aws ec2 describe-images --region "$REGION" --owners 099720109477   --filters     "Name=name,Values=ubuntu/images/hvm-ssd/ubuntu-jammy-22.04-amd64-server-*"     "Name=architecture,Values=x86_64"     "Name=virtualization-type,Values=hvm"     "Name=state,Values=available"   --query "Images | sort_by(@,&CreationDate) | [-1].ImageId" --output text)

echo $AMI_ID
```

### 5.3 Create/recreate key pair
```bash
rm -f ~/Downloads/${KEY_NAME}.pem
aws ec2 delete-key-pair --region "$REGION" --key-name "$KEY_NAME" 2>/dev/null || true

aws ec2 create-key-pair --region "$REGION" --key-name "$KEY_NAME"   --query 'KeyMaterial' --output text > ~/Downloads/${KEY_NAME}.pem

chmod 400 ~/Downloads/${KEY_NAME}.pem
ls -la ~/Downloads/${KEY_NAME}.pem
```

### 5.4 Create Security Group (default VPC) + allow SSH from current IP
```bash
MYIP=$(curl -s https://checkip.amazonaws.com | tr -d '\n')
VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true   --query 'Vpcs[0].VpcId' --output text)

SG_ID=$(aws ec2 create-security-group --region "$REGION"   --group-name "$SG_NAME" --description "$TAG_NAME" --vpc-id "$VPC_ID"   --query GroupId --output text)

aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$SG_ID"   --protocol tcp --port 22 --cidr ${MYIP}/32

echo $SG_ID
```

### 5.5 User-data bootstrap (cloud-init)
Created locally as `/tmp/user-data.sh` and passed to `run-instances` via `--user-data file:///tmp/user-data.sh`.

**User-data used:**
```bash
#!/bin/bash
set -eux

apt-get update
apt-get install -y ca-certificates curl git

install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo $VERSION_CODENAME) stable" > /etc/apt/sources.list.d/docker.list

apt-get update
apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

usermod -aG docker ubuntu

cd /home/ubuntu
git clone "https://github.com/TeleViaBox/mini-neo4j-agent-backend.git"
cd mini-neo4j-agent-backend
docker compose up -d --build
```

> NOTE: Local `/tmp/user-data.sh` had a duplicated block (same script repeated twice). In this run, `cloud-init` still completed successfully and the services came up healthy. For future reliability, prefer an idempotent script (see “Hardening” section).

### 5.6 Launch instance in default subnet with public IP
```bash
SUBNET_ID=$(aws ec2 describe-subnets --region "$REGION" --filters Name=vpc-id,Values="$VPC_ID"   --query 'Subnets[0].SubnetId' --output text)

INSTANCE_ID=$(aws ec2 run-instances --region "$REGION"   --image-id "$AMI_ID"   --instance-type "$INSTANCE_TYPE"   --key-name "$KEY_NAME"   --security-group-ids "$SG_ID"   --subnet-id "$SUBNET_ID"   --associate-public-ip-address   --user-data file:///tmp/user-data.sh   --tag-specifications "ResourceType=instance,Tags=[{Key=Name,Value=$TAG_NAME}]"   --query 'Instances[0].InstanceId' --output text)

echo $INSTANCE_ID
aws ec2 wait instance-running --region "$REGION" --instance-ids "$INSTANCE_ID"
```

### 5.7 Fetch public/private IPs
```bash
EC2_IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID"   --query 'Reservations[0].Instances[0].PublicIpAddress' --output text)
SERVICE_PRIV_IP=$(aws ec2 describe-instances --region "$REGION" --instance-ids "$INSTANCE_ID"   --query 'Reservations[0].Instances[0].PrivateIpAddress' --output text)

echo $EC2_IP
echo $SERVICE_PRIV_IP
```

---

## 6) Connecting + verifying on the service EC2

### 6.1 SSH in
```bash
ssh -i ~/Downloads/mini-neo4j-ec2-key.pem ubuntu@18.189.141.50
```

### 6.2 Validate containers + health endpoints
On EC2:
```bash
docker ps
curl -s http://localhost:8000/v1/health
curl -s http://localhost:8000/v1/ready
```

### 6.3 Inspect cloud-init output
On EC2:
```bash
sudo tail -n 120 /var/log/cloud-init-output.log
```
Observed: `Cloud-init ... finished ...` and docker build logs, indicating bootstrap completed.

---

## 7) Accessing UI safely (recommended): SSH tunnels from Mac

Instead of opening Grafana/Prometheus/Neo4j to the public internet, use port-forwarding:
```bash
ssh -i ~/Downloads/mini-neo4j-ec2-key.pem ubuntu@18.189.141.50   -L 8000:localhost:8000   -L 3000:localhost:3000   -L 9090:localhost:9090   -L 7474:localhost:7474
```

Then open locally:
- API docs: `http://localhost:8000/docs`
- Grafana: `http://localhost:3000`
- Prometheus: `http://localhost:9090`
- Neo4j Browser: `http://localhost:7474`

> A common mistake was attempting to run this tunnel *from inside the EC2* (where the PEM does not exist).
> Fix: run tunnels from the **Mac**, not from the instance.

---

## 8) Troubleshooting log (real issues encountered + fixes)

### 8.1 AWS CLI got stuck at `(END)`
Cause: AWS CLI pager output.  
Fix:
```bash
export AWS_PAGER=""
```

### 8.2 SSH timed out
Symptom:
```text
nc: ... port 22 failed: Operation timed out
```
Cause: Security Group only allowed an *old* home IP; current public IP changed.  
Fix: add the new IP to the SG, then retest:
```bash
MYIP=$(curl -s https://checkip.amazonaws.com | tr -d '\n')
SG_ID=$(aws ec2 describe-instances --region us-east-2 --instance-ids i-0bae753ec2745d904   --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)

aws ec2 authorize-security-group-ingress --region us-east-2 --group-id "$SG_ID"   --protocol tcp --port 22 --cidr ${MYIP}/32

nc -vz 18.189.141.50 22
```

### 8.3 `UnauthorizedOperation` for EC2 API calls
Cause: IAM user lacked required EC2 permissions.  
Fix: attach/add the required policies/permissions to `cli-admin`, then rerun.

### 8.4 AMI lookup with SSM parameter failed
Symptom: `ssm:GetParameter` denied or `ParameterNotFound`.  
Fix: use `ec2 describe-images` (owner `099720109477`) to pick latest Ubuntu Jammy 22.04 AMI.

---

## 9) Load testing plan (no NAT; run inside AWS)

### 9.1 Create a dedicated load-generator Security Group
Created on Mac:
- Loadgen SG ID: `sg-0c59a492a62167ebc`
- Ingress: SSH (22) from current public IP only

Commands:
```bash
export AWS_PAGER=""
REGION=us-east-2

MYIP=$(curl -s https://checkip.amazonaws.com | tr -d '\n')
VPC_ID=$(aws ec2 describe-vpcs --region "$REGION" --filters Name=isDefault,Values=true --query 'Vpcs[0].VpcId' --output text)

LOAD_SG_ID=$(aws ec2 create-security-group --region "$REGION"   --group-name "mini-loadgen-sg" --description "loadgen" --vpc-id "$VPC_ID"   --query GroupId --output text)

aws ec2 authorize-security-group-ingress --region "$REGION" --group-id "$LOAD_SG_ID"   --protocol tcp --port 22 --cidr ${MYIP}/32

echo "LOAD_SG_ID=$LOAD_SG_ID"
```

### 9.2 Recommended next step (hardening): allow API only from loadgen SG
Instead of opening `:8000` to the internet, allow it only from the load generator SG:
```bash
SERVICE_SG_ID=sg-0c8ef898d357f1150
aws ec2 authorize-security-group-ingress --region us-east-2 --group-id "$SERVICE_SG_ID"   --protocol tcp --port 8000 --source-group "$LOAD_SG_ID"
```

Then run load tests from the loadgen EC2 **to the service private IP** (`172.31.2.115`):
- `http://172.31.2.115:8000/...`

---

## 10) Hardening recommendations (next iterations)

1) **Bind services to localhost on the EC2** and rely on SSH tunneling:
   - In `docker-compose.yml`, use `127.0.0.1:PORT:PORT` for `8000/3000/9090/7474`.
2) Use **idempotent user-data**:
   - `git pull` if repo exists; avoid failing on repeated bootstrap.
3) Lock down Security Groups:
   - Keep SSH to `${MYIP}/32` only.
   - Keep API `:8000` accessible only from loadgen SG.
4) Add a “CD-lite” path:
   - GitHub Actions builds/tests; a controlled deploy step (manual or tag-based) triggers on the EC2.

---

## 11) Cleanup (avoid costs)

Terminate instances when done:
```bash
aws ec2 terminate-instances --region us-east-2 --instance-ids i-0bae753ec2745d904
aws ec2 wait instance-terminated --region us-east-2 --instance-ids i-0bae753ec2745d904
```

Delete security groups (after instances are gone):
```bash
aws ec2 delete-security-group --region us-east-2 --group-id sg-0c8ef898d357f1150
aws ec2 delete-security-group --region us-east-2 --group-id sg-0c59a492a62167ebc
```

Delete key pair:
```bash
aws ec2 delete-key-pair --region us-east-2 --key-name mini-neo4j-ec2-key
rm -f ~/Downloads/mini-neo4j-ec2-key.pem
```
