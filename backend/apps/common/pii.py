"""Helpers for keeping PII out of places it shouldn't be (e.g. log sinks)."""
import hashlib


def email_log_tag(email: str | None) -> str:
    """Short, stable, non-reversible tag for an email — log this instead of the
    raw address. The same email always maps to the same tag, so per-account
    correlation in logs survives without writing PII to stdout/log storage.
    """
    return hashlib.sha256((email or "").strip().lower().encode()).hexdigest()[:10]
