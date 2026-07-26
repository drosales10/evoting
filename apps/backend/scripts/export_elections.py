"""Export elections + positions + eligibility snapshot (no ballots/tallies).

  python -m scripts.export_elections --out elections-export.json
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
    Election,
    ElectoralRegion,
    ElectoralState,
    Member,
    MemberElectionStatus,
    Position,
)
from scripts.seed_ops_common import get_organization, json_safe, resolve_org_slug


async def export_elections(organization_slug: str) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        org = await get_organization(session, organization_slug)
        elections = (
            await session.scalars(
                select(Election)
                .where(Election.organization_id == org.id)
                .order_by(Election.created_at)
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
        members_by_id = {
            m.id: m
            for m in (
                await session.scalars(
                    select(Member).where(Member.organization_id == org.id)
                )
            ).all()
        }

        out_elections = []
        for election in elections:
            positions = (
                await session.scalars(
                    select(Position)
                    .where(Position.election_id == election.id)
                    .order_by(Position.display_order, Position.code)
                )
            ).all()
            statuses = (
                await session.scalars(
                    select(MemberElectionStatus).where(
                        MemberElectionStatus.election_id == election.id
                    )
                )
            ).all()

            eligibility = []
            for row in statuses:
                member = members_by_id.get(row.member_id)
                if member is None:
                    continue
                eligibility.append(
                    {
                        "registry_code": member.registry_code,
                        "dni": member.dni,
                        "email": member.email,
                        "eligible": row.eligible,
                        "eligibility_reason": row.eligibility_reason,
                        # Always false on seed target — no votes copied
                        "has_voted": False,
                    }
                )

            out_elections.append(
                {
                    "title": election.title,
                    "voting_type": election.voting_type,
                    "start_time": json_safe(election.start_time),
                    "end_time": json_safe(election.end_time),
                    "quorum_threshold_pct": json_safe(election.quorum_threshold_pct),
                    "status": election.status,
                    "scope_level": election.scope_level,
                    "region_code": (
                        region_by_id[election.region_id].code
                        if election.region_id
                        else None
                    ),
                    "state_code": (
                        state_by_id[election.state_id].code if election.state_id else None
                    ),
                    "public_key": election.public_key,
                    "signing_public_key": election.signing_public_key,
                    "frozen_at": json_safe(election.frozen_at),
                    "activated_at": json_safe(election.activated_at),
                    "positions": [
                        {
                            "code": p.code,
                            "title": p.title,
                            "is_required": p.is_required,
                            "display_order": p.display_order,
                        }
                        for p in positions
                    ],
                    "eligibility": eligibility,
                }
            )

    return {"organization_slug": organization_slug, "elections": out_elections}


async def _run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)
    slug = resolve_org_slug(args.org)
    try:
        payload = await export_elections(slug)
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(
                f"Wrote {args.out} ({len(payload['elections'])} elections)",
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
