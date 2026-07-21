import hashlib
from datetime import UTC, date, datetime
from decimal import ROUND_CEILING, Decimal
from io import BytesIO
from pathlib import Path
from typing import Annotated, Literal, cast
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.tokens import AccessClaims
from app.core.config import settings
from app.db.session import get_db_session
from app.models import (
    AuditLog,
    Candidate,
    Election,
    EncryptedBallot,
    Member,
    MemberElectionStatus,
    Organization,
    Position,
    Slate,
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
    activated_at: datetime | None
    created_at: datetime


class AdminElectionActivationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_key: str = Field(min_length=16, max_length=8192)

    @field_validator("public_key", mode="before")
    @classmethod
    def normalize_public_key(cls, value: str) -> str:
        return value.strip()

    @field_validator("public_key", mode="after")
    @classmethod
    def validate_public_key_pem(cls, value: str) -> str:
        if "-----BEGIN PUBLIC KEY-----" not in value or "-----END PUBLIC KEY-----" not in value:
            raise ValueError("public_key must be an RSA SubjectPublicKeyInfo PEM")
        try:
            public_key = load_pem_public_key(value.encode())
        except ValueError as exc:
            raise ValueError("public_key is not valid PEM key material") from exc
        if not isinstance(public_key, RSAPublicKey):
            raise ValueError("public_key must contain an RSA public key")
        return value


class AdminElectionActivationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    election_id: UUID
    election_status: ElectionStatus
    activated_at: datetime
    snapshot_member_count: int = Field(ge=0)
    eligible_member_count: int = Field(ge=0)
    position_count: int = Field(ge=1)
    slate_count: int = Field(ge=1)
    candidate_count: int = Field(ge=1)
    public_key_sha256: str = Field(min_length=64, max_length=64)


class AdminElectionCloseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    force_pilot: bool = False
    reason: str = Field(min_length=10, max_length=255)


class AdminElectionCloseResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    election_id: UUID
    election_status: ElectionStatus
    closed_at: datetime
    eligible_member_count: int = Field(ge=0)
    voted_member_count: int = Field(ge=0)
    ballot_count: int = Field(ge=0)
    quorum_threshold_pct: Decimal
    quorum_required: int = Field(ge=0)
    quorum_met: bool
    pilot_override: bool


class AdminTallyReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    election_id: UUID
    election_status: ElectionStatus
    eligible_member_count: int = Field(ge=0)
    voted_member_count: int = Field(ge=0)
    ballot_count: int = Field(ge=0)
    quorum_threshold_pct: Decimal
    quorum_required: int = Field(ge=0)
    quorum_met: bool
    public_key_sha256: str | None
    requires_offline_private_key: bool
    zkp_verification_available: bool
    can_mark_tallied: bool


class AdminElectionEligibilityResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    election_id: UUID
    election_status: ElectionStatus
    snapshot_member_count: int = Field(ge=0)
    eligible_member_count: int = Field(ge=0)
    ineligible_member_count: int = Field(ge=0)


class AdminElectionEligibilityMemberResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    member_id: UUID
    registry_code: str | None
    full_name: str
    dni: str
    email: str
    status: str
    alive: bool | None
    eligible: bool
    reason: str


class AdminSlateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=150)
    slogan: str | None = Field(default=None, max_length=255)
    proxy_member_id: UUID | None = None

    @field_validator("name", "slogan", mode="before")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class AdminSlateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    organization_id: UUID
    election_id: UUID
    name: str
    slogan: str | None
    proxy_member_id: UUID | None
    status: str
    candidate_count: int = Field(ge=0)
    created_at: datetime


class AdminCandidateCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    position_id: UUID
    member_id: UUID
    bio: str | None = Field(default=None, max_length=5000)

    @field_validator("bio", mode="before")
    @classmethod
    def normalize_bio(cls, value: str | None) -> str | None:
        return value.strip() if value is not None else None


class AdminCandidateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    slate_id: UUID
    position_id: UUID
    position_code: str
    position_title: str
    member_id: UUID
    member_registry_code: str | None
    member_full_name: str
    member_dni: str
    bio: str | None
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


