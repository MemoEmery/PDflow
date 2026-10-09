import subprocess, tempfile, shutil, html, re
from pathlib import Path
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import simpleSplit, ImageReader

OFFICE = {".doc",".docx",".odt",".xls",".xlsx",".ods",".csv",".ppt",".pptx",".odp"}
IMAGES = {".jpg",".jpeg",".png",".webp"}
TIMEOUT = 90

def office_to_pdf(src: Path, out_dir: Path) -> Path:
    # copia com o nome limpo: o LibreOffice imprime o nome do arquivo em CSV/planilhas
    clean = src.parent / "_lo"; clean.mkdir(exist_ok=True)
    named = clean / re.sub(r"^\d{3}_", "", src.name); shutil.copy(src, named); src = named
    # perfil isolado por job evita conflito entre execuções simultâneas
    with tempfile.TemporaryDirectory() as profile:
        cmd = ["soffice", f"-env:UserInstallation=file://{profile}", "--headless",
               "--convert-to", "pdf", "--outdir", str(out_dir), str(src)]
        subprocess.run(cmd, check=True, timeout=TIMEOUT, capture_output=True)
    out = out_dir / (src.stem + ".pdf")
    if not out.exists(): raise RuntimeError("LibreOffice não gerou o PDF")
    shutil.rmtree(clean, ignore_errors=True)
    return out

Image.MAX_IMAGE_PIXELS = 50_000_000  # protege contra "bombas" de descompressão
SIZES = {"A4": (595.28, 841.89), "Letter": (612, 792)}
MARGINS = {"none": 0, "small": 18, "medium": 36}

def images_to_pdf(srcs: list[Path], out: Path, opts: dict | None = None) -> Path:
    opts = opts or {}
    size, orient, margin = (str(opts.get(k, d)) for k, d in (("size", "fit"), ("orientation", "auto"), ("margin", "none")))
    if size not in {"fit", *SIZES} or orient not in {"auto", "portrait", "landscape"} or margin not in MARGINS:
        raise ValueError("Opções de página inválidas.")
    m = MARGINS[margin]; c = canvas.Canvas(str(out))
    for s in srcs:
        im = ImageOps.exif_transpose(Image.open(s))
        if im.mode in ("RGBA", "LA", "P"):
            im = im.convert("RGBA"); bg = Image.new("RGB", im.size, "white"); bg.paste(im, mask=im.split()[3]); im = bg
        im = im.convert("RGB"); iw, ih = im.size
        if size == "fit": pw, ph = iw * 72 / 150 + 2 * m, ih * 72 / 150 + 2 * m
        else:
            pw, ph = SIZES[size]
            land = (iw > ih) if orient == "auto" else orient == "landscape"
            if land: pw, ph = ph, pw
        c.setPageSize((pw, ph))
        k = min((pw - 2 * m) / iw, (ph - 2 * m) / ih); w, h = iw * k, ih * k
        c.drawImage(ImageReader(im), (pw - w) / 2, (ph - h) / 2, w, h); c.showPage()
    c.save(); return out

def text_to_pdf(src: Path, out: Path) -> Path:
    text = src.read_text(encoding="utf-8", errors="replace")
    c = canvas.Canvas(str(out), pagesize=A4)
    w, h = A4; m = 50; y = h - m
    for line in text.splitlines() or [""]:
        for part in simpleSplit(line, "Helvetica", 10, w - 2*m) or [""]:
            if y < m: c.showPage(); y = h - m
            c.setFont("Helvetica", 10); c.drawString(m, y, part); y -= 14
    c.save(); return out

def html_to_pdf(src: Path, out: Path) -> Path:
    from weasyprint import HTML
    # url_fetcher bloqueado: impede SSRF / leitura de arquivos locais
    def deny(url, *a, **k): raise ValueError("recurso externo bloqueado")
    HTML(string=src.read_text(encoding="utf-8", errors="replace"), url_fetcher=deny).write_pdf(str(out))
    return out

def _clean(p: Path) -> Path:
    n = p.with_name(re.sub(r'^\d{3}_', '', p.name))
    if n != p: p.rename(n)
    return n

def convert(files: list[Path], work: Path, opts: dict | None = None) -> Path:
    return _clean(_convert(files, work, opts))

def _convert(files: list[Path], work: Path, opts: dict | None = None) -> Path:
    exts = {f.suffix.lower() for f in files}
    if exts <= IMAGES:
        return images_to_pdf(files, work / "resultado.pdf", opts)
    f = files[0]; e = f.suffix.lower()
    if e in OFFICE: return office_to_pdf(f, work)
    if e == ".txt": return text_to_pdf(f, work / (f.stem + ".pdf"))
    if e in {".html",".htm"}: return html_to_pdf(f, work / (f.stem + ".pdf"))
    raise ValueError("Esse formato ainda não é suportado.")
