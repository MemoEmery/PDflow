"""Testes do módulo Separar PDF com IA. A IA é simulada (nenhuma chamada externa)."""
import io, json, os, sys, tempfile, time, zipfile
from pathlib import Path
os.environ["STORAGE_DIR"] = tempfile.mkdtemp(); os.environ.pop("REDIS_URL", None); os.environ.pop("ANTHROPIC_API_KEY", None)
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pymupdf as fitz, pytest
from fastapi.testclient import TestClient
from main import app
from pdf_splitter.analysis import semantic_analyzer as sa
from pdf_splitter.analysis.parameter_parser import NeedsRewrite, heuristic_parse

app.state.limiter.enabled = False
c = TestClient(app)

def nf_pdf(plan, keyword_on_first=True, footer=True):
    """plan: [(numero, paginas)] — cada documento é uma nota fiscal."""
    d = fitz.open()
    for num, pgs in plan:
        for k in range(pgs):
            p = d.new_page(); y = 60
            if k == 0:
                if keyword_on_first: p.insert_text((72, y), "NOTA FISCAL ELETRÔNICA"); y += 20
                p.insert_text((72, y), f"Nº {num:06d}"); y += 20; p.insert_text((72, y), "Cliente: ACME LTDA")
            else: p.insert_text((72, 60), f"Itens da nota {num} pagina {k + 1}")
            if footer: p.insert_text((72, 780), f"Página {k + 1} de {pgs}")
    return d.tobytes()

def start(pdf: bytes):
    r = c.post("/api/split", files={"file": ("lote.pdf", pdf, "application/pdf")}); assert r.status_code == 202, r.text
    sid = r.json()["split_id"]
    for _ in range(100):
        s = c.get(f"/api/split/{sid}").json()
        if s["status"] in ("completed", "failed"): break
        time.sleep(.1)
    return sid, s

def run(sid):
    for _ in range(150):
        s = c.get(f"/api/split/{sid}").json()
        if s["stage"] == "done" or s.get("exec_error"): return s
        time.sleep(.1)
    raise AssertionError("tempo esgotado")

PARAMS = {"strategy": "keyword", "start_keywords": ["NOTA FISCAL"], "identifier": {"type": "invoice_number"}}

def test_instrucoes_do_enunciado():
    cases = {"Separe sempre que começar um novo contrato.": ("keyword", "none"), "Cada cliente deve ficar em um PDF separado.": ("identifier", "customer_name"),
             "Separe pela mudança do nome do paciente.": ("identifier", "customer_name"), "Separe os documentos utilizando o número do processo.": ("identifier", "process"),
             "Cada nota fiscal deve ficar em um arquivo separado.": ("keyword", "none")}
    for t, (strat, ident) in cases.items():
        p, _ = heuristic_parse(t); assert (p.strategy, p.identifier.type) == (strat, ident), t
    with pytest.raises(NeedsRewrite): heuristic_parse("faça algo legal")

def test_fluxo_completo_com_prova_de_integridade():
    sid, s = start(nf_pdf([(1245, 3), (1246, 2), (1247, 4), (1248, 2), (1249, 2)]))
    assert s["status"] == "completed" and s["info"]["page_count"] == 13 and s["info"]["text_pages"] == 13
    i = c.post(f"/api/split/{sid}/interpret", json={"instruction": "Cada nota fiscal deve ficar em um arquivo separado. O número da nota deve ser usado no nome."}).json()
    assert i["source"] == "heuristic" and i["params"]["identifier"]["type"] == "invoice_number"
    pl = c.post(f"/api/split/{sid}/simulate", json=i["params"]).json()
    assert [(d["start"], d["end"]) for d in pl["documents"]] == [(1, 3), (4, 5), (6, 9), (10, 11), (12, 13)]
    assert pl["integrity"]["ok"] and not pl["needs_review"] and all(d["level"] == "alta" for d in pl["documents"])
    assert any("NOTA FISCAL" in e for e in pl["documents"][1]["evidence"])          # explicabilidade
    assert c.post(f"/api/split/{sid}/execute", json={"documents": pl["documents"]}).status_code == 202
    s = run(sid); rep = s["report"]
    assert rep["status"] == "completed" and (rep["pages_original"], rep["pages_processed"], rep["lost"], rep["duplicated"]) == (13, 13, 0, 0)
    assert all(ch["ok"] for ch in rep["checks"]) and [f["name"] for f in rep["files"]][:2] == ["nota_fiscal_001245.pdf", "nota_fiscal_001246.pdf"]
    f2 = c.get(f"/api/split/{sid}/file/3"); assert f2.status_code == 200 and len(fitz.open(stream=f2.content)) == 4
    z = zipfile.ZipFile(io.BytesIO(c.get(f"/api/split/{sid}/zip").content)); assert len(z.namelist()) == 5
    assert c.get(f"/api/split/{sid}/page/1.png").headers["content-type"] == "image/png"
    assert c.delete(f"/api/split/{sid}").status_code == 204 and c.get(f"/api/split/{sid}").status_code == 404

