"""Voter API for a single sealed statute ballot."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
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
from app.models import StatuteBallot, StatuteConsultation, StatuteIssuanceToken, StatuteMemberStatus
from app.services.audit import append_audit_event
from app.services.ballot_crypto import BallotCryptoError, parse_encrypted_payload
from app.services.csrf import require_csrf
from app.services.rate_limit import client_key, rate_limiter
from app.services.statute_crypto import StatuteCryptoError, verify_statute_proof_at_cast
from app.services.statute_flow import StatuteFlowError, require_can_cast
from app.services.statute_tree import load_statute_tree, tree_as_json

router = APIRouter(prefix="/voter", tags=["voter-statutes"])


class StatuteVoterSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consultation_id: UUID
    title: str
    status: str
    start_time: datetime
    end_time: datetime
    has_voted: bool


class StatuteVoterDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    consultation_id: UUID
    title: str
    status: str
    start_time: datetime
    end_time: datetime
    public_key: str
    key_version: str
    has_voted: bool
    article_set_hash: str
    approval_threshold_pct: str
    zkp_verification_enabled: bool
    titles: list[dict[str, Any]]


class StatuteIssuanceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    issuance_token: str
    expires_at: datetime


class StatuteBallotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    encrypted_payload: str = Field(min_length=40)
    receipt_hash: str = Field(min_length=64, max_length=64)
    zkp_proof: str = Field(min_length=16)
    key_version: str = Field(min_length=1, max_length=50)
    issuance_token: str | None = None


class StatuteBallotResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool
    receipt_hash: str
    ballot_id: UUID
    recorded_at: datetime
    qr_payload: str


def _hash_issuance_token(token: str) -> str:
    if not settings.jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La autenticación del elector no está configurada",
        )
    return hashlib.sha256(f"{settings.jwt_secret}:issuance:{token}".encode()).hexdigest()


def _actor_hash(principal_id: UUID) -> str:
    return hashlib.sha256(str(principal_id).encode("utf-8")).hexdigest()


async def _active_consultation(
    session: AsyncSession,
    consultation_id: UUID,
    claims: AccessClaims,
) -> StatuteConsultation:
    consultation = await session.scalar(
        select(StatuteConsultation).where(
            StatuteConsultation.id == consultation_id,
            StatuteConsultation.organization_id == claims.org_id,
        )
    )
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta no encontrada")
    now = datetime.now(UTC)
    if (
        consultation.status != "ACTIVE"
        or consultation.start_time > now
        or consultation.end_time <= now
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La consulta no está recibiendo votos",
        )
    if not consultation.public_key or not consultation.article_set_hash:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La consulta no tiene clave pública",
        )
    return consultation


async def _eligibility(
    session: AsyncSession,
    consultation: StatuteConsultation,
    claims: AccessClaims,
    *,
    lock: bool = False,
) -> StatuteMemberStatus:
    statement = select(StatuteMemberStatus).where(
        StatuteMemberStatus.consultation_id == consultation.id,
        StatuteMemberStatus.member_id == claims.sub,
    )
    if lock:
        statement = statement.with_for_update()
    row = await session.scalar(statement)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No hay padrón de esta consulta para el miembro",
        )
    try:
        require_can_cast(
            eligible=row.eligible,
            has_voted=row.has_voted,
            reason=row.eligibility_reason,
        )
    except StatuteFlowError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    return row


@router.get("/statutes", response_model=list[StatuteVoterSummary])
async def list_voter_statutes(
    response: Response,
    claims: Annotated[AccessClaims, Depends(require_voter)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[StatuteVoterSummary]:
    response.headers["Cache-Control"] = "no-store"
    now = datetime.now(UTC)
    rows = (
        await session.execute(
            select(StatuteConsultation, StatuteMemberStatus.has_voted)
            .join(
                StatuteMemberStatus,
                (StatuteMemberStatus.consultation_id == StatuteConsultation.id)
                & (StatuteMemberStatus.member_id == claims.sub)
                & (StatuteMemberStatus.eligible.is_(True)),
            )
            .where(
                StatuteConsultation.organization_id == claims.org_id,
                StatuteConsultation.status == "ACTIVE",
                StatuteConsultation.start_time <= now,
                StatuteConsultation.end_time > now,
            )
            .order_by(StatuteConsultation.end_time.asc())
        )
    ).all()
    return [
        StatuteVoterSummary(
            consultation_id=consultation.id,
            title=consultation.title,
            status=consultation.status,
            start_time=consultation.start_time,
            end_time=consultation.end_time,
            has_voted=has_voted,
        )
        for consultation, has_voted in rows
    ]


@router.get("/statutes/{consultation_id}", response_model=StatuteVoterDetail)
async def get_voter_statute(
    consultation_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(require_voter)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteVoterDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _active_consultation(session, consultation_id, claims)
    eligibility = await session.scalar(
        select(StatuteMemberStatus).where(
            StatuteMemberStatus.consultation_id == consultation.id,
            StatuteMemberStatus.member_id == claims.sub,
        )
    )
    if eligibility is None or not eligibility.eligible:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El miembro no es elegible para esta consulta",
        )
    tree = await load_statute_tree(
        session,
        organization_id=claims.org_id,
        consultation_id=consultation.id,
    )
    return StatuteVoterDetail(
        consultation_id=consultation.id,
        title=consultation.title,
        status=consultation.status,
        start_time=consultation.start_time,
        end_time=consultation.end_time,
        public_key=consultation.public_key or "",
        key_version="v1",
        has_voted=eligibility.has_voted,
        article_set_hash=consultation.article_set_hash or "",
        approval_threshold_pct=str(consultation.approval_threshold_pct),
        zkp_verification_enabled=settings.zkp_verification_enabled,
        titles=tree_as_json(tree),
    )


@router.post(
    "/statutes/{consultation_id}/issuance-token",
    response_model=StatuteIssuanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def issue_statute_token(
    consultation_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(require_voter)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> StatuteIssuanceResponse:
    response.headers["Cache-Control"] = "no-store"
    await require_csrf(session, claims, csrf_token, realm="VOTER")
    consultation = await _active_consultation(session, consultation_id, claims)
    eligibility = await _eligibility(session, consultation, claims)
    if eligibility.has_voted:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El miembro ya emitió su boleta para esta consulta",
        )
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + timedelta(minutes=10)
    session.add(
        StatuteIssuanceToken(
            id=uuid4(),
            organization_id=claims.org_id,
            consultation_id=consultation.id,
            member_id=claims.sub,
            token_hash=_hash_issuance_token(token),
            expires_at=expires_at,
        )
    )
    await session.commit()
    return StatuteIssuanceResponse(issuance_token=token, expires_at=expires_at)


@router.post(
    "/statutes/{consultation_id}/ballots",
    response_model=StatuteBallotResponse,
    status_code=status.HTTP_201_CREATED,
)
async def cast_statute_ballot(
    consultation_id: UUID,
    payload: StatuteBallotRequest,
    request: Request,
    response: Response,
    claims: Annotated[AccessClaims, Depends(require_voter)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> StatuteBallotResponse:
    """Store one encrypted ballot linked to the member. The plaintext stays sealed."""
    response.headers["Cache-Control"] = "no-store"
    rate_limiter.hit(
        client_key(request, "voter-statute-ballot"),
        limit=settings.rate_limit_ballot_per_minute,
        window_seconds=60,
    )
    await require_csrf(session, claims, csrf_token, realm="VOTER")
    consultation = await _active_consultation(session, consultation_id, claims)
    if payload.key_version != "v1":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Versión de clave no soportada",
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
            detail="El recibo no coincide con el sobre cifrado",
        )
    try:
        verify_statute_proof_at_cast(
            encrypted_payload=payload.encrypted_payload,
            zkp_proof=payload.zkp_proof,
            article_set_hash_value=consultation.article_set_hash or "",
            require_integrity_proof=settings.zkp_verification_enabled,
            allow_dev_stub=settings.pilot_overrides_allowed,
        )
    except StatuteCryptoError as exc:
        await append_audit_event(
            session,
            organization_id=claims.org_id,
            event_type="STATUTE_BALLOT_REJECTED",
            actor_id_hash=_actor_hash(claims.sub),
            details={"consultation_id": str(consultation.id), "reason": str(exc)},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    eligibility = await _eligibility(session, consultation, claims, lock=True)
    if settings.ballot_issuance_required:
        if not payload.issuance_token:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El token de emisión es obligatorio",
            )
        issuance = await session.scalar(
            select(StatuteIssuanceToken)
            .where(
                StatuteIssuanceToken.token_hash == _hash_issuance_token(payload.issuance_token),
                StatuteIssuanceToken.consultation_id == consultation.id,
                StatuteIssuanceToken.member_id == claims.sub,
                StatuteIssuanceToken.organization_id == claims.org_id,
            )
            .with_for_update()
        )
        now = datetime.now(UTC)
        if issuance is None or issuance.consumed_at is not None or issuance.expires_at <= now:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="El token de emisión es inválido o ya se usó",
            )
        issuance.consumed_at = now

    recorded_at = datetime.now(UTC)
    receipt_hash = payload.receipt_hash.lower()
    qr_payload = f"{settings.app_public_url.rstrip('/')}/r/{receipt_hash}"
    ballot = StatuteBallot(
        organization_id=claims.org_id,
        consultation_id=consultation.id,
        member_id=claims.sub,
        encrypted_payload=payload.encrypted_payload,
        receipt_hash=receipt_hash,
        zkp_proof=payload.zkp_proof,
        key_version=payload.key_version,
        qr_payload=qr_payload,
    )
    session.add(ballot)
    eligibility.has_voted = True
    eligibility.voted_at = recorded_at
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="STATUTE_BALLOT_CAST",
        actor_id_hash=_actor_hash(claims.sub),
        details={
            "consultation_id": str(consultation.id),
            "receipt_hash": receipt_hash,
        },
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El miembro ya emitió su boleta para esta consulta",
        ) from exc
    await session.refresh(ballot)
    return StatuteBallotResponse(
        accepted=True,
        receipt_hash=ballot.receipt_hash,
        ballot_id=ballot.id,
        recorded_at=recorded_at,
        qr_payload=ballot.qr_payload or qr_payload,
    )
