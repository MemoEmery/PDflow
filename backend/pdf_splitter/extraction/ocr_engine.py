"""OCR atrás de uma interface: trocar o motor (serviço externo, modelo local, multimodal) não afeta o resto."""
import io, os, shutil
from abc import ABC, abstractmethod

class OCRProvider(ABC):
    name = "base"
    @abstractmethod
    def available(self) -> bool: ...
    @abstractmethod
    def extract_text(self, image_png: bytes) -> str: ...

class NullOCR(OCRProvider):
    name = "nenhum"
    def available(self) -> bool: return False
    def extract_text(self, image_png: bytes) -> str: return ""

class TesseractOCR(OCRProvider):
    name = "tesseract"
    def __init__(self): self.lang = os.getenv("OCR_LANG", "por+eng")
    def available(self) -> bool: return shutil.which("tesseract") is not None
    def extract_text(self, image_png: bytes) -> str:
        import pytesseract
        from PIL import Image
        return pytesseract.image_to_string(Image.open(io.BytesIO(image_png)), lang=self.lang, timeout=60)

def get_ocr() -> OCRProvider:
    t = TesseractOCR()
    return t if t.available() else NullOCR()
