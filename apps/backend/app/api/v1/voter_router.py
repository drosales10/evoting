import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_voter
from app.auth.tokens import AccessClaims
from app.core.config import settings
from app.db.session import get_db_session
from app.models import (
    BallotIssuanceToken,
    Candidate,
    Election,
    EncryptedBallot,
    Member,
    MemberElectionStatus,
    Position,
    Slate,
)
from app.services.audit import append_audit_event
from app.services.ballot_crypto import (
    BallotCryptoError,
    parse_encrypted_payload,
    slate_set_hash,
    verify_proof_at_cast,
)
from app.services.csrf import require_csrf
from app.services.rate_limit import client_key, rate_limiter

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
    slate_set_hash: str
    zkp_verification_enabled: bool
    positions: list[VoterPositionResponse]
    slates: list[VoterSlateResponse]


class VoterIssuanceTokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuance_token: str
    expires_at: datetime


class VoterBallotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encrypted_payload: str = Field(min_length=32, max_length=1_048_576)
    receipt_hash: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    zkp_proof: str = Field(min_length=16, max_length=65_536)
    key_version: str = Field(default="v1", min_length=1, max_length=50)
    issuance_token: str | None = Field(default=None, min_length=16, max_length=256)


class VoterBallotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    receipt_hash: str
    ballot_id: UUID
    recorded_at: datetime


def _hash_issuance_token(token: str) -> str:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Voter authentication is not configured",
        )
    return hashlib.sha256(f"{settings.jwt_secret}:issuance:{token}".encode()).hexdigest()


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
        slate_set_hash=slate_set_hash([str(slate.id) for slate in slates]),
        zkp_verification_enabled=settings.zkp_verification_enabled,
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
    "/elections/{election_id}/issuance-token",
    response_model=VoterIssuanceTokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_ballot_token(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(require_voter)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> VoterIssuanceTokenResponse:
    """Issue a single-use cast token decoupled from the ballot payload."""
    response.headers["Cache-Control"] = "no-store"
    await require_csrf(session, claims, csrf_token, realm="VOTER")
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
    if eligibility.has_voted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Voter has already cast a ballot for this election",
        )
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    session.add(
        BallotIssuanceToken(
            id=uuid4(),
            organization_id=claims.org_id,
            election_id=election.id,
            member_id=claims.sub,
            token_hash=_hash_issuance_token(token),
            expires_at=expires_at,
        )
    )
    await session.commit()
    return VoterIssuanceTokenResponse(issuance_token=token, expires_at=expires_at)


@router.post(
    "/elections/{election_id}/ballots",
    response_model=VoterBallotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def cast_voter_ballot(
    election_id: UUID,
    payload: VoterBallotRequest,
    request: Request,
    response: Response,
    claims: Annotated[AccessClaims, Depends(require_voter)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> VoterBallotResponse:
    """Record a client-encrypted ballot without storing a voter identifier on it."""
    response.headers["Cache-Control"] = "no-store"
    rate_limiter.hit(
        client_key(request, "voter-ballot"),
        limit=settings.rate_limit_ballot_per_minute,
        window_seconds=60,
    )
    await require_csrf(session, claims, csrf_token, realm="VOTER")
    election = await _get_active_election(session, election_id, claims)
    if payload.key_version != "v1":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Unsupported election key version",
        )
    try:
        parse_encrypted_payload(payload.encrypted_payload)
    except BallotCryptoError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    expected_receipt = hashlib.sha256(payload.encrypted_payload.encode("utf-8")).hexdigest()
    if expected_receipt != payload.receipt_hash.lower():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receipt hash does not match encrypted payload",
        )

    slates = list(
        (
            await session.scalars(
                select(Slate).where(
                    Slate.election_id == election.id,
                    Slate.organization_id == claims.org_id,
                )
            )
        ).all()
    )
    try:
        verify_proof_at_cast(
            encrypted_payload=payload.encrypted_payload,
            zkp_proof=payload.zkp_proof,
            slate_set_hash=slate_set_hash([str(s.id) for s in slates]),
            require_integrity_proof=settings.zkp_verification_enabled,
            allow_dev_stub=settings.pilot_overrides_allowed,
        )
    except BallotCryptoError as exc:
        await append_audit_event(
            session,
            organization_id=claims.org_id,
            event_type="BALLOT_ZKP_REJECTED",
            actor_id_hash=hashlib.sha256(str(claims.sub).encode("utf-8")).hexdigest(),
            details={"election_id": str(election.id), "reason": str(exc)},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

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

    if settings.ballot_issuance_required:
        if not payload.issuance_token:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="issuance_token is required",
            )
        issuance = await session.scalar(
            select(BallotIssuanceToken)
            .where(
                BallotIssuanceToken.token_hash == _hash_issuance_token(payload.issuance_token),
                BallotIssuanceToken.election_id == election.id,
                BallotIssuanceToken.member_id == claims.sub,
                BallotIssuanceToken.organization_id == claims.org_id,
            )
            .with_for_update()
        )
        now = datetime.now(UTC)
        if (
            issuance is None
            or issuance.consumed_at is not None
            or issuance.expires_at <= now
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Invalid or consumed issuance token",
            )
        issuance.consumed_at = now

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
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="BALLOT_CAST",
        actor_id_hash=hashlib.sha256(str(claims.sub).encode("utf-8")).hexdigest(),
        details={
            "election_id": str(election.id),
            "receipt_hash": ballot.receipt_hash,
        },
    )
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
