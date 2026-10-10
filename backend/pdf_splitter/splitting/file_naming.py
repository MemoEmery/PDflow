import re, unicodedata

def _safe(s: str) -> str:
    s = unicodedata.normalize("NFKD", s); s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"_+", "_", re.sub(r"[^A-Za-z0-9._-]+", "_", s)).strip("._-")[:80]

def clean_name(name: str) -> str:
    name = re.sub(r"\.pdf$", "", name.strip(), flags=re.I)
    return _safe(name)

def build_names(docs: list[dict], params) -> list[str]:
    """Nomes a partir do conteúdo identificado; sem identificador, documento_001, 002..."""
    used: dict[str, int] = {}; out = []
    for i, d in enumerate(docs, 1):
        base = ""
        if d.get("identifier"):
            tpl = params.name_template or "{identifier}"
            base = _safe(tpl.replace("{identifier}", str(d["identifier"])).replace("{type}", params.document_type or "").replace("{n}", f"{i:03d}"))
            if params.document_type and "{type}" not in tpl: base = _safe(f"{params.document_type}_{base}")
        base = base or f"documento_{i:03d}"
        used[base] = used.get(base, 0) + 1
        out.append(base if used[base] == 1 else f"{base}_{used[base]}")
    return out
