"""Identity Resolver — maps external IDs (jira-xxx, gl-xxx) to canonical employee_id."""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Employee

logger = logging.getLogger("epiap.identity")

# In-memory cache to avoid repeated DB lookups within a session
_cache: dict[str, Optional[str]] = {}


async def resolve_employee_id(
    session: AsyncSession, external_id: str
) -> str:
    """Resolve an external connector ID to a canonical employee_id.

    Mapping:
      jira-{accountId}    → lookup by jira_account_id
      gl-{email}          → lookup by email
      jenkins-{username}  → lookup by jenkins_username

    Returns the canonical employee_id if found, otherwise returns the
    external_id as-is (unresolved).
    """
    if external_id in _cache:
        return _cache[external_id] or external_id

    canonical = None

    if external_id.startswith("jira-"):
        account_id = external_id[5:]  # strip "jira-"
        result = await session.execute(
            select(Employee.employee_id).where(
                Employee.jira_account_id == account_id
            )
        )
        row = result.scalar_one_or_none()
        if row:
            canonical = row

    elif external_id.startswith("gl-"):
        email = external_id[3:]  # strip "gl-"
        result = await session.execute(
            select(Employee.employee_id).where(
                Employee.email == email
            )
        )
        row = result.scalar_one_or_none()
        if row:
            canonical = row

    elif external_id.startswith("jenkins-"):
        username = external_id[8:]  # strip "jenkins-"
        result = await session.execute(
            select(Employee.employee_id).where(
                Employee.jenkins_username == username
            )
        )
        row = result.scalar_one_or_none()
        if row:
            canonical = row

    _cache[external_id] = canonical
    return canonical or external_id


def clear_cache():
    """Clear the in-memory identity cache (e.g., after employee updates)."""
    _cache.clear()
