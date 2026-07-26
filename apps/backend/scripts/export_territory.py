"""Export territorial hierarchy N1–N5 including GeoJSON geometries.

  python -m scripts.export_territory --org sociedad-forestales-afines \\
    --out territory-geo-export.json

Use --compact for a smaller file (no pretty-print).
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


def _unit(code: str, name: str, geojson: dict[str, Any] | None, **extra: Any) -> dict[str, Any]:
    row: dict[str, Any] = {"code": code, "name": name, "geojson": geojson}
    row.update(extra)
    return row


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
        org_geojson = organization.geojson

    states_by_region: dict[UUID, list[ElectoralState]] = {}
    for state in states:
        states_by_region.setdefault(state.region_id, []).append(state)

    muns_by_state: dict[UUID, list[ElectoralMunicipality]] = {}
    for mun in municipalities:
        muns_by_state.setdefault(mun.state_id, []).append(mun)

    mesas_by_mun: dict[UUID, list[ElectoralPollingPlace]] = {}
    for mesa in polling_places:
        mesas_by_mun.setdefault(mesa.municipality_id, []).append(mesa)

    with_geo = {
        "organization": 1 if org_geojson else 0,
        "regions": sum(1 for r in regions if r.geojson),
        "states": sum(1 for s in states if s.geojson),
        "municipalities": sum(1 for m in municipalities if m.geojson),
        "polling_places": sum(1 for p in polling_places if p.geojson),
    }

    regions_payload: list[dict[str, Any]] = []
    for region in regions:
        region_states: list[dict[str, Any]] = []
        for state in states_by_region.get(region.id, []):
            state_muns: list[dict[str, Any]] = []
            for mun in muns_by_state.get(state.id, []):
                state_muns.append(
                    _unit(
                        mun.code,
                        mun.name,
                        mun.geojson,
                        polling_places=[
                            _unit(mesa.code, mesa.name, mesa.geojson)
                            for mesa in mesas_by_mun.get(mun.id, [])
                        ],
                    )
                )
            region_states.append(
                _unit(state.code, state.name, state.geojson, municipalities=state_muns)
            )
        regions_payload.append(
            _unit(region.code, region.name, region.geojson, states=region_states)
        )

    return {
        "organization_slug": organization_slug,
        "organization_geojson": org_geojson,
        "regions": regions_payload,
        "_meta": {
            "units_with_geojson": with_geo,
            "note": "Geometries live in geojson JSONB (N1–N5). PostGIS geom is not used by the app.",
        },
    }


async def _run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Export territory + GeoJSON")
    parser.add_argument(
        "--org",
        default=settings.seed_admin_org_slug or os.environ.get("SEED_ADMIN_ORG_SLUG"),
    )
    parser.add_argument("--out", default=None)
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Minified JSON (smaller upload)",
    )
    args = parser.parse_args(argv)
    if not args.org:
        raise SystemExit("Pass --org or set SEED_ADMIN_ORG_SLUG")

    try:
        payload = await export_territory(args.org)
        meta = payload.get("_meta", {})
        if args.compact:
            text = json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + "\n"
        else:
            text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            size_mb = Path(args.out).stat().st_size / (1024 * 1024)
            print(
                f"Wrote {args.out} ({size_mb:.2f} MiB) geojson={meta.get('units_with_geojson')}",
                file=sys.stderr,
            )
        else:
            sys.stdout.write(text)
    finally:
        await dispose_engine()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run(sys.argv[1:])))


if __name__ == "__main__":
    main()
