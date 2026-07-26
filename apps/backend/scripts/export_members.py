"""Export members (padrón) to JSON — no photo blobs, no invented data.

  SEED_ADMIN_ORG_SLUG=sociedad-forestales-afines \\
    python -m scripts.export_members --out members-export.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.session import dispose_engine, get_session_factory
from app.models import (
    ElectoralMunicipality,
    ElectoralPollingPlace,
    ElectoralRegion,
    ElectoralState,
    Member,
)
from scripts.seed_ops_common import get_organization, json_safe, resolve_org_slug


async def export_members(organization_slug: str) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        org = await get_organization(session, organization_slug)
        members = (
            await session.scalars(
                select(Member)
                .where(Member.organization_id == org.id)
                .order_by(Member.registry_code.nulls_last(), Member.dni)
            )
        ).all()

        region_by_id = {
            r.id: r
            for r in (
                await session.scalars(
                    select(ElectoralRegion).where(
                        ElectoralRegion.organization_id == org.id
                    )
                )
            ).all()
        }
        state_by_id = {
            s.id: s
            for s in (
                await session.scalars(
                    select(ElectoralState).where(ElectoralState.organization_id == org.id)
                )
            ).all()
        }
        mun_by_id = {
            m.id: m
            for m in (
                await session.scalars(
                    select(ElectoralMunicipality).where(
                        ElectoralMunicipality.organization_id == org.id
                    )
                )
            ).all()
        }
        mesa_by_id = {
            p.id: p
            for p in (
                await session.scalars(
                    select(ElectoralPollingPlace).where(
                        ElectoralPollingPlace.organization_id == org.id
                    )
                )
            ).all()
        }

        rows = []
        for m in members:
            rows.append(
                {
                    "email": m.email,
                    "full_name": m.full_name,
                    "dni": m.dni,
                    "registry_code": m.registry_code,
                    "status": m.status,
                    "member_type": m.member_type,
                    "membership_months": m.membership_months,
                    "decade": m.decade,
                    "graduation_year": m.graduation_year,
                    "semester": m.semester,
                    "sex": m.sex,
                    "alive": m.alive,
                    "section": m.section,
                    "location": m.location,
                    "region": m.region,
                    "title": m.title,
                    "mention": m.mention,
                    "graduation_date": json_safe(m.graduation_date),
                    "region_code": region_by_id[m.region_id].code if m.region_id else None,
                    "state_code": state_by_id[m.state_id].code if m.state_id else None,
                    "municipality_code": (
                        mun_by_id[m.municipality_id].code if m.municipality_id else None
                    ),
                    "polling_place_code": (
                        mesa_by_id[m.polling_place_id].code if m.polling_place_id else None
                    ),
                }
            )

    return {"organization_slug": organization_slug, "members": rows}


async def _run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    slug = resolve_org_slug(args.org)
    try:
        payload = await export_members(slug)
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"Wrote {args.out} ({len(payload['members'])} members)", file=sys.stderr)
        else:
            sys.stdout.write(text)
    finally:
        await dispose_engine()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run(sys.argv[1:])))


if __name__ == "__main__":
    main()
