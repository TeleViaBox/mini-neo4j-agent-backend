import os
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request, Response
from pydantic import BaseModel, Field

from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST

from neo4j_client import Neo4jClient

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

app = FastAPI(title="mini-mem0-backend", version="0.1.0")

neo = Neo4jClient()

# Prometheus metrics (keep labels low-cardinality)
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["method", "route", "http_status"],
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "route"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
)

def _route_label(request: Request) -> str:
    r = request.scope.get("route")
    if r and hasattr(r, "path"):
        return r.path
    return request.url.path

@app.on_event("startup")
def on_startup():
    # init schema/indexes
    neo.init_schema()

@app.on_event("shutdown")
def on_shutdown():
    neo.close()

@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    route = _route_label(request)
    method = request.method
    start = time.perf_counter()

    try:
        response = await call_next(request)
        status = str(response.status_code)
        return response
    finally:
        dur = time.perf_counter() - start
        # status might not exist if exception before response creation
        try:
            status = str(locals().get("response").status_code)  # type: ignore
        except Exception:
            status = "500"
        HTTP_REQUESTS_TOTAL.labels(method=method, route=route, http_status=status).inc()
        HTTP_REQUEST_DURATION.labels(method=method, route=route).observe(dur)

class MemoryIn(BaseModel):
    user_id: str = Field(..., min_length=1)
    text: str = Field(..., min_length=1, max_length=5000)

class MemoryOut(BaseModel):
    id: str
    user_id: str
    text: str
    created_at: str

@app.get("/v1/health")
def health():
    return {"ok": True}

@app.get("/v1/ready")
def ready():
    if not neo.ping():
        raise HTTPException(status_code=503, detail="neo4j not ready")
    return {"ready": True}

@app.post("/v1/memories", response_model=MemoryOut)
def create_memory(payload: MemoryIn):
    if not neo.ping():
        raise HTTPException(status_code=503, detail="neo4j not ready")

    memory_id = str(uuid4())
    created_at = datetime.now(timezone.utc).isoformat()
    neo.add_memory(user_id=payload.user_id, text=payload.text, memory_id=memory_id, created_at=created_at)

    return MemoryOut(id=memory_id, user_id=payload.user_id, text=payload.text, created_at=created_at)

@app.get("/v1/memories/search")
def search_memories(user_id: str, q: str, limit: int = 10):
    if limit < 1 or limit > 50:
        raise HTTPException(status_code=400, detail="limit must be 1..50")
    if not neo.ping():
        raise HTTPException(status_code=503, detail="neo4j not ready")

    rows = neo.search_memories(user_id=user_id, q=q, limit=limit)
    return {"results": rows}

@app.get("/metrics")
def metrics():
    data = generate_latest()
    return Response(content=data, media_type=CONTENT_TYPE_LATEST)
