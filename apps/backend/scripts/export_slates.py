"""Export slates + candidates (references members/positions by codes).

  python -m scripts.export_slates --out slates-export.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.db.session import dispose_engine, get_session_factory
from app.models import Candidate, Election, Member, Position, Slate
from scripts.seed_ops_common import get_organization, resolve_org_slug


async def export_slates(organization_slug: str) -> dict:
    factory = get_session_factory()
    async with factory() as session:
        org = await get_organization(session, organization_slug)
        elections = (
            await session.scalars(
                select(Election).where(Election.organization_id == org.id)
            )
        ).all()
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
            positions_by_id = {
                p.id: p
                for p in (
                    await session.scalars(
                        select(Position).where(Position.election_id == election.id)
                    )
                ).all()
            }
            slates = (
                await session.scalars(
                    select(Slate)
                    .where(Slate.election_id == election.id)
                    .order_by(Slate.name)
                )
            ).all()
            slate_rows = []
            for slate in slates:
                proxy = members_by_id.get(slate.proxy_member_id) if slate.proxy_member_id else None
                candidates = (
                    await session.scalars(
                        select(Candidate).where(Candidate.slate_id == slate.id)
                    )
                ).all()
                cand_rows = []
                for cand in candidates:
                    member = members_by_id.get(cand.member_id)
                    position = positions_by_id.get(cand.position_id)
                    if member is None or position is None:
                        continue
                    cand_rows.append(
                        {
                            "position_code": position.code,
                            "registry_code": member.registry_code,
                            "dni": member.dni,
                            "email": member.email,
                            "bio": cand.bio,
                            "photo_url": cand.photo_url,
                        }
                    )
                slate_rows.append(
                    {
                        "name": slate.name,
                        "slogan": slate.slogan,
                        "logo_url": slate.logo_url,
                        "work_plan_pdf_url": slate.work_plan_pdf_url,
                        "video_url": slate.video_url,
                        "status": slate.status,
                        "proxy_registry_code": proxy.registry_code if proxy else None,
                        "proxy_dni": proxy.dni if proxy else None,
                        "proxy_email": proxy.email if proxy else None,
                        "candidates": cand_rows,
                    }
                )
            if slate_rows:
                out_elections.append(
                    {
                        "election_title": election.title,
                        "slates": slate_rows,
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
        payload = await export_slates(slug)
        n = sum(len(e["slates"]) for e in payload["elections"])
        text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"Wrote {args.out} ({n} slates)", file=sys.stderr)
        else:
            sys.stdout.write(text)
    finally:
        await dispose_engine()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run(sys.argv[1:])))


if __name__ == "__main__":
    main()
