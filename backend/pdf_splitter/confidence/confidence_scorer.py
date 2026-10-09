CAP_WITHOUT_CONFIRMATION = 84   # sem confirmação independente, nunca passa de "média confiança"
INDEPENDENT = {"structure", "footer", "semantic"}

def level(score: int) -> str:
    return "alta" if score >= 90 else "media" if score >= 75 else "baixa"

def score_start(evidences, possible: int) -> int:
    """Pontos das evidências a favor menos penalidades das contrárias, em relação ao máximo possível
    com as camadas disponíveis. Sem confirmação independente (estrutura, rodapé, IA ou duas famílias
    de regra), a nota é limitada: uma única regra isolada não basta para 'alta confiança'."""
    if possible <= 0: return 0
    pts = sum(e.weight for e in evidences if e.weight > 0); pen = -sum(e.weight for e in evidences if e.weight < 0)
    s = max(0, min(100, round(100 * (pts - pen) / possible)))
    pos = {e.rule for e in evidences if e.weight > 0}
    if not (pos & INDEPENDENT) and len(pos & {"text", "regex", "field"}) < 2: s = min(s, CAP_WITHOUT_CONFIRMATION)
    return s
