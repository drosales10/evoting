"""Unlock elections stuck in FREEZE/ACTIVE/CLOSED/TALLIED back to REGISTRATION.

Also resets slates to PENDING and clears vote flags (does not delete padrón/planchas).
Optionally purges ballots/tallies/issuance tokens for a clean re-run.

  SEED_ADMIN_ORG_SLUG=sociedad-forestales-afines \\
    python -m scripts.unlock_elections

  # Solo una elección por título:
  python -m scripts.unlock_elections --title "Nombre de la elección"

  # Conservar boletas/tallies (solo cambia status):
  python -m scripts.unlock_elections --keep-ballots
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import delete, select, update

from app.db.session import dispose_engine, get_session_factory
from app.models import (
    BallotIssuanceToken,
    Election,
    ElectionTally,
    ElectionTallyProposal,
    EncryptedBallot,
    MemberElectionStatus,
    Slate,
)
from scripts.seed_ops_common import get_organization, resolve_org_slug

UNLOCK_FROM = {"FREEZE", "ACTIVE", "CLOSED", "TALLIED"}
TARGET_STATUS = "REGISTRATION"


async def unlock_elections(
    *,
    organization_slug: str,
    election_title: str | None = None,
    purge_runtime: bool = True,
) -> str:
    factory = get_session_factory()
    async with factory() as session:
        org = await get_organization(session, organization_slug)
        stmt = select(Election).where(Election.organization_id == org.id)
        if election_title:
            stmt = stmt.where(Election.title == election_title)
        elections = (await session.scalars(stmt)).all()
        if not elections:
            raise RuntimeError("No elections found for that organization/title")

        unlocked = 0
        slates_reset = 0
        eligibility_reset = 0
        purged = {"ballots": 0, "tokens": 0, "tallies": 0, "proposals": 0}

        for election in elections:
            if election.status in UNLOCK_FROM or election.status == TARGET_STATUS:
                election.status = TARGET_STATUS
                election.frozen_at = None
                election.activated_at = None
                # Force a fresh key ceremony on next activate
                election.public_key = None
                election.signing_public_key = None
                unlocked += 1

            slate_result = await session.execute(
                update(Slate)
                .where(Slate.election_id == election.id)
                .values(status="PENDING", validation_hash=None)
            )
            slates_reset += slate_result.rowcount or 0

            mes_result = await session.execute(
                update(MemberElectionStatus)
                .where(MemberElectionStatus.election_id == election.id)
                .values(has_voted=False, voted_at=None)
            )
            eligibility_reset += mes_result.rowcount or 0

            if purge_runtime:
                r = await session.execute(
                    delete(EncryptedBallot).where(EncryptedBallot.election_id == election.id)
                )
                purged["ballots"] += r.rowcount or 0
                r = await session.execute(
                    delete(BallotIssuanceToken).where(
                        BallotIssuanceToken.election_id == election.id
                    )
                )
                purged["tokens"] += r.rowcount or 0
                r = await session.execute(
                    delete(ElectionTallyProposal).where(
                        ElectionTallyProposal.election_id == election.id
                    )
                )
                purged["proposals"] += r.rowcount or 0
                r = await session.execute(
                    delete(ElectionTally).where(ElectionTally.election_id == election.id)
                )
                purged["tallies"] += r.rowcount or 0

        await session.commit()

    return (
        f"organization={organization_slug}; unlocked_elections={unlocked}; "
        f"target={TARGET_STATUS}; slates_reset={slates_reset}; "
        f"eligibility_vote_flags_cleared={eligibility_reset}; "
        f"purged={purged}"
    )


async def _run(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--org", default=None)
    parser.add_argument("--title", default=None, help="Unlock a single election by title")
    parser.add_argument(
        "--keep-ballots",
        action="store_true",
        help="Do not delete ballots/tallies/issuance tokens",
    )
    args = parser.parse_args(argv)
    slug = resolve_org_slug(args.org)
    try:
        print(
            await unlock_elections(
                organization_slug=slug,
                election_title=args.title,
                purge_runtime=not args.keep_ballots,
            )
        )
    finally:
        await dispose_engine()
    return 0


def main() -> None:
    raise SystemExit(asyncio.run(_run(sys.argv[1:])))


if __name__ == "__main__":
    main()
