"""PDFs sintéticos com gabarito (páginas iniciais reais). Incluem casos difíceis para regras simples."""
import random
from dataclasses import dataclass
import pymupdf as fitz

FILL = ["Declaro que as informações acima são verdadeiras e conferem com os documentos apresentados.",
        "O pagamento deverá ser efetuado em até trinta dias após a emissão do documento.",
        "Valores expressos em reais, já incluídos os tributos incidentes sobre a operação.",
        "As partes elegem o foro da comarca para dirimir quaisquer dúvidas oriundas deste instrumento.",
        "Material entregue conforme especificações técnicas combinadas previamente entre as partes."]
NAMES = ["Maria Souza", "João Lima", "Ana Paz", "Carlos Dias", "Beatriz Rocha", "Pedro Alves", "Lúcia Nunes", "Rafael Costa", "Marta Ribeiro", "Tiago Melo"]

@dataclass
class Case:
    name: str; pdf: bytes; instruction: str; truth: list[int]; hard: str

def _pdf(pages):
    d = fitz.open()
    for lines in pages:
        p = d.new_page(); y = 60
        for ln in lines: p.insert_text((60, y), ln, fontsize=10); y += 16
    return d.tobytes()

def _cnpj(i): return f"{10 + i:02d}.345.678/0001-{90 + i:02d}"
def _cnj(i): return f"{1000000 + i * 37:07d}-{10 + i:02d}.2026.8.17.{1000 + i:04d}"

def _docs(rng, n_docs, first, rest, lo=1, hi=4):
    """first(i,total)->linhas da 1ª página; rest(i,k,total)->linhas das demais. Retorna (páginas, gabarito)."""
    pages, truth = [], []
    for i in range(n_docs):
        n = rng.randint(lo, hi); truth.append(len(pages) + 1)
        for k in range(n):
            ls = first(i, n) if k == 0 else rest(i, k, n)
            pages.append(ls + [f"Página {k + 1} de {n}"])
    return pages, truth

def build_cases(seed=7) -> list[Case]:
    rng = random.Random(seed); out = []
    nf_i = lambda i, n: ["DANFE", "NOTA FISCAL ELETRÔNICA", f"Nº {1245 + i:06d}", f"CNPJ {_cnpj(i)}", rng.choice(FILL)]
    pg, tr = _docs(rng, 8, nf_i, lambda i, k, n: [f"Itens da nota {1245 + i}", rng.choice(FILL), rng.choice(FILL)])
    out.append(Case("nf_limpa", _pdf(pg), 'Separe sempre que começar uma nova nota fiscal. Considere como início uma página que contenha "DANFE" '
                    'ou "NOTA FISCAL ELETRÔNICA". Use o número da nota no nome do arquivo.', tr, "fácil"))
    pg, tr = _docs(rng, 8, lambda i, n: ["NOTA FISCAL ELETRÔNICA", f"Nº {2000 + i:06d}", f"CNPJ {_cnpj(i)}", rng.choice(FILL)],
                   lambda i, k, n: [f"Esta página complementa a nota fiscal nº {2000 + i}", rng.choice(FILL)])
    out.append(Case("nf_citada_em_todas", _pdf(pg), "Cada nota fiscal deve ficar em um arquivo separado.", tr, "a palavra aparece em todas as páginas"))
    ocr = lambda i, n: [("N0TA FISC4L ELETR0NICA" if i % 3 == 2 else "NOTA FISCAL ELETRÔNICA"), f"Nº {3000 + i:06d}", f"CNPJ {_cnpj(i)}", rng.choice(FILL)]
    pg, tr = _docs(rng, 9, ocr, lambda i, k, n: [f"Itens da nota {3000 + i}", rng.choice(FILL)])
    out.append(Case("nf_titulo_com_erro_de_ocr", _pdf(pg), 'Separe quando aparecer "NOTA FISCAL ELETRÔNICA". O número da nota identifica o arquivo.', tr, "título ilegível em 1/3 dos inícios"))
    pg, tr = _docs(rng, 6, lambda i, n: ["CONTRATO DE PRESTAÇÃO DE SERVIÇOS", f"Contrato nº {500 + i}", f"CONTRATANTE: {NAMES[i]}", rng.choice(FILL)],
                   lambda i, k, n: ([f"CLÁUSULA {k}: conforme este contrato", rng.choice(FILL)] if k < n - 1 else [f"ANEXO I", f"Integra o contrato nº {500 + i}", rng.choice(FILL)]), 2, 5)
    out.append(Case("contratos_com_anexos", _pdf(pg), "Separe sempre que começar um novo contrato.", tr, "'contrato' aparece no corpo e nos anexos"))
    pg, tr = _docs(rng, 7, lambda i, n: [f"Cliente: {NAMES[i]}", "Extrato de movimentações", rng.choice(FILL)],
                   lambda i, k, n: [f"Cliente: {NAMES[i]}", f"Encaminhado ao cliente {NAMES[(i + 3) % 10]}" if k % 2 else "Continuação do extrato", rng.choice(FILL)], 2, 4)
    out.append(Case("clientes_por_nome", _pdf(pg), "Cada cliente deve ficar em um PDF separado. O nome do cliente aparece em todas as páginas.", tr, "outros nomes citados no corpo"))
    pg, tr = _docs(rng, 7, lambda i, n: [f"Processo nº {_cnj(i)}", "Petição inicial", rng.choice(FILL)],
                   lambda i, k, n: [f"Processo nº {_cnj(i)}", f"Apensado ao processo {_cnj(i + 20)}" if k == 1 else "Despacho", rng.choice(FILL)], 2, 4)
    out.append(Case("processos_cnj", _pdf(pg), "Cada número de processo deve iniciar um documento.", tr, "outro número citado no corpo"))
    pages, truth = [], []
    for i in range(8):
        truth.append(len(pages) + 1)
        if i % 2 == 0: pages.append(["RECIBO", f"Recebi de {NAMES[i]} a quantia de R$ {100 + i * 10},00", "Referente a serviços prestados."])
        else:
            n = rng.randint(2, 4)
            for k in range(n): pages.append(["RELATÓRIO MENSAL DE ATIVIDADES", "Resumo executivo"] if k == 0 else [f"Seção {k + 1}: detalhamento", rng.choice(FILL)])
    out.append(Case("recibos_e_relatorios", _pdf(pages), "Separe cada recibo e cada relatório em um arquivo próprio.", truth, "dois tipos de documento misturados"))
    return out
