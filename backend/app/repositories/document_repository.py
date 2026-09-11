from sqlalchemy import desc
from sqlalchemy.orm import Session
from app.models.document import ProcessedDocument


def save_result(db: Session, document_name: str, document_type: str,
                 status: str, result_json: dict, error_message: str | None = None) -> ProcessedDocument:
    record = ProcessedDocument(
        document_name=document_name,
        document_type=document_type,
        processing_status=status,
        result_json=result_json,
        error_message=error_message,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def get_latest_by_name(db: Session, document_name: str) -> ProcessedDocument | None:
    return (
        db.query(ProcessedDocument)
        .filter(ProcessedDocument.document_name == document_name)
        .order_by(desc(ProcessedDocument.created_at))
        .first()
    )


def list_all(db: Session, limit: int = 200) -> list[ProcessedDocument]:
    return (
        db.query(ProcessedDocument)
        .order_by(desc(ProcessedDocument.created_at))
        .limit(limit)
        .all()
    )
