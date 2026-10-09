import hashlib
import pymupdf as fitz
from .metadata import pdf_metadata
from .ocr_engine import OCRProvider

MIN_TEXT = 25          # menos que isso = página sem texto (provavelmente escaneada)
MAX_CHARS = 20000      # por página (limita memória e custo)
MAX_PAGES = 500

def fingerprint(page) -> str:
    """Impressão digital da página (tamanho + pixels em baixa resolução). Igual na original e nos PDFs gerados."""
    pix = page.get_pixmap(dpi=36, alpha=False)
    h = hashlib.sha256(); h.update(f"{pix.width}x{pix.height}".encode()); h.update(pix.samples)
    return h.hexdigest()

def open_pdf(path):
    doc = fitz.open(path)
    if doc.needs_pass: raise ValueError("Este PDF está protegido por senha. Desbloqueie-o antes.")
    if doc.page_count == 0: raise ValueError("O PDF não tem páginas.")
    if doc.page_count > MAX_PAGES: raise ValueError(f"O PDF excede o limite de {MAX_PAGES} páginas para esta ferramenta.")
    return doc

def extract_pages(doc, ocr: OCRProvider, progress=None) -> list[dict]:
    out = []
    for i, page in enumerate(doc):
        text = page.get_text("text")[:MAX_CHARS]
        scanned = len(text.strip()) < MIN_TEXT
        ocr_used = False
        if scanned and ocr.available():
            try:
                text = ocr.extract_text(page.get_pixmap(dpi=200, alpha=False).tobytes("png"))[:MAX_CHARS]; ocr_used = True
            except Exception:
                text = ""
        out.append({"n": i + 1, "text": text, "scanned": scanned, "ocr": ocr_used, "chars": len(text.strip()), "fp": fingerprint(page)})
        if progress: progress(i + 1, doc.page_count)
    return out

def summarize(doc, pages, ocr, size_bytes) -> dict:
    return {"page_count": len(pages), "size_bytes": size_bytes,
            "text_pages": sum(1 for p in pages if not p["scanned"]),
            "scanned_pages": sum(1 for p in pages if p["scanned"]),
            "ocr_pages": sum(1 for p in pages if p["ocr"]),
            "empty_pages": sum(1 for p in pages if p["chars"] < 1),
            "ocr_engine": ocr.name, "metadata": pdf_metadata(doc)}