def test_nao_separa_em_silencio_quando_ha_duvida():
    sid, _ = start(nf_pdf([(1, 3), (2, 3)], footer=False))                # só 2 documentos: sem confirmação independente
    pl = c.post(f"/api/split/{sid}/simulate", json={"strategy": "keyword", "start_keywords": ["NOTA FISCAL"]}).json()   # uma única regra, sem confirmação independente
    assert pl["needs_review"] and pl["documents"][1]["level"] == "media" and pl["documents"][1]["review"]
    r = c.post(f"/api/split/{sid}/execute", json={"documents": pl["documents"]}); assert r.status_code == 409
    assert c.post(f"/api/split/{sid}/execute", json={"documents": pl["documents"], "acknowledge_review": True}).status_code == 202
    assert run(sid)["report"]["status"] == "completed"

def test_criterio_amplo_e_criterio_sem_limites():
    sid, _ = start(nf_pdf([(1, 3), (2, 3), (3, 3)]))
    broad = c.post(f"/api/split/{sid}/simulate", json={"strategy": "keyword", "start_keywords": ["Cliente", "Itens", "NOTA"]}).json()
    assert "criterion_too_broad" in [i["code"] for i in broad["issues"]]
    none = c.post(f"/api/split/{sid}/simulate", json={"strategy": "keyword", "start_keywords": ["CONTRATO"]}).json()
    assert any(i["code"] == "no_boundaries" and i["severity"] == "error" for i in none["issues"]) and none["needs_review"]

def test_ambiguidade_oferece_alternativas_e_edicao_valida_cobertura():
    sid, _ = start(nf_pdf([(1, 4), (2, 4), (3, 1), (4, 4)]))
    pl = c.post(f"/api/split/{sid}/simulate", json=PARAMS).json()
    amb = next(i for i in pl["issues"] if i["code"] == "ambiguous_boundary"); assert len(amb["alternatives"]) == 2
    a = amb["alternatives"][0]["starts"]; docs = [{"start": s + 1, "end": (a[k + 1] if k + 1 < len(a) else 13)} for k, s in enumerate(a)]
    ed = c.post(f"/api/split/{sid}/plan", json={"documents": docs}).json()
    assert "ambiguous_boundary" not in [i["code"] for i in ed["issues"]] and ed["integrity"]["ok"]
    bad = c.post(f"/api/split/{sid}/plan", json={"documents": [{"start": 1, "end": 5}, {"start": 7, "end": 13}]}); assert bad.status_code == 422 and "órfãs" in bad.json()["detail"]
    assert c.post(f"/api/split/{sid}/plan", json={"documents": [{"start": 1, "end": 7}, {"start": 7, "end": 13}]}).status_code == 422

