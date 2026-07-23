from datetime import datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models import Election, ElectionBroadcast, ElectionTally
from app.repositories.elections import PublicElectionRepository
from app.services.tally_artifact import artifact_sha256, verify_artifact
from app.services.youtube import youtube_embed_url

router = APIRouter(prefix="/public", tags=["public"])


class PublicElection(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    voting_type: str
    start_time: datetime
    end_time: datetime
    status: str
    broadcast_status: str | None = None
    has_live: bool = False


class PublicBroadcastMilestone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    label: str
    at: datetime
    note: str | None = None


class PublicBroadcastResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    election_id: UUID
    title: str
    description: str | None
    status: str
    youtube_url: str
    embed_url: str
    scheduled_start_at: datetime | None
    went_live_at: datetime | None
    ended_at: datetime | None
    artifact_sha256: str | None
    verify_path: str | None
    milestones: list[PublicBroadcastMilestone]


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
    quorum_threshold_pct: str | float
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


class PublicVerifyResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_hash: str
    election_id: UUID
    title: str
    verification: PublicTallyVerification
    ballot_count: int
    quorum_met: bool
    counts: list[PublicTallyCount]
    public_key: str
    signature: str
    artifact: dict[str, Any]
    download_path: str


def _signing_or_public_pem(election: Election) -> str:
    return election.signing_public_key or election.public_key or ""


async def _load_official_tally(
    session: AsyncSession,
    *,
    election_id: UUID | None = None,
    artifact_hash: str | None = None,
) -> tuple[Election, ElectionTally]:
    statement = (
        select(Election, ElectionTally)
        .join(ElectionTally, ElectionTally.election_id == Election.id)
        .where(
            Election.status == "TALLIED",
            ElectionTally.quorum_met.is_(True),
            ElectionTally.pilot_override.is_(False),
        )
    )
    if election_id is not None:
        statement = statement.where(Election.id == election_id)
    if artifact_hash is not None:
        statement = statement.where(ElectionTally.artifact_sha256 == artifact_hash.lower())
    result = (await session.execute(statement)).one_or_none()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published election results not found",
        )
    return result


def _verify_tally(election: Election, tally: ElectionTally) -> tuple[PublicTallyArtifact, bool, bool]:
    artifact_model = PublicTallyArtifact.model_validate(tally.artifact)
    stored_artifact_sha256 = artifact_sha256(tally.artifact)
    pem = _signing_or_public_pem(election)
    public_key = load_pem_public_key(pem.encode("utf-8"))
    if not isinstance(public_key, RSAPublicKey):
        raise ValueError("not rsa")
    hash_matches = stored_artifact_sha256 == tally.artifact_sha256
    signature_valid = hash_matches and verify_artifact(tally.artifact, tally.signature, public_key)
    if not signature_valid or artifact_model.election_id != election.id:
        raise ValueError("verification failed")
    return artifact_model, hash_matches, signature_valid


@router.get("/elections/{election_id}/results", response_model=PublicElectionResult)
async def get_public_election_results(
    election_id: UUID,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PublicElectionResult:
    """Return only quorum-compliant, non-pilot aggregated results."""
    response.headers["Cache-Control"] = "no-store"
    election, tally = await _load_official_tally(session, election_id=election_id)
    try:
        artifact_model, hash_matches, signature_valid = _verify_tally(election, tally)
    except (AttributeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Published election result verification failed",
        ) from exc
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
        public_key=_signing_or_public_pem(election),
        verification=PublicTallyVerification(
            artifact_sha256_matches=hash_matches,
            signature_valid=signature_valid,
        ),
        counts=artifact_model.counts,
    )