def _eligibility_reason(status_value: str, alive: bool | None, eligible: bool) -> str:
    if eligible:
        return "Cumple: miembro ACTIVE y Vivo confirmado"
    if status_value != "ACTIVE":
        return "Miembro INACTIVE"
    if alive is False:
        return "Vivo marcado como 0"
    return "Vivo no confirmado"


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


async def _get_organization_election(
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
    return election


async def _eligibility_counts(
    session: AsyncSession,
    election_id: UUID,
    organization_id: UUID,
    election_status: ElectionStatus,
) -> AdminElectionEligibilityResponse:
    snapshot_member_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(MemberElectionStatus)
                .where(
                    MemberElectionStatus.election_id == election_id,
                    MemberElectionStatus.organization_id == organization_id,
                )
            )
        ).scalar_one()
    )
    eligible_member_count = int(
        (
            await session.execute(
                select(func.count())
                .select_from(MemberElectionStatus)
                .where(
                    MemberElectionStatus.election_id == election_id,
                    MemberElectionStatus.organization_id == organization_id,
                    MemberElectionStatus.eligible.is_(True),
                )
            )
        ).scalar_one()
    )
    return AdminElectionEligibilityResponse(
        election_id=election_id,
        election_status=election_status,
        snapshot_member_count=snapshot_member_count,
        eligible_member_count=eligible_member_count,
        ineligible_member_count=snapshot_member_count - eligible_member_count,
    )


async def _get_slate_and_election(
    session: AsyncSession,
    slate_id: UUID,
    organization_id: UUID,
    allow_freeze: bool,
) -> tuple[Slate, Election]:
    slate = await session.scalar(
        select(Slate).where(
            Slate.id == slate_id,
            Slate.organization_id == organization_id,
        )
    )
    if slate is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Slate not found")
    election = await _get_organization_election(session, slate.election_id, organization_id)
    allowed_states = {"REGISTRATION", "FREEZE"} if allow_freeze else {"REGISTRATION"}
    if election.status not in allowed_states:
        expected = "REGISTRATION or FREEZE" if allow_freeze else "REGISTRATION"
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Slate operation requires election state {expected}",
        )
    return slate, election


async def _candidate_count(session: AsyncSession, slate_id: UUID) -> int:
    return int(
        (
            await session.execute(
                select(func.count()).select_from(Candidate).where(Candidate.slate_id == slate_id)
            )
        ).scalar_one()
    )


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
    election = await _get_organization_election(session, election_id, claims.org_id)
    if election.status not in {"DRAFT", "REGISTRATION", "FREEZE"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Positions can only be reviewed before election activation",
        )
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


@router.post(
    "/elections/{election_id}/open-registration",
    response_model=AdminElectionEligibilityResponse,
)
async def open_election_registration(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminElectionEligibilityResponse:
    """Open registration and snapshot tenant-scoped member eligibility."""
    response.headers["Cache-Control"] = "no-store"
    election = await _get_organization_election(session, election_id, claims.org_id)
    if election.status != "DRAFT":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only DRAFT elections can open registration",
        )

    members = await session.scalars(select(Member).where(Member.organization_id == claims.org_id))
    for member in members:
        member_eligible = member.status == "ACTIVE" and member.alive is True
        session.add(
            MemberElectionStatus(
                organization_id=claims.org_id,
                election_id=election.id,
                member_id=member.id,
                eligible=member_eligible,
                eligibility_reason=_eligibility_reason(
                    member.status, member.alive, member_eligible
                ),
                has_voted=False,
            )
        )
    election.status = "REGISTRATION"
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Eligibility snapshot already exists for this election",
        ) from exc
    return await _eligibility_counts(
        session, election.id, claims.org_id, cast(ElectionStatus, election.status)
    )


@router.post(
    "/elections/{election_id}/freeze",
    response_model=AdminElectionEligibilityResponse,
)
async def freeze_election_roster(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminElectionEligibilityResponse:
    """Freeze the registration snapshot without changing the anonymous ballot model."""
    response.headers["Cache-Control"] = "no-store"
    election = await _get_organization_election(session, election_id, claims.org_id)
    if election.status != "REGISTRATION":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only REGISTRATION elections can be frozen",
        )
    election.status = "FREEZE"
    election.frozen_at = datetime.now(UTC)
    await session.commit()
    return await _eligibility_counts(
        session, election.id, claims.org_id, cast(ElectionStatus, election.status)
    )


