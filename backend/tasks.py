"""Função executada pelo worker (RQ) ou, sem Redis, por uma thread da API."""
import logging
from pathlib import Path
import store
from services.converters import convert
from services.pdf_tools import run_pdf_tool, PDF_TOOLS

log = logging.getLogger("pdflow")
GENERIC = "Não foi possível converter o arquivo. Tente novamente."

def run_job(job_id: str, paths: list[str], tool: str, opts: dict):
    job = store.load(job_id)
    if not job: return
    job["status"] = "processing"; store.save(job)
    files = [Path(p) for p in paths]; work = store.STORAGE / job_id
    try:
        out = run_pdf_tool(tool, files, work, opts) if tool in PDF_TOOLS else convert(files, work, opts)
        job.update(status="completed", file_id=job_id, filename=out.name)
    except ValueError as e:
        job.update(status="failed", error=str(e))
    except Exception:
        log.exception("falha na conversão")
        job.update(status="failed", error=GENERIC)
    finally:
        for f in files: f.unlink(missing_ok=True)
    store.save(job)

def mark_failed(job, connection, type, value, traceback):  # timeout / worker morto
    jid = job.args[0]; j = store.load(jid)
    if j: j.update(status="failed", error=GENERIC); store.save(j)


# ---------- Separar PDF com IA (módulo adicional) ----------
SPLIT_GENERIC = "Não foi possível processar o PDF. Tente novamente."

def split_analyze_task(job_id: str, size: int):
    from pdf_splitter.orchestration import split_pipeline as sp
    job = store.load(job_id)
    if not job: return
    job["status"] = "processing"; store.save(job)
    def prog(d, t):
        if d % 5 == 0 or d == t: job["progress"] = {"done": d, "total": t}; store.save(job)
    try:
        info = sp.analyze_upload(store.STORAGE / job_id, size, prog); job.update(status="completed", stage="ready", info=info)
    except ValueError as e: job.update(status="failed", error=str(e))
    except Exception: log.exception("falha na análise"); job.update(status="failed", error=SPLIT_GENERIC)
    store.save(job)

def split_execute_task(job_id: str, docs: list, ack: bool):
    from pdf_splitter.orchestration import split_pipeline as sp
    job = store.load(job_id)
    if not job: return
    job["status"] = "processing"; store.save(job)
    try:
        rep = sp.execute(store.STORAGE / job_id, docs, ack); job.update(status="completed", stage="done", result_status=rep["status"])
    except (ValueError, sp.NeedsReview) as e: job.update(status="completed", stage="ready", exec_error=str(e))
    except Exception: log.exception("falha na separação"); job.update(status="completed", stage="ready", exec_error=SPLIT_GENERIC)
    store.save(job)
