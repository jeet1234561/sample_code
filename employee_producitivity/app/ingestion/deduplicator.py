"""Deduplication strategy:

Primary: PostgreSQL partial unique index on raw_source_id (handled in base connector)
Secondary: In-memory set for hot-path dedup before DB round-trip
"""

from typing import Set


class InMemoryDeduplicator:
    """Simple in-memory set for fast dedup within a single poll cycle.

    Not persistent across restarts — the DB unique index is the authoritative guard.
    """

    def __init__(self):
        self._seen: Set[str] = set()

    def is_duplicate(self, raw_source_id: str) -> bool:
        if raw_source_id in self._seen:
            return True
        self._seen.add(raw_source_id)
        return False

    def reset(self):
        self._seen.clear()
