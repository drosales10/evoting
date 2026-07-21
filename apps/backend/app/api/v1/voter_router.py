import hashlib
import hmac
from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_voter
from app.auth.tokens import AccessClaims
from app.core.config import settings
from app.db.session import get_db_session
from app.models import (
    AuthSession,
    Candidate,
    Election,
    EncryptedBallot,
    Member,
    MemberElectionStatus,
    Position,
    Slate,
)

router = APIRouter(prefix="/voter", tags=["voter"])


class VoterPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    code: str
    title: str
    is_required: bool
    display_order: int


class VoterCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    position_id: UUID
    position_code: str
    position_title: str
    member_full_name: str


class VoterSlateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    name: str
    slogan: str | None
    candidates: list[VoterCandidateResponse]


class VoterElectionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    election_id: UUID
    title: str
    status: str
    start_time: datetime
    end_time: datetime
    public_key: str
    key_version: str
    has_voted: bool
    positions: list[VoterPositionResponse]
    slates: list[VoterSlateResponse]


class VoterBallotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encrypted_payload: str = Field(min_length=32, max_length=1_048_576)
    receipt_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    zkp_proof: str = Field(min_length=16, max_length=65_536)
    key_version: str = Field(default="v1", min_length=1, max_length=50)


class VoterBallotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    receipt_hash: str
    ballot_id: UUID
    recorded_at: datetime


async def _get_active_election(
    session: AsyncSession,
    election_id: UUID,
    claims: AccessClaims,
) -> Election:
    election = await session.scalar(
        select(Election).where(
            Election.id == election_id,
            Election.organization_id == claims.org_id,
        )
    )
    if election is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Election not found")
    now = datetime.now(UTC)
    if election.status != "ACTIVE" or election.start_time > now or election.end_time <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Election is not accepting votes",
        )
    if not election.public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Election public key is not configured",
        )
    return election


async def _require_voter_csrf(
    session: AsyncSession,
    claims: AccessClaims,
    csrf_token: str | None,
) -> None:
    if not csrf_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token required",
        )
    auth_session = await session.scalar(
        select(AuthSession).where(
            AuthSession.id == claims.session_id,
            AuthSession.organization_id == claims.org_id,
            AuthSession.principal_id == claims.sub,
            AuthSession.realm == "VOTER",
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > datetime.now(UTC),
        )
    )
    if auth_session is None or not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Voter session is not active",
        )
    expected = hashlib.sha256(f"{settings.jwt_secret}:{csrf_token}".encode()).hexdigest()
    if not hmac.compare_digest(expected, auth_session.csrf_token_hash):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid CSRF token",
        )


@router.get(
    "/elections/{election_id}",
    response_model=VoterElectionResponse,
)
async def get_voter_election(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(require_voter)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> VoterElectionResponse:
    """Return the public ballot contract for the authenticated eligible voter."""
    response.headers["Cache-Control"] = "no-store"
    election = await _get_active_election(session, election_id, claims)
    eligibility = await session.scalar(
        select(MemberElectionStatus).where(
            MemberElectionStatus.election_id == election.id,
            MemberElectionStatus.organization_id == claims.org_id,
            MemberElectionStatus.member_id == claims.sub,
        )
    )
    if eligibility is None or not eligibility.eligible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voter is not eligible for this election",
        )

    positions = list(
        (
            await session.scalars(
                select(Position)
                .where(Position.election_id == election.id)
                .order_by(Position.display_order.asc(), Position.created_at.asc())
            )
        ).all()
    )
    slates = list(
        (
            await session.scalars(
                select(Slate)
                .where(
                    Slate.organization_id == claims.org_id,
                    Slate.election_id == election.id,
                )
                .order_by(Slate.created_at.asc())
            )
        ).all()
    )
    candidate_rows = (
        (
            await session.execute(
                select(Candidate, Position, Member)
                .join(Position, Position.id == Candidate.position_id)
                .join(Member, Member.id == Candidate.member_id)
                .where(
                    Candidate.slate_id.in_([slate.id for slate in slates]),
                    Position.election_id == election.id,
                    Member.organization_id == claims.org_id,
                )
                .order_by(Position.display_order.asc(), Candidate.created_at.asc())
            )
        ).all()
        if slates
        else []
    )
    candidates_by_slate: dict[UUID, list[VoterCandidateResponse]] = {
        slate.id: [] for slate in slates
    }
    for candidate, position, member in candidate_rows:
        candidates_by_slate[candidate.slate_id].append(
            VoterCandidateResponse(
                id=candidate.id,
                position_id=position.id,
                position_code=position.code,
                position_title=position.title,
                member_full_name=member.full_name,
            )
        )
    public_key = election.public_key
    if not public_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Election public key is not configured",
        )
    return VoterElectionResponse(
        election_id=election.id,
        title=election.title,
        status=election.status,
        start_time=election.start_time,
        end_time=election.end_time,
        public_key=public_key,
        key_version="v1",
        has_voted=eligibility.has_voted,
        positions=[VoterPositionResponse.model_validate(position) for position in positions],
        slates=[
            VoterSlateResponse(
                id=slate.id,
                name=slate.name,
                slogan=slate.slogan,
                candidates=candidates_by_slate[slate.id],
            )
            for slate in slates
        ],
    )


@router.post(
    "/elections/{election_id}/ballots",
    response_model=VoterBallotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def cast_voter_ballot(
    election_id: UUID,
    payload: VoterBallotRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(require_voter)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> VoterBallotResponse:
    """Record a client-encrypted ballot without storing a voter identifier on it."""
    response.headers["Cache-Control"] = "no-store"
    if not settings.voter_test_mode:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Voter ballot test flow is disabled; configure the production "
                "cryptographic ceremony"
            ),
        )
    await _require_voter_csrf(session, claims, csrf_token)
    election = await _get_active_election(session, election_id, claims)
    if payload.key_version != "v1":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported election key version",
        )
    expected_receipt = hashlib.sha256(payload.encrypted_payload.encode("utf-8")).hexdigest()
    if not hmac.compare_digest(expected_receipt, payload.receipt_hash.lower()):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receipt hash does not match encrypted payload",
        )

    eligibility = await session.scalar(
        select(MemberElectionStatus)
        .where(
            MemberElectionStatus.election_id == election.id,
            MemberElectionStatus.organization_id == claims.org_id,
            MemberElectionStatus.member_id == claims.sub,
        )
        .with_for_update()
    )
    if eligibility is None or not eligibility.eligible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Voter is not eligible for this election",
        )
    if eligibility.has_voted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Voter has already cast a ballot for this election",
        )

    recorded_at = datetime.now(UTC)
    ballot = EncryptedBallot(
        organization_id=claims.org_id,
        election_id=election.id,
        encrypted_payload=payload.encrypted_payload,
        receipt_hash=payload.receipt_hash.lower(),
        zkp_proof=payload.zkp_proof,
        key_version=payload.key_version,
    )
    session.add(ballot)
    eligibility.has_voted = True
    eligibility.voted_at = recorded_at
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This ballot receipt already exists",
        ) from exc
    await session.refresh(ballot)
    return VoterBallotResponse(
        accepted=True,
        receipt_hash=ballot.receipt_hash,
        ballot_id=ballot.id,
        recorded_at=recorded_at,
    )
