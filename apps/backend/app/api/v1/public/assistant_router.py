"""Public electoral assistant powered by Google Gemini."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import get_settings
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
    enabled: bool
    has_api_key: bool


@router.get("/status", response_model=AssistantPublicStatus)
async def assistant_status() -> AssistantPublicStatus:
    s = get_settings()
    ready = gemini_configured()
    return AssistantPublicStatus(
        provider="google-gemini",
        gemini_configured=ready,
        assistant_available=ready,
        model_id=s.gemini_model_id if ready else None,
        enabled=bool(s.gemini_enabled),
        has_api_key=bool((s.gemini_api_key or "").strip()),
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
    s = get_settings()
    rate_limiter.hit(
        client_key(request, "assistant-ask"),
        limit=s.rate_limit_assistant_per_minute,
        window_seconds=60,
    )
    if not gemini_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Gemini no configurado en este proceso API "
                f"(enabled={bool(s.gemini_enabled)}, has_api_key="
                f"{bool((s.gemini_api_key or '').strip())}). "
                "Pon GEMINI_ENABLED=true y GEMINI_API_KEY en el .env de la raíz "
                "y reinicia uvicorn."
            ),
        )
    try:
        result = await ask_electoral_assistant(payload.question)
    except Exception as exc:  # noqa: BLE001
        message = str(exc).replace("\n", " ").strip()
        key = (s.gemini_api_key or "").strip()
        if key:
            message = message.replace(key, "***")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Gemini request failed ({type(exc).__name__}): {message[:300]}",
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
