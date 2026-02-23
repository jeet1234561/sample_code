"""Central normalization utilities shared across connectors."""

from datetime import datetime, timezone
from typing import Optional


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is UTC. If naive, assume UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def resolve_employee_id_from_email(email: str, lookup_table: dict) -> str:
    """Map an email to an internal employee_id using a preloaded lookup dict."""
    return lookup_table.get(email, f"email-{email}")


def sanitize_payload(payload: dict) -> dict:
    """Remove None values and truncate long strings for storage efficiency."""
    cleaned = {}
    for k, v in payload.items():
        if v is None:
            continue
        if isinstance(v, str) and len(v) > 1000:
            v = v[:1000] + "..."
        cleaned[k] = v
    return cleaned
