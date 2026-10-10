"""Orquestra: extração -> parâmetros -> detecção -> simulação -> (confirmação) -> separação -> reanálise
independente -> integridade -> autocorreção -> relatório. A IA só fornece evidências; as decisões críticas
(cobertura, ordem, páginas perdidas/duplicadas) são determinísticas."""
import json, zipfile
from datetime import datetime, timezone
from pathlib import Path
from ..analysis.document_boundary_detector import Issue, detect, doc_confidence, docs_from_starts
from ..analysis.parameter_parser import parse_instruction
from ..analysis.pattern_detector import extract_identifier
from ..analysis.rule_engine import Page
from ..analysis.semantic_analyzer import get_analyzer
from ..confidence.confidence_scorer import level
from ..extraction.ocr_engine import get_ocr
from ..extraction.text_extractor import extract_pages, open_pdf, summarize
from ..models import SplitParams
from ..splitting.file_naming import build_names, clean_name
from ..splitting.pdf_splitter import split
from ..validation.content_validator import validate_content
from ..validation.integrity_validator import check_ranges
from ..validation.result_validator import validate_results
from ..validation.rule_validator import validate_criteria

MAX_FIX_ATTEMPTS = 2
class NeedsReview(Exception): pass

def _now(): return datetime.now(timezone.utc).strftime("%H:%M:%S")
def _rw(path: Path, data=None):
    if data is None: return json.loads(path.read_text(encoding="utf-8"))
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

# ---------- 1. extração ----------
def analyze_upload(work: Path, size_bytes: int, progress=None) -> dict:
    doc = open_pdf(work / "original.pdf"); ocr = get_ocr()
    with doc:
        pages = extract_pages(doc, ocr, progress); info = summarize(doc, pages, ocr, size_bytes)
    _rw(work / "analysis.json", {"pages": pages, "info": info}); return info

def load_pages(work: Path):
    a = _rw(work / "analysis.json"); return a, [Page(p["n"], p["text"], p["scanned"]) for p in a["pages"]]

# ---------- 2. instrução -> parâmetros ----------
def interpret(work: Path, instruction: str) -> dict:
    _, pages = load_pages(work)
    params, notes, source = parse_instruction(instruction, pages)
    return {"params": params.model_dump(), "notes": notes, "source": source}

# ---------- 3. simulação ----------
def _ai_candidates(pages, det):
    st = set(det.starts)
    idx = [i for i in det.starts if i > 0 and det.scores[i] < 90]
    idx += [i for i in range(len(pages)) if i not in st and pages[i].counter and pages[i].counter[0] == 1][:10]
    idx += [i for i in range(len(pages)) if i not in st and any(e.rule == "structure" and e.weight > 0 for e in det.evidence[i])][:10]
    return idx

def build_docs(det, params, pages, starts, auto_starts, names: dict | None = None, removed=frozenset()) -> list[dict]:
    names = names or {}
    rng = docs_from_starts(starts, det.n); docs = []
    for k, (a, b) in enumerate(rng):
        joined = any(a < r <= b for r in removed)      # o usuário uniu documentos aqui
        manual = a not in auto_starts or joined
        ident = next((det.ids[i] for i in range(a, b + 1) if det.ids[i]), None)
        conf = None if manual else doc_confidence(det, a, b)
        ev = ["Documentos unidos pelo usuário." if joined else "Divisão definida manualmente pelo usuário."] if manual else [f"{e.detail} ({'+' if e.weight > 0 else ''}{e.weight})" for e in det.evidence[a]]
        docs.append({"index": k + 1, "start": a + 1, "end": b + 1, "identifier": ident, "manual": manual, "confidence": conf,
                     "level": "manual" if manual else level(conf), "evidence": ev, "warnings": [], "review": False, "user_name": names.get(a)})
    auto = build_names(docs, params)
    for d, n in zip(docs, auto): d["name"] = clean_name(d["user_name"]) if d["user_name"] else n
    for d in docs: d.pop("user_name")
    return docs

def _issues(det, params, pages, starts, ai_issues):
    iss = [*validate_criteria(det, params, starts), *validate_content(pages, det, starts, det.ids)]
    iss += [i for i in ai_issues if i.pages and (i.pages[0] - 1) not in starts]
    return iss

