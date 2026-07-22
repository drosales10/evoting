"""Geo FeatureCollection builders for territorial layers N1-N5."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Election,
    ElectoralMunicipality,
    ElectoralPollingPlace,
    ElectoralRegion,
    ElectoralState,
    Member,
    MemberElectionStatus,
    Organization,
)


def _feature(level: str, entity_id: UUID, name: str, code: str, geojson: dict[str, Any] | None, props: dict[str, Any]) -> dict[str, Any] | None:
    if not geojson or "type" not in geojson:
        # Placeholder bbox-less point skip — still emit with null geom for list UIs
        return {
            "type": "Feature",
            "geometry": None,
            "properties": {
                "level": level,
                "id": str(entity_id),
                "code": code,
                "name": name,
                **props,
            },
        }
    geometry = geojson.get("geometry") if geojson.get("type") == "Feature" else geojson
    return {
        "type": "Feature",
        "geometry": geometry,
        "properties": {
            "level": level,
            "id": str(entity_id),
            "code": code,
            "name": name,
            **props,
        },
    }


async def build_admin_feature_collection(
    session: AsyncSession,
    organization_id: UUID,
    levels: set[str],
) -> dict[str, Any]:
    features: list[dict[str, Any]] = []

    if "N1" in levels:
        org = await session.scalar(select(Organization).where(Organization.id == organization_id))
        if org:
            features.append(
                {
                    "type": "Feature",
                    "geometry": None,
                    "properties": {
                        "level": "N1",
                        "id": str(org.id),
                        "code": org.slug,
                        "name": org.name,
                    },
                }
            )

    if "N2" in levels:
        for row in (
            await session.scalars(
                select(ElectoralRegion).where(ElectoralRegion.organization_id == organization_id)
            )
        ).all():
            feat = _feature("N2", row.id, row.name, row.code, row.geojson, {})
            if feat:
                features.append(feat)

    if "N3" in levels:
        for row in (
            await session.scalars(
                select(ElectoralState).where(ElectoralState.organization_id == organization_id)
            )
        ).all():
            feat = _feature(
                "N3",
                row.id,
                row.name,
                row.code,
                row.geojson,
                {"region_id": str(row.region_id)},
            )
            if feat:
                features.append(feat)

    if "N4" in levels:
        for row in (
            await session.scalars(
                select(ElectoralMunicipality).where(
                    ElectoralMunicipality.organization_id == organization_id
                )
            )
        ).all():
            feat = _feature(
                "N4",
                row.id,
                row.name,
                row.code,
                row.geojson,
                {"state_id": str(row.state_id)},
            )
            if feat:
                features.append(feat)

    if "N5" in levels:
        for row in (
            await session.scalars(
                select(ElectoralPollingPlace).where(
                    ElectoralPollingPlace.organization_id == organization_id
                )
            )
        ).all():
            feat = _feature(
                "N5",
                row.id,
                row.name,
                row.code,
                row.geojson,
                {"municipality_id": str(row.municipality_id)},
            )
            if feat:
                features.append(feat)

    return {"type": "FeatureCollection", "features": features}


async def build_public_results_collection(
    session: AsyncSession,
    election: Election,
) -> dict[str, Any]:
    """Aggregate participation by N2–N5 for choropleth-style client map."""
    features: list[dict[str, Any]] = []

    async def _counts_for(member_attr: str, unit_id: UUID) -> tuple[int, int]:
        voted = int(
            (
                await session.execute(
                    select(func.count(MemberElectionStatus.id))
                    .join(Member, Member.id == MemberElectionStatus.member_id)
                    .where(
                        MemberElectionStatus.election_id == election.id,
                        MemberElectionStatus.has_voted.is_(True),
                        getattr(Member, member_attr) == unit_id,
                    )
                )
            ).scalar_one()
        )
        eligible = int(
            (
                await session.execute(
                    select(func.count(MemberElectionStatus.id))
                    .join(Member, Member.id == MemberElectionStatus.member_id)
                    .where(
                        MemberElectionStatus.election_id == election.id,
                        MemberElectionStatus.eligible.is_(True),
                        getattr(Member, member_attr) == unit_id,
                    )
                )
            ).scalar_one()
        )
        return voted, eligible

    org = await session.scalar(
        select(Organization).where(Organization.id == election.organization_id)
    )
    if org:
        features.append(
            {
                "type": "Feature",
                "geometry": None,
                "properties": {
                    "level": "N1",
                    "id": str(org.id),
                    "code": org.slug,
                    "name": org.name,
                    "election_id": str(election.id),
                },
            }
        )

    regions = (
        await session.scalars(
            select(ElectoralRegion).where(
                ElectoralRegion.organization_id == election.organization_id
            )
        )
    ).all()
    for region in regions:
        voted, eligible = await _counts_for("region_id", region.id)
        feat = _feature(
            "N2",
            region.id,
            region.name,
            region.code,
            region.geojson,
            {
                "voted_count": voted,
                "eligible_count": eligible,
                "participation_pct": round((voted / eligible) * 100, 2) if eligible else 0,
                "election_id": str(election.id),
            },
        )
        if feat:
            features.append(feat)

    states = (
        await session.scalars(
            select(ElectoralState).where(ElectoralState.organization_id == election.organization_id)
        )
    ).all()
    for state in states:
        voted, eligible = await _counts_for("state_id", state.id)
        feat = _feature(
            "N3",
            state.id,
            state.name,
            state.code,
            state.geojson,
            {
                "voted_count": voted,
                "eligible_count": eligible,
                "participation_pct": round((voted / eligible) * 100, 2) if eligible else 0,
                "election_id": str(election.id),
            },
        )
        if feat:
            features.append(feat)

    municipalities = (
        await session.scalars(
            select(ElectoralMunicipality).where(
                ElectoralMunicipality.organization_id == election.organization_id
            )
        )
    ).all()
    for muni in municipalities:
        voted, eligible = await _counts_for("municipality_id", muni.id)
        feat = _feature(
            "N4",
            muni.id,
            muni.name,
            muni.code,
            muni.geojson,
            {
                "voted_count": voted,
                "eligible_count": eligible,
                "participation_pct": round((voted / eligible) * 100, 2) if eligible else 0,
                "election_id": str(election.id),
            },
        )
        if feat:
            features.append(feat)

    places = (
        await session.scalars(
            select(ElectoralPollingPlace).where(
                ElectoralPollingPlace.organization_id == election.organization_id
            )
        )
    ).all()
    for place in places:
        voted, eligible = await _counts_for("polling_place_id", place.id)
        feat = _feature(
            "N5",
            place.id,
            place.name,
            place.code,
            place.geojson,
            {
                "voted_count": voted,
                "eligible_count": eligible,
                "participation_pct": round((voted / eligible) * 100, 2) if eligible else 0,
                "election_id": str(election.id),
            },
        )
        if feat:
            features.append(feat)

    return {
        "type": "FeatureCollection",
        "features": features,
        "properties": {
            "election_id": str(election.id),
            "title": election.title,
            "scope_level": election.scope_level,
        },
    }
