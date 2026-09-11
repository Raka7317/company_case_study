from typing import Any, Optional
from pydantic import BaseModel


class FieldValue(BaseModel):
    """A single extracted field with grounding evidence."""
    value: Optional[Any] = None
    confidence: Optional[float] = None  # OPTIONAL per spec
    page_number: Optional[int] = None
    source_text: Optional[str] = None


class ValidationCheck(BaseModel):
    name: str
    formula: str
    operands: dict
    calculated_value: Optional[float] = None
    reported_value: Optional[float] = None
    variance: Optional[float] = None
    status: str  # PASS | FAIL | NOT_APPLICABLE
    period: Optional[str] = None


class ValidationResult(BaseModel):
    checks: list[ValidationCheck]
    overall_status: str
    issues: list[str]


class FileValidation(BaseModel):
    file_type: Optional[str] = None
    is_supported: bool
    is_readable: bool
    page_count: Optional[int] = None
    status: str
    reason: Optional[str] = None
