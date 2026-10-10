"""Detecta onde cada documento começa. Camadas independentes: regras (texto/regex/campo), estrutura,
contador de páginas, continuidade e (opcional) IA. Devolve evidências e pontuação por página."""
from dataclasses import dataclass, field
from statistics import median
from ..confidence.confidence_scorer import INDEPENDENT, score_start
from ..models import SplitParams
from .pattern_detector import signature
from .rule_engine import (ContinuityRule, Ctx, Evidence, FieldRule, FooterRule, Page, RegexRule, SemanticRule, TextRule)

@dataclass
class Issue:
    code: str; severity: str; message: str
    pages: list = field(default_factory=list); alternatives: list = field(default_factory=list)
    def to_dict(self): return self.__dict__

@dataclass
class Detection:
    n: int
    candidates: list          # índices (0-based) que satisfazem o critério primário
    starts: list              # início de documentos após regras de tamanho mínimo
    scores: list              # nota (0-100) de cada página ser início
    evidence: list            # evidências (texto) por página
    ids: list                 # identificador por página
    issues: list
    footer_reliable: bool
    primary_hits: int

def _jaccard(a, b): return len(a & b) / len(a | b) if a | b else 0.0

def detect(pages: list[Page], params: SplitParams, verdicts: dict | None = None) -> Detection:
    n, s = len(pages), params.strategy
    text_r = TextRule(params.start_keywords, params.keyword_location) if params.start_keywords else None
    regex_r = RegexRule(params.start_regexes) if params.start_regexes else None
    field_r = FieldRule(params.identifier) if params.identifier.type != "none" else None
    primaries = {"keyword": [text_r], "pattern": [regex_r], "identifier": [field_r], "semantic": []}.get(s) or []
    if s == "combined": primaries = [text_r, regex_r, field_r]
    primaries = [r for r in primaries if r]
    footer = FooterRule(pages); cont = ContinuityRule(field_r) if field_r else None; sem = SemanticRule(verdicts) if verdicts else None
    ctx, cur, last = Ctx(), None, None
    per, cands, ids = [], [], []
    for i, p in enumerate(pages):
        ctx.current_id, ctx.prev_id = cur, last
        evs = {r.name: r.evaluate(p, ctx) for r in (text_r, regex_r, field_r) if r}
        if s == "semantic":
            v = (verdicts or {}).get(i)
            start = bool(footer.reliable and p.counter and p.counter[0] == 1) or bool(v and v["is_start"] and v["confidence"] >= 0.6)
        elif s == "combined" and params.combine == "all": start = all(evs.get(r.name) for r in primaries)
        else: start = any(evs.get(r.name) for r in primaries)
        val = field_r.value(p) if field_r else None
        per.append((dict(evs), dict(cur_id=cur, prev_id=last))); ids.append(val)
        if start and i > 0: cands.append(i)
        if val:
            if start or cur is None or i == 0: cur = val
            last = val
    star = [0] + cands
    sigs = [signature(p.lines) for p in pages]
    struct_ok = len(star) >= 3
    possible = sum(r.weight for r in (text_r, regex_r, field_r) if r) + (10 if struct_ok else 0) + (10 if footer.reliable else 0) + (10 if verdicts is not None else 0)
    if s == "semantic": possible = max(possible, 10)
    scores, evidence = [], []
    for i, p in enumerate(pages):
        evs, c = per[i]; ctx.current_id, ctx.prev_id = c["cur_id"], c["prev_id"]
        el: list[Evidence] = [e for e in evs.values() if e]
        for r in (footer, cont, sem):
            e = r.evaluate(p, ctx) if r else None
            if e: el.append(e)
        if struct_ok:
            others = [sigs[j] for j in star if j != i]
            sim = sum(sorted((_jaccard(sigs[i], o) for o in others), reverse=True)[:3]) / min(3, len(others))
            if sim >= 0.5: el.append(Evidence("structure", 10, f"Estrutura semelhante às outras primeiras páginas ({round(sim * 100)}%)"))
            elif sim < 0.3: el.append(Evidence("structure", -10, f"Estrutura diferente das outras primeiras páginas ({round(sim * 100)}%)"))
        if i == 0 and primaries and not any(evs.get(r.name) for r in primaries):
            el.append(Evidence("rule", -sum(r.weight for r in primaries), "A primeira página não satisfaz o critério definido"))
        scores.append(score_start(el, possible)); evidence.append(el)
    issues, minp = [], max(params.min_document_pages, 1 if params.allow_single_page_documents else 2)
    kept = [0]
    for i in cands:
        if i - kept[-1] < minp: issues.append(Issue("short_document", "info", f"Página {i + 1} parece um início, mas o documento teria menos de {minp} página(s); mantida junto do anterior.", [i + 1]))
        else: kept.append(i)
    if len(kept) > 1 and n - kept[-1] < minp:
        i = kept.pop(); issues.append(Issue("short_document", "info", f"Página {i + 1} parece um início, mas o último documento teria menos de {minp} página(s).", [i + 1]))
    return Detection(n, cands, kept, scores, evidence, ids, issues, footer.reliable, len(cands) + 0)

def docs_from_starts(starts: list[int], n: int) -> list[tuple[int, int]]:
    st = sorted(set([0] + [s for s in starts if 0 < s < n]))
    return [(a, (st[k + 1] - 1) if k + 1 < len(st) else n - 1) for k, a in enumerate(st)]

def doc_confidence(det: Detection, a: int, b: int) -> int:
    """Confiança do documento = a menor nota entre o seu início e o início do próximo (o seu fim)."""
    nxt = det.scores[b + 1] if b + 1 < det.n else 100
    return min(det.scores[a], nxt)

def independent_support(det: Detection, i: int) -> bool:
    return any(e.rule in INDEPENDENT and e.weight > 0 for e in det.evidence[i])

def ambiguity_issues(det: Detection, starts: list | None = None) -> list[Issue]:
    """Dois inícios consecutivos (páginas i e i+1) quando os demais documentos são longos."""
    out, st = [], (det.starts if starts is None else starts)
    lens = [b - a + 1 for a, b in docs_from_starts(st, det.n)]
    typical = median(lens) if lens else 1
    for k in range(len(st) - 1):
        a, b = st[k], st[k + 1]
        if b - a == 1 and typical >= 3:
            alt1 = [x for x in st if x != b]; alt2 = [x for x in st if x != a]
            out.append(Issue("ambiguous_boundary", "warning", f"As páginas {a + 1} e {b + 1} parecem ambas início de documento; os outros documentos têm cerca de {int(typical)} páginas.",
                             [a + 1, b + 1], [{"label": f"Início na página {a + 1}", "starts": alt1}, {"label": f"Início na página {b + 1}", "starts": alt2}]))
    return out
