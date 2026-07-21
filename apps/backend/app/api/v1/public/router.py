from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session

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
    """Return only elections that are safe for the public portal.

    This endpoint is intentionally read-only. It assumes the existing database has the
    conceptual `elections` table described by the project specification; no DDL is run.
    """
    response.headers["Cache-Control"] = "no-store"
    query = text(
        """
        SELECT id, title, voting_type, start_time, end_time, status
        FROM elections
        WHERE status IN ('REGISTRATION', 'FREEZE', 'ACTIVE', 'CLOSED', 'TALLIED')
        ORDER BY start_time ASC
        """
    )

    try:
        result = await session.execute(query)
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Public election data is temporarily unavailable",
        ) from exc

    return [PublicElection.model_validate(row) for row in result.mappings().all()]
