"""Shared helpers for operational export/seed scripts."""

from __future__ import annotations

import os
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import (
    ElectoralMunicipality,
    ElectoralPollingPlace,
    ElectoralRegion,
    ElectoralState,
    Member,
    Organization,
)


def resolve_org_slug(explicit: str | None = None) -> str:
    slug = (
        explicit
        or settings.seed_admin_org_slug
        or os.environ.get("SEED_ADMIN_ORG_SLUG")
    )
    if not slug:
        raise RuntimeError("Set SEED_ADMIN_ORG_SLUG or pass --org")
    return slug


async def get_organization(session: AsyncSession, slug: str) -> Organization:
    organization = await session.scalar(
        select(Organization).where(Organization.slug == slug)
    )
    if organization is None:
        raise RuntimeError(f"Organization slug={slug!r} not found. Run seed_admin first.")
    return organization


def json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return value


def parse_datetime(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        return value
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    return datetime.fromisoformat(text)


def parse_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    return date.fromisoformat(str(value)[:10])


async def territory_code_maps(
    session: AsyncSession, org_id: UUID
) -> tuple[
    dict[str, ElectoralRegion],
    dict[str, ElectoralState],
    dict[str, ElectoralMunicipality],
    dict[str, ElectoralPollingPlace],
]:
    regions = {
        r.code: r
        for r in (
            await session.scalars(
                select(ElectoralRegion).where(ElectoralRegion.organization_id == org_id)
            )
        ).all()
    }
    states = {
        s.code: s
        for s in (
            await session.scalars(
                select(ElectoralState).where(ElectoralState.organization_id == org_id)
            )
        ).all()
    }
    municipalities = {
        m.code: m
        for m in (
            await session.scalars(
                select(ElectoralMunicipality).where(
                    ElectoralMunicipality.organization_id == org_id
                )
            )
        ).all()
    }
    polling_places = {
        p.code: p
        for p in (
            await session.scalars(
                select(ElectoralPollingPlace).where(
                    ElectoralPollingPlace.organization_id == org_id
                )
            )
        ).all()
    }
    return regions, states, municipalities, polling_places


async def find_member(
    session: AsyncSession,
    org_id: UUID,
    *,
    registry_code: str | None = None,
    dni: str | None = None,
    email: str | None = None,
) -> Member | None:
    if registry_code:
        member = await session.scalar(
            select(Member).where(
                Member.organization_id == org_id,
                Member.registry_code == registry_code,
            )
        )
        if member is not None:
            return member
    if dni:
        member = await session.scalar(
            select(Member).where(Member.organization_id == org_id, Member.dni == dni)
        )
        if member is not None:
            return member
    if email:
        return await session.scalar(
            select(Member).where(
                Member.organization_id == org_id,
                Member.email == email.strip().lower(),
            )
        )
    return None


def member_ref(raw: dict[str, Any]) -> tuple[str | None, str | None, str | None]:
    return (
        (str(raw["registry_code"]).strip() if raw.get("registry_code") else None),
        (str(raw["dni"]).strip() if raw.get("dni") else None),
        (str(raw["email"]).strip().lower() if raw.get("email") else None),
    )
