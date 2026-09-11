import uuid
from pathlib import Path
from app.core.config import settings

ALLOWED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}


def safe_filename(original_name: str) -> str:
    """Prevent path traversal; keep original name for display but store
    under a random-prefixed safe name on disk."""
    ext = Path(original_name).suffix.lower()
    stem = Path(original_name).stem.replace("/", "_").replace("\\", "_")
    return f"{stem}__{uuid.uuid4().hex[:8]}{ext}"


def save_upload(contents: bytes, original_name: str) -> Path:
    dest = settings.UPLOAD_DIR / safe_filename(original_name)
    with open(dest, "wb") as f:
        f.write(contents)
    return dest