@router.get("/verify/{artifact_hash}", response_model=PublicVerifyResponse)
async def verify_public_artifact(
    artifact_hash: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PublicVerifyResponse:
    """Independent verification surface keyed by artifact SHA-256."""
    response.headers["Cache-Control"] = "no-store"
    if len(artifact_hash) != 64:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid hash")
    election, tally = await _load_official_tally(session, artifact_hash=artifact_hash)
    try:
        artifact_model, hash_matches, signature_valid = _verify_tally(election, tally)
    except (AttributeError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Artifact verification failed",
        ) from exc
    return PublicVerifyResponse(
        artifact_hash=tally.artifact_sha256,
        election_id=election.id,
        title=election.title,
        verification=PublicTallyVerification(
            artifact_sha256_matches=hash_matches,
            signature_valid=signature_valid,
        ),
        ballot_count=tally.ballot_count,
        quorum_met=tally.quorum_met,
        counts=artifact_model.counts,
        public_key=_signing_or_public_pem(election),
        signature=tally.signature,
        artifact=tally.artifact,
        download_path=f"/api/v1/public/verify/{tally.artifact_sha256}/artifact",
    )


@router.get("/verify/{artifact_hash}/artifact")
async def download_public_artifact(
    artifact_hash: str,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JSONResponse:
    """Download the signed artifact JSON for offline verification."""
    response.headers["Cache-Control"] = "no-store"
    election, tally = await _load_official_tally(session, artifact_hash=artifact_hash)
    _verify_tally(election, tally)
    return JSONResponse(
        content={
            "artifact": tally.artifact,
            "signature": tally.signature,
            "artifact_sha256": tally.artifact_sha256,
            "public_key": _signing_or_public_pem(election),
            "acta": tally.acta,
        },
        headers={
            "Content-Disposition": f'attachment; filename="tally-{artifact_hash[:16]}.json"',
        },
    )


@router.get("/elections", response_model=list[PublicElection])
async def list_public_elections(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PublicElection]:
    """Return only elections approved for public publication."""
    response.headers["Cache-Control"] = "no-store"
    repository = PublicElectionRepository()

    try:
        elections = await repository.fetch_published(session)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public election data is temporarily unavailable",
        ) from exc

    election_ids = [election.id for election in elections]
    broadcasts: dict[UUID, ElectionBroadcast] = {}
    if election_ids:
        rows = (
            await session.scalars(
                select(ElectionBroadcast).where(ElectionBroadcast.election_id.in_(election_ids))
            )
        ).all()
        broadcasts = {row.election_id: row for row in rows}

    items: list[PublicElection] = []
    for election in elections:
        broadcast = broadcasts.get(election.id)
        base = PublicElection.model_validate(election)
        if broadcast is None:
            items.append(base)
            continue
        items.append(
            base.model_copy(
                update={
                    "broadcast_status": broadcast.status,
                    "has_live": broadcast.status == "LIVE",
                }
            )
        )
    return items


@router.get("/elections/{election_id}/broadcast", response_model=PublicBroadcastResponse)
async def get_public_election_broadcast(
    election_id: UUID,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PublicBroadcastResponse:
    """Return ceremony broadcast metadata for the public portal."""
    response.headers["Cache-Control"] = "no-store"
    election = await session.scalar(select(Election).where(Election.id == election_id))
    if election is None or election.status not in {
        "REGISTRATION",
        "FREEZE",
        "ACTIVE",
        "CLOSED",
        "TALLIED",
    }:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Election not found")
    row = await session.scalar(
        select(ElectionBroadcast).where(ElectionBroadcast.election_id == election_id)
    )
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broadcast not found")

    milestones: list[PublicBroadcastMilestone] = []
    raw = row.milestones if isinstance(row.milestones, list) else []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            milestones.append(PublicBroadcastMilestone.model_validate(entry))
        except Exception:
            continue

    return PublicBroadcastResponse(
        election_id=election_id,
        title=row.title,
        description=row.description,
        status=row.status,
        youtube_url=row.youtube_url,
        embed_url=youtube_embed_url(row.youtube_video_id),
        scheduled_start_at=row.scheduled_start_at,
        went_live_at=row.went_live_at,
        ended_at=row.ended_at,
        artifact_sha256=row.artifact_sha256,
        verify_path=(
            f"/verify/{row.artifact_sha256}" if row.artifact_sha256 else None
        ),
        milestones=milestones,
    )


@router.get("/geo/territory/{election_id}")
async def public_geo_territory(
    election_id: UUID,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    levels: str = "N1,N2,N3,N4,N5",
) -> dict:
    """FeatureCollection territorial (sin PII) para una elección publicada."""
    response.headers["Cache-Control"] = "no-store"
    from app.services.geo_features import build_admin_feature_collection

    election = await session.scalar(select(Election).where(Election.id == election_id))
    if election is None or election.status not in {
        "ACTIVE",
        "CLOSED",
        "TALLIED",
        "FREEZE",
        "REGISTRATION",
    }:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Published election territory not found",
        )
    level_set = {part.strip().upper() for part in levels.split(",") if part.strip()}
    return await build_admin_feature_collection(
        session, election.organization_id, level_set or {"N2", "N3"}
    )


@router.get("/geo/results/{election_id}")
async def public_geo_results(
    election_id: UUID,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict:
    """FeatureCollection of territorial participation for official tallied elections."""
    response.headers["Cache-Control"] = "no-store"
    from app.services.geo_features import build_public_results_collection

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
    election, _tally = result
    return await build_public_results_collection(session, election)
