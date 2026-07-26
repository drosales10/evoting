"""Seed slates + candidates from export JSON.

  SEED_SLATES_FILE=slates-export.json python -m scripts.seed_slates

Requires members + elections(+positions) already seeded.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select

from app.db.session import dispose_engine, get_session_factory
from app.models import Candidate, Election, Position, Slate
from scripts.seed_ops_common import find_member, get_organization, resolve_org_slug


async def seed_slates(*, data_path: Path, organization_slug: str | None = None) -> str:
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or "elections" not in payload:
        raise RuntimeError(f"Invalid slates file: {data_path}")
    slug = organization_slug or payload.get("organization_slug") or resolve_org_slug()

    counts = {
        "slates_created": 0,
        "slates_updated": 0,
        "candidates_created": 0,
        "candidates_updated": 0,
        "candidates_skipped": 0,
    }

    factory = get_session_factory()
    async with factory() as session:
        org = await get_organization(session, slug)

        for block in payload["elections"]:
            election_title = str(block["election_title"]).strip()
            election = await session.scalar(
                select(Election).where(
                    Election.organization_id == org.id,
                    Election.title == election_title,
                )
            )
            if election is None:
                raise RuntimeError(
                    f"Election title={election_title!r} not found. Seed elections first."
                )

            positions_by_code = {
                p.code: p
                for p in (
                    await session.scalars(
                        select(Position).where(Position.election_id == election.id)
                    )
                ).all()
            }

            for raw in block.get("slates") or []:
                name = str(raw["name"]).strip()
                proxy = await find_member(
                    session,
                    org.id,
                    registry_code=raw.get("proxy_registry_code"),
                    dni=raw.get("proxy_dni"),
                    email=raw.get("proxy_email"),
                )
                slate = await session.scalar(
                    select(Slate).where(
                        Slate.election_id == election.id,
                        Slate.name == name,
                    )
                )
                slate_fields = {
                    "name": name,
                    "slogan": raw.get("slogan"),
                    "logo_url": raw.get("logo_url"),
                    "work_plan_pdf_url": raw.get("work_plan_pdf_url"),
                    "video_url": raw.get("video_url"),
                    "status": str(raw.get("status") or "PENDING"),
                    "proxy_member_id": proxy.id if proxy else None,
                    "validation_hash": None,
                }
                if slate is None:
                    slate = Slate(
                        id=uuid4(),
                        organization_id=org.id,
                        election_id=election.id,
                        **slate_fields,
                    )
                    session.add(slate)
                    await session.flush()
                    counts["slates_created"] += 1
                else:
                    for key, value in slate_fields.items():
                        setattr(slate, key, value)
                    counts["slates_updated"] += 1

                for cand_raw in raw.get("candidates") or []:
                    position_code = str(cand_raw["position_code"]).strip().upper()
                    position = positions_by_code.get(position_code)
                    member = await find_member(
                        session,
                        org.id,
                        registry_code=cand_raw.get("registry_code"),
                        dni=cand_raw.get("dni"),
                        email=cand_raw.get("email"),
                    )
                    if position is None or member is None:
                        counts["candidates_skipped"] += 1
                        continue
                    candidate = await session.scalar(
                        select(Candidate).where(
                            Candidate.slate_id == slate.id,
                            Candidate.position_id == position.id,
                        )
                    )
                    if candidate is None:
                        session.add(
                            Candidate(
                                id=uuid4(),
                                slate_id=slate.id,
                                position_id=position.id,
                                member_id=member.id,
                                bio=cand_raw.get("bio"),
                                photo_url=cand_raw.get("photo_url"),
                            )
                        )
                        counts["candidates_created"] += 1
                    else:
                        candidate.member_id = member.id
                        candidate.bio = cand_raw.get("bio")
                        candidate.photo_url = cand_raw.get("photo_url")
                        counts["candidates_updated"] += 1

        await session.commit()

    summary = ", ".join(f"{k}={v}" for k, v in counts.items())
    return f"organization={slug}; file={data_path}; {summary}"


async def _run() -> int:
    path = Path(os.environ.get("SEED_SLATES_FILE", ""))
    if not path.is_file():
        raise RuntimeError(
            "Set SEED_SLATES_FILE to an export from python -m scripts.export_slates"
        )
    try:
        print(await seed_slates(data_path=path))
    finally:
        await dispose_engine()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run()))


if __name__ == "__main__":
    main()
