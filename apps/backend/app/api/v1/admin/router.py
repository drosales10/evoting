import hashlib
from datetime import UTC, date, datetime
from decimal import ROUND_CEILING, Decimal
from io import BytesIO
from pathlib import Path
from typing import Annotated, Any, Literal, cast
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    Header,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from PIL import Image, UnidentifiedImageError
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from sqlalchemy import func, or_, select
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
    ElectionTally,
    ElectionTallyProposal,
    ElectoralRegion,
    ElectoralState,
    EncryptedBallot,
    Member,
    MemberElectionStatus,
    Organization,
    Position,
    Slate,
)
from app.services.audit import append_audit_event
from app.services.csrf import require_csrf
from app.services.member_spreadsheet import (
    MAX_IMPORT_BYTES,
    MemberImportResult,
    build_member_workbook,
    import_members,
    parse_member_workbook,
)
from app.services.tally_acta import build_official_acta
from app.services.tally_artifact import artifact_sha256, verify_artifact

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
    region: str | None = Field(default=None, max_length=120)
    section: str | None = Field(default=None, max_length=120)
    location: str | None = Field(default=None, max_length=120)
    region_id: UUID | None = None
    state_id: UUID | None = None

    @field_validator("email", "full_name", "dni", mode="before")
    @classmethod
    def normalize_text(cls, value: str) -> str:
        return value.strip()

    @field_validator("email", mode="after")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        return value.lower()

    @field_validator("region", "section", "location", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


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
    region: str | None
    region_id: UUID | None = None
    state_id: UUID | None = None
    municipality_id: UUID | None = None
    polling_place_id: UUID | None = None
    mention: str | None
    graduation_date: date | None
    photo_filename: str | None
    photo_content_type: str | None
    photo_size_bytes: int | None
    created_at: datetime


class AdminMemberListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[AdminMemberResponse]
    page: int
    limit: int
    total: int
    total_pages: int


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
    scope_level: Literal["NATIONAL", "REGIONAL", "STATE"] = "NATIONAL"
    region_id: UUID | None = None
    state_id: UUID | None = None

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
        if self.scope_level == "REGIONAL" and self.region_id is None:
            raise ValueError("region_id is required for REGIONAL elections")
        if self.scope_level == "STATE" and self.state_id is None:
            raise ValueError("state_id is required for STATE elections")
        if self.scope_level == "NATIONAL":
            self.region_id = None
            self.state_id = None
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
    scope_level: str = "NATIONAL"
    region_id: UUID | None = None
    state_id: UUID | None = None
    activated_at: datetime | None
    created_at: datetime


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


class AdminElectionActivationRequest(BaseModel):
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


class AdminTallyCount(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slate_id: UUID
    slate_name: str
    votes: int = Field(ge=0)


class AdminTallyArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact_version: Literal["pilot-tally-v1"]
    election_id: UUID
    public_key_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    generated_at: datetime
    eligible_member_count: int = Field(ge=0)
    voted_member_count: int = Field(ge=0)
    quorum_threshold_pct: Decimal = Field(ge=0, le=100)
    quorum_required: int = Field(ge=0)
    quorum_met: bool
    ballot_count: int = Field(ge=0)
    receipt_hashes: list[str]
    counts: list[AdminTallyCount]


class AdminTallyPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact: dict[str, Any]
    signature: str = Field(min_length=32, max_length=8192)
    pilot_override: bool = False
    reason: str = Field(min_length=10, max_length=255)
    approval_stage: Literal["propose", "confirm", "publish"] = "publish"


class AdminTallyPublishResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tally_id: UUID | None = None
    proposal_id: UUID | None = None
    election_id: UUID
    election_status: ElectionStatus
    artifact_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    ballot_count: int = Field(ge=0)
    quorum_met: bool
    pilot_override: bool
    counts: list[AdminTallyCount]
    published_at: datetime | None = None
    approval_stage: Literal["propose", "confirm", "publish"]
    acta_sha256: str | None = None


class AdminElectionAuditResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    event_type: str
    actor_id_hash: str | None
    details: dict[str, Any]
    created_at: datetime
    prev_hash: str | None = None
    entry_hash: str | None = None


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


async def _require_election_mutation(
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    csrf_token: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> AccessClaims:
    await require_csrf(session, claims, csrf_token, realm="ADMIN")
    return claims


def _actor_hash(principal_id: UUID) -> str:
    return hashlib.sha256(str(principal_id).encode("utf-8")).hexdigest()


def _signing_pem(election: Election) -> str:
    return election.signing_public_key or election.public_key or ""


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


@router.get("/members", response_model=AdminMemberListResponse)
async def list_admin_members(
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_member_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    q: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    limit: int = Query(default=25, ge=1, le=200),
    region_id: UUID | None = Query(default=None),
    state_id: UUID | None = Query(default=None),
    sort: str = Query(default="full_name"),
) -> AdminMemberListResponse:
    """List the administrative roster with search, filters and pagination."""
    response.headers["Cache-Control"] = "no-store"
    filters = [Member.organization_id == claims.org_id]
    if q:
        like = f"%{q.strip()}%"
        filters.append(
            or_(
                Member.full_name.ilike(like),
                Member.dni.ilike(like),
                Member.email.ilike(like),
                Member.registry_code.ilike(like),
                Member.region.ilike(like),
                Member.section.ilike(like),
            )
        )
    if region_id:
        filters.append(Member.region_id == region_id)
    if state_id:
        filters.append(Member.state_id == state_id)

    total = int(
        (await session.execute(select(func.count(Member.id)).where(*filters))).scalar_one()
    )
    order = Member.full_name.asc()
    if sort == "created_at":
        order = Member.created_at.desc()
    elif sort == "registry_code":
        order = Member.registry_code.asc()
    statement = (
        select(Member)
        .where(*filters)
        .order_by(order, Member.created_at.asc())
        .offset((page - 1) * limit)
        .limit(limit)
    )
    members = list((await session.scalars(statement)).all())
    total_pages = max(1, (total + limit - 1) // limit) if total else 1
    return AdminMemberListResponse(
        items=[AdminMemberResponse.model_validate(member) for member in members],
        page=page,
        limit=limit,
        total=total,
        total_pages=total_pages,
    )


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
        region=payload.region,
        section=payload.section,
        location=payload.location,
        region_id=payload.region_id,
        state_id=payload.state_id,
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
    if payload.scope_level == "REGIONAL" and payload.region_id:
        region = await session.scalar(
            select(ElectoralRegion).where(
                ElectoralRegion.id == payload.region_id,
                ElectoralRegion.organization_id == claims.org_id,
            )
        )
        if region is None:
            raise HTTPException(status_code=404, detail="Region not found")
    if payload.scope_level == "STATE" and payload.state_id:
        state = await session.scalar(
            select(ElectoralState).where(
                ElectoralState.id == payload.state_id,
                ElectoralState.organization_id == claims.org_id,
            )
        )
        if state is None:
            raise HTTPException(status_code=404, detail="State not found")
    election = Election(
        organization_id=claims.org_id,
        title=payload.title,
        voting_type=payload.voting_type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        quorum_threshold_pct=payload.quorum_threshold_pct,
        status="DRAFT",
        scope_level=payload.scope_level,
        region_id=payload.region_id,
        state_id=payload.state_id,
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

    members_query = select(Member).where(Member.organization_id == claims.org_id)
    if election.scope_level == "REGIONAL" and election.region_id:
        members_query = members_query.where(Member.region_id == election.region_id)
    elif election.scope_level == "STATE" and election.state_id:
        members_query = members_query.where(Member.state_id == election.state_id)
    members = await session.scalars(members_query)
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
    claims: Annotated[AccessClaims, Depends(_require_election_mutation)],
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
    signing_public_key = payload.signing_public_key or public_key
    public_key_sha256 = hashlib.sha256(public_key.encode("utf-8")).hexdigest()
    signing_public_key_sha256 = hashlib.sha256(signing_public_key.encode("utf-8")).hexdigest()
    election.public_key = public_key
    election.signing_public_key = signing_public_key
    election.activated_at = activation_time
    election.status = "ACTIVE"
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="ELECTION_ACTIVATED",
        actor_id_hash=_actor_hash(claims.sub),
        details={
            "election_id": str(election.id),
            "snapshot_member_count": snapshot_member_count,
            "eligible_member_count": eligible_member_count,
            "position_count": len(positions),
            "slate_count": len(slates),
            "candidate_count": candidate_count,
            "public_key_sha256": public_key_sha256,
            "signing_public_key_sha256": signing_public_key_sha256,
            "keys_separated": signing_public_key != public_key,
        },
    )
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="KEY_CEREMONY_OPENED",
        actor_id_hash=_actor_hash(claims.sub),
        details={
            "election_id": str(election.id),
            "public_key_sha256": public_key_sha256,
            "signing_public_key_sha256": signing_public_key_sha256,
        },
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
    claims: Annotated[AccessClaims, Depends(_require_election_mutation)],
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
    if pilot_override and not settings.pilot_overrides_allowed:
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
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="ELECTION_CLOSED",
        actor_id_hash=_actor_hash(claims.sub),
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
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="KEY_CEREMONY_CLOSED",
        actor_id_hash=_actor_hash(claims.sub),
        details={"election_id": str(election.id), "pilot_override": pilot_override},
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
        zkp_verification_available=settings.zkp_verification_enabled,
        can_mark_tallied=election.status == "CLOSED",
    )


@router.post(
    "/elections/{election_id}/tally",
    response_model=AdminTallyPublishResponse,
)
async def publish_tally(
    election_id: UUID,
    payload: AdminTallyPublishRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_mutation)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> AdminTallyPublishResponse:
    """Verify an offline signed tally; optionally require dual approval before TALLIED."""
    response.headers["Cache-Control"] = "no-store"
    election = await session.scalar(
        select(Election)
        .where(Election.id == election_id, Election.organization_id == claims.org_id)
        .with_for_update()
    )
    if election is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Election not found")
    if election.status != "CLOSED":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only CLOSED elections can publish a tally",
        )
    if payload.pilot_override and not settings.pilot_overrides_allowed:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Pilot tally publication is available only in development test mode",
        )
    if await session.scalar(select(ElectionTally).where(ElectionTally.election_id == election.id)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tally has already been published for this election",
        )

    try:
        artifact_model = AdminTallyArtifact.model_validate(payload.artifact)
    except ValueError as exc:
        await append_audit_event(
            session,
            organization_id=claims.org_id,
            event_type="TALLY_VERIFICATION_FAILED",
            actor_id_hash=_actor_hash(claims.sub),
            details={"election_id": str(election.id), "reason": "invalid_artifact"},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid tally artifact",
        ) from exc
    if artifact_model.election_id != election.id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tally artifact election does not match the requested election",
        )
    signing_pem = _signing_pem(election)
    if not signing_pem:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Election public key is not configured",
        )
    expected_public_key_hash = hashlib.sha256(signing_pem.encode("utf-8")).hexdigest()
    # Prefer signing key hash; accept encryption key hash for lab ballots signed with same key.
    allowed_hashes = {expected_public_key_hash}
    if election.public_key:
        allowed_hashes.add(hashlib.sha256(election.public_key.encode("utf-8")).hexdigest())
    if artifact_model.public_key_sha256 not in allowed_hashes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tally artifact public key hash does not match the election",
        )
    try:
        public_key = load_pem_public_key(signing_pem.encode("utf-8"))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Election public key is invalid",
        ) from exc
    if not isinstance(public_key, RSAPublicKey) or not verify_artifact(
        payload.artifact, payload.signature, public_key
    ):
        await append_audit_event(
            session,
            organization_id=claims.org_id,
            event_type="TALLY_VERIFICATION_FAILED",
            actor_id_hash=_actor_hash(claims.sub),
            details={"election_id": str(election.id), "reason": "invalid_signature"},
        )
        await session.commit()
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tally artifact signature is invalid",
        )

    eligible_count, voted_count, ballot_count = await _election_participation_counts(
        session, election.id, claims.org_id
    )
    quorum_required = _required_quorum_votes(eligible_count, election.quorum_threshold_pct)
    quorum_met = voted_count >= quorum_required
    if (
        artifact_model.eligible_member_count != eligible_count
        or artifact_model.voted_member_count != voted_count
        or artifact_model.ballot_count != ballot_count
        or artifact_model.quorum_required != quorum_required
        or artifact_model.quorum_met != quorum_met
        or artifact_model.quorum_threshold_pct != election.quorum_threshold_pct
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tally artifact counts do not match the election snapshot",
        )
    if not quorum_met and not payload.pilot_override:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Quorum is not met; pilot_override is required for this local test tally",
        )

    current_receipts = sorted(
        receipt.lower()
        for receipt in (
            await session.scalars(
                select(EncryptedBallot.receipt_hash).where(
                    EncryptedBallot.election_id == election.id,
                    EncryptedBallot.organization_id == claims.org_id,
                )
            )
        )
    )
    artifact_receipts = sorted(receipt.lower() for receipt in artifact_model.receipt_hashes)
    if artifact_receipts != current_receipts:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tally artifact receipts do not match the encrypted ballot set",
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
    slate_names = {slate.id: slate.name for slate in slates}
    artifact_slate_ids = {item.slate_id for item in artifact_model.counts}
    if artifact_slate_ids != set(slate_names):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tally artifact slate set does not match the election",
        )
    if any(slate_names[item.slate_id] != item.slate_name for item in artifact_model.counts):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tally artifact slate names do not match the election",
        )
    if sum(item.votes for item in artifact_model.counts) != ballot_count:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Tally counts do not sum to the encrypted ballot count",
        )

    sha = artifact_sha256(payload.artifact)
    actor = _actor_hash(claims.sub)
    dual_required = settings.require_dual_tally_approval and not payload.pilot_override
    stage = payload.approval_stage
    if dual_required and stage == "publish":
        stage = "propose"

    if dual_required and stage == "propose":
        existing = await session.scalar(
            select(ElectionTallyProposal).where(ElectionTallyProposal.election_id == election.id)
        )
        if existing is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="A tally proposal already exists for this election",
            )
        proposal = ElectionTallyProposal(
            organization_id=claims.org_id,
            election_id=election.id,
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
            event_type="TALLY_PROPOSED",
            actor_id_hash=actor,
            details={
                "election_id": str(election.id),
                "artifact_sha256": sha,
                "reason": payload.reason,
            },
        )
        await session.commit()
        return AdminTallyPublishResponse(
            proposal_id=proposal.id,
            election_id=election.id,
            election_status=cast(ElectionStatus, election.status),
            artifact_sha256=sha,
            ballot_count=ballot_count,
            quorum_met=quorum_met,
            pilot_override=payload.pilot_override,
            counts=artifact_model.counts,
            approval_stage="propose",
        )

    first_approver = actor
    second_approver: str | None = None
    if dual_required and stage == "confirm":
        proposal = await session.scalar(
            select(ElectionTallyProposal)
            .where(ElectionTallyProposal.election_id == election.id)
            .with_for_update()
        )
        if proposal is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No tally proposal found; propose first",
            )
        if proposal.proposer_hash == actor:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Second approver must be a different administrator",
            )
        if (
            proposal.artifact_sha256 != sha
            or proposal.signature != payload.signature
            or proposal.pilot_override != payload.pilot_override
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Confirm payload does not match the pending proposal",
            )
        first_approver = proposal.proposer_hash
        second_approver = actor
        await session.delete(proposal)

    published_at = datetime.now(UTC)
    acta = build_official_acta(
        artifact=payload.artifact,
        signature=payload.signature,
        artifact_sha256_hex=sha,
        dual_approval={
            "first_approver_hash": first_approver,
            "second_approver_hash": second_approver,
            "required": dual_required,
        },
    )
    tally = ElectionTally(
        organization_id=claims.org_id,
        election_id=election.id,
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
    election.status = "TALLIED"
    await append_audit_event(
        session,
        organization_id=claims.org_id,
        event_type="ELECTION_TALLIED",
        actor_id_hash=actor,
        details={
            "election_id": str(election.id),
            "tally_id": str(tally.id),
            "artifact_sha256": tally.artifact_sha256,
            "ballot_count": ballot_count,
            "quorum_met": quorum_met,
            "pilot_override": payload.pilot_override,
            "reason": payload.reason,
            "acta_sha256": acta.get("acta_sha256"),
            "dual_approval": dual_required,
        },
    )
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A tally has already been published for this election",
        ) from exc
    return AdminTallyPublishResponse(
        tally_id=tally.id,
        election_id=election.id,
        election_status=cast(ElectionStatus, election.status),
        artifact_sha256=tally.artifact_sha256,
        ballot_count=ballot_count,
        quorum_met=quorum_met,
        pilot_override=payload.pilot_override,
        counts=artifact_model.counts,
        published_at=published_at,
        approval_stage="confirm" if dual_required else "publish",
        acta_sha256=str(acta.get("acta_sha256")),
    )


