# app/security/pii_redaction.py
# 2026-04-02
"""Purpose: Redact common PII patterns before prompts or logs leave the deterministic backend path."""

from __future__ import annotations

##BRICK 1: Imports and redaction patterns
import re
from typing import Any


EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_RE = re.compile(r"(?<!\d)\+?\d[\d -]{7,}\d(?!\d)")
LONG_DIGIT_RE = re.compile(r"\b\d{10,19}\b")


##BRICK 2: Recursive text and payload redaction helpers
def redact_text(value: str) -> str:
    redacted = EMAIL_RE.sub("[redacted-email]", value)
    # Long uninterrupted digit strings should be classified as account/card-like
    # identifiers before phone matching can absorb them.
    redacted = LONG_DIGIT_RE.sub("[redacted-number]", redacted)
    redacted = PHONE_RE.sub("[redacted-phone]", redacted)
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
