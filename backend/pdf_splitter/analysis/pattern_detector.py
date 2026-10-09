import re, unicodedata
import regex
from ..models import Identifier

HEADER_LINES = 8
PATTERNS = {"cpf": r"\b\d{3}\.\d{3}\.\d{3}-\d{2}\b",
            "cnpj": r"\b\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}\b",
            "process": r"\b\d{7}-\d{2}\.\d{4}\.\d\.\d{2}\.\d{4}\b"}
COUNTER = regex.compile(r"(?i)p[aá]g(?:ina|\.)?\s*(\d{1,4})\s*(?:de|/)\s*(\d{1,4})")

def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c)).casefold()

def lines_of(text: str) -> list[str]:
    return [l.strip() for l in text.splitlines() if l.strip()]

def safe_search(pattern: str, text: str, flags=0):
    """Busca com limite de tempo: expressões regulares escritas pelo usuário/IA não podem travar o servidor."""
    try: return regex.search(pattern, text[:60000], flags, timeout=1.0)
    except (TimeoutError, regex.error): return None

def _clean_name(v: str) -> str | None:
    v = regex.split(r"\s{3,}|\s\|\s|\s(?:CPF|CNPJ)\b", v.strip())[0].strip(" .:-–")
    return re.sub(r"\s+", " ", v).upper() if len(v) >= 3 else None

def extract_identifier(text: str, ident: Identifier) -> str | None:
    t = ident.type
    if t == "none": return None
    scope = "\n".join(lines_of(text)[:15]) if ident.location == "page_start" else text
    if t in PATTERNS:
        m = safe_search(PATTERNS[t], scope); return m.group(0) if m else None
    if t == "invoice_number":
        m = safe_search(r"(?i)(?:n[úu]mero|n[ºo°]\.?)\s*[:\-]?\s*(\d{1,3}(?:\.\d{3})+|\d{3,9})\b", scope)
        return m.group(1).replace(".", "") if m else None
    if t == "contract_number":
        for m in regex.finditer(r"(?i)contrato\s*(?:n[ºo°]\.?|n[úu]mero)?\s*[:\-]?\s*([A-Z0-9][\w\-/\.]{2,30})", scope[:60000], timeout=1.0):
            if any(c.isdigit() for c in m.group(1)): return m.group(1).strip(".")
        return None
    if t == "customer_name":
        label = regex.escape(ident.label) if ident.label else r"(?:cliente|paciente|contratante|benefici[aá]rio|nome(?:\s+do\s+cliente)?)"
        m = safe_search(rf"(?i){label}\s*[:\-–]\s*([^\n\r]{{3,80}})", scope)
        return _clean_name(m.group(1)) if m else None
    if t == "custom_regex" and ident.regex:
        m = safe_search(ident.regex, scope)
        return (m.group(1) if m and m.groups() else m.group(0))[:80] if m else None
    return None

def page_counter(lines: list[str]) -> tuple[int, int] | None:
    """'Página 2 de 5' no cabeçalho/rodapé -> (2, 5)."""
    for l in lines[:3] + lines[-4:]:
        m = COUNTER.search(l)
        if m and int(m.group(1)) <= int(m.group(2)): return int(m.group(1)), int(m.group(2))
    return None

def signature(lines: list[str]) -> set[str]:
    """Estrutura da página: palavras das primeiras linhas, com dígitos mascarados."""
    toks = set()
    for l in lines[:HEADER_LINES]:
        for w in re.sub(r"\d", "#", norm(l)).split():
            if len(w) >= 3: toks.add(w)
    return toks
