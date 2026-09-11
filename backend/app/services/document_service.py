import time
import datetime as dt
from pathlib import Path
from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.services import document_validation_service, ocr_service, extraction_service, financial_validation_service
from app.repositories import document_repository
from app.utils.exceptions import AppError

logger = get_logger(__name__)

VALID_DOC_TYPES = {"invoice", "balance_sheet", "profit_and_loss", "cash_flow_statement"}


def process_document(db: Session, path: Path, original_name: str, document_type: str) -> dict:
    start = time.time()

    if document_type not in VALID_DOC_TYPES:
        raise AppError("INVALID_DOCUMENT_TYPE",
                        f"document_type must be one of {sorted(VALID_DOC_TYPES)}", 400)

    try:
        file_validation = document_validation_service.validate_file(path, original_name)
    except AppError as exc:
        # Store a FAILED record for dashboard visibility, but also propagate
        # the error to the API layer so the correct HTTP status is returned
        # (per section 5.3 Error Response).
        result = _build_failed_result(original_name, document_type, exc, start)
        document_repository.save_result(db, original_name, document_type, "FAILED", result, exc.message)
        raise

    try:
        pages = ocr_service.extract_text(path, file_validation.file_type)
        ocr_used = any(p.ocr_used for p in pages)

        extracted, method = extraction_service.extract_fields(document_type, pages)
        validation = financial_validation_service.validate(document_type, extracted)

        required = extraction_service.REQUIRED_FIELDS.get(document_type, [])
        extracted_present = sum(1 for k in required if isinstance(extracted.get(k), dict)
                                 and extracted[k].get("value") is not None)
        has_line_items = bool(extracted.get("line_items"))
        status = "PASS" if (extracted_present > 0 or has_line_items) else "FAILED"

        result = {
            "document_name": original_name,
            "document_type": document_type,
            "processing_status": status,
            "file_validation": file_validation.model_dump(),
            "extracted_data": extracted,
            "validation": validation,
            "processing_metadata": {
                "extraction_method": method,
                "ocr_used": ocr_used,
                "processed_at": dt.datetime.utcnow().isoformat() + "Z",
                "processing_time_ms": int((time.time() - start) * 1000),
            },
        }
        document_repository.save_result(db, original_name, document_type, status, result)
        logger.info("Processed %s (%s) -> %s", original_name, document_type, status)
        return result

    except AppError as exc:
        result = _build_failed_result(original_name, document_type, exc, start)
        document_repository.save_result(db, original_name, document_type, "FAILED", result, exc.message)
        return result
    except Exception as exc:  # noqa: BLE001
        logger.exception("Unexpected processing failure for %s", original_name)
        app_exc = AppError("PROCESSING_ERROR", "An unexpected error occurred while processing the document.", 500)
        result = _build_failed_result(original_name, document_type, app_exc, start)
        document_repository.save_result(db, original_name, document_type, "FAILED", result, str(exc))
        return result


def _build_failed_result(original_name: str, document_type: str, exc: AppError, start: float) -> dict:
    return {
        "document_name": original_name,
        "document_type": document_type,
        "processing_status": "FAILED",
        "file_validation": {
            "is_supported": exc.code != "UNSUPPORTED_FILE_TYPE",
            "is_readable": exc.code not in ("CORRUPTED_FILE",),
            "status": "FAILED",
            "reason": exc.message,
        },
        "extracted_data": {},
        "validation": {"checks": [], "overall_status": "NOT_APPLICABLE", "issues": [exc.message]},
        "processing_metadata": {
            "ocr_used": False,
            "processed_at": dt.datetime.utcnow().isoformat() + "Z",
            "processing_time_ms": int((time.time() - start) * 1000),
        },
        "error": {"code": exc.code, "message": exc.message},
    }
