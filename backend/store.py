"""Estado das tarefas. Com REDIS_URL usa Redis (API e workers em processos separados);
sem ele, usa memória (desenvolvimento local, um único processo)."""
import os, json, time
from pathlib import Path

STORAGE = Path(os.getenv("STORAGE_DIR", "storage")).resolve(); STORAGE.mkdir(parents=True, exist_ok=True)
REDIS = None
if os.getenv("REDIS_URL"):
    import redis
    REDIS = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True)
_mem: dict[str, dict] = {}

def save(job: dict):
    if REDIS: REDIS.set(f"job:{job['job_id']}", json.dumps(job), ex=int(max(job["expires"] - time.time(), 60)) + 300)
    else: _mem[job["job_id"]] = job

def load(job_id: str) -> dict | None:
    if REDIS:
        raw = REDIS.get(f"job:{job_id}"); return json.loads(raw) if raw else None
    return _mem.get(job_id)

def delete(job_id: str):
    if REDIS: REDIS.delete(f"job:{job_id}")
    else: _mem.pop(job_id, None)
