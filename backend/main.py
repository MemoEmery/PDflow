import uuid, shutil, time, re, json, threading, logging, os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import store
from tasks import run_job, mark_failed
from services.converters import OFFICE, IMAGES
from services.pdf_tools import PDF_TOOLS

log = logging.getLogger("pdflow")
STORAGE = store.STORAGE
MAX_BYTES = 25 * 1024 * 1024
MAX_FILES = 20
TTL = 30 * 60  # resultados e originais são apagados em até 30 min
MIMES = {".pdf": "application/pdf", ".zip": "application/zip",
         ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
         ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
         ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
         ".txt": "text/plain; charset=utf-8"}
ALLOWED = OFFICE | IMAGES | {".txt", ".html", ".htm"}
MIME_OK = {".jpg": "image/", ".jpeg": "image/", ".png": "image/", ".webp": "image/"}

app = FastAPI(title="PDflow API", version="0.4.0")
limiter = Limiter(key_func=get_remote_address); app.state.limiter = limiter
pool = ThreadPoolExecutor(max_workers=2)
queue = None
if store.REDIS:
    from rq import Queue
    queue = Queue(connection=store.REDIS)

def enqueue(fn, *args):
    if queue: queue.enqueue(fn, *args, job_timeout=900 if fn is not run_job else 180, result_ttl=0, failure_ttl=60, on_failure=mark_failed)
    else: pool.submit(fn, *args)

from split_api import build_router  # módulo adicional: Separar PDF com IA
app.include_router(build_router(limiter, enqueue))

def safe_name(name: str) -> str:
    return re.sub(r"[^\w.\-]", "_", Path(name).name)[:100] or "arquivo"

def _remove(job_id: str):
    if re.fullmatch(r"[0-9a-f]{32}", job_id): shutil.rmtree(STORAGE / job_id, ignore_errors=True)
    store.delete(job_id)

# ---------- conversões ----------
@app.post("/api/convert", status_code=202)
@limiter.limit("20/minute")
async def create_conversion(request: Request, files: list[UploadFile] = File(...),
                            tool: str = Form("to-pdf"), options: str = Form("{}")):
    if len(files) > MAX_FILES: raise HTTPException(400, f"Envie no máximo {MAX_FILES} arquivos.")
    if tool != "to-pdf" and tool not in PDF_TOOLS: raise HTTPException(400, "Ferramenta desconhecida.")
    try:
        opts = json.loads(options) if len(options) <= 2000 else None
        if not isinstance(opts, dict): raise ValueError
    except ValueError: raise HTTPException(400, "Opções inválidas.")
    allowed = {".pdf"} if tool in PDF_TOOLS else ALLOWED
    job_id = uuid.uuid4().hex; work = STORAGE / job_id; work.mkdir()
    saved, names = [], []
    try:
        for i, up in enumerate(files):
            name = safe_name(up.filename or "arquivo"); ext = Path(name).suffix.lower()
            if ext not in allowed: raise HTTPException(400, "Esse formato ainda não é suportado.")
            if ext in MIME_OK and not (up.content_type or "").startswith(MIME_OK[ext]):
                raise HTTPException(400, "Esse formato ainda não é suportado.")
            data = await up.read(MAX_BYTES + 1)
            if len(data) > MAX_BYTES: raise HTTPException(413, "O arquivo excede o limite permitido.")
            if ext == ".pdf" and not data.startswith(b"%PDF"): raise HTTPException(400, "Esse arquivo não parece ser um PDF válido.")
            p = work / f"{i:03d}_{name}"; p.write_bytes(data); saved.append(p); names.append(name)
        if tool in PDF_TOOLS and (len(saved) < 2 if tool == "merge-pdf" else len(saved) != 1):
            raise HTTPException(400, "Envie pelo menos 2 PDFs." if tool == "merge-pdf" else "Envie um único PDF.")
        if {p.suffix.lower() for p in saved} & IMAGES and not all(p.suffix.lower() in IMAGES for p in saved):
            raise HTTPException(400, "Não misture imagens com outros formatos na mesma conversão.")
    except HTTPException:
        shutil.rmtree(work, ignore_errors=True); raise
    now = time.time()
    store.save({"job_id": job_id, "status": "pending", "created": now, "expires": now + TTL})
    enqueue(run_job, job_id, [str(p) for p in saved], tool, opts)
    return {"job_id": job_id, "status": "pending"}

