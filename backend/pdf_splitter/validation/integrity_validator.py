"""Integridade determinística: nenhuma página perdida, duplicada, fora de ordem ou sem atribuição.
Não depende de IA."""
def check_ranges(docs: list[dict], n: int) -> dict:
    """docs: [{'start','end'}] com páginas 1-based."""
    count = [0] * (n + 1); problems = []
    prev_end = 0
    for k, d in enumerate(docs, 1):
        a, b = d["start"], d["end"]
        if not (1 <= a <= b <= n): problems.append(f"Documento {k}: intervalo inválido ({a}–{b})."); continue
        if a <= prev_end: problems.append(f"Documento {k}: começa na página {a}, antes do fim do anterior ({prev_end}) — fora de ordem ou sobreposto.")
        prev_end = max(prev_end, b)
        for p in range(a, b + 1): count[p] += 1
    lost = [p for p in range(1, n + 1) if count[p] == 0]; dup = [p for p in range(1, n + 1) if count[p] > 1]
    if lost: problems.append(f"Páginas sem documento (órfãs): {_fmt(lost)}.")
    if dup: problems.append(f"Páginas em mais de um documento: {_fmt(dup)}.")
    return {"ok": not problems, "pages_total": n, "covered": n - len(lost), "lost": lost, "duplicated": dup, "problems": problems,
            "coverage_pct": round(100 * (n - len(lost)) / n, 1) if n else 0}

def _fmt(pages: list[int]) -> str:
    out, i = [], 0
    while i < len(pages):
        j = i
        while j + 1 < len(pages) and pages[j + 1] == pages[j] + 1: j += 1
        out.append(str(pages[i]) if i == j else f"{pages[i]}–{pages[j]}"); i = j + 1
    return ", ".join(out)