def _finish(docs, issues, params, n) -> dict:
    thr = round(params.confidence_threshold * 100)
    for d in docs:
        hit = [i for i in issues if i.severity != "info" and any(d["start"] <= p <= d["end"] for p in i.pages)]
        d["warnings"] = [i.message for i in hit]
        d["review"] = bool((not d["manual"] and d["confidence"] < thr) or hit)
    blocking = check_ranges(docs, n)
    levels = [d["level"] for d in docs]
    needs = any(d["review"] for d in docs) or any(i.severity in ("warning", "error") for i in issues)
    return {"documents": docs, "issues": [i.to_dict() for i in issues], "integrity": blocking, "needs_review": needs,
            "summary": {"documents": len(docs), "high": levels.count("alta"), "medium": levels.count("media"), "low": levels.count("baixa"),
                        "manual": levels.count("manual"), "review": sum(d["review"] for d in docs)}}

def simulate(work: Path, params: SplitParams) -> dict:
    a, pages = load_pages(work); n = len(pages)
    det = detect(pages, params); verdicts, ai_issues, ai_used = None, [], False
    analyzer = get_analyzer(); idx = _ai_candidates(pages, det)
    if idx or det.starts:
        v = analyzer.classify_starts(pages, [0] + idx, params)
        if v is not None:
            verdicts, ai_used = v, True; det = detect(pages, params, v)
            for i, r in v.items():
                if i > 0 and i not in det.starts and r["is_start"] and r["confidence"] >= 0.75:
                    ai_issues.append(Issue("ai_divergence", "warning", f"A IA sugere um início na página {i + 1} ({r['reason']}), mas as regras não detectaram. Divergência entre as camadas.", [i + 1],
                                           [{"label": f"Dividir também na página {i + 1}", "starts": sorted(set(det.starts) | {i})}, {"label": "Manter como está", "starts": det.starts}]))
    starts = det.starts
    issues = _issues(det, params, pages, starts, ai_issues) + det.issues
    plan = _finish(build_docs(det, params, pages, starts, set(starts)), issues, params, n)
    plan["layers"] = {"rules": True, "structure": len(starts) >= 3, "footer": det.footer_reliable, "ai": ai_used}
    _rw(work / "ctx.json", {"params": params.model_dump(), "auto_starts": starts, "verdicts": {str(k): v for k, v in (verdicts or {}).items()},
                            "ai_issues": [i.to_dict() for i in ai_issues]})
    return plan

# ---------- 4. edição da prévia ----------
def _ctx(work: Path):
    c = _rw(work / "ctx.json"); params = SplitParams(**c["params"])
    verd = {int(k): v for k, v in c["verdicts"].items()} or None
    return c, params, verd

def apply_edit(work: Path, docs_in: list[dict]) -> dict:
    """Recalcula a prévia a partir dos limites escolhidos pelo usuário (a confiança vem do servidor, nunca do cliente)."""
    c, params, verd = _ctx(work); a, pages = load_pages(work); n = len(pages)
    check = check_ranges(docs_in, n)
    if not check["ok"]: raise ValueError(" ".join(check["problems"]))
    det = detect(pages, params, verd)
    starts = sorted(d["start"] - 1 for d in docs_in)
    names = {d["start"] - 1: d["name"] for d in docs_in if d.get("name")}
    ai_issues = [Issue(**i) for i in c["ai_issues"]]
    issues = _issues(det, params, pages, starts, ai_issues)
    plan = _finish(build_docs(det, params, pages, starts, set(c["auto_starts"]), names, set(c["auto_starts"]) - set(starts)), issues, params, n)
    plan["layers"] = {"rules": True, "structure": len(det.starts) >= 3, "footer": det.footer_reliable, "ai": verd is not None}
    return plan

# ---------- 5. separação + validação + autocorreção ----------
def _autocorrect(docs, issues, ids, starts_set):
    new, notes = set(starts_set), []
    for i in issues:
        d = docs[i["doc"] - 1] if i.get("doc") else None
        if i["code"] == "internal_start" and d and not d["manual"]:
            new.add(i["pages"][0] - 1); notes.append(f"Página {i['pages'][0]} apresentava características de início de documento; criada uma divisão.")
        elif i["code"] == "mixed_ids" and d and not d["manual"]:
            first = next((ids[p - 1] for p in range(d["start"], d["end"] + 1) if ids[p - 1]), None)
            p = next((p for p in range(d["start"], d["end"] + 1) if ids[p - 1] and ids[p - 1] != first), None)
            if p: new.add(p - 1); notes.append(f"Identificador diferente na página {p}; criada uma divisão.")
        elif i["code"] == "split_mid_document" and not docs[next(k for k, x in enumerate(docs) if x["start"] == i["pages"][0])]["manual"]:
            new.discard(i["pages"][0] - 1); notes.append(f"Página {i['pages'][0]} apresentava continuidade do documento anterior; divisão removida.")
    return (new, notes) if new != set(starts_set) else (None, [])