@router.post(
    "/elections/{election_id}/activate",
    response_model=AdminElectionActivationResponse,
)
async def activate_election(
    election_id: UUID,
    payload: AdminElectionActivationRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminElectionActivationResponse:
    """Open a frozen election after validating its immutable voting material."""
    response.headers["Cache-Control"] = "no-store"
    election = await session.scalar(
        select(Election)
        .where(Election.id == election_id, Election.organization_id == claims.org_id)
        .with_for_update()
    )
    if election is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Election not found")
    if election.status != "FREEZE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only FREEZE elections can be activated",
        )

    activation_time = datetime.now(UTC)
    if election.start_time > activation_time:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Election cannot be activated before its scheduled start time",
        )
    if election.end_time <= activation_time:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Election end time has already passed",
        )

    snapshot_member_count, eligible_member_count = (
        int(value)
        for value in (
            await session.execute(
                select(
                    func.count(MemberElectionStatus.id),
                    func.count(MemberElectionStatus.id).filter(
                        MemberElectionStatus.eligible.is_(True)
                    ),
                ).where(
                    MemberElectionStatus.election_id == election.id,
                    MemberElectionStatus.organization_id == claims.org_id,
                )
            )
        ).one()
    )
    current_member_count = int(
        (
            await session.execute(
                select(func.count(Member.id)).where(Member.organization_id == claims.org_id)
            )
        ).scalar_one()
    )
    if snapshot_member_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Election has no eligibility snapshot",
        )
    if snapshot_member_count != current_member_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member roster changed after freeze; review and recreate the election",
        )
    if eligible_member_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Election has no eligible members",
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
    if not positions:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Election requires at least one position before activation",
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
    if not slates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Election requires at least one slate before activation",
        )

    candidate_rows = (
        await session.execute(
            select(Candidate.slate_id, Candidate.position_id)
            .join(Slate, Slate.id == Candidate.slate_id)
            .where(
                Slate.organization_id == claims.org_id,
                Slate.election_id == election.id,
            )
        )
    ).all()
    candidates_by_slate: dict[UUID, set[UUID]] = {}
    for slate_id, position_id in candidate_rows:
        candidates_by_slate.setdefault(slate_id, set()).add(position_id)
    required_position_ids = {position.id for position in positions if position.is_required}
    incomplete_slates = [
        slate.name
        for slate in slates
        if not required_position_ids.issubset(candidates_by_slate.get(slate.id, set()))
    ]
    if incomplete_slates:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Every slate must have a candidate for each required position",
        )
    candidate_count = len(candidate_rows)
    if candidate_count == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Election requires at least one candidate before activation",
        )

    public_key = payload.public_key
    public_key_sha256 = hashlib.sha256(public_key.encode("utf-8")).hexdigest()
    election.public_key = public_key
    election.activated_at = activation_time
    election.status = "ACTIVE"
    session.add(
        AuditLog(
            organization_id=claims.org_id,
            event_type="ELECTION_ACTIVATED",
            actor_id_hash=hashlib.sha256(str(claims.sub).encode("utf-8")).hexdigest(),
            details={
                "election_id": str(election.id),
                "snapshot_member_count": snapshot_member_count,
                "eligible_member_count": eligible_member_count,
                "position_count": len(positions),
                "slate_count": len(slates),
                "candidate_count": candidate_count,
                "public_key_sha256": public_key_sha256,
            },
        )
    )
    await session.commit()
    return AdminElectionActivationResponse(
        election_id=election.id,
        election_status=cast(ElectionStatus, election.status),
        activated_at=activation_time,
        snapshot_member_count=snapshot_member_count,
        eligible_member_count=eligible_member_count,
        position_count=len(positions),
        slate_count=len(slates),
        candidate_count=candidate_count,
        public_key_sha256=public_key_sha256,
    )


