from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.tokens import AccessClaims
from app.db.session import get_db_session
from app.models import Election, EncryptedBallot, Member, Organization, Position

router = APIRouter(prefix="/admin", tags=["admin"])
ELECTION_MANAGER_ROLES = frozenset({"SUPER_ADMIN", "ELECTORAL_JUSTICE"})
ElectionStatus = Literal["DRAFT", "REGISTRATION", "FREEZE", "ACTIVE", "CLOSED", "TALLIED"]


class AdminOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_slug: str
    organization_name: str
    roles: list[str] = Field(min_length=1)
    member_count: int = Field(ge=0)
    election_count: int = Field(ge=0)
    encrypted_ballot_count: int = Field(ge=0)


class AdminElectionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=3, max_length=255)
    voting_type: Literal["SLATE_PLURALITY"] = "SLATE_PLURALITY"
    start_time: datetime
    end_time: datetime
    quorum_threshold_pct: Decimal = Field(default=Decimal("30.00"), ge=0, le=100)

    @model_validator(mode="after")
    def validate_schedule(self) -> "AdminElectionCreateRequest":
        for value, field_name in (
            (self.start_time, "start_time"),
            (self.end_time, "end_time"),
        ):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError(f"{field_name} must include a timezone")
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        return self


class AdminElectionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    title: str
    voting_type: str
    start_time: datetime
    end_time: datetime
    quorum_threshold_pct: Decimal
    status: ElectionStatus
    created_at: datetime


class AdminPositionCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=2, max_length=100)
    code: str = Field(min_length=2, max_length=50, pattern=r"^[A-Z][A-Z0-9_-]{1,49}$")
    is_required: bool = True
    display_order: int = Field(default=0, ge=0, le=10000)

    @field_validator("title", mode="before")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        return value.strip()

    @field_validator("code", mode="before")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        return value.strip().upper()


class AdminPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    election_id: UUID
    title: str
    code: str
    is_required: bool
    display_order: int
    created_at: datetime


async def _count_for_organization(
    session: AsyncSession,
    model: type[Member] | type[Election] | type[EncryptedBallot],
    organization_id: UUID,
) -> int:
    statement = (
        select(func.count()).select_from(model).where(model.organization_id == organization_id)
    )
    return int((await session.execute(statement)).scalar_one())


async def _require_election_manager(
    claims: Annotated[AccessClaims, Depends(require_admin)],
) -> AccessClaims:
    if not ELECTION_MANAGER_ROLES.intersection(claims.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Election management role required",
        )
    return claims


async def _get_draft_election(
    session: AsyncSession,
    election_id: UUID,
    organization_id: UUID,
) -> Election:
    election = await session.scalar(
        select(Election).where(
            Election.id == election_id,
            Election.organization_id == organization_id,
        )
    )
    if election is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Election not found",
        )
    if election.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only DRAFT elections can be configured",
        )
    return election


@router.get("/overview", response_model=AdminOverviewResponse)
async def admin_overview(
    response: Response,
    claims: Annotated[AccessClaims, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminOverviewResponse:
    """Return aggregate tenant-scoped data for the ADMIN dashboard."""
    response.headers["Cache-Control"] = "no-store"
    organization = await session.scalar(
        select(Organization).where(Organization.id == claims.org_id)
    )
    if organization is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Organization not found",
        )

    return AdminOverviewResponse(
        organization_slug=organization.slug,
        organization_name=organization.name,
        roles=claims.roles,
        member_count=await _count_for_organization(session, Member, claims.org_id),
        election_count=await _count_for_organization(session, Election, claims.org_id),
        encrypted_ballot_count=await _count_for_organization(
            session, EncryptedBallot, claims.org_id
        ),
    )


@router.get("/elections", response_model=list[AdminElectionResponse])
async def list_admin_elections(
    response: Response,
    claims: Annotated[AccessClaims, Depends(require_admin)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AdminElectionResponse]:
    """List every election belonging to the authenticated ADMIN organization."""
    response.headers["Cache-Control"] = "no-store"
    statement = (
        select(Election)
        .where(Election.organization_id == claims.org_id)
        .order_by(Election.start_time.asc(), Election.created_at.desc())
    )
    elections = await session.scalars(statement)
    return [AdminElectionResponse.model_validate(election) for election in elections]


@router.post(
    "/elections",
    response_model=AdminElectionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_election(
    payload: AdminElectionCreateRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminElectionResponse:
    """Create a tenant-scoped election in DRAFT state."""
    response.headers["Cache-Control"] = "no-store"
    election = Election(
        organization_id=claims.org_id,
        title=payload.title,
        voting_type=payload.voting_type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        quorum_threshold_pct=payload.quorum_threshold_pct,
        status="DRAFT",
    )
    session.add(election)
    await session.commit()
    await session.refresh(election)
    return AdminElectionResponse.model_validate(election)


@router.get(
    "/elections/{election_id}/positions",
    response_model=list[AdminPositionResponse],
)
async def list_admin_positions(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AdminPositionResponse]:
    """List positions only for a DRAFT election in the ADMIN tenant."""
    response.headers["Cache-Control"] = "no-store"
    await _get_draft_election(session, election_id, claims.org_id)
    statement = (
        select(Position)
        .where(Position.election_id == election_id)
        .order_by(Position.display_order.asc(), Position.created_at.asc())
    )
    positions = await session.scalars(statement)
    return [AdminPositionResponse.model_validate(position) for position in positions]


@router.post(
    "/elections/{election_id}/positions",
    response_model=AdminPositionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_position(
    election_id: UUID,
    payload: AdminPositionCreateRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminPositionResponse:
    """Create a position only while its tenant-scoped election is DRAFT."""
    response.headers["Cache-Control"] = "no-store"
    await _get_draft_election(session, election_id, claims.org_id)
    position = Position(
        election_id=election_id,
        title=payload.title,
        code=payload.code,
        is_required=payload.is_required,
        display_order=payload.display_order,
    )
    session.add(position)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Position code already exists for this election",
        ) from exc
    await session.refresh(position)
    return AdminPositionResponse.model_validate(position)
