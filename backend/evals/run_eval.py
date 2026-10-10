"""Mede o acerto do separador, sem IA e com IA, em PDFs sintéticos com gabarito.
Uso (na pasta backend):
    python -m evals.run_eval                       # só regras (não precisa de chave)
    ANTHROPIC_API_KEY=... python -m evals.run_eval # regras e IA, lado a lado
    python -m evals.run_eval --fake                # IA SIMULADA, só para testar o medidor (não mede a IA real)
Provedor: ANTHROPIC_API_KEY ou GEMINI_API_KEY (SPLIT_AI_PROVIDER escolhe). Custo: EVAL_PRICE_IN / EVAL_PRICE_OUT em US$ por milhão de tokens
(padrão só para o Claude Haiku 4.5: 1,00 / 5,00; confirme na tabela atual. Para o Gemini, informe os preços)."""
import json, os, sys, tempfile, time, re
from pathlib import Path
KEYS = {k: os.environ.pop(k) for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY") if os.environ.get(k)}  # modo "regras" não pode usar IA
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(); os.environ.pop("REDIS_URL", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi.testclient import TestClient
from main import app
from pdf_splitter.analysis import semantic_analyzer as sa
from evals.corpus import build_cases

app.state.limiter.enabled = False
c = TestClient(app)
PRICE_IN, PRICE_OUT = os.getenv("EVAL_PRICE_IN"), os.getenv("EVAL_PRICE_OUT")   # US$ por milhão de tokens

class Oracle(sa.LLMClient):
    """IA SIMULADA: responde com o gabarito (com 5% de erro). Serve só para validar o medidor."""
    name, model = "simulada", "simulada"
    truth: set[int] = set(); stats = {"calls": 0, "errors": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0}
    def complete(self, system, user, max_tokens=1500):
        self.stats["calls"] += 1
        if "Converta a instrução" in user: raise RuntimeError("interpretação indisponível no modo simulado")
        pages = [int(x) for x in re.findall(r'"page": (\d+)', user)]
        return json.dumps([{"page": p, "is_start": (p in self.truth) ^ (p % 20 == 7), "confidence": 0.9, "reason": "simulado"} for p in pages])

def run_case(case, label):
    r = c.post("/api/split", files={"file": ("lote.pdf", case.pdf, "application/pdf")}); sid = r.json()["split_id"]
    for _ in range(300):
        s = c.get(f"/api/split/{sid}").json()
        if s["status"] in ("completed", "failed"): break
        time.sleep(.1)
    res = {"case": case.name, "mode": label, "hard": case.hard, "truth": case.truth, "interpret": "ok"}
    t0 = time.time(); ir = c.post(f"/api/split/{sid}/interpret", json={"instruction": case.instruction})
    if ir.status_code != 200:
        res.update(interpret="falhou", error=ir.json().get("detail", "")[:120], f1=0.0, exact=False, alerta=True, starts=[]); return res
    j = ir.json(); res["source"] = j["source"]; res["params"] = j["params"]
    sim = c.post(f"/api/split/{sid}/simulate", json=j["params"]).json()
    docs = sim.get("documents") or sim.get("docs") or []
    starts = sorted(d["start"] for d in docs)
    pred, truth = set(starts[1:]), set(case.truth[1:])
    tp = len(pred & truth); prec = tp / len(pred) if pred else (1.0 if not truth else 0.0); rec = tp / len(truth) if truth else 1.0
    res.update(starts=starts, precision=round(prec, 3), recall=round(rec, 3), f1=round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0,
               exact=starts == case.truth, alerta=bool(sim.get("needs_review")), n_avisos=len(sim.get("issues", [])), seconds=round(time.time() - t0, 2))
    c.delete(f"/api/split/{sid}")
    return res

def run(label, cases, client=None):
    out = []
    for case in cases:
        if client is None: sa.set_llm(None)
        else:
            sa.set_llm(client); client.truth = set(case.truth) if isinstance(client, Oracle) else None
        before = dict(client.stats) if client else None
        r = run_case(case, label)
        if client: r["ai"] = {k: round(client.stats[k] - before[k], 2) for k in before}
        out.append(r)
    sa.set_llm(None); return out

def show(rs, title):
    print(f"\n== {title}"); print(f"{'caso':28} {'interpretou':11} {'F1':>5} {'exato':>6} {'alerta':>7}  limites encontrados / gabarito")
    for r in rs: print(f"{r['case']:28} {r['interpret']:11} {r['f1']:>5} {'sim' if r['exact'] else 'não':>6} {'sim' if r['alerta'] else 'não':>7}  {r['starts']} / {r['truth']}" + (f"  [{r['error']}]" if r.get("error") else ""))
    ok = [r for r in rs if r["interpret"] == "ok"]
    print(f"-> interpretou {len(ok)}/{len(rs)} | F1 médio {sum(r['f1'] for r in rs) / len(rs):.3f} | documentos exatos {sum(r['exact'] for r in rs)}/{len(rs)} | "
          f"ERROS SEM ALERTA (o pior caso): {sum((not r['exact']) and (not r['alerta']) for r in rs)}")

def main():
    cases = build_cases(); report = {}
    base = run("regras", cases); show(base, "SEM IA (só regras)"); report["regras"] = base
    os.environ.update(KEYS); client = Oracle() if "--fake" in sys.argv else sa.get_llm()
    if client is None: print("\n(nenhuma chave definida: modo com IA não executado. Use ANTHROPIC_API_KEY ou GEMINI_API_KEY)")
    else:
        tag = "IA SIMULADA (não mede a IA real)" if isinstance(client, Oracle) else f"COM IA ({client.name}: {client.model})"
        ai = run("ia", cases, client); show(ai, tag); report["ia"] = ai; st = client.stats
        pi, po = PRICE_IN or ("1.0" if client.name == "anthropic" else None), PRICE_OUT or ("5.0" if client.name == "anthropic" else None)
        cost = f"US$ {st['input_tokens'] / 1e6 * float(pi) + st['output_tokens'] / 1e6 * float(po):.4f}" if pi and po else "defina EVAL_PRICE_IN e EVAL_PRICE_OUT (US$ por milhão de tokens; não chuto preços)"
        print(f"chamadas {st['calls']} | falhas {st['errors']} | tokens {st['input_tokens']} entrada / {st['output_tokens']} saída | {st['seconds']:.1f}s | custo estimado: {cost}")
    Path(__file__).with_name("resultados.json").write_text(json.dumps(report, ensure_ascii=False, indent=1))

if __name__ == "__main__": main()
