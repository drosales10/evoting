"""Public statute text and, once tallied, the nominal article results."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.models import StatuteConsultation, StatuteTally
from app.services.statute_tree import load_statute_tree, tree_as_json
from app.services.tally_artifact import artifact_sha256, verify_artifact

router = APIRouter(prefix="/public", tags=["public-statutes"])

PUBLIC_TEXT_STATUSES = frozenset({"ACTIVE", "CLOSED", "TALLIED"})


class PublicStatuteSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    status: str
    start_time: datetime
    end_time: datetime
    has_results: bool


class PublicStatuteDocument(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    title: str
    status: str
    start_time: datetime
    end_time: datetime
    approval_threshold_pct: str
    quorum_threshold_pct: str
    titles: list[dict[str, Any]]


async def _public_consultation(
    session: AsyncSession,
    consultation_id: UUID,
) -> StatuteConsultation:
    consultation = await session.scalar(
        select(StatuteConsultation).where(StatuteConsultation.id == consultation_id)
    )
    if consultation is None or consultation.status not in PUBLIC_TEXT_STATUSES:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Consulta no encontrada")
    return consultation


@router.get("/statutes", response_model=list[PublicStatuteSummary])
async def list_public_statutes(
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[PublicStatuteSummary]:
    response.headers["Cache-Control"] = "no-store"
    rows = list(
        (
            await session.scalars(
                select(StatuteConsultation)
                .where(StatuteConsultation.status.in_(tuple(PUBLIC_TEXT_STATUSES)))
                .order_by(StatuteConsultation.activated_at.desc().nullslast())
            )
        ).all()
    )
    return [
        PublicStatuteSummary(
            id=item.id,
            title=item.title,
            status=item.status,
            start_time=item.start_time,
            end_time=item.end_time,
            has_results=item.status == "TALLIED",
        )
        for item in rows
    ]


@router.get("/statutes/{consultation_id}", response_model=PublicStatuteDocument)
async def get_public_statute(
    consultation_id: UUID,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PublicStatuteDocument:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _public_consultation(session, consultation_id)
    tree = await load_statute_tree(
        session,
        organization_id=consultation.organization_id,
        consultation_id=consultation.id,
    )
    return PublicStatuteDocument(
        id=consultation.id,
        title=consultation.title,
        status=consultation.status,
        start_time=consultation.start_time,
        end_time=consultation.end_time,
        approval_threshold_pct=str(consultation.approval_threshold_pct),
        quorum_threshold_pct=str(consultation.quorum_threshold_pct),
        titles=tree_as_json(tree),
    )


@router.get("/statutes/{consultation_id}/results")
async def get_public_statute_results(
    consultation_id: UUID,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    consultation = await _public_consultation(session, consultation_id)
    if consultation.status != "TALLIED":
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El acta todavía no está publicada",
        )
    tally = await session.scalar(
        select(StatuteTally).where(StatuteTally.consultation_id == consultation.id)
    )
    if tally is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Acta no encontrada")
    signing_pem = consultation.signing_public_key or consultation.public_key or ""
    signature_valid = False
    hash_matches = artifact_sha256(tally.artifact) == tally.artifact_sha256
    if signing_pem:
        try:
            public_key = load_pem_public_key(signing_pem.encode("utf-8"))
            signature_valid = isinstance(public_key, RSAPublicKey) and verify_artifact(
                tally.artifact, tally.signature, public_key
            )
        except ValueError:
            signature_valid = False
    return {
        "consultation_id": consultation.id,
        "title": consultation.title,
        "status": consultation.status,
        "artifact_sha256": tally.artifact_sha256,
        "signature": tally.signature,
        "artifact": tally.artifact,
        "quorum_met": tally.quorum_met,
        "ballot_count": tally.ballot_count,
        "verification": {
            "artifact_sha256_matches": hash_matches,
            "signature_valid": signature_valid,
        },
    }
