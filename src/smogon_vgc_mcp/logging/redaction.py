"""Sensitive data redaction utilities for log parameters."""

from typing import Any

SENSITIVE_KEYS: frozenset[str] = frozenset(
    {"password", "token", "api_key", "secret", "auth", "credential", "key"}
)


def redact_sensitive(
    data: dict[str, Any],
    sensitive_keys: frozenset[str] = SENSITIVE_KEYS,
) -> dict[str, Any]:
    """Redact sensitive values from a dictionary for safe logging.

    Recursively processes nested dictionaries. Values are redacted if
    any sensitive key substring is found in the key name (case-insensitive).
    """
    result: dict[str, Any] = {}
    for k, v in data.items():
        key_lower = k.lower()
        if any(sensitive in key_lower for sensitive in sensitive_keys):
            result[k] = "[REDACTED]"
        elif isinstance(v, dict):
            result[k] = redact_sensitive(v, sensitive_keys)
        elif isinstance(v, list):
            result[k] = [
                redact_sensitive(item, sensitive_keys) if isinstance(item, dict) else item
                for item in v
            ]
        else:
            result[k] = v
    return result