@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    j = store.load(job_id)
    if not j: raise HTTPException(404, "Tarefa não encontrada ou já expirou.")
    return {k: j.get(k) for k in ("job_id", "status", "filename", "error", "file_id") if k in j}

def _file_path(file_id: str) -> Path:
    j = store.load(file_id) if re.fullmatch(r"[0-9a-f]{32}", file_id) else None
    if not j or j["status"] != "completed" or "filename" not in j: raise HTTPException(404, "Arquivo não encontrado.")
    return STORAGE / file_id / j["filename"]

@app.get("/api/files/{file_id}")
def get_file(file_id: str, download: bool = True):
    p = _file_path(file_id)
    return FileResponse(p, media_type=MIMES.get(p.suffix, "application/octet-stream"), filename=p.name,
                        content_disposition_type="attachment" if download else "inline")

@app.delete("/api/files/{file_id}", status_code=204)
def delete_file(file_id: str):
    _file_path(file_id); _remove(file_id)

def cleaner():  # roda na API; funciona igual com Redis ou memória
    while True:
        try:
            now = time.time()
            for d in STORAGE.iterdir():
                if not d.is_dir(): continue
                j = store.load(d.name)
                if (j and j["expires"] < now) or (not j and now - d.stat().st_mtime > 120):
                    shutil.rmtree(d, ignore_errors=True); store.delete(d.name)
        except Exception: log.exception("falha na limpeza")
        time.sleep(60)
threading.Thread(target=cleaner, daemon=True).start()

_origins = [o.strip().rstrip("/") for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]
if _origins:  # site em outro endereço (ex.: Vercel). Vazio = só mesmo endereço, sem CORS.
    from fastapi.middleware.cors import CORSMiddleware
    app.add_middleware(CORSMiddleware, allow_origins=_origins, allow_methods=["GET", "POST", "DELETE"], allow_headers=["*"],
                       expose_headers=["Content-Disposition"], allow_credentials=False, max_age=600)

@app.get("/api/health", include_in_schema=False)
def health(): return {"status": "ok"}

@app.exception_handler(RateLimitExceeded)
async def too_many(_, exc):
    return JSONResponse({"detail": "Muitas tentativas seguidas. Aguarde um minuto."}, status_code=429)

@app.exception_handler(RequestValidationError)
async def invalid(_, exc):
    msg = str(exc.errors()[0].get("msg", "")).replace("Value error, ", "") if exc.errors() else ""
    return JSONResponse({"detail": "Os dados enviados são inválidos" + (f": {msg}" if msg else ".")}, status_code=422)

@app.exception_handler(Exception)
async def generic(_, exc):
    log.exception("erro não tratado")
    return JSONResponse({"detail": "Algo deu errado. Tente novamente."}, status_code=500)

STATIC = Path("static").resolve(); (STATIC / "assets").mkdir(parents=True, exist_ok=True)
app.mount("/assets", StaticFiles(directory=STATIC / "assets"), name="assets")

@app.get("/{path:path}", include_in_schema=False)
def spa(path: str):
    if path.startswith("api/"): raise HTTPException(404, "Recurso não encontrado.")
    f = (STATIC / path).resolve()
    if path and f.is_file() and STATIC in f.parents: return FileResponse(f)
    idx = STATIC / "index.html"
    if not idx.exists(): raise HTTPException(404, "Frontend não compilado.")
    return FileResponse(idx)
