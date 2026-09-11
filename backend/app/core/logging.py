import logging
import sys
from app.core.config import settings


def setup_logging() -> None:
    root = logging.getLogger()
    if root.handlers:
        return  # already configured (avoid duplicate handlers on reload)

    root.setLevel(settings.LOG_LEVEL)
    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
