# Asistente electoral con Google Gemini 3.5 Flash

## Qué hace

FAQ pública en `/cliente/asistente` usando **Google Gemini 3.5 Flash**.  
Fuera del path de urna: no ve boletas, claves privadas ni padrón.

## Variables

```bash
GEMINI_ENABLED=true
GEMINI_API_KEY=tu_api_key
GEMINI_MODEL_ID=gemini-3.5-flash
GEMINI_MAX_TOKENS=1536
RATE_LIMIT_ASSISTANT_PER_MINUTE=20
```

Obtén la key en: https://aistudio.google.com/apikey

Modelo por defecto (estable / GA):
- `gemini-3.5-flash`

> No usar `gemini-2.0-flash` (deprecado).

## Endpoints

| Método | Ruta |
|--------|------|
| GET | `/health/ai` |
| GET | `/api/v1/public/assistant/status` |
| GET | `/api/v1/public/assistant/ai` |
| POST | `/api/v1/public/assistant/ask` `{"question":"..."}` |

## Nota hackathon

AWS (S3/Bedrock) se retiró del código por bloqueo de cuenta. El asistente IA queda con Gemini 3.5 Flash; Kiro sigue como tooling de desarrollo.
