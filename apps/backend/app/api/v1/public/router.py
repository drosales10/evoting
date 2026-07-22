from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models import Election, ElectionTally
from app.repositories.elections import PublicElectionRepository

router = APIRouter(prefix="/public", tags=["public"])


class PublicElection(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    voting_type: str
    start_time: datetime
    end_time: datetime
    status: str


class PublicTallyCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slate_id: UUID
    slate_name: str
    votes: int


class PublicElectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    election_id: UUID
    title: str
    voting_type: str
    ballot_count: int
    published_at: datetime
    counts: list[PublicTallyCount]


@router.get("/elections/{election_id}/results", response_model=PublicElectionResult)
async def get_public_election_results(
    election_id: UUID,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PublicElectionResult:
    """Return only quorum-compliant, non-pilot aggregated results."""
    response.headers["Cache-Control"] = "no-store"
    row = await session.execute(
        select(Election, ElectionTally)
        .join(ElectionTally, ElectionTally.election_id == Election.id)
        .where(
            Election.id == election_id,
            Election.status == "TALLIED",
            ElectionTally.quorum_met.is_(True),
            ElectionTally.pilot_override.is_(False),
        )
    )
    result = row.one_or_none()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published election results not found",
        )
    election, tally = result
    artifact_counts = tally.artifact.get("counts", [])
    return PublicElectionResult(
        election_id=election.id,
        title=election.title,
        voting_type=election.voting_type,
        ballot_count=tally.ballot_count,
        published_at=tally.created_at,
        counts=[PublicTallyCount.model_validate(count) for count in artifact_counts],
    )


@router.get("/elections", response_model=list[PublicElection])
async def list_public_elections(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PublicElection]:
    """Return only elections approved for public publication.

    This endpoint is intentionally read-only. It returns a controlled projection and never
    exposes roster, participation or ballot data.
    """
    response.headers["Cache-Control"] = "no-store"
    repository = PublicElectionRepository()

    try:
        elections = await repository.fetch_published(session)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public election data is temporarily unavailable",
        ) from exc

    return [PublicElection.model_validate(election) for election in elections]
