"""Export territorial hierarchy N2–N5 to JSON (for seeding another environment).

Usage (from apps/backend):

  SEED_ADMIN_ORG_SLUG=sociedad-forestales-afines \\
    python -m scripts.export_territory > territory-export.json

  # Or write to a path
  python -m scripts.export_territory --out /tmp/territory.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

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


async def export_territory(organization_slug: str) -> dict[str, Any]:
    factory = get_session_factory()
    async with factory() as session:
        organization = await session.scalar(
            select(Organization).where(Organization.slug == organization_slug)
        )
        if organization is None:
            raise RuntimeError(f"Organization slug={organization_slug!r} not found")

        org_id: UUID = organization.id
        regions = (
            await session.scalars(
                select(ElectoralRegion)
                .where(ElectoralRegion.organization_id == org_id)
                .order_by(ElectoralRegion.code)
            )
        ).all()
        states = (
            await session.scalars(
                select(ElectoralState)
                .where(ElectoralState.organization_id == org_id)
                .order_by(ElectoralState.code)
            )
        ).all()
        municipalities = (
            await session.scalars(
                select(ElectoralMunicipality)
                .where(ElectoralMunicipality.organization_id == org_id)
                .order_by(ElectoralMunicipality.code)
            )
        ).all()
        polling_places = (
            await session.scalars(
                select(ElectoralPollingPlace)
                .where(ElectoralPollingPlace.organization_id == org_id)
                .order_by(ElectoralPollingPlace.code)
            )
        ).all()

    states_by_region: dict[UUID, list[ElectoralState]] = {}
    for state in states:
        states_by_region.setdefault(state.region_id, []).append(state)

    muns_by_state: dict[UUID, list[ElectoralMunicipality]] = {}
    for mun in municipalities:
        muns_by_state.setdefault(mun.state_id, []).append(mun)

    mesas_by_mun: dict[UUID, list[ElectoralPollingPlace]] = {}
    for mesa in polling_places:
        mesas_by_mun.setdefault(mesa.municipality_id, []).append(mesa)

    regions_payload: list[dict[str, Any]] = []
    for region in regions:
        region_states: list[dict[str, Any]] = []
        for state in states_by_region.get(region.id, []):
            state_muns: list[dict[str, Any]] = []
            for mun in muns_by_state.get(state.id, []):
                state_muns.append(
                    {
                        "code": mun.code,
                        "name": mun.name,
                        "polling_places": [
                            {"code": mesa.code, "name": mesa.name}
                            for mesa in mesas_by_mun.get(mun.id, [])
                        ],
                    }
                )
            region_states.append(
                {
                    "code": state.code,
                    "name": state.name,
                    "municipalities": state_muns,
                }
            )
        regions_payload.append(
            {
                "code": region.code,
                "name": region.name,
                "states": region_states,
            }
        )

    return {
        "organization_slug": organization_slug,
        "regions": regions_payload,
    }


async def _run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Export territory hierarchy to JSON")
    parser.add_argument(
        "--org",
        default=settings.seed_admin_org_slug or os.environ.get("SEED_ADMIN_ORG_SLUG"),
        help="Organization slug (default: SEED_ADMIN_ORG_SLUG)",
    )
    parser.add_argument("--out", default=None, help="Output file (default: stdout)")
    args = parser.parse_args(argv)
    if not args.org:
        raise SystemExit("Pass --org or set SEED_ADMIN_ORG_SLUG")

    try:
        payload = await export_territory(args.org)
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"Wrote {args.out}", file=sys.stderr)
        else:
            sys.stdout.write(text)
    finally:
        await dispose_engine()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run(sys.argv[1:])))


if __name__ == "__main__":
    main()
