"""Public electoral assistant powered by Google Gemini."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.services.gemini_assistant import ask_electoral_assistant, gemini_configured, probe_gemini
from app.services.rate_limit import client_key, rate_limiter

router = APIRouter(prefix="/public/assistant", tags=["public-assistant"])


class AssistantAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=2000)


class AssistantAskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    answer: str
    model_id: str
    provider: str
    disclaimer: str


class AssistantPublicStatus(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider: str
    gemini_configured: bool
    assistant_available: bool
    model_id: str | None


@router.get("/status", response_model=AssistantPublicStatus)
async def assistant_status() -> AssistantPublicStatus:
    return AssistantPublicStatus(
        provider="google-gemini",
        gemini_configured=gemini_configured(),
        assistant_available=gemini_configured(),
        model_id=settings.gemini_model_id if gemini_configured() else None,
    )


@router.get("/ai", response_model=dict)
async def public_ai_probe() -> dict:
    """Non-sensitive AI integration probe for demos and health dashboards."""
    gemini = await probe_gemini()
    return {
        "gemini": gemini,
        "note": (
            "Gemini never accesses ballots, private keys, or the member roster. "
            "It only answers public process FAQs outside the ballot path."
        ),
    }


@router.post("/ask", response_model=AssistantAskResponse)
async def ask_assistant(
    payload: AssistantAskRequest,
    request: Request,
) -> AssistantAskResponse:
    rate_limiter.hit(
        client_key(request, "assistant-ask"),
        limit=settings.rate_limit_assistant_per_minute,
        window_seconds=60,
    )
    if not gemini_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Gemini assistant is not configured. "
                "Set GEMINI_ENABLED=true and GEMINI_API_KEY."
            ),
        )
    try:
        result = await ask_electoral_assistant(payload.question)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini request failed: {type(exc).__name__}",
        ) from exc
    return AssistantAskResponse(
        answer=result["answer"],
        model_id=result["model_id"],
        provider=result["provider"],
        disclaimer=(
            "Asistente informativo (Gemini). No forma parte de la urna, "
            "no ve boletas ni claves privadas."
        ),
    )
