from fastapi import APIRouter, UploadFile, File, Form, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.logging import get_logger
from app.utils.file_utils import save_upload
from app.utils.exceptions import AppError, DocumentNotFoundError
from app.services import document_service
from app.repositories import document_repository

router = APIRouter(prefix="/api/v1", tags=["documents"])
logger = get_logger(__name__)


@router.get("/health")
def health():
    return {"status": "ok"}


@router.post("/documents/process")
async def process_document(
    file: UploadFile = File(...),
    document_type: str = Form(...),
    db: Session = Depends(get_db),
):
    contents = await file.read()
    if not contents:
        raise AppError("CORRUPTED_FILE", "The uploaded file is empty.", 400)
    path = save_upload(contents, file.filename)
    return document_service.process_document(db, path, file.filename, document_type)


@router.get("/documents/{document_name}")
def get_document(document_name: str, db: Session = Depends(get_db)):
    record = document_repository.get_latest_by_name(db, document_name)
    if not record:
        raise DocumentNotFoundError(f"No processed document found named '{document_name}'.")
    return record.result_json


@router.get("/documents")
def list_documents(db: Session = Depends(get_db)):
    records = document_repository.list_all(db)
    return {
        "count": len(records),
        "documents": [
            {
                "document_name": r.document_name,
                "document_type": r.document_type,
                "processing_status": r.processing_status,
                "created_at": r.created_at.isoformat() + "Z",
            }
            for r in records
        ],
    }