def execute(work: Path, docs_in: list[dict], ack: bool, progress=None) -> dict:
    hist = []
    def log(m): hist.append({"t": _now(), "event": m})
    plan = apply_edit(work, docs_in)
    if not plan["integrity"]["ok"]: raise ValueError(" ".join(plan["integrity"]["problems"]))
    if plan["needs_review"] and not ack: raise NeedsReview("Há divisões de baixa confiança ou alertas. Revise e confirme que revisou antes de separar.")
    c, params, verd = _ctx(work); a, pages = load_pages(work); n = len(pages)
    det = detect(pages, params, verd); original = work / "original.pdf"
    docs = plan["documents"]; log(f"Separação iniciada com {len(docs)} documento(s) ({'revisada pelo usuário' if ack else 'sem alertas'}).")
    attempt, rep, files = 0, None, []
    while True:
        files = split(original, docs, work / "out")
        rep = validate_results(files, docs, a["pages"], params, n)
        out_pages = []
        for d, f in zip(docs, files):
            import pymupdf as fitz
            with fitz.open(f) as o:
                for j, p in enumerate(o):
                    t = p.get_text("text")
                    out_pages.append(Page(d["start"] + j, t if len(t.strip()) >= 25 else pages[d["start"] - 1 + j].text))
        ids = [extract_identifier(p.text, params.identifier) for p in out_pages]
        starts = [d["start"] - 1 for d in docs]
        post = [i.to_dict() | {"doc": next(k + 1 for k, d in enumerate(docs) if d["start"] - 1 == s)} for i in validate_content(out_pages, det, starts, ids)
                for s in [i.pages[0] - 1 if i.code == "split_mid_document" else -1] if i.code == "split_mid_document"]
        all_issues = rep["issues"] + post
        log(f"Reanálise independente: {sum(c['ok'] for c in rep['checks'])}/{len(rep['checks'])} verificações OK, {len(all_issues)} alerta(s).")
        if not all_issues or attempt >= MAX_FIX_ATTEMPTS: break
        new, notes = _autocorrect(docs, all_issues, ids, set(starts))
        if new is None: break
        attempt += 1; [log(f"Autocorreção {attempt}: {m}") for m in notes]
        keep = {d["start"] - 1: d["name"] for d in docs if d["manual"]}
        docs = build_docs(det, params, pages, sorted(new), set(c["auto_starts"]) | new, keep)
        docs = _finish(docs, [], params, n)["documents"]; log("Nova proposta gerada e revalidada.")
    status = "review_required" if not rep["ok"] else ("completed" if not all_issues else "completed_with_warnings")
    zp = work / "arquivos.zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for f in files: z.write(f, f.name.split("_", 1)[1])
    levels = [d["level"] for d in docs]
    report = {"status": status, "pages_original": n, "pages_processed": rep["pages_processed"], "lost": rep["lost"], "duplicated": rep["duplicated"],
              "documents": len(docs), "high": levels.count("alta"), "medium": levels.count("media"), "low": levels.count("baixa"), "manual": levels.count("manual"),
              "review": sum(d["review"] for d in docs), "integrity_ok": rep["ok"], "checks": rep["checks"], "issues": all_issues, "digest": rep["digest"],
              "history": hist, "corrections": attempt, "ai_used": verd is not None,
              "files": [{"index": k, "name": d["name"] + ".pdf", "pages": f"{d['start']}–{d['end']}" if d["start"] != d["end"] else str(d["start"]),
                         "confidence": d["confidence"], "level": d["level"], "manual": d["manual"], "identifier": d["identifier"], "size": f.stat().st_size,
                         "evidence": d["evidence"]} for k, (d, f) in enumerate(zip(docs, files), 1)]}
    log("Relatório final gerado."); report["history"] = hist; _rw(work / "report.json", report); return report
