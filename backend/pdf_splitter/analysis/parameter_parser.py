"""Instrução em linguagem natural -> SplitParams. Com IA: interpretação livre; sem IA: heurísticas em português.
Em ambos os casos o resultado é validado pelo modelo e mostrado ao usuário; nunca se executa o texto bruto."""
import json, re
from pydantic import ValidationError
from ..models import SplitParams
from .pattern_detector import norm
from .semantic_analyzer import UNTRUSTED, get_llm, parse_json

DOC_TERMS = {"nota fiscal": ["NOTA FISCAL", "DANFE"], "contrato": ["CONTRATO"], "recibo": ["RECIBO"], "fatura": ["FATURA"],
             "relatorio": ["RELATÓRIO"], "laudo": ["LAUDO"], "boleto": ["BOLETO"], "holerite": ["HOLERITE"]}
CHANGE = re.compile(r"mudanc|muda\b|mudar|diferente|novo cliente|cada cliente|por cliente|cada paciente|por paciente|cada numero|cada processo|numero do processo|utilizando o numero|pelo numero")

class NeedsRewrite(ValueError): pass

def heuristic_parse(instruction: str) -> tuple[SplitParams, list[str]]:
    raw, t = instruction, norm(instruction); notes, kws, d = [], [], {}
    for m in re.finditer(r'["“]([^"”]{2,80})["”]|(?<!\w)\'([^\']{2,80})\'(?!\w)', raw):
        kws.append((m.group(1) or m.group(2)).strip())
    ident = {"type": "none"}
    if "cnpj" in t and ("aparec" in t or "cada" in t or "mudan" in t): ident = {"type": "cnpj"}
    elif "cpf" in t and ("aparec" in t or "cada" in t or "mudan" in t): ident = {"type": "cpf"}
    if re.search(r"numero do processo|\bprocesso\b", t): ident = {"type": "process"}
    elif re.search(r"numero da nota|numero da nf", t): ident = {"type": "invoice_number"}
    elif re.search(r"numero do contrato", t): ident = {"type": "contract_number"}
    elif re.search(r"cliente|paciente|\bnome\b", t):
        ident = {"type": "customer_name"}
        if "paciente" in t and "cliente" not in t: ident["label"] = "paciente"
    if not kws:
        found = [(term, words) for term, words in DOC_TERMS.items() if re.search(rf"\b{term}s?\b", t)]
        for term, words in found: kws += [w for w in words if w not in kws]
        if found:
            if len(found) == 1: d["document_type"] = found[0][0].replace(" ", "_")
            notes.append("Sugeri palavras-chave para " + ", ".join(f'"{term}"' for term, _ in found) + ": " + ", ".join(kws) + ". Confira se é isso mesmo.")
            if len(found) > 1: notes.append("A instrução cita mais de um tipo de documento; qualquer um deles inicia um novo documento.")
    if not kws:
        caps = [w for w in re.findall(r"\b[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{4,}(?:\s[A-ZÁÀÂÃÉÊÍÓÔÕÚÇ]{3,}){0,3}\b", raw) if w not in {"CPF", "CNPJ", "NUNCA", "SEMPRE"}]
        kws = caps[:5]
    if "inicio" in t or "titulo" in t or "cabecalho" in t: d["keyword_location"] = "header"
    if re.search(r"\bcpf\b", t) and "aparec" in t and not kws and ident["type"] in ("none", "cpf"): ident = {"type": "none"}; d["start_regexes"] = [r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b"]; notes.append("Padrão de CPF usado como critério de início.")
    if re.search(r"\bcnpj\b", t) and "aparec" in t and not kws and ident["type"] in ("none", "cnpj"): ident = {"type": "none"}; d["start_regexes"] = [r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b"]; notes.append("Padrão de CNPJ usado como critério de início.")
    if kws: d["start_keywords"] = kws
    if ident["type"] != "none":
        d["identifier"] = ident
        if "inicio" in t or "primeira pagina" in t: d["identifier"]["location"] = "page_start"
    if d.get("start_regexes") and not kws: d["strategy"] = "pattern"
    elif ident["type"] != "none" and (CHANGE.search(t) or not kws): d["strategy"] = "identifier"
    elif kws and ident["type"] != "none": d["strategy"] = "keyword"; notes.append("O identificador será usado como evidência e para nomear os arquivos.")
    else: d["strategy"] = "keyword"
    if d["strategy"] == "keyword" and not kws or d["strategy"] == "identifier" and ident["type"] == "none":
        raise NeedsRewrite("Não consegui identificar o critério de separação. Cite um texto entre aspas (ex.: \"CONTRATO\") ou um identificador (CPF, CNPJ, número do processo, nome do cliente).")
    try: p = SplitParams(**d)
    except ValidationError as e: raise NeedsRewrite("Não foi possível montar os parâmetros: " + e.errors()[0]["msg"])
    notes.insert(0, "Interpretação por regras simples (IA desativada). Confira os parâmetros abaixo.")
    return p, notes

def ai_parse(instruction: str, sample_pages) -> tuple[SplitParams, list[str]]:
    client = get_llm()
    schema = json.dumps(SplitParams.model_json_schema()["properties"], ensure_ascii=False)[:2500]
    samples = [{"page": p.n, "start": p.text.strip()[:300]} for p in sample_pages[:4]]
    user = (f"Converta a instrução do usuário em parâmetros de separação de PDF.\nInstrução: {json.dumps(instruction, ensure_ascii=False)}\n"
            f"Amostra de páginas: {json.dumps(samples, ensure_ascii=False)}\nCampos permitidos (JSON Schema): {schema}\n"
            "Use apenas os campos do schema. Palavras-chave devem aparecer literalmente nas páginas de início. "
            'Responda um objeto JSON: {"params": {...}, "notes": ["explicações curtas"]}')
    data = parse_json(client.complete(UNTRUSTED, user, 1500))
    return SplitParams(**data["params"]), [str(n)[:200] for n in data.get("notes", [])][:6]

def parse_instruction(instruction: str, sample_pages) -> tuple[SplitParams, list[str], str]:
    if get_llm():
        try:
            p, notes = ai_parse(instruction, sample_pages); return p, notes, "ai"
        except Exception:
            p, notes = heuristic_parse(instruction)
            return p, ["A IA não respondeu de forma utilizável; usei as regras simples."] + notes, "heuristic"
    p, notes = heuristic_parse(instruction); return p, notes, "heuristic"
