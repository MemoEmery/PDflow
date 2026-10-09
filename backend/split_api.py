"""Rotas de /api/split — módulo adicional; reutiliza fila, armazenamento temporário e limpeza do projeto."""
import re, shutil, time, uuid
from pathlib import Path
import pymupdf as fitz
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
import store, tasks
from pdf_splitter.analysis.parameter_parser import NeedsRewrite
from pdf_splitter.analysis.semantic_analyzer import ai_status
from pdf_splitter.extraction.ocr_engine import get_ocr
from pdf_splitter.models import SplitParams
from pdf_splitter.orchestration import split_pipeline as sp

SPLIT_TTL = 60 * 60                 # sessões de separação ficam 60 min (há revisão humana no meio)
SPLIT_MAX_BYTES = 100 * 1024 * 1024

class DocIn(BaseModel):
    start: int; end: int; name: str | None = Field(None, max_length=100)
class PlanIn(BaseModel):
    documents: list[DocIn] = Field(min_length=1, max_length=500)
class ExecIn(PlanIn):
    acknowledge_review: bool = False
class InterpretIn(BaseModel):
    instruction: str = Field(min_length=3, max_length=2000)

def _job(split_id: str) -> dict:
    j = store.load(split_id) if re.fullmatch(r"[0-9a-f]{32}", split_id) else None
    if not j or j.get("kind") != "split": raise HTTPException(404, "Sessão não encontrada ou expirada.")
    return j

def _ready(split_id: str) -> Path:
    j = _job(split_id)
    if j["stage"] not in ("ready", "done") or j["status"] != "completed": raise HTTPException(409, "O PDF ainda está sendo analisado.")
    return store.STORAGE / split_id

def build_router(limiter, enqueue) -> APIRouter:
    r = APIRouter(prefix="/api/split")

    @r.post("", status_code=202)
    @limiter.limit("10/minute")
    async def upload(request: Request, file: UploadFile = File(...)):
        if not (file.filename or "").lower().endswith(".pdf"): raise HTTPException(400, "Envie um arquivo PDF.")
        sid = uuid.uuid4().hex; work = store.STORAGE / sid; work.mkdir()
        try:
            size = 0
            with open(work / "original.pdf", "wb") as f:
                while chunk := await file.read(1024 * 1024):
                    size += len(chunk)
                    if size > SPLIT_MAX_BYTES: raise HTTPException(413, "O arquivo excede o limite de 100 MB.")
                    f.write(chunk)
            with open(work / "original.pdf", "rb") as f:
                if f.read(4) != b"%PDF": raise HTTPException(400, "Esse arquivo não parece ser um PDF válido.")
        except HTTPException:
            shutil.rmtree(work, ignore_errors=True); raise
        now = time.time()
        store.save({"job_id": sid, "kind": "split", "status": "pending", "stage": "extracting", "progress": {"done": 0, "total": 0},
                    "created": now, "expires": now + SPLIT_TTL})
        enqueue(tasks.split_analyze_task, sid, size)
        return {"split_id": sid}

    @r.get("/{sid}")
    def state(sid: str):
        j = _job(sid); out = {k: j.get(k) for k in ("status", "stage", "progress", "info", "error", "exec_error")}
        out["ai"] = ai_status(); out["ocr"] = {"engine": get_ocr().name, "available": get_ocr().available()}
        rp = store.STORAGE / sid / "report.json"
        if j["stage"] == "done" and rp.exists(): out["report"] = sp._rw(rp)
        return out

    @r.post("/{sid}/interpret")
    @limiter.limit("30/minute")
    def interpret(request: Request, sid: str, body: InterpretIn):
        work = _ready(sid)
        try: return sp.interpret(work, body.instruction)
        except NeedsRewrite as e: raise HTTPException(422, str(e))

    @r.post("/{sid}/simulate")
    @limiter.limit("30/minute")
    def simulate(request: Request, sid: str, params: SplitParams):
        return sp.simulate(_ready(sid), params)

    @r.post("/{sid}/plan")
    @limiter.limit("60/minute")
    def plan(request: Request, sid: str, body: PlanIn):
        work = _ready(sid)
        if not (work / "ctx.json").exists(): raise HTTPException(409, "Simule a separação primeiro.")
        try: return sp.apply_edit(work, [d.model_dump() for d in body.documents])
        except ValueError as e: raise HTTPException(422, str(e))

    @r.post("/{sid}/execute", status_code=202)
    @limiter.limit("10/minute")
    def execute(request: Request, sid: str, body: ExecIn):
        work = _ready(sid); j = _job(sid)
        if not (work / "ctx.json").exists(): raise HTTPException(409, "Simule a separação primeiro.")
        docs = [d.model_dump() for d in body.documents]
        try: pl = sp.apply_edit(work, docs)
        except ValueError as e: raise HTTPException(422, str(e))
        if pl["needs_review"] and not body.acknowledge_review:
            raise HTTPException(409, "Há divisões de baixa confiança ou alertas. Revise e confirme que revisou antes de separar.")
        for p in ("report.json", "arquivos.zip"): (work / p).unlink(missing_ok=True)
        j.update(status="pending", stage="splitting", progress={"done": 0, "total": 1}, exec_error=None); store.save(j)
        enqueue(tasks.split_execute_task, sid, docs, body.acknowledge_review)
        return {"split_id": sid}

    @r.get("/{sid}/page/{n}.png")
    def page(sid: str, n: int):
        work = _ready(sid)
        with fitz.open(work / "original.pdf") as d:
            if not 1 <= n <= d.page_count: raise HTTPException(404, "Página inexistente.")
            png = d[n - 1].get_pixmap(dpi=50, alpha=False).tobytes("png")
        return Response(png, media_type="image/png", headers={"Cache-Control": "private, max-age=300"})

    def _report(sid):
        _job(sid); rp = store.STORAGE / sid / "report.json"
        if not rp.exists(): raise HTTPException(404, "Resultado ainda não disponível.")
        return sp._rw(rp)

    @r.get("/{sid}/file/{k}")
    def file(sid: str, k: int):
        rep = _report(sid)
        if not 1 <= k <= len(rep["files"]): raise HTTPException(404, "Arquivo não encontrado.")
        f = next((store.STORAGE / sid / "out").glob(f"{k:03d}_*.pdf"), None)
        if not f: raise HTTPException(404, "Arquivo não encontrado.")
        return FileResponse(f, media_type="application/pdf", filename=rep["files"][k - 1]["name"])

    @r.get("/{sid}/zip")
    def zip_(sid: str):
        _report(sid); z = store.STORAGE / sid / "arquivos.zip"
        if not z.exists(): raise HTTPException(404, "Arquivo não encontrado.")
        return FileResponse(z, media_type="application/zip", filename="documentos_separados.zip")

    @r.delete("/{sid}", status_code=204)
    def delete(sid: str):
        _job(sid); shutil.rmtree(store.STORAGE / sid, ignore_errors=True); store.delete(sid)

    return r
