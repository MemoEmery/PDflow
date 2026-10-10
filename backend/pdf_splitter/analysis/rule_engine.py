"""Motor de regras determinístico, independente da IA. Cada regra devolve uma evidência (peso > 0 apoia
'aqui começa um documento'; peso < 0 contradiz). A IA só entra como mais uma regra (SemanticRule)."""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from ..models import Identifier
from .pattern_detector import (HEADER_LINES, extract_identifier, lines_of, norm, page_counter, safe_search)

@dataclass
class Page:
    n: int
    text: str
    scanned: bool = False
    lines: list = field(default_factory=list)
    norm: str = ""
    head: str = ""
    counter: tuple | None = None
    def __post_init__(self):
        self.lines = lines_of(self.text); self.norm = norm(self.text)
        self.head = norm("\n".join(self.lines[:HEADER_LINES])); self.counter = page_counter(self.lines)

@dataclass
class Evidence:
    rule: str
    weight: int
    detail: str
    value: str | None = None

@dataclass
class Ctx:
    current_id: str | None = None   # identificador do documento em andamento
    prev_id: str | None = None      # último identificador visto

class Rule(ABC):
    name = "rule"; weight = 0
    @abstractmethod
    def evaluate(self, page: Page, ctx: Ctx) -> Evidence | None: ...

class TextRule(Rule):
    name, weight = "text", 40
    def __init__(self, keywords, location="anywhere"):
        self.kws = [(k, re.compile(rf"(?<!\w){re.escape(norm(k))}(?!\w)")) for k in keywords]; self.location = location
    def evaluate(self, page, ctx):
        scope = page.head if self.location == "header" else page.norm
        for k, rx in self.kws:
            if rx.search(scope):
                return Evidence("text", self.weight, f'Encontrado o texto "{k}"' + (" no cabeçalho" if self.location == "header" else ""), k)
        return None

class HeaderRule(TextRule):
    def __init__(self, keywords): super().__init__(keywords, "header")

class RegexRule(Rule):
    name, weight = "regex", 40
    def __init__(self, patterns): self.patterns = patterns
    def evaluate(self, page, ctx):
        for p in self.patterns:
            m = safe_search(p, page.text)
            if m: return Evidence("regex", self.weight, f"Padrão {p[:40]} encontrado ({m.group(0)[:30]})", m.group(0)[:60])
        return None

class FieldRule(Rule):
    name, weight = "field", 25
    def __init__(self, ident: Identifier): self.ident = ident; self._cache: dict[int, str | None] = {}
    def value(self, page):
        if page.n not in self._cache: self._cache[page.n] = extract_identifier(page.text, self.ident)
        return self._cache[page.n]
    def evaluate(self, page, ctx):
        v = self.value(page)
        if not v: return None
        if ctx.current_id is None: return Evidence("field", self.weight, f"Identificador encontrado: {v}", v) if page.n == 1 else None
        if v != ctx.current_id: return Evidence("field", self.weight, f"Novo identificador: {v} (anterior: {ctx.current_id})", v)
        return None

class FooterRule(Rule):
    """Contador 'Página x de y' no cabeçalho/rodapé: x = 1 apoia início; x > 1 indica continuação."""
    name = "footer"; weight = 10
    def __init__(self, pages): self.reliable = sum(1 for p in pages if p.counter) >= max(2, 0.5 * len(pages))
    def evaluate(self, page, ctx):
        if not page.counter: return None
        x, y = page.counter
        return Evidence("footer", 10, f"Contador indica página 1 de {y}") if x == 1 else Evidence("footer", -25, f"Contador indica página {x} de {y} (continuação)")

class ContinuityRule(Rule):
    """Contradiz um início quando o identificador é o mesmo da página anterior."""
    name = "continuity"
    def __init__(self, fr: FieldRule): self.fr = fr
    def evaluate(self, page, ctx):
        v = self.fr.value(page)
        if v and ctx.prev_id and v == ctx.prev_id: return Evidence("continuity", -25, f"Mesmo identificador da página anterior ({v})")
        return None

class SemanticRule(Rule):
    name, weight = "semantic", 10
    def __init__(self, verdicts): self.v = verdicts
    def evaluate(self, page, ctx):
        r = self.v.get(page.n - 1)
        if not r or r["confidence"] < 0.6: return None
        return Evidence("semantic", 10, f"IA classificou como início: {r['reason']}") if r["is_start"] else Evidence("semantic", -20, f"IA indica continuação: {r['reason']}")
