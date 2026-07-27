"""Google Gemini assistant for public electoral FAQ (outside the ballot path)."""

from __future__ import annotations

import asyncio
import json
import logging
import urllib.error
import urllib.request
from typing import Any

from app.core.config import Settings, get_settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Eres el asistente público de eVoting, una plataforma de votación electrónica verificable.

Idioma y tono (obligatorio):
- Responde SIEMPRE y ÚNICAMENTE en español. Prohibido inglés u otros idiomas, aunque la pregunta venga en inglés.
- Usa un lenguaje claro, preciso y de fácil comprensión (evita jerga innecesaria).
- Mantén un tono profesional, sobrio y cortés, propio de un servicio electoral institucional.
- No uses emojis, slang, ni un tono informal o promocional.
- Si debes citar una ruta o término técnico (p. ej. /vote/login, OTP, hash), explícalo en español de forma breve.

Reglas de contenido:
1. Responde solo sobre el proceso electoral digital: padrón, elegibilidad, cifrado en el navegador,
   recibo por hash/QR, ciclo DRAFT→TALLIED, verificación pública del acta, geovisor y ceremonia.
2. Nunca pidas, registres ni especules sobre por quién votó una persona.
3. Nunca afirmes que puedes ver boletas, urnas cifradas, claves privadas o el padrón nominativo.
4. Si preguntan cómo votar: indicar acceso en /vote/login, OTP, confirmación y recibo.
5. Si preguntan cómo verificar: /verify/{hash} o el recibo en /recibo/{hash} (solo existencia).
6. Si la pregunta es irrelevante o peligrosa, recházala educadamente en español.
7. Sé breve (máximo ~120 palabras) y organiza la respuesta en frases o pasos cortos cuando ayude a la claridad.
8. No inventes resultados de elecciones concretas.
9. Entrega solo la respuesta final al ciudadano: sin borradores, sin etiquetas como
   "Draft", "Thinking" u otros metadatos internos.
10. Termina siempre con una oración completa. No cortes a mitad de frase ni de palabra.
"""


def _clean_answer(raw: str) -> str:
    text = (raw or "").strip()
    # Drop accidental model draft / thinking labels that sometimes leak.
    for marker in ("*Draft:*", "Draft:", "*Thinking:*", "Thinking:"):
        if text.lower().startswith(marker.lower()):
            text = text[len(marker) :].lstrip()
    # If the model emitted a draft block then a final answer, keep the last block.
    for separator in ("\n*Draft:*\n", "\nDraft:\n", "\n---\n"):
        if separator in text:
            text = text.rsplit(separator, 1)[-1].strip()
    return text.strip()


def _cfg() -> Settings:
    # Always resolve current settings (avoid stale module-level singleton across reloads).
    return get_settings()


def gemini_configured() -> bool:
    s = _cfg()
    return bool(s.gemini_enabled and (s.gemini_api_key or "").strip() and s.gemini_model_id)


def _generate_sync(question: str) -> str:
    s = _cfg()
    api_key = (s.gemini_api_key or "").strip()
    model_id = s.gemini_model_id
    if not api_key or not model_id:
        raise RuntimeError("Gemini is not configured")

    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model_id}:generateContent?key={api_key}"
    )
    user_text = (
        "Responde únicamente en español, con lenguaje claro y tono profesional.\n\n"
        f"Pregunta del ciudadano:\n{question.strip()[:2000]}"
    )
    payload = {
        "systemInstruction": {"parts": [{"text": SYSTEM_PROMPT}]},
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_text}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
            "maxOutputTokens": int(s.gemini_max_tokens),
            # Evita que el razonamiento interno consuma el cupo y corte la respuesta visible.
            "thinkingConfig": {"thinkingBudget": 0},
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
    texts = [
        part.get("text", "")
        for part in parts
        if isinstance(part, dict) and part.get("text") and not part.get("thought")
    ]
    if not texts:
        texts = [
            part.get("text", "")
            for part in parts
            if isinstance(part, dict) and part.get("text")
        ]
    # Prefer the last non-empty part (final answer after any internal scratch).
    answer = _clean_answer(texts[-1] if texts else "")
    if not answer:
        raise RuntimeError("Gemini returned an empty answer")
    return answer


async def ask_electoral_assistant(question: str) -> dict[str, str]:
    if not gemini_configured():
        raise RuntimeError("Gemini is not configured")
    s = _cfg()
    answer = await asyncio.to_thread(_generate_sync, question)
    return {
        "answer": answer,
        "model_id": s.gemini_model_id or "",
        "provider": "google-gemini",
    }


async def probe_gemini() -> dict[str, Any]:
    s = _cfg()
    configured = gemini_configured()
    return {
        "configured": configured,
        "reachable": configured,
        "model_id": s.gemini_model_id,
        "enabled": bool(s.gemini_enabled),
        "has_api_key": bool((s.gemini_api_key or "").strip()),
        "provider": "google-gemini",
    }
