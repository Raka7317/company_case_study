"""
Input-control layer. Validates file type, integrity and page count
BEFORE any OCR / extraction is attempted. This is not document-type
classification -- the document_type is supplied by the caller.
"""
from pathlib import Path
import fitz  # PyMuPDF
from PIL import Image, UnidentifiedImageError

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.extraction import FileValidation
from app.utils.exceptions import (
    UnsupportedFileTypeError, CorruptedFileError, PageLimitExceededError
)

logger = get_logger(__name__)

MIME_BY_EXT = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def validate_file(path: Path, original_name: str) -> FileValidation:
    ext = Path(original_name).suffix.lower()
    file_type = MIME_BY_EXT.get(ext)

    if not path.exists() or path.stat().st_size == 0:
        logger.warning("Empty upload rejected: %s", original_name)
        raise CorruptedFileError("The uploaded file is empty.")

    if file_type is None:
        logger.warning("Unsupported file type rejected: %s", original_name)
        raise UnsupportedFileTypeError()

    page_count = 1
    try:
        if file_type == "application/pdf":
            doc = fitz.open(path)
            page_count = doc.page_count
            if page_count == 0:
                raise CorruptedFileError("PDF has no pages.")
            # touch first page to confirm it is actually readable
            _ = doc[0].get_text()
            doc.close()
        else:
            with Image.open(path) as img:
                img.verify()
            page_count = 1
    except (CorruptedFileError,):
        raise
    except (UnidentifiedImageError, Exception) as exc:  # noqa: BLE001
        logger.error("Corrupted/unreadable file %s: %s", original_name, exc)
        raise CorruptedFileError(f"File could not be read: {exc}") from exc

    if page_count > settings.MAX_PAGES:
        logger.warning("Page limit exceeded for %s (%s pages)", original_name, page_count)
        raise PageLimitExceededError(
            f"Document has {page_count} pages; maximum allowed is {settings.MAX_PAGES}."
        )

    logger.info("File validation PASS for %s (%s, %s page(s))", original_name, file_type, page_count)
    return FileValidation(
        file_type=file_type,
        is_supported=True,
        is_readable=True,
        page_count=page_count,
        status="PASS",
    )
