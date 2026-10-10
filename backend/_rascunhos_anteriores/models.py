from dataclasses import dataclass

@dataclass
class PageData:
    n: int
    text: str
    source: str                 # "text" | "ocr" | "empty"
    norm: str = ""              # texto normalizado (sem acento, minúsculo)
    header: str = ""            # primeiras linhas, normalizadas
    footer: str = ""            # últimas linhas, normalizadas
    marker: tuple | None = None # ("Página 2 de 5") -> (2, 5)
