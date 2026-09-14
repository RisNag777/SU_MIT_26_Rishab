"""OCR helpers for scanned PDFs — convert page images to text and cache results."""

from __future__ import annotations

from pathlib import Path

_MIN_NATIVE_TEXT = 400


def ocr_cache_path(pdf_path: Path) -> Path:
    return pdf_path.with_suffix(pdf_path.suffix + ".ocr.txt")


def read_ocr_cache(pdf_path: Path) -> str | None:
    cache = ocr_cache_path(pdf_path)
    if cache.is_file() and cache.stat().st_size > 0:
        return cache.read_text(encoding="utf-8")
    return None


def write_ocr_cache(pdf_path: Path, text: str) -> Path:
    cache = ocr_cache_path(pdf_path)
    cache.write_text(text, encoding="utf-8")
    return cache


def native_pdf_text(pdf_path: Path) -> str:
    """Extract embedded text (no OCR)."""
    parts: list[str] = []
    try:
        import fitz

        doc = fitz.open(pdf_path)
        try:
            for page in doc:
                t = (page.get_text() or "").strip()
                if t:
                    parts.append(t)
        finally:
            doc.close()
    except Exception:
        from pypdf import PdfReader

        reader = PdfReader(str(pdf_path))
        for page in reader.pages:
            t = (page.extract_text() or "").strip()
            if t:
                parts.append(t)
    return "\n\n".join(parts).strip()


def needs_ocr(pdf_path: Path, native_text: str | None = None) -> bool:
    text = native_text if native_text is not None else native_pdf_text(pdf_path)
    return len(text) < _MIN_NATIVE_TEXT


def ocr_pdf_to_text(pdf_path: Path, *, dpi: float = 180, progress=None) -> str:
    """
    OCR every page of a PDF to a single text string.

    progress: optional callable(page_index_1based, total_pages)
    """
    import fitz
    import numpy as np
    from rapidocr_onnxruntime import RapidOCR

    engine = RapidOCR()
    doc = fitz.open(pdf_path)
    page_texts: list[str] = []
    try:
        total = doc.page_count
        matrix = fitz.Matrix(dpi / 72, dpi / 72)
        for i, page in enumerate(doc):
            if progress:
                progress(i + 1, total)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            # RGB array for RapidOCR
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n == 4:
                img = img[:, :, :3]
            result, _ = engine(img)
            lines: list[str] = []
            if result:
                for item in result:
                    # item: [box, text, confidence]
                    if len(item) >= 2 and item[1]:
                        lines.append(str(item[1]).strip())
            page_body = "\n".join(lines).strip()
            if page_body:
                page_texts.append(f"--- Page {i + 1} ---\n{page_body}")
    finally:
        doc.close()

    return "\n\n".join(page_texts).strip()


def ensure_pdf_text(pdf_path: Path, *, force_ocr: bool = False, progress=None) -> tuple[str, str]:
    """
    Return (text, source) where source is 'native', 'cache', or 'ocr'.

    Uses native extract when rich enough; otherwise OCR cache or fresh OCR.
    """
    native = native_pdf_text(pdf_path)
    if not force_ocr and not needs_ocr(pdf_path, native):
        return native, "native"

    if not force_ocr:
        cached = read_ocr_cache(pdf_path)
        if cached:
            return cached, "cache"

    ocr_text = ocr_pdf_to_text(pdf_path, progress=progress)
    if ocr_text:
        write_ocr_cache(pdf_path, ocr_text)
        return ocr_text, "ocr"

    # Fall back to whatever native text exists
    if native:
        return native, "native"
    return "", "empty"