@router.get(
    "/elections/{election_id}/audit",
    response_model=list[AdminElectionAuditResponse],
)
async def list_election_audit(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    event_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[AdminElectionAuditResponse]:
    """Return tenant-scoped audit events with pagination and optional type filter."""
    response.headers["Cache-Control"] = "no-store"
    election = await _get_organization_election(session, election_id, claims.org_id)
    statement = (
        select(AuditLog)
        .where(
            AuditLog.organization_id == claims.org_id,
            AuditLog.details["election_id"].as_string() == str(election.id),
        )
        .order_by(AuditLog.created_at.asc())
        .offset(offset)
        .limit(limit)
    )
    if event_type:
        statement = statement.where(AuditLog.event_type == event_type)
    events = (await session.scalars(statement)).all()
    return [
        AdminElectionAuditResponse(
            id=event.id,
            event_type=event.event_type,
            actor_id_hash=event.actor_id_hash,
            details=event.details or {},
            created_at=event.created_at,
            prev_hash=event.prev_hash,
            entry_hash=event.entry_hash,
        )
        for event in events
    ]


@router.get("/elections/{election_id}/audit/export")
async def export_election_audit(
    election_id: UUID,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """Export election audit events as JSON (append-only snapshot)."""
    events = await list_election_audit(
        election_id, response, claims, session, event_type=None, limit=1000, offset=0
    )
    body = [
        {
            "id": str(item.id),
            "event_type": item.event_type,
            "actor_id_hash": item.actor_id_hash,
            "details": item.details,
            "created_at": item.created_at.isoformat(),
            "prev_hash": item.prev_hash,
            "entry_hash": item.entry_hash,
        }
        for item in events
    ]
    import json

    payload = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
    return Response(
        content=payload,
        media_type="application/json",
        headers={
            "Content-Disposition": f'attachment; filename="audit-{election_id}.json"',
            "Cache-Control": "no-store",
        },
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
