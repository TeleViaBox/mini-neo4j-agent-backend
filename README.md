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
