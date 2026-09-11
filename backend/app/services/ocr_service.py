"""
Extracts raw text per page. Native-text PDFs are parsed directly; when a
page has little/no embedded text (scanned page) it is rasterised and run
through Tesseract OCR. Images always go through OCR.
"""
from pathlib import Path
from dataclasses import dataclass

import fitz  # PyMuPDF
import pytesseract
from PIL import Image, ImageOps, ImageFilter

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)
pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

# Tesseract page-segmentation mode 6 ("assume a single uniform block of
# text") works much better than the default (3) on receipts/invoices,
# which are dense, narrow, multi-column blocks of text rather than a full
# page of prose.
_OCR_CONFIG = "--psm 6"

# Below this width we upscale before OCR -- small/low-res photos (common
# for phone-photographed receipts) lose thin character strokes that
# Tesseract needs.
_MIN_OCR_WIDTH = 1500


def _preprocess_for_ocr(img: Image.Image) -> Image.Image:
    """Best-effort cleanup to improve OCR accuracy on photographed / low
    quality documents (as opposed to clean digital scans):
    - convert to grayscale (drops color noise/shadows that confuse OCR)
    - upscale small images so character strokes are thick enough to read
    - autocontrast to flatten uneven lighting/shadows common in photos
    - light sharpen to crisp up edges softened by upscaling
    This never touches the original file -- it only affects what gets
    fed to Tesseract, and the OCR'd text is still used verbatim (or not
    at all) downstream, nothing is invented.
    """
    gray = img.convert("L")
    if gray.width < _MIN_OCR_WIDTH:
        scale = min(3, max(2, _MIN_OCR_WIDTH // max(gray.width, 1)))
        gray = gray.resize((gray.width * scale, gray.height * scale), Image.LANCZOS)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.SHARPEN)
    return gray


def _ocr_best(img: Image.Image) -> str:
    """Run OCR on both the raw and the preprocessed image and keep
    whichever produced more readable text (more characters is a cheap
    but effective proxy for "less got dropped/garbled"). Falls back to
    the raw pass if preprocessing fails for any reason.
    """
    raw_text = pytesseract.image_to_string(img, config=_OCR_CONFIG)
    try:
        pre_text = pytesseract.image_to_string(_preprocess_for_ocr(img), config=_OCR_CONFIG)
    except Exception as exc:  # noqa: BLE001
        logger.warning("OCR preprocessing failed, using raw pass only: %s", exc)
        return raw_text
    return pre_text if len(pre_text.strip()) >= len(raw_text.strip()) else raw_text


@dataclass
class PageText:
    page_number: int
    text: str
    ocr_used: bool


def extract_text(path: Path, file_type: str) -> list[PageText]:
    if file_type == "application/pdf":
        return _extract_pdf(path)
    return _extract_image(path)


def _extract_pdf(path: Path) -> list[PageText]:
    pages: list[PageText] = []
    doc = fitz.open(path)
    for i in range(doc.page_count):
        page = doc[i]
        native_text = page.get_text().strip()
        if len(native_text) >= settings.OCR_MIN_NATIVE_CHARS:
            pages.append(PageText(page_number=i + 1, text=native_text, ocr_used=False))
            continue
        # scanned / image-only page -> rasterise + OCR
        try:
            pix = page.get_pixmap(dpi=250)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            ocr_text = _ocr_best(img)
            logger.info("OCR used for page %s of %s", i + 1, path.name)
            pages.append(PageText(page_number=i + 1, text=ocr_text.strip(), ocr_used=True))
        except Exception as exc:  # noqa: BLE001
            logger.error("OCR failed for page %s of %s: %s", i + 1, path.name, exc)
            pages.append(PageText(page_number=i + 1, text=native_text, ocr_used=False))
    doc.close()
    return pages


def _extract_image(path: Path) -> list[PageText]:
    try:
        img = Image.open(path)
        text = _ocr_best(img)
        logger.info("OCR used for image %s", path.name)
        return [PageText(page_number=1, text=text.strip(), ocr_used=True)]
    except Exception as exc:  # noqa: BLE001
        logger.error("OCR failed for image %s: %s", path.name, exc)
        return [PageText(page_number=1, text="", ocr_used=True)]