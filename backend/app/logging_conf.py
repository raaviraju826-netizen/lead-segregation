from __future__ import annotations

import logging
import re

from .config import get_settings


def setup_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, get_settings().log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def redact(text: str, limit: int = 80) -> str:
    """Never log full email bodies; log a short redacted preview only."""
    t = _EMAIL_RE.sub("<email>", text or "")
    return (t[:limit] + "…") if len(t) > limit else t
