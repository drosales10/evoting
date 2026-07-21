from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.auth.router import router as auth_router
from app.api.v1.public.router import router as public_router
from app.core.config import settings
from app.db.session import dispose_engine, get_engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    await dispose_engine()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Initial eVoting API with separated public, voter, party and admin surfaces.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)

app.include_router(auth_router, prefix="/api/v1")
app.include_router(public_router, prefix="/api/v1")


@app.get("/health", tags=["health"])
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "evoting-api"}


@app.get("/health/ready", tags=["health"])
async def readiness() -> dict[str, str]:
    engine = get_engine()
    if engine is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="DATABASE_URL is not configured",
        )

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database is unavailable",
        ) from exc

    return {"status": "ready", "database": "reachable"}
