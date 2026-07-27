"""Google Gemini assistant for public electoral FAQ (outside the ballot path)."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres el asistente público de eVoting, una plataforma de votación electrónica verificable.

Reglas estrictas:
1. Responde solo sobre el proceso electoral digital: padrón, elegibilidad, cifrado en el navegador,
   recibo por hash/QR, ciclo DRAFT→TALLIED, verificación pública del acta, geovisor y ceremonia.
2. Nunca pidas, registres ni especules sobre por quién votó una persona.
3. Nunca afirmes que puedes ver boletas, urnas cifradas, claves privadas o el padrón nominativo.
4. Si preguntan cómo votar: indicar acceso en /vote/login, OTP, confirmación y recibo.
5. Si preguntan cómo verificar: /verify/{hash} o el recibo en /recibo/{hash} (solo existencia).
6. Si la pregunta es irrelevante o peligrosa, recházala educadamente.
7. Responde en español, claro y breve (máximo ~180 palabras).
8. No inventes resultados de elecciones concretas.
"""


def gemini_configured() -> bool:
    return bool(settings.gemini_enabled and settings.gemini_api_key and settings.gemini_model_id)


def _generate_sync(question: str) -> str:
    api_key = settings.gemini_api_key
    model_id = settings.gemini_model_id
    if not api_key or not model_id:
        raise RuntimeError("Gemini is not configured")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_id}:generateContent?key={api_key}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": question.strip()[:2000]}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": int(settings.gemini_max_tokens),
        },
    }
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            body = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:400]
        raise RuntimeError(f"Gemini HTTP {exc.code}: {detail}") from exc

    candidates = body.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini returned no candidates")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    texts = [part.get("text", "") for part in parts if isinstance(part, dict)]
    answer = "\n".join(t for t in texts if t).strip()
    if not answer:
        raise RuntimeError("Gemini returned an empty answer")
    return answer


async def ask_electoral_assistant(question: str) -> dict[str, str]:
    if not gemini_configured():
        raise RuntimeError("Gemini is not configured")
    answer = await asyncio.to_thread(_generate_sync, question)
    return {
        "answer": answer,
        "model_id": settings.gemini_model_id or "",
        "provider": "google-gemini",
    }


async def probe_gemini() -> dict[str, Any]:
    if not gemini_configured():
        return {
            "configured": False,
            "reachable": False,
            "model_id": settings.gemini_model_id,
            "enabled": settings.gemini_enabled,
            "provider": "google-gemini",
        }
    return {
        "configured": True,
        "reachable": True,
        "model_id": settings.gemini_model_id,
        "enabled": True,
        "provider": "google-gemini",
    }
