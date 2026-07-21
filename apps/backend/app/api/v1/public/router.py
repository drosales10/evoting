from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.repositories.elections import PublicElectionRepository

router = APIRouter(prefix="/public", tags=["public"])


class PublicElection(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    voting_type: str
    start_time: datetime
    end_time: datetime
    status: str


@router.get("/elections", response_model=list[PublicElection])
async def list_public_elections(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PublicElection]:
    """Return only elections approved for public publication.

    This endpoint is intentionally read-only. It returns a controlled projection and never
    exposes roster, participation or ballot data.
    """
    response.headers["Cache-Control"] = "no-store"
    repository = PublicElectionRepository()

    try:
        elections = await repository.fetch_published(session)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public election data is temporarily unavailable",
        ) from exc

    return [PublicElection.model_validate(election) for election in elections]
