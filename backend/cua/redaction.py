"""
Redaction — never persist secrets or raw sensitive data into artifacts or logs.

This is regulated financial data. Two layers:
  1. Structural: inputs/outputs flagged `sensitive=True` in the schema are masked
     wherever we serialize them (logs, evidence, artifacts).
  2. Pattern-based: a best-effort scrubber for values that slip through free-text
     (LLM reasoning, error messages, DOM snippets) — emails, card-like numbers,
     SSNs, bearer tokens, api keys.

Redaction is applied at the log/evidence boundary, so the live run still uses the
real values in memory; only what we WRITE DOWN is masked.
"""
from __future__ import annotations

import re
from typing import Any

MASK = "«redacted»"

_PATTERNS = [
    # 13-19 digit card-like sequences (allowing spaces/dashes)
    (re.compile(r"\b(?:\d[ -]?){13,19}\b"), "«card»"),
    # US SSN
    (re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), "«ssn»"),
    # emails
    (re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"), "«email»"),
    # bearer / api keys / long opaque tokens
    (re.compile(r"\b(?:sk|rzp|gsk|pk|Bearer)[-_a-zA-Z0-9]{8,}\b"), "«token»"),
    (re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"), "«token»"),
]


def scrub_text(text: str) -> str:
    if not text:
        return text
    out = text
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    return out


def scrub_value(value: Any) -> Any:
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, dict):
        return {k: scrub_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub_value(v) for v in value]
    return value


def redact_mapping(data: dict[str, Any], sensitive_keys: set[str]) -> dict[str, Any]:
    """Mask keys marked sensitive by the schema, scrub the rest by pattern."""
    result: dict[str, Any] = {}
    for key, value in data.items():
        if key in sensitive_keys:
            result[key] = MASK
        else:
            result[key] = scrub_value(value)
    return result
