import datetime as dt
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from app.core.database import Base


class ProcessedDocument(Base):
    """
    Stores the latest (and, implicitly via created_at ordering, all)
    processing results for a given document_name. Retrieval by name
    always returns the most recently created row.
    """
    __tablename__ = "processed_documents"

    id = Column(Integer, primary_key=True, index=True)
    document_name = Column(String(512), index=True, nullable=False)
    document_type = Column(String(64), nullable=False)
    processing_status = Column(String(16), nullable=False)  # PASS / FAILED
    result_json = Column(JSON, nullable=False)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, default=dt.datetime.utcnow, index=True)