def test_uniao_feita_pelo_usuario_fica_travada():
    sid, _ = start(nf_pdf([(1, 3), (2, 3), (3, 3), (4, 3)]))
    pl = c.post(f"/api/split/{sid}/simulate", json=PARAMS).json()
    ed = c.post(f"/api/split/{sid}/plan", json={"documents": [{"start": 1, "end": 6}, {"start": 7, "end": 9}, {"start": 10, "end": 12}]}).json()
    assert ed["documents"][0]["manual"] and ed["documents"][0]["level"] == "manual"
    c.post(f"/api/split/{sid}/execute", json={"documents": ed["documents"], "acknowledge_review": True})
    rep = run(sid)["report"]
    assert rep["corrections"] == 0 and [f["pages"] for f in rep["files"]][0] == "1–6"          # a autocorreção não desfaz a decisão do usuário
    assert rep["lost"] == 0 and rep["duplicated"] == 0

def test_autocorrecao_registrada_no_historico():
    d = fitz.open()      # 2ª nota SEM a palavra-chave na primeira página: a regra sozinha junta as duas notas
    for num, kw in ((10, True), (11, False)):
        for k in range(2):
            p = d.new_page()
            if k == 0:
                if kw: p.insert_text((72, 60), "NOTA FISCAL")
                p.insert_text((72, 80), f"Nº {num:06d}")
            else: p.insert_text((72, 60), f"continuação {num}")
    sid, _ = start(d.tobytes())
    pl = c.post(f"/api/split/{sid}/simulate", json=PARAMS).json()
    assert len(pl["documents"]) == 1 and "mixed_document" in [i["code"] for i in pl["issues"]] and pl["needs_review"]
    c.post(f"/api/split/{sid}/execute", json={"documents": pl["documents"], "acknowledge_review": True})
    rep = run(sid)["report"]
    assert rep["corrections"] == 1 and rep["documents"] == 2 and any("Autocorreção" in h["event"] for h in rep["history"])
    assert rep["lost"] == 0 and rep["duplicated"] == 0 and rep["status"] in ("completed", "completed_with_warnings")

def test_pdf_escaneado_usa_ocr():
    import shutil
    if not shutil.which("tesseract"): pytest.skip("sem Tesseract")
    d = fitz.open(); src = fitz.open(); pg = src.new_page(width=600, height=300); pg.insert_text((40, 120), "CONTRATO 12345", fontsize=40)
    d.new_page().insert_image(fitz.Rect(0, 0, 600, 300), pixmap=pg.get_pixmap(dpi=150))
    sid, s = start(d.tobytes())
    assert s["info"]["scanned_pages"] == 1 and s["info"]["ocr_pages"] == 1
    assert c.post(f"/api/split/{sid}/simulate", json={"strategy": "keyword", "start_keywords": ["CONTRATO"]}).status_code == 200

def test_ia_simulada_e_divergencia_entre_camadas():
    class Fake(sa.LLMClient):
        name, model = "fake", "fake"
        def complete(self, system, user, max_tokens=1500):
            assert "NÃO CONFIÁVEL" in system
            if "Converta a instrução" in user: return json.dumps({"params": {"strategy": "keyword", "start_keywords": ["NOTA FISCAL"]}, "notes": ["ok"]})
            pages = [int(x) for x in __import__("re").findall(r'"page": (\d+)', user)]
            return json.dumps([{"page": p, "is_start": p in (1, 4, 9), "confidence": 0.9, "reason": "teste"} for p in pages])
    sa.set_llm(Fake())
    try:
        sid, _ = start(nf_pdf([(1, 3), (2, 3), (3, 3)]))
        assert c.get(f"/api/split/{sid}").json()["ai"]["enabled"]
        i = c.post(f"/api/split/{sid}/interpret", json={"instruction": "separe por nota"}).json(); assert i["source"] == "ai"
        pl = c.post(f"/api/split/{sid}/simulate", json=i["params"]).json()
        assert pl["layers"]["ai"] and any(e for d in pl["documents"] for e in d["evidence"] if "IA classificou" in e)
        sa.set_llm(type("Bad", (sa.LLMClient,), {"name": "x", "model": "x", "complete": lambda *a, **k: "não é json"})())
        pl2 = c.post(f"/api/split/{sid}/simulate", json=i["params"]).json(); assert pl2["layers"]["ai"] is False       # IA falhou: segue só com regras
    finally: sa.set_llm(None)

