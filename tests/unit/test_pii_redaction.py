from app.security.pii_redaction import redact_text, redact_value


def test_redact_text_masks_email_phone_and_long_numbers() -> None:
    source = "Email me at jane@example.com or call +233 20 123 4567 about 1234567890123456."

    redacted = redact_text(source)

    assert "[redacted-email]" in redacted
    assert "[redacted-phone]" in redacted
    assert "[redacted-number]" in redacted


def test_redact_value_recurses_through_nested_payloads() -> None:
    payload = {
        "email": "jane@example.com",
        "contacts": ["+233 20 123 4567", {"account": "123456789012"}],
    }

    redacted = redact_value(payload)

    assert redacted["email"] == "[redacted-email]"
    assert redacted["contacts"][0] == "[redacted-phone]"
    assert redacted["contacts"][1]["account"] == "[redacted-number]"
