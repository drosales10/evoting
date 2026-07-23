"""Admin APIs for election ceremony YouTube broadcasts."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.tokens import AccessClaims
from app.db.session import get_db_session
from app.models import Election, ElectionBroadcast
from app.services.audit import append_audit_event
from app.services.csrf import require_csrf
from app.services.youtube import YouTubeUrlError, extract_youtube_video_id, youtube_embed_url

router = APIRouter(prefix="/admin", tags=["admin-broadcast"])

ELECTION_MANAGER_ROLES = frozenset({"SUPER_ADMIN", "ELECTORAL_JUSTICE"})
BroadcastStatus = Literal["SCHEDULED", "LIVE", "ENDED", "ARCHIVED"]
MilestoneType = Literal["CLOSE", "KEY_COMPARE", "PUBLISH", "GEO_ACTIVE"]


class BroadcastMilestone(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: MilestoneType
    label: str
    at: datetime
    note: str | None = None


class BroadcastUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    youtube_url: str = Field(min_length=8, max_length=2048)
    title: str = Field(min_length=3, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    scheduled_start_at: datetime | None = None

    @field_validator("youtube_url", "title", mode="before")
    @classmethod
    def strip_required(cls, value: str) -> str:
        return value.strip()

    @field_validator("description", mode="before")
    @classmethod
    def strip_optional(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class BroadcastStatusRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: BroadcastStatus


class BroadcastMilestoneRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: MilestoneType
    note: str | None = Field(default=None, max_length=1000)

    @field_validator("note", mode="before")
    @classmethod
    def strip_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class BroadcastResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    election_id: UUID
    youtube_url: str
    youtube_video_id: str
    embed_url: str
    title: str
    description: str | None
    status: BroadcastStatus
    scheduled_start_at: datetime | None
    went_live_at: datetime | None
    ended_at: datetime | None
    artifact_sha256: str | None
    milestones: list[BroadcastMilestone]
    has_key_compare_milestone: bool
    created_at: datetime
    updated_at: datetime


_MILESTONE_LABELS: dict[str, str] = {
    "CLOSE": "Cierre de votación",
    "KEY_COMPARE": "Comparación de claves (offline)",
    "PUBLISH": "Publicación de resultados",
    "GEO_ACTIVE": "Activación en geovisor",
}


def _actor_hash(principal_id: UUID) -> str:
    import hashlib

    return hashlib.sha256(str(principal_id).encode("utf-8")).hexdigest()


async def _require_election_manager(
    claims: Annotated[AccessClaims, Depends(require_admin)],
) -> AccessClaims:
    if not ELECTION_MANAGER_ROLES.intersection(claims.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Election management role required",
        )
    return claims


async def _require_election_mutation(
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> AccessClaims:
    await require_csrf(session, claims, csrf_token, realm="ADMIN")
    return claims


async def _get_org_election(
    session: AsyncSession, election_id: UUID, organization_id: UUID
) -> Election:
    election = await session.scalar(
        select(Election).where(
            Election.id == election_id,
            Election.organization_id == organization_id,
        )
    )
    if election is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Election not found")
    return election


def _parse_milestones(raw: Any) -> list[BroadcastMilestone]:
    if not isinstance(raw, list):
        return []
    items: list[BroadcastMilestone] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        try:
            items.append(BroadcastMilestone.model_validate(entry))
        except Exception:
            continue
    return items


def serialize_broadcast(row: ElectionBroadcast) -> BroadcastResponse:
    milestones = _parse_milestones(row.milestones)
    return BroadcastResponse(
        id=row.id,
        election_id=row.election_id,
        youtube_url=row.youtube_url,
        youtube_video_id=row.youtube_video_id,
        embed_url=youtube_embed_url(row.youtube_video_id),
        title=row.title,
        description=row.description,
        status=row.status,  # type: ignore[arg-type]
        scheduled_start_at=row.scheduled_start_at,
        went_live_at=row.went_live_at,
        ended_at=row.ended_at,
        artifact_sha256=row.artifact_sha256,
        milestones=milestones,
        has_key_compare_milestone=any(m.type == "KEY_COMPARE" for m in milestones),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def append_milestone(
    row: ElectionBroadcast,
    *,
    milestone_type: MilestoneType,
    note: str | None = None,
    at: datetime | None = None,
) -> BroadcastMilestone:
    milestones = list(row.milestones or [])
    # Keep a single entry per type (latest wins).
    milestones = [m for m in milestones if not (isinstance(m, dict) and m.get("type") == milestone_type)]
    entry = {
        "type": milestone_type,
        "label": _MILESTONE_LABELS[milestone_type],
        "at": (at or datetime.now(UTC)).isoformat(),
        "note": note,
    }
    milestones.append(entry)
    row.milestones = milestones
    row.updated_at = datetime.now(UTC)
    return BroadcastMilestone.model_validate(entry)


async def get_broadcast_for_election(
    session: AsyncSession, election_id: UUID, organization_id: UUID
) -> ElectionBroadcast | None:
    return await session.scalar(
        select(ElectionBroadcast).where(
            ElectionBroadcast.election_id == election_id,
            ElectionBroadcast.organization_id == organization_id,
        )
    )


@router.get("/elections/{election_id}/broadcast", response_model=BroadcastResponse)
async def get_election_broadcast(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BroadcastResponse:
    response.headers["Cache-Control"] = "no-store"
    await _get_org_election(session, election_id, claims.org_id)
    row = await get_broadcast_for_election(session, election_id, claims.org_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broadcast not found")
    return serialize_broadcast(row)


@router.put("/elections/{election_id}/broadcast", response_model=BroadcastResponse)
async def upsert_election_broadcast(
    election_id: UUID,
    payload: BroadcastUpsertRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BroadcastResponse:
    response.headers["Cache-Control"] = "no-store"
    await _get_org_election(session, election_id, claims.org_id)
    try:
        video_id = extract_youtube_video_id(payload.youtube_url)
    except YouTubeUrlError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    row = await get_broadcast_for_election(session, election_id, claims.org_id)
    created = row is None
    if row is None:
        row = ElectionBroadcast(
            organization_id=claims.org_id,
            election_id=election_id,
            youtube_url=payload.youtube_url.strip(),
            youtube_video_id=video_id,
            title=payload.title,
            description=payload.description,
            status="SCHEDULED",
            scheduled_start_at=payload.scheduled_start_at,
            milestones=[],
        )
        session.add(row)
    else:
        row.youtube_url = payload.youtube_url.strip()
        row.youtube_video_id = video_id
        row.title = payload.title
        row.description = payload.description
        row.scheduled_start_at = payload.scheduled_start_at
        row.updated_at = datetime.now(UTC)

    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="BROADCAST_SCHEDULED" if created else "BROADCAST_UPDATED",
        actor_id_hash=_actor_hash(claims.sub),
        details={
            "election_id": str(election_id),
            "broadcast_id": str(row.id),
            "youtube_video_id": video_id,
            "status": row.status,
        },
    )
    await session.commit()
    await session.refresh(row)
    return serialize_broadcast(row)


@router.post("/elections/{election_id}/broadcast/status", response_model=BroadcastResponse)
async def set_broadcast_status(
    election_id: UUID,
    payload: BroadcastStatusRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BroadcastResponse:
    response.headers["Cache-Control"] = "no-store"
    await _get_org_election(session, election_id, claims.org_id)
    row = await get_broadcast_for_election(session, election_id, claims.org_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broadcast not found")

    now = datetime.now(UTC)
    row.status = payload.status
    row.updated_at = now
    if payload.status == "LIVE" and row.went_live_at is None:
        row.went_live_at = now
    if payload.status in {"ENDED", "ARCHIVED"} and row.ended_at is None:
        row.ended_at = now

    event_type = {
        "SCHEDULED": "BROADCAST_SCHEDULED",
        "LIVE": "BROADCAST_LIVE",
        "ENDED": "BROADCAST_ENDED",
        "ARCHIVED": "BROADCAST_ENDED",
    }[payload.status]
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type=event_type,
        actor_id_hash=_actor_hash(claims.sub),
        details={
            "election_id": str(election_id),
            "broadcast_id": str(row.id),
            "status": payload.status,
        },
    )
    await session.commit()
    await session.refresh(row)
    return serialize_broadcast(row)


@router.post("/elections/{election_id}/broadcast/milestones", response_model=BroadcastResponse)
async def add_broadcast_milestone(
    election_id: UUID,
    payload: BroadcastMilestoneRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> BroadcastResponse:
    response.headers["Cache-Control"] = "no-store"
    await _get_org_election(session, election_id, claims.org_id)
    row = await get_broadcast_for_election(session, election_id, claims.org_id)
    if row is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Broadcast not found")

    milestone = append_milestone(row, milestone_type=payload.type, note=payload.note)
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="BROADCAST_MILESTONE",
        actor_id_hash=_actor_hash(claims.sub),
        details={
            "election_id": str(election_id),
            "broadcast_id": str(row.id),
            "milestone_type": milestone.type,
            "note": milestone.note,
        },
    )
    await session.commit()
    await session.refresh(row)
    return serialize_broadcast(row)
