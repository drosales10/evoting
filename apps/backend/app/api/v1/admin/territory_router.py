"""Admin territory CRUD and geo FeatureCollection endpoints."""

from __future__ import annotations

from typing import Annotated, Any, Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_admin
from app.auth.tokens import AccessClaims
from app.db.session import get_db_session
from app.models import (
    ElectoralMunicipality,
    ElectoralPollingPlace,
    ElectoralRegion,
    ElectoralState,
    Organization,
)
from app.services.geo_features import build_admin_feature_collection

router = APIRouter(prefix="/admin", tags=["admin-territory"])
ELECTION_MANAGER_ROLES = frozenset({"SUPER_ADMIN", "ELECTORAL_JUSTICE"})


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
    return await _require_election_manager(claims)


class TerritoryUnitRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=255)
    geojson: dict[str, Any] | None = None
    parent_id: UUID | None = None


class TerritoryUnitResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    code: str
    name: str
    geojson: dict[str, Any] | None = None
    parent_id: UUID | None = None
    level: Literal["N1", "N2", "N3", "N4", "N5"]


@router.get("/territory/organization", response_model=TerritoryUnitResponse)
async def get_organization_unit(
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TerritoryUnitResponse:
    """Return the N1 organization unit for the authenticated tenant."""
    response.headers["Cache-Control"] = "no-store"
    org = await session.scalar(select(Organization).where(Organization.id == claims.org_id))
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    return TerritoryUnitResponse(
        id=org.id,
        code=org.slug,
        name=org.name,
        geojson=org.geojson,
        level="N1",
    )


@router.get("/territory/regions", response_model=list[TerritoryUnitResponse])
async def list_regions(
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> list[TerritoryUnitResponse]:
    response.headers["Cache-Control"] = "no-store"
    rows = (
        await session.scalars(
            select(ElectoralRegion)
            .where(ElectoralRegion.organization_id == claims.org_id)
            .order_by(ElectoralRegion.name.asc())
        )
    ).all()
    return [
        TerritoryUnitResponse(
            id=r.id, code=r.code, name=r.name, geojson=r.geojson, level="N2"
        )
        for r in rows
    ]


@router.post("/territory/regions", response_model=TerritoryUnitResponse, status_code=201)
async def create_region(
    payload: TerritoryUnitRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TerritoryUnitResponse:
    response.headers["Cache-Control"] = "no-store"
    row = ElectoralRegion(
        id=uuid4(),
        organization_id=claims.org_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        geojson=payload.geojson,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Region code already exists") from exc
    await session.refresh(row)
    return TerritoryUnitResponse(
        id=row.id, code=row.code, name=row.name, geojson=row.geojson, level="N2"
    )


@router.get("/territory/states", response_model=list[TerritoryUnitResponse])
async def list_states(
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    region_id: Annotated[UUID | None, Query()] = None,
) -> list[TerritoryUnitResponse]:
    response.headers["Cache-Control"] = "no-store"
    statement = select(ElectoralState).where(ElectoralState.organization_id == claims.org_id)
    if region_id:
        statement = statement.where(ElectoralState.region_id == region_id)
    rows = (await session.scalars(statement.order_by(ElectoralState.name.asc()))).all()
    return [
        TerritoryUnitResponse(
            id=r.id,
            code=r.code,
            name=r.name,
            geojson=r.geojson,
            parent_id=r.region_id,
            level="N3",
        )
        for r in rows
    ]


@router.post("/territory/states", response_model=TerritoryUnitResponse, status_code=201)
async def create_state(
    payload: TerritoryUnitRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TerritoryUnitResponse:
    response.headers["Cache-Control"] = "no-store"
    if not payload.parent_id:
        raise HTTPException(status_code=422, detail="parent_id (region) is required")
    region = await session.scalar(
        select(ElectoralRegion).where(
            ElectoralRegion.id == payload.parent_id,
            ElectoralRegion.organization_id == claims.org_id,
        )
    )
    if region is None:
        raise HTTPException(status_code=404, detail="Region not found")
    row = ElectoralState(
        id=uuid4(),
        organization_id=claims.org_id,
        region_id=payload.parent_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        geojson=payload.geojson,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="State code already exists") from exc
    await session.refresh(row)
    return TerritoryUnitResponse(
        id=row.id,
        code=row.code,
        name=row.name,
        geojson=row.geojson,
        parent_id=row.region_id,
        level="N3",
    )


@router.get("/territory/municipalities", response_model=list[TerritoryUnitResponse])
async def list_municipalities(
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    state_id: Annotated[UUID | None, Query()] = None,
) -> list[TerritoryUnitResponse]:
    response.headers["Cache-Control"] = "no-store"
    statement = select(ElectoralMunicipality).where(
        ElectoralMunicipality.organization_id == claims.org_id
    )
    if state_id:
        statement = statement.where(ElectoralMunicipality.state_id == state_id)
    rows = (await session.scalars(statement.order_by(ElectoralMunicipality.name.asc()))).all()
    return [
        TerritoryUnitResponse(
            id=r.id,
            code=r.code,
            name=r.name,
            geojson=r.geojson,
            parent_id=r.state_id,
            level="N4",
        )
        for r in rows
    ]


@router.post("/territory/municipalities", response_model=TerritoryUnitResponse, status_code=201)
async def create_municipality(
    payload: TerritoryUnitRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TerritoryUnitResponse:
    response.headers["Cache-Control"] = "no-store"
    if not payload.parent_id:
        raise HTTPException(status_code=422, detail="parent_id (state) is required")
    state = await session.scalar(
        select(ElectoralState).where(
            ElectoralState.id == payload.parent_id,
            ElectoralState.organization_id == claims.org_id,
        )
    )
    if state is None:
        raise HTTPException(status_code=404, detail="State not found")
    row = ElectoralMunicipality(
        id=uuid4(),
        organization_id=claims.org_id,
        state_id=payload.parent_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        geojson=payload.geojson,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Municipality code already exists") from exc
    await session.refresh(row)
    return TerritoryUnitResponse(
        id=row.id,
        code=row.code,
        name=row.name,
        geojson=row.geojson,
        parent_id=row.state_id,
        level="N4",
    )


@router.get("/territory/polling-places", response_model=list[TerritoryUnitResponse])
async def list_polling_places(
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    municipality_id: Annotated[UUID | None, Query()] = None,
) -> list[TerritoryUnitResponse]:
    response.headers["Cache-Control"] = "no-store"
    statement = select(ElectoralPollingPlace).where(
        ElectoralPollingPlace.organization_id == claims.org_id
    )
    if municipality_id:
        statement = statement.where(ElectoralPollingPlace.municipality_id == municipality_id)
    rows = (await session.scalars(statement.order_by(ElectoralPollingPlace.name.asc()))).all()
    return [
        TerritoryUnitResponse(
            id=r.id,
            code=r.code,
            name=r.name,
            geojson=r.geojson,
            parent_id=r.municipality_id,
            level="N5",
        )
        for r in rows
    ]


@router.post("/territory/polling-places", response_model=TerritoryUnitResponse, status_code=201)
async def create_polling_place(
    payload: TerritoryUnitRequest,
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TerritoryUnitResponse:
    response.headers["Cache-Control"] = "no-store"
    if not payload.parent_id:
        raise HTTPException(status_code=422, detail="parent_id (municipality) is required")
    muni = await session.scalar(
        select(ElectoralMunicipality).where(
            ElectoralMunicipality.id == payload.parent_id,
            ElectoralMunicipality.organization_id == claims.org_id,
        )
    )
    if muni is None:
        raise HTTPException(status_code=404, detail="Municipality not found")
    row = ElectoralPollingPlace(
        id=uuid4(),
        organization_id=claims.org_id,
        municipality_id=payload.parent_id,
        code=payload.code.strip().upper(),
        name=payload.name.strip(),
        geojson=payload.geojson,
    )
    session.add(row)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Polling place code already exists") from exc
    await session.refresh(row)
    return TerritoryUnitResponse(
        id=row.id,
        code=row.code,
        name=row.name,
        geojson=row.geojson,
        parent_id=row.municipality_id,
        level="N5",
    )


@router.put("/territory/{level}/{unit_id}/geojson")
async def upsert_unit_geojson(
    level: Literal["N1", "N2", "N3", "N4", "N5"],
    unit_id: UUID,
    payload: dict[str, Any],
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_member_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    if level == "N1":
        if unit_id != claims.org_id:
            raise HTTPException(status_code=404, detail="Organization not found")
        org = await session.scalar(
            select(Organization).where(Organization.id == claims.org_id)
        )
        if org is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        org.geojson = _coerce_stored_geojson(payload)
        await session.commit()
        return {"status": "updated", "level": level, "id": str(unit_id)}

    model_map = {
        "N2": ElectoralRegion,
        "N3": ElectoralState,
        "N4": ElectoralMunicipality,
        "N5": ElectoralPollingPlace,
    }
    model = model_map[level]
    row = await session.scalar(
        select(model).where(model.id == unit_id, model.organization_id == claims.org_id)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Territory unit not found")
    row.geojson = _coerce_stored_geojson(payload)
    await session.commit()
    return {"status": "updated", "level": level, "id": str(unit_id)}


def _coerce_stored_geojson(payload: dict[str, Any]) -> dict[str, Any]:
    """Prefer storing a single Feature so readers always find .geometry."""
    geo_type = payload.get("type")
    if geo_type == "Feature":
        return payload
    if geo_type == "FeatureCollection":
        features = payload.get("features") or []
        first = next((f for f in features if isinstance(f, dict) and f.get("geometry")), None)
        if first:
            return {
                "type": "Feature",
                "geometry": first["geometry"],
                "properties": first.get("properties") or {},
            }
        return payload
    if geo_type in {
        "Point",
        "MultiPoint",
        "Polygon",
        "MultiPolygon",
        "LineString",
        "MultiLineString",
        "GeometryCollection",
    }:
        return {"type": "Feature", "geometry": payload, "properties": {}}
    return payload


@router.get("/geo/features")
async def admin_geo_features(
    response: Response,
    claims: Annotated[AccessClaims, Depends(_require_election_manager)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    levels: str = Query(default="N2,N3,N4,N5"),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "no-store"
    level_set = {part.strip().upper() for part in levels.split(",") if part.strip()}
    return await build_admin_feature_collection(session, claims.org_id, level_set)