def test_regex_malicioso_nao_trava_e_entradas_invalidas():
    sid, _ = start(nf_pdf([(1, 2), (2, 2)]))
    t = time.time(); r = c.post(f"/api/split/{sid}/simulate", json={"strategy": "pattern", "start_regexes": ["(a+)+$"]}); assert time.time() - t < 8 and r.status_code == 200
    assert c.post(f"/api/split/{sid}/simulate", json={"strategy": "pattern", "start_regexes": ["(["]}).status_code == 422
    assert c.post("/api/split", files={"file": ("x.pdf", b"nao e pdf", "application/pdf")}).status_code == 400
    enc = fitz.open(); enc.new_page(); b = enc.tobytes(encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="x", owner_pw="y")
    assert start(b)[1]["status"] == "failed"


def test_cliente_gemini_formato_da_chamada_tokens_e_erros(monkeypatch):
    seen = {}
    class Resp:
        def __init__(self, j): self.j = j
        def raise_for_status(self): pass
        def json(self): return self.j
    def fake_post(url, timeout, headers, json):
        seen.update(url=url, headers=headers, body=json)
        return Resp(FAKE_RESP.pop(0))
    FAKE_RESP = [{"candidates": [{"content": {"parts": [{"text": "raciocínio", "thought": True}, {"text": '{"ok": 1}'}]}}],
                  "usageMetadata": {"promptTokenCount": 120, "candidatesTokenCount": 10, "thoughtsTokenCount": 5}},
                 {"candidates": [{"finishReason": "SAFETY"}], "usageMetadata": {"promptTokenCount": 7}}]
    monkeypatch.setattr(sa.httpx, "post", fake_post)
    g = sa.GeminiClient("CHAVE", "gemini-2.5-flash")
    assert g.complete("SISTEMA", "USUARIO") == '{"ok": 1}'                       # ignora partes de "raciocínio"
    assert seen["url"].endswith("/v1beta/models/gemini-2.5-flash:generateContent") and seen["headers"]["x-goog-api-key"] == "CHAVE"
    assert seen["body"]["systemInstruction"]["parts"][0]["text"] == "SISTEMA" and seen["body"]["contents"][0]["parts"][0]["text"] == "USUARIO"
    assert seen["body"]["generationConfig"]["thinkingConfig"] == {"thinkingBudget": 0}
    assert g.stats["input_tokens"] == 120 and g.stats["output_tokens"] == 15 and g.stats["calls"] == 1
    with pytest.raises(RuntimeError): g.complete("s", "u")                        # resposta vazia/bloqueada vira erro tratável
    assert g.stats["calls"] == 2

def test_escolha_do_provedor_de_ia(monkeypatch):
    sa.set_llm(None)
    for k in ("ANTHROPIC_API_KEY", "GEMINI_API_KEY", "GOOGLE_API_KEY", "SPLIT_AI_PROVIDER", "SPLIT_AI_MODEL"): monkeypatch.delenv(k, raising=False)
    assert sa.get_llm() is None and sa.ai_status() == {"enabled": False, "model": None, "provider": None}
    monkeypatch.setenv("GOOGLE_API_KEY", "g"); assert isinstance(sa.get_llm(), sa.GeminiClient)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "a"); assert isinstance(sa.get_llm(), sa.AnthropicClient)       # sem preferência: Claude
    monkeypatch.setenv("SPLIT_AI_PROVIDER", "google"); assert isinstance(sa.get_llm(), sa.GeminiClient)
    monkeypatch.setenv("SPLIT_AI_MODEL", "gemini-2.5-flash-lite"); assert sa.ai_status()["model"] == "gemini-2.5-flash-lite"
    monkeypatch.delenv("GOOGLE_API_KEY"); assert sa.get_llm() is None                                      # provedor escolhido sem chave: desativa
