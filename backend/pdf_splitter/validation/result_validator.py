"""Segunda análise INDEPENDENTE: reabre os PDFs gerados, extrai o texto de novo, reaplica as regras a cada
arquivo e reconstrói virtualmente o original para comparar página a página (impressão digital)."""
import hashlib
from pathlib import Path
import pymupdf as fitz
from ..analysis.document_boundary_detector import detect
from ..analysis.rule_engine import Page
from ..extraction.text_extractor import MIN_TEXT, fingerprint

def validate_results(files: list[Path], docs: list[dict], orig_pages: list[dict], params, n: int) -> dict:
    checks, issues, rebuilt = [], [], []
    def add(name, ok, detail): checks.append({"name": name, "ok": bool(ok), "detail": detail})
    opened_ok = True
    for k, (f, d) in enumerate(zip(files, docs), 1):
        want = d["end"] - d["start"] + 1
        try: out = fitz.open(f)
        except Exception:
            opened_ok = False; issues.append({"code": "cannot_open", "doc": k, "pages": [], "message": f"O arquivo do documento {k} não abre."}); continue
        with out:
            if out.page_count != want:
                issues.append({"code": "page_count", "doc": k, "pages": [], "message": f"Documento {k}: esperado {want} página(s), gerado {out.page_count}."}); continue
            fps = [fingerprint(p) for p in out]; rebuilt += fps
            exp = [orig_pages[i]["fp"] for i in range(d["start"] - 1, d["end"])]
            for j, (a, b) in enumerate(zip(fps, exp)):
                if a != b: issues.append({"code": "page_changed", "doc": k, "pages": [d["start"] + j], "message": f"Documento {k}: a página {d['start'] + j} do original difere da página gerada."})
            pg = []
            for j, p in enumerate(out):
                t = p.get_text("text")
                if len(t.strip()) < MIN_TEXT: t = orig_pages[d["start"] - 1 + j]["text"]   # página escaneada: reaproveita o OCR
                pg.append(Page(j + 1, t))
            if params.strategy != "semantic" and len(pg) > 1:
                det = detect(pg, params)
                minp = max(params.min_document_pages, 1 if params.allow_single_page_documents else 2)
                for j in det.candidates:
                    if j >= minp and len(pg) - j >= minp:
                        issues.append({"code": "internal_start", "doc": k, "pages": [d["start"] + j],
                                       "message": f"Documento {k} contém, na página {d['start'] + j}, características de início de outro documento (possível mistura)."})
            if params.identifier.type != "none" and len(pg) > 1:
                det2 = detect(pg, params)
                vals = {v for v in det2.ids if v}
                if len(vals) > 1: issues.append({"code": "mixed_ids", "doc": k, "pages": [], "message": f"Documento {k} contém mais de um identificador ({', '.join(sorted(vals))[:80]})."})
    exp_all = [p["fp"] for p in orig_pages]
    seq_ok = rebuilt == exp_all
    add("Todos os arquivos abrem", opened_ok, f"{len(files)} arquivo(s)")
    add("Quantidade de páginas confere com a prévia", not any(i["code"] == "page_count" for i in issues), "por documento")
    add("Reconstrução virtual igual ao original (mesma ordem, mesmo conteúdo)", seq_ok,
        f"{len(rebuilt)} de {n} páginas" if seq_ok else f"{len(rebuilt)} páginas geradas para {n} no original")
    add("Nenhuma página alterada", not any(i["code"] == "page_changed" for i in issues), "impressão digital por página")
    add("Sem mistura entre documentos", not any(i["code"] in ("internal_start", "mixed_ids") for i in issues), "regras reaplicadas a cada arquivo")
    digest = hashlib.sha256("".join(rebuilt).encode()).hexdigest()[:16]
    lost = max(0, n - len(rebuilt)); dup = max(0, len(rebuilt) - n)
    return {"ok": all(c["ok"] for c in checks), "checks": checks, "issues": issues, "pages_original": n, "pages_processed": len(rebuilt),
            "lost": lost, "duplicated": dup, "sequence_equal": seq_ok, "digest": digest}
