from __future__ import annotations

import re

from app.errors import ValidationError


SESSION_ID_RE = re.compile(r"^[A-Za-z0-9._:-]{1,128}$")


def validate_chat_request(
    *,
    message: str,
    session_id: str | None,
    max_message_chars: int,
) -> None:
    if not isinstance(message, str) or not message.strip():
        raise ValidationError("A non-empty message is required.")

    if len(message.strip()) > max_message_chars:
        raise ValidationError(
            f"Message exceeds the maximum length of {max_message_chars} characters."
        )

    if session_id and not SESSION_ID_RE.match(session_id):
        raise ValidationError("session_id contains unsupported characters.")
