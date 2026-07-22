"""Append-only audit helpers with hash chaining."""

from __future__ import annotations

import hashlib
import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AuditLog


def _canonical_details(details: dict[str, Any] | None) -> str:
    return json.dumps(details or {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def compute_entry_hash(
    *,
    organization_id: UUID,
    event_type: str,
    actor_id_hash: str | None,
    details: dict[str, Any] | None,
    prev_hash: str | None,
) -> str:
    material = "|".join(
        [
            str(organization_id),
            event_type,
            actor_id_hash or "",
            _canonical_details(details),
            prev_hash or "GENESIS",
        ]
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


async def latest_audit_hash(session: AsyncSession, organization_id: UUID) -> str | None:
    return await session.scalar(
        select(AuditLog.entry_hash)
        .where(AuditLog.organization_id == organization_id)
        .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
        .limit(1)
    )


async def append_audit_event(
    session: AsyncSession,
    *,
    organization_id: UUID,
    event_type: str,
    actor_id_hash: str | None,
    details: dict[str, Any] | None,
) -> AuditLog:
    prev_hash = await latest_audit_hash(session, organization_id)
    entry_hash = compute_entry_hash(
        organization_id=organization_id,
        event_type=event_type,
        actor_id_hash=actor_id_hash,
        details=details,
        prev_hash=prev_hash,
    )
    row = AuditLog(
        organization_id=organization_id,
        event_type=event_type,
        actor_id_hash=actor_id_hash,
        details=details,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    session.add(row)
    return row
