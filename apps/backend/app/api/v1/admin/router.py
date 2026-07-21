import hashlib
from datetime import UTC, date, datetime
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile, status
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.tokens import AccessClaims
from app.db.session import get_db_session
from app.models import (
    Election,
    EncryptedBallot,
    Member,
    MemberElectionStatus,
    Organization,
    Position,
)
from app.services.member_spreadsheet import (
    MAX_IMPORT_BYTES,
    MemberImportResult,
    build_member_workbook,
    import_members,
    parse_member_workbook,
)

router = APIRouter(prefix="/admin", tags=["admin"])
ELECTION_MANAGER_ROLES = frozenset({"SUPER_ADMIN", "ELECTORAL_JUSTICE"})
MEMBER_MANAGER_ROLES = frozenset({"SUPER_ADMIN", "ELECTORAL_JUSTICE"})
ElectionStatus = Literal["DRAFT", "REGISTRATION", "FREEZE", "ACTIVE", "CLOSED", "TALLIED"]


class AdminOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_slug: str
    organization_name: str
    roles: list[str] = Field(min_length=1)
    member_count: int = Field(ge=0)
    election_count: int = Field(ge=0)
    encrypted_ballot_count: int = Field(ge=0)


class AdminMemberCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=255)
    full_name: str = Field(min_length=2, max_length=255)
    dni: str = Field(min_length=3, max_length=50, pattern=r"^[A-Za-z0-9._-]+$")
    membership_months: int = Field(default=0, ge=0, le=1200)

    @field_validator("email", "full_name", "dni", mode="before")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()


class AdminMemberResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    registry_code: str | None
    email: str
    full_name: str
    dni: str
    status: str
    member_type: str | None
    membership_months: int
    decade: int | None
    graduation_year: int | None
    semester: str | None
    sex: str | None
    alive: bool | None
    section: str | None
    location: str | None
    mention: str | None
    graduation_date: date | None
    photo_filename: str | None
    photo_content_type: str | None
    photo_size_bytes: int | None
    created_at: datetime


class AdminMemberImportErrorResponse(BaseModel):
    row_number: int
    registry_code: str | None
    message: str


class AdminMemberImportResponse(BaseModel):
    rows_read: int
    created: int
    updated: int
    failed: int
    dry_run: bool
    errors: list[AdminMemberImportErrorResponse]


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


async def _require_member_manager(
    claims: Annotated[AccessClaims, Depends(require_admin)],
) -> AccessClaims:
    if not MEMBER_MANAGER_ROLES.intersection(claims.roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Member management role required",
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


@router.get("/members", response_model=list[AdminMemberResponse])
async def list_admin_members(
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_member_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AdminMemberResponse]:
    """List the administrative roster for the authenticated organization."""
    response.headers["Cache-Control"] = "no-store"
    statement = (
        select(Member)
        .where(Member.organization_id == claims.org_id)
        .order_by(Member.full_name.asc(), Member.created_at.asc())
    )
    members = await session.scalars(statement)
    return [AdminMemberResponse.model_validate(member) for member in members]


@router.post(
    "/members",
    response_model=AdminMemberResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_member(
    payload: AdminMemberCreateRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_member_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminMemberResponse:
    """Create an active roster member inside the authenticated organization."""
    response.headers["Cache-Control"] = "no-store"
    member = Member(
        organization_id=claims.org_id,
        email=payload.email,
        full_name=payload.full_name,
        dni=payload.dni,
        status="ACTIVE",
        membership_months=payload.membership_months,
    )
    session.add(member)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member email or DNI already exists in this organization",
        ) from exc
    await session.refresh(member)
    return AdminMemberResponse.model_validate(member)


@router.post("/members/import", response_model=AdminMemberImportResponse)
async def import_admin_members(
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_member_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[UploadFile, File(...)],
    dry_run: Annotated[bool, Form()] = False,
) -> AdminMemberImportResponse:
    """Import the administrative roster from the documented XLSX contract."""
    response.headers["Cache-Control"] = "no-store"
    if not file.filename or Path(file.filename).suffix.casefold() != ".xlsx":
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Only .xlsx files are supported",
        )
    content = await file.read(MAX_IMPORT_BYTES + 1)
    if len(content) > MAX_IMPORT_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The XLSX file exceeds the 20 MB limit",
        )
    try:
        members, parse_errors, rows_read = parse_member_workbook(content)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    result: MemberImportResult = await import_members(
        session,
        claims.org_id,
        members,
        parse_errors,
        rows_read,
        dry_run,
    )
    return AdminMemberImportResponse(
        rows_read=result.rows_read,
        created=result.created,
        updated=result.updated,
        failed=result.failed,
        dry_run=dry_run,
        errors=[
            AdminMemberImportErrorResponse(
                row_number=error.row_number,
                registry_code=error.registry_code,
                message=error.message,
            )
            for error in result.errors
        ],
    )


@router.get("/members/export")
async def export_admin_members(
    claims: Annotated[AccessClaims, Depends(_require_member_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> StreamingResponse:
    """Export the tenant-scoped roster using the documented XLSX contract."""
    statement = (
        select(Member)
        .where(Member.organization_id == claims.org_id)
        .order_by(Member.full_name.asc(), Member.created_at.asc())
    )
    members = list((await session.scalars(statement)).all())
    workbook = build_member_workbook(members)
    return StreamingResponse(
        workbook,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="padron_administrativo.xlsx"',
        },
    )


@router.post("/members/{member_id}/photo", response_model=AdminMemberResponse)
async def upload_admin_member_photo(
    member_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_member_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    file: Annotated[UploadFile, File(...)],
) -> AdminMemberResponse:
    """Validate and store a member image as PostgreSQL BYTEA."""
    response.headers["Cache-Control"] = "no-store"
    allowed_types = {"image/jpeg", "image/png", "image/webp", "image/gif"}
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Supported photo formats are JPEG, PNG, WEBP and GIF",
        )
    content = await file.read(5 * 1024 * 1024 + 1)
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="The photo exceeds the 5 MB limit",
        )
    try:
        with Image.open(BytesIO(content)) as image:
            image.verify()
    except (UnidentifiedImageError, OSError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The uploaded file is not a valid image",
        ) from exc
    member = await session.scalar(
        select(Member).where(Member.id == member_id, Member.organization_id == claims.org_id)
    )
    if member is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    member.photo_data = content
    member.photo_content_type = file.content_type
    member.photo_filename = Path(file.filename or "member-photo").name[:255]
    member.photo_sha256 = hashlib.sha256(content).hexdigest()
    member.photo_size_bytes = len(content)
    await session.commit()
    await session.refresh(member)
    return AdminMemberResponse.model_validate(member)


@router.get("/members/{member_id}/photo")
async def get_admin_member_photo(
    member_id: UUID,
    claims: Annotated[AccessClaims, Depends(_require_member_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Serve a stored member photo only to an authorized ADMIN tenant."""
    member = await session.scalar(
        select(Member).where(Member.id == member_id, Member.organization_id == claims.org_id)
    )
    if member is None or not member.photo_data or not member.photo_content_type:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Photo not found")
    return Response(
        content=member.photo_data,
        media_type=member.photo_content_type,
        headers={"Cache-Control": "private, no-store"},
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
