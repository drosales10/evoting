"""Admin API for statute consultations. Parallel to elections; slates stay untouched."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.tokens import AccessClaims
from app.core.config import settings
from app.db.session import get_db_session
from app.models import (
    Member,
    StatuteArticle,
    StatuteBallot,
    StatuteChapter,
    StatuteConsultation,
    StatuteMemberStatus,
    StatuteTally,
    StatuteTallyProposal,
    StatuteTitle,
)
from app.services.audit import append_audit_event
from app.services.csrf import require_csrf
from app.services.member_metrics import evaluate_voter_eligibility
from app.services.statute_crypto import article_set_hash
from app.services.statute_flow import StatuteFlowError, require_editable, require_status
from app.services.statute_tally import (
    article_meets_threshold,
    build_statute_acta,
    required_quorum_votes,
)
from app.services.statute_tree import flatten_article_ids, load_statute_tree
from app.services.tally_artifact import artifact_sha256, verify_artifact

router = APIRouter(prefix="/admin", tags=["admin-statutes"])

STATUTE_MANAGER_ROLES = frozenset({"SUPER_ADMIN", "ELECTORAL_JUSTICE"})


def _actor_hash(principal_id: UUID) -> str:
    return hashlib.sha256(str(principal_id).encode("utf-8")).hexdigest()


def _flow(exc: StatuteFlowError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.message)


def _validate_rsa_public_pem(value: str, field_name: str) -> str:
    if "-----BEGIN PUBLIC KEY-----" not in value or "-----END PUBLIC KEY-----" not in value:
        raise ValueError(f"{field_name} must be an RSA SubjectPublicKeyInfo PEM")
    try:
        public_key = load_pem_public_key(value.encode())
    except ValueError as exc:
        raise ValueError(f"{field_name} is not valid PEM key material") from exc
    if not isinstance(public_key, RSAPublicKey):
        raise ValueError(f"{field_name} must contain an RSA public key")
    return value


def _aware(value: datetime, field_name: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} must include a timezone")


class StatuteCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=255)
    start_time: datetime
    end_time: datetime
    quorum_threshold_pct: Decimal = Field(default=Decimal("30.00"), ge=0, le=100)
    approval_threshold_pct: Decimal = Field(default=Decimal("50.00"), ge=0, le=100)

    @model_validator(mode="after")
    def validate_schedule(self) -> "StatuteCreateRequest":
        _aware(self.start_time, "start_time")
        _aware(self.end_time, "end_time")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class StatuteUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, min_length=3, max_length=255)
    start_time: datetime | None = None
    end_time: datetime | None = None
    quorum_threshold_pct: Decimal | None = Field(default=None, ge=0, le=100)
    approval_threshold_pct: Decimal | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def validate_schedule(self) -> "StatuteUpdateRequest":
        if self.start_time is not None:
            _aware(self.start_time, "start_time")
        if self.end_time is not None:
            _aware(self.end_time, "end_time")
        if (
            self.start_time is not None
            and self.end_time is not None
            and self.end_time <= self.start_time
        ):
            raise ValueError("end_time must be after start_time")
        return self


class TitleWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1, le=999)
    description: str = Field(min_length=1, max_length=255)
    display_order: int = Field(default=0, ge=0, le=9999)


class ChapterWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1, le=999)
    description: str = Field(default="", max_length=255)
    display_order: int = Field(default=0, ge=0, le=9999)


class ArticleWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    number: int = Field(ge=1, le=9999)
    content: str = Field(min_length=1, max_length=20000)
    display_order: int = Field(default=0, ge=0, le=9999)


class ArticleOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    number: int
    content: str
    display_order: int
    chapter_id: UUID


class ChapterOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    number: int
    description: str
    display_order: int
    title_id: UUID
    articles: list[ArticleOut]


class TitleOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    number: int
    description: str
    display_order: int
    chapters: list[ChapterOut]


class StatuteSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    status: str
    start_time: datetime
    end_time: datetime
    quorum_threshold_pct: Decimal
    approval_threshold_pct: Decimal
    article_count: int
    created_at: datetime


class StatuteDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    status: str
    start_time: datetime
    end_time: datetime
    quorum_threshold_pct: Decimal
    approval_threshold_pct: Decimal
    article_set_hash: str | None
    frozen_at: datetime | None
    activated_at: datetime | None
    created_at: datetime
    titles: list[TitleOut]


class StatuteActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_key: str = Field(min_length=16, max_length=8192)
    signing_public_key: str | None = Field(default=None, min_length=16, max_length=8192)

    @field_validator("public_key", "signing_public_key", mode="before")
    @classmethod
    def normalize_public_key(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip()

    @field_validator("public_key", mode="after")
    @classmethod
    def validate_public_key_pem(cls, value: str) -> str:
        return _validate_rsa_public_pem(value, "public_key")

    @field_validator("signing_public_key", mode="after")
    @classmethod
    def validate_signing_public_key_pem(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return _validate_rsa_public_pem(value, "signing_public_key")


class StatuteCloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force_pilot: bool = False
    reason: str = Field(min_length=10, max_length=255)


class StatuteTallyResponseItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: UUID
    full_name: str = Field(min_length=1, max_length=255)
    registry_code: str | None = None
    approved: bool
    comment: str | None = None


class StatuteTallyArticle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    article_id: UUID
    number: int
    content: str
    title_number: int
    title_description: str
    chapter_number: int
    chapter_description: str
    approved_count: int = Field(ge=0)
    rejected_count: int = Field(ge=0)
    meets_threshold: bool
    responses: list[StatuteTallyResponseItem]


class StatuteTallyArtifactModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_version: Literal["statute-tally-v1"]
    consultation_id: UUID
    public_key_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime
    eligible_member_count: int = Field(ge=0)
    voted_member_count: int = Field(ge=0)
    quorum_threshold_pct: Decimal = Field(ge=0, le=100)
    approval_threshold_pct: Decimal = Field(ge=0, le=100)
    quorum_required: int = Field(ge=0)
    quorum_met: bool
    ballot_count: int = Field(ge=0)
    receipt_hashes: list[str]
    articles: list[StatuteTallyArticle]


class StatuteTallyPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact: dict[str, Any]
    signature: str = Field(min_length=32, max_length=8192)
    pilot_override: bool = False
    reason: str = Field(min_length=10, max_length=255)
    approval_stage: Literal["propose", "confirm", "publish"] = "publish"


async def _require_manager(
    claims: Annotated[AccessClaims, Depends(require_admin)],
) -> AccessClaims:
    if not STATUTE_MANAGER_ROLES.intersection(claims.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Se requiere un rol de gestión electoral",
        )
    return claims


async def _require_mutation(
    claims: Annotated[AccessClaims, Depends(_require_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> AccessClaims:
    await require_csrf(session, claims, csrf_token, realm="ADMIN")
    return claims


async def _get_consultation(
    session: AsyncSession,
    consultation_id: UUID,
    organization_id: UUID,
    *,
    lock: bool = False,
) -> StatuteConsultation:
    statement = select(StatuteConsultation).where(
        StatuteConsultation.id == consultation_id,
        StatuteConsultation.organization_id == organization_id,
    )
    if lock:
        statement = statement.with_for_update()
    consultation = await session.scalar(statement)
    if consultation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta no encontrada")
    return consultation


async def _detail(
    session: AsyncSession,
    consultation: StatuteConsultation,
) -> StatuteDetail:
    tree = await load_statute_tree(
        session,
        organization_id=consultation.organization_id,
        consultation_id=consultation.id,
    )
    return StatuteDetail(
        id=consultation.id,
        title=consultation.title,
        status=consultation.status,
        start_time=consultation.start_time,
        end_time=consultation.end_time,
        quorum_threshold_pct=consultation.quorum_threshold_pct,
        approval_threshold_pct=consultation.approval_threshold_pct,
        article_set_hash=consultation.article_set_hash,
        frozen_at=consultation.frozen_at,
        activated_at=consultation.activated_at,
        created_at=consultation.created_at,
        titles=[TitleOut.model_validate(title) for title in tree],
    )


async def _participation(
    session: AsyncSession,
    consultation_id: UUID,
    organization_id: UUID,
) -> tuple[int, int, int]:
    eligible_count, voted_count = (
        int(value)
        for value in (
            await session.execute(
                select(
                    func.count(StatuteMemberStatus.id),
                    func.count(StatuteMemberStatus.id).filter(
                        StatuteMemberStatus.has_voted.is_(True)
                    ),
                ).where(
                    StatuteMemberStatus.consultation_id == consultation_id,
                    StatuteMemberStatus.organization_id == organization_id,
                    StatuteMemberStatus.eligible.is_(True),
                )
            )
        ).one()
    )
    ballot_count = int(
        (
            await session.execute(
                select(func.count(StatuteBallot.id)).where(
                    StatuteBallot.consultation_id == consultation_id,
                    StatuteBallot.organization_id == organization_id,
                )
            )
        ).scalar_one()
    )
    return eligible_count, voted_count, ballot_count


def _summary(consultation: StatuteConsultation, article_count: int) -> StatuteSummary:
    return StatuteSummary(
        id=consultation.id,
        title=consultation.title,
        status=consultation.status,
        start_time=consultation.start_time,
        end_time=consultation.end_time,
        quorum_threshold_pct=consultation.quorum_threshold_pct,
        approval_threshold_pct=consultation.approval_threshold_pct,
        article_count=article_count,
        created_at=consultation.created_at,
    )


@router.get("/statutes", response_model=list[StatuteSummary])
async def list_statutes(
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[StatuteSummary]:
    response.headers["Cache-Control"] = "no-store"
    consultations = list(
        (
            await session.scalars(
                select(StatuteConsultation)
                .where(StatuteConsultation.organization_id == claims.org_id)
                .order_by(StatuteConsultation.created_at.desc())
            )
        ).all()
    )
    counts = dict(
        (
            await session.execute(
                select(StatuteArticle.consultation_id, func.count(StatuteArticle.id))
                .where(StatuteArticle.organization_id == claims.org_id)
                .group_by(StatuteArticle.consultation_id)
            )
        ).all()
    )
    return [_summary(item, int(counts.get(item.id, 0))) for item in consultations]


@router.post("/statutes", response_model=StatuteDetail, status_code=status.HTTP_201_CREATED)
async def create_statute(
    payload: StatuteCreateRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = StatuteConsultation(
        organization_id=claims.org_id,
        title=payload.title.strip(),
        start_time=payload.start_time,
        end_time=payload.end_time,
        quorum_threshold_pct=payload.quorum_threshold_pct,
        approval_threshold_pct=payload.approval_threshold_pct,
        status="DRAFT",
    )
    session.add(consultation)
    await session.flush()
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="STATUTE_CREATED",
        actor_id_hash=_actor_hash(claims.sub),
        details={"consultation_id": str(consultation.id), "title": consultation.title},
    )
    await session.commit()
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.get("/statutes/{consultation_id}", response_model=StatuteDetail)
async def get_statute(
    consultation_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _get_consultation(session, consultation_id, claims.org_id)
    return await _detail(session, consultation)


@router.patch("/statutes/{consultation_id}", response_model=StatuteDetail)
async def update_statute(
    consultation_id: UUID,
    payload: StatuteUpdateRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _get_consultation(session, consultation_id, claims.org_id, lock=True)
    try:
        require_editable(consultation.status)
    except StatuteFlowError as exc:
        raise _flow(exc) from exc
    if payload.title is not None:
        consultation.title = payload.title.strip()
    if payload.start_time is not None:
        consultation.start_time = payload.start_time
    if payload.end_time is not None:
        consultation.end_time = payload.end_time
    if payload.quorum_threshold_pct is not None:
        consultation.quorum_threshold_pct = payload.quorum_threshold_pct
    if payload.approval_threshold_pct is not None:
        consultation.approval_threshold_pct = payload.approval_threshold_pct
    if consultation.end_time <= consultation.start_time:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La fecha de cierre debe ser posterior a la de apertura",
        )
    await session.commit()
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.delete("/statutes/{consultation_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_statute(
    consultation_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _get_consultation(session, consultation_id, claims.org_id, lock=True)
    try:
        require_status(consultation.status, "DRAFT", "Solo se elimina una consulta en borrador")
    except StatuteFlowError as exc:
        raise _flow(exc) from exc
    await session.delete(consultation)
    await session.commit()


@router.post(
    "/statutes/{consultation_id}/titles",
    response_model=StatuteDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_title(
    consultation_id: UUID,
    payload: TitleWriteRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _editable(session, consultation_id, claims.org_id)
    session.add(
        StatuteTitle(
            organization_id=claims.org_id,
            consultation_id=consultation.id,
            number=payload.number,
            description=payload.description.strip(),
            display_order=payload.display_order or payload.number,
        )
    )
    await _commit_structure(session)
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.patch("/statutes/{consultation_id}/titles/{title_id}", response_model=StatuteDetail)
async def update_title(
    consultation_id: UUID,
    title_id: UUID,
    payload: TitleWriteRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _editable(session, consultation_id, claims.org_id)
    title = await _title(session, consultation, title_id)
    title.number = payload.number
    title.description = payload.description.strip()
    title.display_order = payload.display_order
    await _commit_structure(session)
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.delete(
    "/statutes/{consultation_id}/titles/{title_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_title(
    consultation_id: UUID,
    title_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _editable(session, consultation_id, claims.org_id)
    title = await _title(session, consultation, title_id)
    await session.delete(title)
    await session.commit()


@router.post(
    "/statutes/{consultation_id}/titles/{title_id}/chapters",
    response_model=StatuteDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_chapter(
    consultation_id: UUID,
    title_id: UUID,
    payload: ChapterWriteRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _editable(session, consultation_id, claims.org_id)
    title = await _title(session, consultation, title_id)
    session.add(
        StatuteChapter(
            organization_id=claims.org_id,
            consultation_id=consultation.id,
            title_id=title.id,
            number=payload.number,
            description=payload.description.strip(),
            display_order=payload.display_order or payload.number,
        )
    )
    await _commit_structure(session)
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.patch("/statutes/{consultation_id}/chapters/{chapter_id}", response_model=StatuteDetail)
async def update_chapter(
    consultation_id: UUID,
    chapter_id: UUID,
    payload: ChapterWriteRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _editable(session, consultation_id, claims.org_id)
    chapter = await _chapter(session, consultation, chapter_id)
    chapter.number = payload.number
    chapter.description = payload.description.strip()
    chapter.display_order = payload.display_order
    await _commit_structure(session)
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.delete(
    "/statutes/{consultation_id}/chapters/{chapter_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_chapter(
    consultation_id: UUID,
    chapter_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _editable(session, consultation_id, claims.org_id)
    chapter = await _chapter(session, consultation, chapter_id)
    await session.delete(chapter)
    await session.commit()


@router.post(
    "/statutes/{consultation_id}/chapters/{chapter_id}/articles",
    response_model=StatuteDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_article(
    consultation_id: UUID,
    chapter_id: UUID,
    payload: ArticleWriteRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _editable(session, consultation_id, claims.org_id)
    chapter = await _chapter(session, consultation, chapter_id)
    session.add(
        StatuteArticle(
            organization_id=claims.org_id,
            consultation_id=consultation.id,
            chapter_id=chapter.id,
            number=payload.number,
            content=payload.content.strip(),
            display_order=payload.display_order or payload.number,
        )
    )
    await _commit_structure(session)
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.patch("/statutes/{consultation_id}/articles/{article_id}", response_model=StatuteDetail)
async def update_article(
    consultation_id: UUID,
    article_id: UUID,
    payload: ArticleWriteRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _editable(session, consultation_id, claims.org_id)
    article = await _article(session, consultation, article_id)
    article.number = payload.number
    article.content = payload.content.strip()
    article.display_order = payload.display_order
    await _commit_structure(session)
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.delete(
    "/statutes/{consultation_id}/articles/{article_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
)
async def delete_article(
    consultation_id: UUID,
    article_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> None:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _editable(session, consultation_id, claims.org_id)
    article = await _article(session, consultation, article_id)
    await session.delete(article)
    await session.commit()


@router.post("/statutes/{consultation_id}/open-registration", response_model=StatuteDetail)
async def open_registration(
    consultation_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _get_consultation(session, consultation_id, claims.org_id, lock=True)
    try:
        require_status(
            consultation.status,
            "DRAFT",
            "Solo un borrador puede abrir el registro del padrón",
        )
    except StatuteFlowError as exc:
        raise _flow(exc) from exc
    members = await session.scalars(select(Member).where(Member.organization_id == claims.org_id))
    for member in members:
        decision = evaluate_voter_eligibility(
            status=member.status,
            alive=member.alive,
            member_type=member.member_type,
        )
        session.add(
            StatuteMemberStatus(
                organization_id=claims.org_id,
                consultation_id=consultation.id,
                member_id=member.id,
                eligible=decision.eligible,
                eligibility_reason=decision.reason,
                has_voted=False,
            )
        )
    consultation.status = "REGISTRATION"
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="STATUTE_REGISTRATION_OPENED",
        actor_id_hash=_actor_hash(claims.sub),
        details={"consultation_id": str(consultation.id)},
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El padrón de esta consulta ya fue fotografiado",
        ) from exc
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.post("/statutes/{consultation_id}/freeze", response_model=StatuteDetail)
async def freeze_statute(
    consultation_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _get_consultation(session, consultation_id, claims.org_id, lock=True)
    try:
        require_status(
            consultation.status,
            "REGISTRATION",
            "Solo se congela una consulta en registro",
        )
    except StatuteFlowError as exc:
        raise _flow(exc) from exc
    tree = await load_statute_tree(
        session,
        organization_id=claims.org_id,
        consultation_id=consultation.id,
    )
    article_ids = flatten_article_ids(tree)
    if not article_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El estatuto necesita al menos un artículo antes de congelarse",
        )
    consultation.article_set_hash = article_set_hash(article_ids)
    consultation.frozen_at = datetime.now(UTC)
    consultation.status = "FREEZE"
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="STATUTE_FROZEN",
        actor_id_hash=_actor_hash(claims.sub),
        details={
            "consultation_id": str(consultation.id),
            "article_count": len(article_ids),
            "article_set_hash": consultation.article_set_hash,
        },
    )
    await session.commit()
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.post("/statutes/{consultation_id}/activate", response_model=StatuteDetail)
async def activate_statute(
    consultation_id: UUID,
    payload: StatuteActivationRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StatuteDetail:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _get_consultation(session, consultation_id, claims.org_id, lock=True)
    try:
        require_status(consultation.status, "FREEZE", "Solo se activa un estatuto congelado")
    except StatuteFlowError as exc:
        raise _flow(exc) from exc
    now = datetime.now(UTC)
    if consultation.start_time > now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La consulta no puede activarse antes de su apertura",
        )
    if consultation.end_time <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La ventana de la consulta ya cerró",
        )
    snapshot_count, eligible_count = (
        int(value)
        for value in (
            await session.execute(
                select(
                    func.count(StatuteMemberStatus.id),
                    func.count(StatuteMemberStatus.id).filter(
                        StatuteMemberStatus.eligible.is_(True)
                    ),
                ).where(
                    StatuteMemberStatus.consultation_id == consultation.id,
                    StatuteMemberStatus.organization_id == claims.org_id,
                )
            )
        ).one()
    )
    current_members = int(
        (
            await session.execute(
                select(func.count(Member.id)).where(Member.organization_id == claims.org_id)
            )
        ).scalar_one()
    )
    if snapshot_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La consulta no tiene padrón fotografiado",
        )
    if snapshot_count != current_members:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El padrón cambió después del congelado; hay que rehacer la consulta",
        )
    if eligible_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No hay miembros elegibles",
        )
    tree = await load_statute_tree(
        session,
        organization_id=claims.org_id,
        consultation_id=consultation.id,
    )
    article_ids = flatten_article_ids(tree)
    if not article_ids or not consultation.article_set_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El estatuto congelado no tiene artículos",
        )
    if article_set_hash(article_ids) != consultation.article_set_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El texto no coincide con la huella congelada",
        )
    public_key = payload.public_key
    signing_public_key = payload.signing_public_key or public_key
    consultation.public_key = public_key
    consultation.signing_public_key = signing_public_key
    consultation.activated_at = now
    consultation.status = "ACTIVE"
    public_key_sha256 = hashlib.sha256(public_key.encode("utf-8")).hexdigest()
    signing_sha = hashlib.sha256(signing_public_key.encode("utf-8")).hexdigest()
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="STATUTE_ACTIVATED",
        actor_id_hash=_actor_hash(claims.sub),
        details={
            "consultation_id": str(consultation.id),
            "snapshot_member_count": snapshot_count,
            "eligible_member_count": eligible_count,
            "article_count": len(article_ids),
            "public_key_sha256": public_key_sha256,
            "signing_public_key_sha256": signing_sha,
        },
    )
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="STATUTE_KEY_CEREMONY_OPENED",
        actor_id_hash=_actor_hash(claims.sub),
        details={
            "consultation_id": str(consultation.id),
            "public_key_sha256": public_key_sha256,
            "signing_public_key_sha256": signing_sha,
        },
    )
    await session.commit()
    await session.refresh(consultation)
    return await _detail(session, consultation)


@router.post("/statutes/{consultation_id}/close")
async def close_statute(
    consultation_id: UUID,
    payload: StatuteCloseRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _get_consultation(session, consultation_id, claims.org_id, lock=True)
    try:
        require_status(consultation.status, "ACTIVE", "Solo se cierra una consulta activa")
    except StatuteFlowError as exc:
        raise _flow(exc) from exc
    eligible_count, voted_count, ballot_count = await _participation(
        session, consultation.id, claims.org_id
    )
    quorum_required = required_quorum_votes(eligible_count, consultation.quorum_threshold_pct)
    quorum_met = voted_count >= quorum_required
    if payload.force_pilot and not settings.pilot_overrides_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="El cierre de piloto solo está disponible en modo de prueba",
        )
    if ballot_count != voted_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La participación y las boletas cifradas no coinciden",
        )
    if not payload.force_pilot and consultation.end_time > datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La ventana de votación sigue abierta",
        )
    if not quorum_met and not payload.force_pilot:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Quórum no alcanzado: {voted_count} participaciones; "
                f"se requieren {quorum_required}"
            ),
        )
    closed_at = datetime.now(UTC)
    consultation.status = "CLOSED"
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="STATUTE_CLOSED",
        actor_id_hash=_actor_hash(claims.sub),
        details={
            "consultation_id": str(consultation.id),
            "eligible_member_count": eligible_count,
            "voted_member_count": voted_count,
            "ballot_count": ballot_count,
            "quorum_required": quorum_required,
            "quorum_met": quorum_met,
            "pilot_override": payload.force_pilot,
            "reason": payload.reason,
        },
    )
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="STATUTE_KEY_CEREMONY_CLOSED",
        actor_id_hash=_actor_hash(claims.sub),
        details={"consultation_id": str(consultation.id), "pilot_override": payload.force_pilot},
    )
    await session.commit()
    return {
        "consultation_id": consultation.id,
        "status": consultation.status,
        "closed_at": closed_at,
        "eligible_member_count": eligible_count,
        "voted_member_count": voted_count,
        "ballot_count": ballot_count,
        "quorum_threshold_pct": consultation.quorum_threshold_pct,
        "quorum_required": quorum_required,
        "quorum_met": quorum_met,
        "pilot_override": payload.force_pilot,
    }


@router.get("/statutes/{consultation_id}/tally-readiness")
async def statute_tally_readiness(
    consultation_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _get_consultation(session, consultation_id, claims.org_id)
    eligible_count, voted_count, ballot_count = await _participation(
        session, consultation.id, claims.org_id
    )
    quorum_required = required_quorum_votes(eligible_count, consultation.quorum_threshold_pct)
    signing_pem = consultation.signing_public_key or consultation.public_key
    return {
        "consultation_id": consultation.id,
        "status": consultation.status,
        "eligible_member_count": eligible_count,
        "voted_member_count": voted_count,
        "ballot_count": ballot_count,
        "quorum_threshold_pct": consultation.quorum_threshold_pct,
        "approval_threshold_pct": consultation.approval_threshold_pct,
        "quorum_required": quorum_required,
        "quorum_met": voted_count >= quorum_required,
        "public_key_sha256": (
            hashlib.sha256(signing_pem.encode("utf-8")).hexdigest() if signing_pem else None
        ),
        "requires_offline_private_key": True,
        "can_mark_tallied": consultation.status == "CLOSED",
        "zkp_verification_enabled": settings.zkp_verification_enabled,
    }


@router.post("/statutes/{consultation_id}/tally")
async def publish_statute_tally(
    consultation_id: UUID,
    payload: StatuteTallyPublishRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _get_consultation(session, consultation_id, claims.org_id, lock=True)
    try:
        require_status(
            consultation.status,
            "CLOSED",
            "Solo se publica el acta de una consulta cerrada",
        )
    except StatuteFlowError as exc:
        raise _flow(exc) from exc
    if payload.pilot_override and not settings.pilot_overrides_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="La publicación de piloto solo está disponible en modo de prueba",
        )
    if await session.scalar(
        select(StatuteTally).where(StatuteTally.consultation_id == consultation.id)
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta consulta ya tiene un acta publicada",
        )
    try:
        artifact_model = StatuteTallyArtifactModel.model_validate(payload.artifact)
    except ValueError as exc:
        await append_audit_event(
            session,
            organization_id=claims.org_id,
            event_type="STATUTE_TALLY_REJECTED",
            actor_id_hash=_actor_hash(claims.sub),
            details={"consultation_id": str(consultation.id), "reason": "invalid_artifact"},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El acta no tiene la forma statute-tally-v1",
        ) from exc
    if artifact_model.consultation_id != consultation.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="El acta corresponde a otra consulta",
        )
    signing_pem = consultation.signing_public_key or consultation.public_key or ""
    if not signing_pem:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="La consulta no tiene clave pública de firma",
        )
    allowed_hashes = {hashlib.sha256(signing_pem.encode("utf-8")).hexdigest()}
    if consultation.public_key:
        allowed_hashes.add(hashlib.sha256(consultation.public_key.encode("utf-8")).hexdigest())
    if artifact_model.public_key_sha256 not in allowed_hashes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La huella de clave del acta no coincide",
        )
    try:
        public_key = load_pem_public_key(signing_pem.encode("utf-8"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="La clave pública de firma es inválida",
        ) from exc
    if not isinstance(public_key, RSAPublicKey) or not verify_artifact(
        payload.artifact, payload.signature, public_key
    ):
        await append_audit_event(
            session,
            organization_id=claims.org_id,
            event_type="STATUTE_TALLY_REJECTED",
            actor_id_hash=_actor_hash(claims.sub),
            details={"consultation_id": str(consultation.id), "reason": "invalid_signature"},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="La firma del acta no es válida",
        )

    eligible_count, voted_count, ballot_count = await _participation(
        session, consultation.id, claims.org_id
    )
    quorum_required = required_quorum_votes(eligible_count, consultation.quorum_threshold_pct)
    quorum_met = voted_count >= quorum_required
    if (
        artifact_model.eligible_member_count != eligible_count
        or artifact_model.voted_member_count != voted_count
        or artifact_model.ballot_count != ballot_count
        or artifact_model.quorum_required != quorum_required
        or artifact_model.quorum_met != quorum_met
        or artifact_model.quorum_threshold_pct != consultation.quorum_threshold_pct
        or artifact_model.approval_threshold_pct != consultation.approval_threshold_pct
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Los conteos del acta no coinciden con la consulta",
        )
    if not quorum_met and not payload.pilot_override:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El quórum no se alcanzó",
        )
    current_receipts = sorted(
        receipt.lower()
        for receipt in (
            await session.scalars(
                select(StatuteBallot.receipt_hash).where(
                    StatuteBallot.consultation_id == consultation.id,
                    StatuteBallot.organization_id == claims.org_id,
                )
            )
        )
    )
    if sorted(item.lower() for item in artifact_model.receipt_hashes) != current_receipts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Los recibos del acta no coinciden con la urna",
        )
    await _assert_articles_match(session, consultation, artifact_model)
    await _assert_named_responses(session, consultation, artifact_model)

    sha = artifact_sha256(payload.artifact)
    actor = _actor_hash(claims.sub)
    dual_required = settings.require_dual_tally_approval and not payload.pilot_override
    stage = payload.approval_stage
    if dual_required and stage == "publish":
        stage = "propose"
    if dual_required and stage == "propose":
        existing = await session.scalar(
            select(StatuteTallyProposal).where(
                StatuteTallyProposal.consultation_id == consultation.id
            )
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Ya hay una propuesta de acta pendiente",
            )
        proposal = StatuteTallyProposal(
            organization_id=claims.org_id,
            consultation_id=consultation.id,
            artifact=payload.artifact,
            signature=payload.signature,
            artifact_sha256=sha,
            proposer_hash=actor,
            reason=payload.reason,
            pilot_override=payload.pilot_override,
        )
        session.add(proposal)
        await append_audit_event(
            session,
            organization_id=claims.org_id,
            event_type="STATUTE_TALLY_PROPOSED",
            actor_id_hash=actor,
            details={"consultation_id": str(consultation.id), "artifact_sha256": sha},
        )
        await session.commit()
        return {
            "proposal_id": proposal.id,
            "consultation_id": consultation.id,
            "status": consultation.status,
            "artifact_sha256": sha,
            "approval_stage": "propose",
            "quorum_met": quorum_met,
        }

    first_approver = actor
    second_approver: str | None = None
    if dual_required and stage == "confirm":
        proposal = await session.scalar(
            select(StatuteTallyProposal)
            .where(StatuteTallyProposal.consultation_id == consultation.id)
            .with_for_update()
        )
        if proposal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No hay propuesta de acta; primero hay que proponerla",
            )
        if proposal.proposer_hash == actor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="La segunda aprobación la hace otro administrador",
            )
        if proposal.artifact_sha256 != sha or proposal.signature != payload.signature:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="La confirmación no coincide con la propuesta",
            )
        first_approver = proposal.proposer_hash
        second_approver = actor
        await session.delete(proposal)

    published_at = datetime.now(UTC)
    acta = build_statute_acta(
        artifact=payload.artifact,
        signature=payload.signature,
        artifact_sha256_hex=sha,
        dual_approval={
            "first_approver_hash": first_approver,
            "second_approver_hash": second_approver,
            "required": dual_required,
        },
    )
    tally = StatuteTally(
        organization_id=claims.org_id,
        consultation_id=consultation.id,
        artifact_sha256=sha,
        signature=payload.signature,
        artifact=payload.artifact,
        eligible_member_count=eligible_count,
        voted_member_count=voted_count,
        ballot_count=ballot_count,
        quorum_required=quorum_required,
        quorum_met=quorum_met,
        pilot_override=payload.pilot_override,
        acta=acta,
        first_approver_hash=first_approver,
        second_approver_hash=second_approver,
    )
    session.add(tally)
    consultation.status = "TALLIED"
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="STATUTE_TALLIED",
        actor_id_hash=actor,
        details={
            "consultation_id": str(consultation.id),
            "artifact_sha256": sha,
            "ballot_count": ballot_count,
            "quorum_met": quorum_met,
            "reason": payload.reason,
            "acta_sha256": acta.get("acta_sha256"),
        },
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Esta consulta ya tiene un acta publicada",
        ) from exc
    return {
        "tally_id": tally.id,
        "consultation_id": consultation.id,
        "status": consultation.status,
        "artifact_sha256": sha,
        "published_at": published_at,
        "approval_stage": "confirm" if dual_required else "publish",
        "quorum_met": quorum_met,
        "acta_sha256": acta.get("acta_sha256"),
    }


@router.get("/statutes/{consultation_id}/results")
async def statute_results(
    consultation_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _get_consultation(session, consultation_id, claims.org_id)
    tally = await session.scalar(
        select(StatuteTally).where(
            StatuteTally.consultation_id == consultation.id,
            StatuteTally.organization_id == claims.org_id,
        )
    )
    if tally is None or consultation.status != "TALLIED":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="La consulta todavía no tiene acta publicada",
        )
    return {
        "consultation_id": consultation.id,
        "title": consultation.title,
        "status": consultation.status,
        "artifact_sha256": tally.artifact_sha256,
        "signature": tally.signature,
        "artifact": tally.artifact,
        "acta": tally.acta,
        "quorum_met": tally.quorum_met,
        "ballot_count": tally.ballot_count,
    }


async def _editable(
    session: AsyncSession,
    consultation_id: UUID,
    organization_id: UUID,
) -> StatuteConsultation:
    consultation = await _get_consultation(session, consultation_id, organization_id, lock=True)
    try:
        require_editable(consultation.status)
    except StatuteFlowError as exc:
        raise _flow(exc) from exc
    return consultation


async def _title(
    session: AsyncSession,
    consultation: StatuteConsultation,
    title_id: UUID,
) -> StatuteTitle:
    title = await session.scalar(
        select(StatuteTitle).where(
            StatuteTitle.id == title_id,
            StatuteTitle.consultation_id == consultation.id,
            StatuteTitle.organization_id == consultation.organization_id,
        )
    )
    if title is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Título no encontrado")
    return title


async def _chapter(
    session: AsyncSession,
    consultation: StatuteConsultation,
    chapter_id: UUID,
) -> StatuteChapter:
    chapter = await session.scalar(
        select(StatuteChapter).where(
            StatuteChapter.id == chapter_id,
            StatuteChapter.consultation_id == consultation.id,
            StatuteChapter.organization_id == consultation.organization_id,
        )
    )
    if chapter is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capítulo no encontrado")
    return chapter


async def _article(
    session: AsyncSession,
    consultation: StatuteConsultation,
    article_id: UUID,
) -> StatuteArticle:
    article = await session.scalar(
        select(StatuteArticle).where(
            StatuteArticle.id == article_id,
            StatuteArticle.consultation_id == consultation.id,
            StatuteArticle.organization_id == consultation.organization_id,
        )
    )
    if article is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artículo no encontrado")
    return article


async def _commit_structure(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Ese número ya existe en el estatuto",
        ) from exc


async def _assert_articles_match(
    session: AsyncSession,
    consultation: StatuteConsultation,
    artifact_model: StatuteTallyArtifactModel,
) -> None:
    tree = await load_statute_tree(
        session,
        organization_id=consultation.organization_id,
        consultation_id=consultation.id,
    )
    expected: dict[UUID, dict[str, Any]] = {}
    for title in tree:
        for chapter in title["chapters"]:
            for article in chapter["articles"]:
                expected[article["id"]] = {
                    "number": article["number"],
                    "content": article["content"],
                    "title_number": title["number"],
                    "title_description": title["description"],
                    "chapter_number": chapter["number"],
                    "chapter_description": chapter["description"],
                }
    if {item.article_id for item in artifact_model.articles} != set(expected):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Los artículos del acta no coinciden con el estatuto congelado",
        )
    for item in artifact_model.articles:
        current = expected[item.article_id]
        if (
            item.number != current["number"]
            or item.content != current["content"]
            or item.title_number != current["title_number"]
            or item.title_description != current["title_description"]
            or item.chapter_number != current["chapter_number"]
            or item.chapter_description != current["chapter_description"]
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El texto de un artículo del acta no coincide con el congelado",
            )
        approved = sum(1 for row in item.responses if row.approved)
        rejected = sum(1 for row in item.responses if not row.approved)
        if approved != item.approved_count or rejected != item.rejected_count:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Los conteos de un artículo no cuadran con las respuestas",
            )
        if approved + rejected != artifact_model.ballot_count:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Cada artículo debe tener una respuesta por boleta",
            )
        if item.meets_threshold != article_meets_threshold(
            approved, rejected, consultation.approval_threshold_pct
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="El umbral de aprobación de un artículo no cuadra",
            )


async def _assert_named_responses(
    session: AsyncSession,
    consultation: StatuteConsultation,
    artifact_model: StatuteTallyArtifactModel,
) -> None:
    rows = (
        await session.execute(
            select(Member, StatuteMemberStatus)
            .join(StatuteMemberStatus, StatuteMemberStatus.member_id == Member.id)
            .where(
                StatuteMemberStatus.consultation_id == consultation.id,
                StatuteMemberStatus.organization_id == consultation.organization_id,
                StatuteMemberStatus.eligible.is_(True),
                StatuteMemberStatus.has_voted.is_(True),
            )
        )
    ).all()
    voters = {member.id: member for member, _status in rows}
    for article in artifact_model.articles:
        seen: set[UUID] = set()
        for response in article.responses:
            if response.member_id in seen:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Un artículo repite a un miembro",
                )
            seen.add(response.member_id)
            member = voters.get(response.member_id)
            if member is None or member.full_name != response.full_name:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Una respuesta no corresponde a un miembro que participó",
                )
            registry = member.registry_code or None
            if registry != (response.registry_code or None):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="El código de padrón de una respuesta no coincide",
                )
            if response.approved and response.comment:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Una aprobación no puede traer comentario",
                )
            if not response.approved and not (response.comment and response.comment.strip()):
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Un rechazo debe traer el comentario del miembro",
                )
        if seen != set(voters):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Las respuestas no cubren a quienes participaron",
            )
