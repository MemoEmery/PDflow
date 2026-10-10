import shutil
from pathlib import Path
import pymupdf as fitz

def split(original: Path, docs: list[dict], out_dir: Path) -> list[Path]:
    """Gera um PDF por documento (páginas 1-based, intervalos inclusivos)."""
    shutil.rmtree(out_dir, ignore_errors=True); out_dir.mkdir(parents=True)
    files = []
    with fitz.open(original) as src:
        for k, d in enumerate(docs, 1):
            o = out_dir / f"{k:03d}_{d['name']}.pdf"
            with fitz.open() as dst:
                dst.insert_pdf(src, from_page=d["start"] - 1, to_page=d["end"] - 1)
                dst.save(str(o), garbage=3, deflate=True)
            files.append(o)
    return files
