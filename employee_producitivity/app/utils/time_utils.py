from datetime import datetime, timezone


def ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is UTC. If naive, assume UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_iso_timestamp(ts_string: str) -> datetime:
    """Parse an ISO 8601 timestamp string, handling Z suffix."""
    return datetime.fromisoformat(ts_string.replace("Z", "+00:00"))
