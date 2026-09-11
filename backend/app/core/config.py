"""
Centralised application configuration.
All secrets / environment-specific values MUST come from environment
variables. Nothing here is hardcoded to a real secret.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

_BACKEND_DIR = Path(__file__).resolve().parents[2]
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_BACKEND_DIR.parent / ".env")


class Settings:
    APP_NAME: str = "Document Intelligence Platform"
    API_V1_PREFIX: str = "/api/v1"

    # Storage
    BASE_DIR: Path = Path(__file__).resolve().parents[2]  # -> backend/
    UPLOAD_DIR: Path = Path(os.getenv("UPLOAD_DIR", BASE_DIR / "storage" / "uploads"))
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'storage' / 'app.db'}"
    )

    # Document constraints
    MAX_PAGES: int = int(os.getenv("MAX_PAGES", "3"))
    SUPPORTED_MIME_TYPES = {
        "application/pdf": ".pdf",
        "image/jpeg": ".jpg",
        "image/png": ".png",
    }

    # OCR
    OCR_MIN_NATIVE_CHARS: int = int(os.getenv("OCR_MIN_NATIVE_CHARS", "40"))
    TESSERACT_CMD: str = os.getenv("TESSERACT_CMD", "tesseract")

    # LLM based extraction (optional). If ANTHROPIC_API_KEY is not set the
    # service automatically falls back to the deterministic regex/rule
    # based extractor so the app still works end-to-end without a key.
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-6")

    # Alternative LLM provider. If set (and ANTHROPIC_API_KEY is not), the
    # extractor uses OpenAI's Chat Completions API (JSON mode) instead.
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    # Alternative LLM provider -- Google Gemini via Google AI Studio. This is
    # the option with a genuine no-billing-required free tier (rate-limited
    # Flash / Flash-Lite models, ~1,500 requests/day, no credit card needed).
    # Used if neither ANTHROPIC_API_KEY nor OPENAI_API_KEY is set.
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
    GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")

    # Financial validation tolerance (absolute currency units)
    VALIDATION_TOLERANCE: float = float(os.getenv("VALIDATION_TOLERANCE", "1.0"))
    VALIDATION_TOLERANCE_PCT: float = float(os.getenv("VALIDATION_TOLERANCE_PCT", "0.01"))

    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


settings = Settings()
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
(settings.BASE_DIR / "storage").mkdir(parents=True, exist_ok=True)