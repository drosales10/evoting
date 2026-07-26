"""Seed territorial hierarchy N2–N5 from a JSON file (idempotent by code).

Usage (from apps/backend, with DATABASE_URL and org available):

  # Usa SEED_ADMIN_ORG_SLUG y el JSON por defecto
  python -m scripts.seed_territory

  # JSON / org explícitos
  SEED_TERRITORY_FILE=/path/to/territory.json \\
  SEED_ADMIN_ORG_SLUG=sociedad-forestales-afines \\
    python -m scripts.seed_territory

Does not delete units missing from the file. Updates name when code exists.
Codes are normalized to UPPER (same as admin API).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.core.config import settings
from app.db.session import dispose_engine, get_session_factory
from app.models import (
    ElectoralMunicipality,
    ElectoralPollingPlace,
    ElectoralRegion,
    ElectoralState,
    Organization,
)

DEFAULT_DATA_PATH = Path(__file__).resolve().parent / "seed_data" / "territory.json"


def _norm_code(value: str) -> str:
    return value.strip().upper()


def _load_payload(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or "regions" not in raw:
        raise RuntimeError(f"Invalid territory seed file (missing regions): {path}")
    if not isinstance(raw["regions"], list):
        raise RuntimeError("regions must be a list")
    return raw


async def seed_territory(
    *,
    organization_slug: str | None = None,
    data_path: Path | None = None,
) -> str:
    path = data_path or Path(
        os.environ.get("SEED_TERRITORY_FILE", str(DEFAULT_DATA_PATH))
    )
    if not path.is_file():
        raise RuntimeError(f"Territory seed file not found: {path}")

    payload = _load_payload(path)
    slug = (
        organization_slug
        or payload.get("organization_slug")
        or settings.seed_admin_org_slug
        or os.environ.get("SEED_ADMIN_ORG_SLUG")
    )
    if not slug:
        raise RuntimeError(
            "Set SEED_ADMIN_ORG_SLUG (or organization_slug in the JSON) "
            "so the seeder knows which organization owns the territory"
        )

    factory = get_session_factory()
    counts = {
        "regions_created": 0,
        "regions_updated": 0,
        "states_created": 0,
        "states_updated": 0,
        "municipalities_created": 0,
        "municipalities_updated": 0,
        "polling_places_created": 0,
        "polling_places_updated": 0,
    }

    async with factory() as session:
        organization = await session.scalar(
            select(Organization).where(Organization.slug == slug)
        )
        if organization is None:
            raise RuntimeError(
                f"Organization slug={slug!r} not found. Run seed_admin first."
            )
        org_id = organization.id

        for region_raw in payload["regions"]:
            region_code = _norm_code(str(region_raw["code"]))
            region_name = str(region_raw["name"]).strip()
            region = await session.scalar(
                select(ElectoralRegion).where(
                    ElectoralRegion.organization_id == org_id,
                    ElectoralRegion.code == region_code,
                )
            )
            if region is None:
                region = ElectoralRegion(
                    id=uuid4(),
                    organization_id=org_id,
                    code=region_code,
                    name=region_name,
                )
                session.add(region)
                await session.flush()
                counts["regions_created"] += 1
            elif region.name != region_name:
                region.name = region_name
                counts["regions_updated"] += 1

            for state_raw in region_raw.get("states") or []:
                state_code = _norm_code(str(state_raw["code"]))
                state_name = str(state_raw["name"]).strip()
                state = await session.scalar(
                    select(ElectoralState).where(
                        ElectoralState.organization_id == org_id,
                        ElectoralState.code == state_code,
                    )
                )
                if state is None:
                    state = ElectoralState(
                        id=uuid4(),
                        organization_id=org_id,
                        region_id=region.id,
                        code=state_code,
                        name=state_name,
                    )
                    session.add(state)
                    await session.flush()
                    counts["states_created"] += 1
                else:
                    changed = False
                    if state.region_id != region.id:
                        state.region_id = region.id
                        changed = True
                    if state.name != state_name:
                        state.name = state_name
                        changed = True
                    if changed:
                        counts["states_updated"] += 1

                for mun_raw in state_raw.get("municipalities") or []:
                    mun_code = _norm_code(str(mun_raw["code"]))
                    mun_name = str(mun_raw["name"]).strip()
                    municipality = await session.scalar(
                        select(ElectoralMunicipality).where(
                            ElectoralMunicipality.organization_id == org_id,
                            ElectoralMunicipality.code == mun_code,
                        )
                    )
                    if municipality is None:
                        municipality = ElectoralMunicipality(
                            id=uuid4(),
                            organization_id=org_id,
                            state_id=state.id,
                            code=mun_code,
                            name=mun_name,
                        )
                        session.add(municipality)
                        await session.flush()
                        counts["municipalities_created"] += 1
                    else:
                        changed = False
                        if municipality.state_id != state.id:
                            municipality.state_id = state.id
                            changed = True
                        if municipality.name != mun_name:
                            municipality.name = mun_name
                            changed = True
                        if changed:
                            counts["municipalities_updated"] += 1

                    for mesa_raw in mun_raw.get("polling_places") or []:
                        mesa_code = _norm_code(str(mesa_raw["code"]))
                        mesa_name = str(mesa_raw["name"]).strip()
                        mesa = await session.scalar(
                            select(ElectoralPollingPlace).where(
                                ElectoralPollingPlace.organization_id == org_id,
                                ElectoralPollingPlace.code == mesa_code,
                            )
                        )
                        if mesa is None:
                            session.add(
                                ElectoralPollingPlace(
                                    id=uuid4(),
                                    organization_id=org_id,
                                    municipality_id=municipality.id,
                                    code=mesa_code,
                                    name=mesa_name,
                                )
                            )
                            counts["polling_places_created"] += 1
                        else:
                            changed = False
                            if mesa.municipality_id != municipality.id:
                                mesa.municipality_id = municipality.id
                                changed = True
                            if mesa.name != mesa_name:
                                mesa.name = mesa_name
                                changed = True
                            if changed:
                                counts["polling_places_updated"] += 1

        await session.commit()

    summary = ", ".join(f"{k}={v}" for k, v in counts.items())
    return f"organization={slug}; file={path}; {summary}"


async def _run() -> int:
    try:
        print(await seed_territory())
    finally:
        await dispose_engine()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