def _required_quorum_votes(eligible_member_count: int, threshold_pct: Decimal) -> int:
    if eligible_member_count <= 0 or threshold_pct <= 0:
        return 0
    required = (Decimal(eligible_member_count) * threshold_pct / Decimal("100")).to_integral_value(
        rounding=ROUND_CEILING
    )
    return int(required)


async def _election_participation_counts(
    session: AsyncSession,
    election_id: UUID,
    organization_id: UUID,
) -> tuple[int, int, int]:
    eligible_count, voted_count = (
        int(value)
        for value in (
            await session.execute(
                select(
                    func.count(MemberElectionStatus.id),
                    func.count(MemberElectionStatus.id).filter(
                        MemberElectionStatus.has_voted.is_(True)
                    ),
                ).where(
                    MemberElectionStatus.election_id == election_id,
                    MemberElectionStatus.organization_id == organization_id,
                    MemberElectionStatus.eligible.is_(True),
                )
            )
        ).one()
    )
    ballot_count = int(
        (
            await session.execute(
                select(func.count(EncryptedBallot.id)).where(
                    EncryptedBallot.election_id == election_id,
                    EncryptedBallot.organization_id == organization_id,
                )
            )
        ).scalar_one()
    )
    return eligible_count, voted_count, ballot_count


@router.post(
    "/elections/{election_id}/close",
    response_model=AdminElectionCloseResponse,
)
async def close_election(
    election_id: UUID,
    payload: AdminElectionCloseRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminElectionCloseResponse:
    """Close an election after quorum, or explicitly close the local pilot."""
    response.headers["Cache-Control"] = "no-store"
    election = await session.scalar(
        select(Election)
        .where(Election.id == election_id, Election.organization_id == claims.org_id)
        .with_for_update()
    )
    if election is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Election not found")
    if election.status != "ACTIVE":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only ACTIVE elections can be closed",
        )

    eligible_count, voted_count, ballot_count = await _election_participation_counts(
        session, election.id, claims.org_id
    )
    quorum_required = _required_quorum_votes(eligible_count, election.quorum_threshold_pct)
    quorum_met = voted_count >= quorum_required
    pilot_override = payload.force_pilot
    pilot_override_allowed = settings.environment == "development" and settings.voter_test_mode
    if pilot_override and not pilot_override_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pilot closure is available only in development test mode",
        )
    if ballot_count != voted_count:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Participation and encrypted ballot counts do not match",
        )
    if not pilot_override and election.end_time > datetime.now(UTC):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Election voting window is still open",
        )
    if not quorum_met and not pilot_override:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Quorum not met: {voted_count} votes received; " f"{quorum_required} required"
            ),
        )

    closed_at = datetime.now(UTC)
    election.status = "CLOSED"
    session.add(
        AuditLog(
            organization_id=claims.org_id,
            event_type="ELECTION_CLOSED",
            actor_id_hash=hashlib.sha256(str(claims.sub).encode("utf-8")).hexdigest(),
            details={
                "election_id": str(election.id),
                "eligible_member_count": eligible_count,
                "voted_member_count": voted_count,
                "ballot_count": ballot_count,
                "quorum_threshold_pct": str(election.quorum_threshold_pct),
                "quorum_required": quorum_required,
                "quorum_met": quorum_met,
                "pilot_override": pilot_override,
                "reason": payload.reason,
            },
        )
    )
    await session.commit()
    return AdminElectionCloseResponse(
        election_id=election.id,
        election_status=cast(ElectionStatus, election.status),
        closed_at=closed_at,
        eligible_member_count=eligible_count,
        voted_member_count=voted_count,
        ballot_count=ballot_count,
        quorum_threshold_pct=election.quorum_threshold_pct,
        quorum_required=quorum_required,
        quorum_met=quorum_met,
        pilot_override=pilot_override,
    )


