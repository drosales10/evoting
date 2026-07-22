from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models import Election, ElectionTally
from app.repositories.elections import PublicElectionRepository
from app.services.tally_artifact import artifact_sha256, verify_artifact

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


class PublicTallyArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_version: Literal["pilot-tally-v1"]
    election_id: UUID
    public_key_sha256: str
    generated_at: datetime
    eligible_member_count: int
    voted_member_count: int
    quorum_threshold_pct: str
    quorum_required: int
    quorum_met: bool
    ballot_count: int
    receipt_hashes: list[str]
    counts: list[PublicTallyCount]


class PublicTallyVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_sha256_matches: bool
    signature_valid: bool


class PublicElectionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    election_id: UUID
    title: str
    voting_type: str
    ballot_count: int
    published_at: datetime
    artifact_sha256: str
    public_key_sha256: str
    artifact: PublicTallyArtifact
    signature: str
    public_key: str
    verification: PublicTallyVerification
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
    try:
        artifact_model = PublicTallyArtifact.model_validate(tally.artifact)
        stored_artifact_sha256 = artifact_sha256(tally.artifact)
        public_key = load_pem_public_key(election.public_key.encode("utf-8"))
    except (AttributeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Published election result verification is unavailable",
        ) from exc
    if not isinstance(public_key, RSAPublicKey):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Published election result verification is unavailable",
        )
    hash_matches = stored_artifact_sha256 == tally.artifact_sha256
    signature_valid = hash_matches and verify_artifact(tally.artifact, tally.signature, public_key)
    if not signature_valid or artifact_model.election_id != election.id:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Published election result verification failed",
        )
    return PublicElectionResult(
        election_id=election.id,
        title=election.title,
        voting_type=election.voting_type,
        ballot_count=tally.ballot_count,
        published_at=tally.created_at,
        artifact_sha256=tally.artifact_sha256,
        public_key_sha256=artifact_model.public_key_sha256,
        artifact=artifact_model,
        signature=tally.signature,
        public_key=election.public_key,
        verification=PublicTallyVerification(
            artifact_sha256_matches=hash_matches,
            signature_valid=signature_valid,
        ),
        counts=artifact_model.counts,
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
