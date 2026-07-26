"""Seed elections + positions + eligibility from export JSON.

  SEED_ELECTIONS_FILE=elections-export.json python -m scripts.seed_elections

Idempotent by election title within the organization.
Does not copy votes (has_voted forced false).
"""

from __future__ import annotations

import asyncio
import json
import os
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from app.db.session import dispose_engine, get_session_factory
from app.models import Election, MemberElectionStatus, Position
from scripts.seed_ops_common import (
    find_member,
    get_organization,
    parse_datetime,
    resolve_org_slug,
    territory_code_maps,
)


async def seed_elections(*, data_path: Path, organization_slug: str | None = None) -> str:
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "elections" not in payload:
        raise RuntimeError(f"Invalid elections file: {data_path}")
    slug = organization_slug or payload.get("organization_slug") or resolve_org_slug()

    counts = {
        "elections_created": 0,
        "elections_updated": 0,
        "positions_created": 0,
        "positions_updated": 0,
        "eligibility_upserted": 0,
        "eligibility_skipped": 0,
    }

    factory = get_session_factory()
    async with factory() as session:
        org = await get_organization(session, slug)
        regions, states, _muns, _mesas = await territory_code_maps(session, org.id)

        for raw in payload["elections"]:
            title = str(raw["title"]).strip()
            election = await session.scalar(
                select(Election).where(
                    Election.organization_id == org.id,
                    Election.title == title,
                )
            )
            region_code = raw.get("region_code")
            state_code = raw.get("state_code")
            region_id = (
                regions[region_code].id if region_code and region_code in regions else None
            )
            state_id = states[state_code].id if state_code and state_code in states else None

            fields = {
                "title": title,
                "voting_type": str(raw.get("voting_type") or "SLATE_PLURALITY"),
                "start_time": parse_datetime(raw["start_time"]),
                "end_time": parse_datetime(raw["end_time"]),
                "quorum_threshold_pct": Decimal(str(raw.get("quorum_threshold_pct") or "30")),
                "status": str(raw.get("status") or "DRAFT"),
                "scope_level": str(raw.get("scope_level") or "NATIONAL"),
                "region_id": region_id,
                "state_id": state_id,
                "public_key": raw.get("public_key"),
                "signing_public_key": raw.get("signing_public_key"),
                "frozen_at": (
                    parse_datetime(raw["frozen_at"]) if raw.get("frozen_at") else None
                ),
                "activated_at": (
                    parse_datetime(raw["activated_at"]) if raw.get("activated_at") else None
                ),
            }

            if election is None:
                election = Election(id=uuid4(), organization_id=org.id, **fields)
                session.add(election)
                await session.flush()
                counts["elections_created"] += 1
            else:
                for key, value in fields.items():
                    setattr(election, key, value)
                counts["elections_updated"] += 1

            for pos_raw in raw.get("positions") or []:
                code = str(pos_raw["code"]).strip().upper()
                position = await session.scalar(
                    select(Position).where(
                        Position.election_id == election.id,
                        Position.code == code,
                    )
                )
                pos_fields = {
                    "title": str(pos_raw["title"]).strip(),
                    "code": code,
                    "is_required": bool(pos_raw.get("is_required", True)),
                    "display_order": int(pos_raw.get("display_order") or 0),
                }
                if position is None:
                    session.add(Position(id=uuid4(), election_id=election.id, **pos_fields))
                    counts["positions_created"] += 1
                else:
                    for key, value in pos_fields.items():
                        setattr(position, key, value)
                    counts["positions_updated"] += 1

            for elig in raw.get("eligibility") or []:
                member = await find_member(
                    session,
                    org.id,
                    registry_code=elig.get("registry_code"),
                    dni=elig.get("dni"),
                    email=elig.get("email"),
                )
                if member is None:
                    counts["eligibility_skipped"] += 1
                    continue
                row = await session.scalar(
                    select(MemberElectionStatus).where(
                        MemberElectionStatus.election_id == election.id,
                        MemberElectionStatus.member_id == member.id,
                    )
                )
                if row is None:
                    session.add(
                        MemberElectionStatus(
                            id=uuid4(),
                            organization_id=org.id,
                            election_id=election.id,
                            member_id=member.id,
                            eligible=bool(elig.get("eligible", False)),
                            eligibility_reason=elig.get("eligibility_reason"),
                            has_voted=False,
                            voted_at=None,
                        )
                    )
                else:
                    row.eligible = bool(elig.get("eligible", False))
                    row.eligibility_reason = elig.get("eligibility_reason")
                    row.has_voted = False
                    row.voted_at = None
                counts["eligibility_upserted"] += 1

        await session.commit()

    summary = ", ".join(f"{k}={v}" for k, v in counts.items())
    return f"organization={slug}; file={data_path}; {summary}"


async def _run() -> int:
    path = Path(os.environ.get("SEED_ELECTIONS_FILE", ""))
    if not path.is_file():
        raise RuntimeError(
            "Set SEED_ELECTIONS_FILE to an export from python -m scripts.export_elections"
        )
    try:
        print(await seed_elections(data_path=path))
    finally:
        await dispose_engine()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
