"""Coerência de conteúdo de cada grupo de páginas, com sinais independentes das regras de início."""
from ..analysis.document_boundary_detector import Issue, docs_from_starts

def validate_content(pages, det, starts: list[int], id_by_page) -> list[Issue]:
    out, n = [], det.n
    docs = docs_from_starts(starts, n)
    for k, (a, b) in enumerate(docs):
        found = [(i, id_by_page[i]) for i in range(a, b + 1) if id_by_page[i]]
        distinct = {v for _, v in found}
        if len(distinct) > 1:
            i2 = next(i for i, v in found if v != found[0][1])
            out.append(Issue("mixed_document", "warning", f"Documento {k + 1} (páginas {a + 1}–{b + 1}) contém identificadores diferentes ({', '.join(sorted(distinct))[:80]}): pode misturar documentos.",
                             [i2 + 1], [{"label": f"Dividir na página {i2 + 1}", "starts": sorted(set(starts) | {i2})}]))
        c0 = pages[a].counter
        if c0 and c0[0] > 1 and a > 0:
            out.append(Issue("split_mid_document", "warning", f"Página {a + 1} apresenta características de continuidade (rodapé: página {c0[0]} de {c0[1]}).", [a + 1],
                             [{"label": "Unir ao documento anterior", "starts": [s for s in starts if s != a]}]))
        c1 = pages[b].counter
        if c1 and c1[0] < c1[1] and k + 1 < len(docs):
            end2 = b + (c1[1] - c1[0])
            alt = [s for s in starts if s != b + 1]
            if end2 + 1 < n and end2 + 1 not in alt: alt.append(end2 + 1)
            out.append(Issue("incomplete_document", "warning", f"O documento {k + 1} parece continuar até a página {end2 + 1} (rodapé: página {c1[0]} de {c1[1]}).", [b + 1, end2 + 1],
                             [{"label": f"Estender até a página {end2 + 1}", "starts": sorted(alt)}]))
    return out
