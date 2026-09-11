import datetime as dt
from typing import Any, Optional
from pydantic import BaseModel


class DocumentSummary(BaseModel):
    document_name: str
    document_type: str
    processing_status: str
    created_at: dt.datetime

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    count: int
    documents: list[DocumentSummary]


class ProcessedDocumentResponse(BaseModel):
    """
    Generic envelope for /process and /{document_name}. `result` holds the
    exact structured JSON described in the case study (section 5.2).
    """
    result: dict[str, Any]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
