"""Seed members from an exported JSON (idempotent by registry_code → dni → email).

  SEED_MEMBERS_FILE=members-export.json python -m scripts.seed_members
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.db.session import dispose_engine, get_session_factory
from app.models import Member
from scripts.seed_ops_common import (
    find_member,
    get_organization,
    parse_date,
    resolve_org_slug,
    territory_code_maps,
)


async def seed_members(*, data_path: Path, organization_slug: str | None = None) -> str:
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "members" not in payload:
        raise RuntimeError(f"Invalid members file: {data_path}")
    slug = organization_slug or payload.get("organization_slug") or resolve_org_slug()
    members_raw: list[dict[str, Any]] = payload["members"]

    created = updated = 0
    factory = get_session_factory()
    async with factory() as session:
        org = await get_organization(session, slug)
        regions, states, muns, mesas = await territory_code_maps(session, org.id)

        for raw in members_raw:
            email = str(raw["email"]).strip().lower()
            dni = str(raw["dni"]).strip()
            registry_code = (
                str(raw["registry_code"]).strip() if raw.get("registry_code") else None
            )
            member = await find_member(
                session,
                org.id,
                registry_code=registry_code,
                dni=dni,
                email=email,
            )

            region_code = raw.get("region_code")
            state_code = raw.get("state_code")
            mun_code = raw.get("municipality_code")
            mesa_code = raw.get("polling_place_code")
            region_id = regions[region_code].id if region_code and region_code in regions else None
            state_id = states[state_code].id if state_code and state_code in states else None
            mun_id = muns[mun_code].id if mun_code and mun_code in muns else None
            mesa_id = mesas[mesa_code].id if mesa_code and mesa_code in mesas else None

            fields = {
                "email": email,
                "full_name": str(raw["full_name"]).strip(),
                "dni": dni,
                "registry_code": registry_code,
                "status": str(raw.get("status") or "ACTIVE").strip(),
                "member_type": raw.get("member_type"),
                "membership_months": int(raw.get("membership_months") or 0),
                "decade": raw.get("decade"),
                "graduation_year": raw.get("graduation_year"),
                "semester": raw.get("semester"),
                "sex": raw.get("sex"),
                "alive": raw.get("alive"),
                "section": raw.get("section"),
                "location": raw.get("location"),
                "region": raw.get("region"),
                "title": raw.get("title"),
                "mention": raw.get("mention"),
                "graduation_date": parse_date(raw.get("graduation_date")),
                "region_id": region_id,
                "state_id": state_id,
                "municipality_id": mun_id,
                "polling_place_id": mesa_id,
            }

            if member is None:
                session.add(Member(id=uuid4(), organization_id=org.id, **fields))
                created += 1
            else:
                for key, value in fields.items():
                    setattr(member, key, value)
                updated += 1

        await session.commit()

    return (
        f"organization={slug}; file={data_path}; "
        f"members_created={created}; members_updated={updated}; total={len(members_raw)}"
    )


async def _run() -> int:
    path = Path(os.environ.get("SEED_MEMBERS_FILE", ""))
    if not path.is_file():
        raise RuntimeError(
            "Set SEED_MEMBERS_FILE to an export from python -m scripts.export_members"
        )
    try:
        print(await seed_members(data_path=path))
    finally:
        await dispose_engine()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
