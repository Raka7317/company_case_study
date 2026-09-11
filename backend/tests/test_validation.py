import io
from pathlib import Path
import pytest
from PIL import Image

from app.services import document_validation_service
from app.utils.exceptions import UnsupportedFileTypeError, CorruptedFileError


def test_unsupported_extension_rejected(tmp_path: Path):
    f = tmp_path / "data.txt"
    f.write_text("hello")
    with pytest.raises(UnsupportedFileTypeError):
        document_validation_service.validate_file(f, "data.txt")


def test_empty_file_rejected(tmp_path: Path):
    f = tmp_path / "empty.pdf"
    f.write_bytes(b"")
    with pytest.raises(CorruptedFileError):
        document_validation_service.validate_file(f, "empty.pdf")


def test_valid_png_passes(tmp_path: Path):
    f = tmp_path / "img.png"
    Image.new("RGB", (100, 100), color="white").save(f)
    result = document_validation_service.validate_file(f, "img.png")
    assert result.status == "PASS"
    assert result.file_type == "image/png"
