"""Fila compartilhada: RQ/Redis quando REDIS_URL existe; senão, thread local (dev)."""
from concurrent.futures import ThreadPoolExecutor
import store
from tasks import mark_failed

pool = ThreadPoolExecutor(max_workers=2)
queue = None
if store.REDIS:
    from rq import Queue
    queue = Queue(connection=store.REDIS)

def enqueue(fn, *args, timeout: int = 180):
    if queue: queue.enqueue(fn, *args, job_timeout=timeout, result_ttl=0, failure_ttl=60, on_failure=mark_failed)
    else: pool.submit(fn, *args)