@router.get(
    "/elections/{election_id}/tally-readiness",
    response_model=AdminTallyReadinessResponse,
)
async def get_tally_readiness(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminTallyReadinessResponse:
    """Report tally prerequisites without decrypting or exposing ballot contents."""
    response.headers["Cache-Control"] = "no-store"
    election = await _get_organization_election(session, election_id, claims.org_id)
    eligible_count, voted_count, ballot_count = await _election_participation_counts(
        session, election.id, claims.org_id
    )
    quorum_required = _required_quorum_votes(eligible_count, election.quorum_threshold_pct)
    public_key_sha256 = (
        hashlib.sha256(election.public_key.encode("utf-8")).hexdigest()
        if election.public_key
        else None
    )
    return AdminTallyReadinessResponse(
        election_id=election.id,
        election_status=cast(ElectionStatus, election.status),
        eligible_member_count=eligible_count,
        voted_member_count=voted_count,
        ballot_count=ballot_count,
        quorum_threshold_pct=election.quorum_threshold_pct,
        quorum_required=quorum_required,
        quorum_met=voted_count >= quorum_required,
        public_key_sha256=public_key_sha256,
        requires_offline_private_key=True,
        zkp_verification_available=False,
        can_mark_tallied=False,
    )


@router.get(
    "/elections/{election_id}/eligibility",
    response_model=AdminElectionEligibilityResponse,
)
async def get_election_eligibility(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminElectionEligibilityResponse:
    """Return aggregate eligibility counts without exposing member identity."""
    response.headers["Cache-Control"] = "no-store"
    election = await _get_organization_election(session, election_id, claims.org_id)
    return await _eligibility_counts(
        session, election.id, claims.org_id, cast(ElectionStatus, election.status)
    )


@router.get(
    "/elections/{election_id}/eligibility/members",
    response_model=list[AdminElectionEligibilityMemberResponse],
)
async def list_election_eligibility_members(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    eligible: bool | None = Query(default=None),
) -> list[AdminElectionEligibilityMemberResponse]:
    """List tenant-scoped snapshot eligibility details for ADMIN review."""
    response.headers["Cache-Control"] = "no-store"
    await _get_organization_election(session, election_id, claims.org_id)
    statement = (
        select(MemberElectionStatus, Member)
        .join(Member, Member.id == MemberElectionStatus.member_id)
        .where(
            MemberElectionStatus.election_id == election_id,
            MemberElectionStatus.organization_id == claims.org_id,
            Member.organization_id == claims.org_id,
        )
        .order_by(Member.full_name.asc(), Member.created_at.asc())
    )
    if eligible is not None:
        statement = statement.where(MemberElectionStatus.eligible.is_(eligible))
    rows = (await session.execute(statement)).all()
    return [
        AdminElectionEligibilityMemberResponse(
            member_id=member.id,
            registry_code=member.registry_code,
            full_name=member.full_name,
            dni=member.dni,
            email=member.email,
            status=member.status,
            alive=member.alive,
            eligible=snapshot.eligible,
            reason=snapshot.eligibility_reason
            or _eligibility_reason(member.status, member.alive, snapshot.eligible),
        )
        for snapshot, member in rows
    ]


@router.get(
    "/elections/{election_id}/slates",
    response_model=list[AdminSlateResponse],
)
async def list_admin_slates(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AdminSlateResponse]:
    """List tenant-scoped slates during registration or after freeze."""
    response.headers["Cache-Control"] = "no-store"
    election = await _get_organization_election(session, election_id, claims.org_id)
    if election.status not in {"REGISTRATION", "FREEZE"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slate review requires election state REGISTRATION or FREEZE",
        )
    statement = (
        select(Slate, func.count(Candidate.id))
        .outerjoin(Candidate, Candidate.slate_id == Slate.id)
        .where(
            Slate.organization_id == claims.org_id,
            Slate.election_id == election.id,
        )
        .group_by(Slate.id)
        .order_by(Slate.created_at.asc())
    )
    rows = (await session.execute(statement)).all()
    return [
        AdminSlateResponse(
            id=slate.id,
            organization_id=slate.organization_id,
            election_id=slate.election_id,
            name=slate.name,
            slogan=slate.slogan,
            proxy_member_id=slate.proxy_member_id,
            status=slate.status,
            candidate_count=int(candidate_count),
            created_at=slate.created_at,
        )
        for slate, candidate_count in rows
    ]


@router.post(
    "/elections/{election_id}/slates",
    response_model=AdminSlateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_slate(
    election_id: UUID,
    payload: AdminSlateCreateRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminSlateResponse:
    """Create a slate only while the tenant election is in REGISTRATION."""
    response.headers["Cache-Control"] = "no-store"
    election = await _get_organization_election(session, election_id, claims.org_id)
    if election.status != "REGISTRATION":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slate creation requires election state REGISTRATION",
        )
    if payload.proxy_member_id is not None:
        proxy_member = await session.scalar(
            select(Member).where(
                Member.id == payload.proxy_member_id,
                Member.organization_id == claims.org_id,
            )
        )
        if proxy_member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Proxy member not found",
            )
    slate = Slate(
        organization_id=claims.org_id,
        election_id=election.id,
        name=payload.name,
        slogan=payload.slogan,
        proxy_member_id=payload.proxy_member_id,
        status="PENDING",
    )
    session.add(slate)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Slate name already exists for this election",
        ) from exc
    await session.refresh(slate)
    return AdminSlateResponse(
        id=slate.id,
        organization_id=slate.organization_id,
        election_id=slate.election_id,
        name=slate.name,
        slogan=slate.slogan,
        proxy_member_id=slate.proxy_member_id,
        status=slate.status,
        candidate_count=0,
        created_at=slate.created_at,
    )


@router.get(
    "/slates/{slate_id}/candidates",
    response_model=list[AdminCandidateResponse],
)
async def list_admin_candidates(
    slate_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[AdminCandidateResponse]:
    """List candidates for an organization-owned slate in registration or freeze."""
    response.headers["Cache-Control"] = "no-store"
    slate, _ = await _get_slate_and_election(session, slate_id, claims.org_id, allow_freeze=True)
    statement = (
        select(Candidate, Position, Member)
        .join(Position, Position.id == Candidate.position_id)
        .join(Member, Member.id == Candidate.member_id)
        .where(
            Candidate.slate_id == slate.id,
            Position.election_id == slate.election_id,
            Member.organization_id == claims.org_id,
        )
        .order_by(Position.display_order.asc(), Candidate.created_at.asc())
    )
    rows = (await session.execute(statement)).all()
    return [
        AdminCandidateResponse(
            id=candidate.id,
            slate_id=candidate.slate_id,
            position_id=position.id,
            position_code=position.code,
            position_title=position.title,
            member_id=member.id,
            member_registry_code=member.registry_code,
            member_full_name=member.full_name,
            member_dni=member.dni,
            bio=candidate.bio,
            created_at=candidate.created_at,
        )
        for candidate, position, member in rows
    ]


@router.post(
    "/slates/{slate_id}/candidates",
    response_model=AdminCandidateResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_admin_candidate(
    slate_id: UUID,
    payload: AdminCandidateCreateRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminCandidateResponse:
    """Register an eligible member for a slate position during REGISTRATION."""
    response.headers["Cache-Control"] = "no-store"
    slate, election = await _get_slate_and_election(
        session, slate_id, claims.org_id, allow_freeze=False
    )
    position = await session.scalar(
        select(Position).where(
            Position.id == payload.position_id,
            Position.election_id == election.id,
        )
    )
    if position is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Position not found")
    member = await session.scalar(
        select(Member).where(
            Member.id == payload.member_id,
            Member.organization_id == claims.org_id,
        )
    )
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate member not found",
        )
    eligibility = await session.scalar(
        select(MemberElectionStatus).where(
            MemberElectionStatus.election_id == election.id,
            MemberElectionStatus.organization_id == claims.org_id,
            MemberElectionStatus.member_id == member.id,
        )
    )
    if eligibility is None or not eligibility.eligible:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Candidate member is not eligible for this election",
        )
    candidate = Candidate(
        slate_id=slate.id,
        position_id=position.id,
        member_id=member.id,
        bio=payload.bio,
    )
    session.add(candidate)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This slate already has a candidate for the selected position",
        ) from exc
    await session.refresh(candidate)
    return AdminCandidateResponse(
        id=candidate.id,
        slate_id=candidate.slate_id,
        position_id=position.id,
        position_code=position.code,
        position_title=position.title,
        member_id=member.id,
        member_registry_code=member.registry_code,
        member_full_name=member.full_name,
        member_dni=member.dni,
        bio=candidate.bio,
        created_at=candidate.created_at,
    )
