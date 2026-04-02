from __future__ import annotations

import re
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)(?:\+?\d[\d -]{7,}\d)(?!\d)")
LONG_DIGIT_RE = re.compile(r"\b\d{10,19}\b")


def redact_text(value: str) -> str:
    redacted = EMAIL_RE.sub("[redacted-email]", value)
    redacted = PHONE_RE.sub("[redacted-phone]", redacted)
    redacted = LONG_DIGIT_RE.sub("[redacted-number]", redacted)
    return redacted


def redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_value(item) for item in value)
    if isinstance(value, dict):
        return {str(key): redact_value(item) for key, item in value.items()}
    return value
