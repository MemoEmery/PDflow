"""Valida se o CRITÉRIO definido realmente separa o documento (não só se a IA respondeu)."""
from ..analysis.document_boundary_detector import Detection, Issue, ambiguity_issues

def validate_criteria(det: Detection, params, starts: list | None = None) -> list[Issue]:
    n, out, st = det.n, [], (det.starts if starts is None else starts)
    if n >= 5 and det.primary_hits / n > 0.6:
        out.append(Issue("criterion_too_broad", "warning", f"Critério muito amplo: o padrão aparece em {round(100 * det.primary_hits / n)}% das páginas e não parece marcar o início de um novo documento."))
    if n >= 3 and len(st) == n:
        out.append(Issue("criterion_too_broad", "warning", "Cada página virou um documento. O critério provavelmente aparece em todas as páginas."))
    if len(st) == 1 and n > 1:
        out.append(Issue("no_boundaries", "error", "O critério não encontrou nenhum início de documento além da primeira página. Revise as palavras, padrões ou o identificador."))
    if params.identifier.type != "none":
        missing = [a + 1 for a in st if not det.ids[a]]
        if missing:
            share = round(100 * len(missing) / len(st))
            out.append(Issue("identifier_missing", "warning", f"Critério insuficiente: {len(missing)} documento(s) ({share}%) não têm o identificador esperado na primeira página.", missing[:30]))
    out += ambiguity_issues(det, st)
    return out
