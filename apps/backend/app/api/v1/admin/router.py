from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.tokens import AccessClaims
from app.db.session import get_db_session
from app.models import Election, EncryptedBallot, Member, Organization

router = APIRouter(prefix="/admin", tags=["admin"])


class AdminOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_slug: str
    organization_name: str
    roles: list[str] = Field(min_length=1)
    member_count: int = Field(ge=0)
    election_count: int = Field(ge=0)
    encrypted_ballot_count: int = Field(ge=0)


async def _count_for_organization(
    session: AsyncSession,
    model: type[Member] | type[Election] | type[EncryptedBallot],
    organization_id: UUID,
) -> int:
    statement = (
        select(func.count()).select_from(model).where(model.organization_id == organization_id)
    )
    return int((await session.execute(statement)).scalar_one())


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
