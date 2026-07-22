# eVoting Platform

Plataforma de votación electrónica (piloto → producción) con superficies separadas **ADMIN**, **VOTER** y **pública**.

## Estado

Este repositorio implementa un ciclo electoral controlado (`DRAFT → REGISTRATION → FREEZE → ACTIVE → CLOSED → TALLIED`) con:

- Cifrado de boleta en el navegador (RSA-OAEP + AES-256-GCM)
- Urna sin `member_id` (participación solo en `member_election_status`)
- Escrutinio offline firmado (RSA-PSS) y verificación pública del artefacto
- Cookies HttpOnly por realm (ADMIN / VOTER)

**No publiques resultados de un piloto** como oficiales. Ver [docs/Go_Live_Checklist.md](docs/Go_Live_Checklist.md) y [docs/Pilot_Archive.md](docs/Pilot_Archive.md).

## Stack

| Capa | Tecnología |
|------|------------|
| Frontend | Next.js 15, React 19 (`apps/frontend`) |
| Backend | FastAPI, SQLAlchemy async, Alembic (`apps/backend`) |
| DB | PostgreSQL |
| Workspace | pnpm |

## Arranque local

```bash
# Dependencias
pnpm install
cd apps/backend && pip install -e ".[dev]"

# Variables (copia y completa)
cp .env.example .env

# Migraciones
cd apps/backend && alembic upgrade head

# API
uvicorn app.main:app --reload --app-dir apps/backend --port 8000

# UI
pnpm dev:frontend
```

Con Docker: `docker compose up --build` (ver `docker-compose.yml`).

## Documentación operativa

| Documento | Contenido |
|-----------|-----------|
| [docs/Go_Live_Checklist.md](docs/Go_Live_Checklist.md) | Criterios para elección oficial |
| [docs/Pilot_Archive.md](docs/Pilot_Archive.md) | Archivar piloto y no publicar votos de prueba |
| [docs/Key_Ceremony.md](docs/Key_Ceremony.md) | Ceremonia de claves y custodia |
| [docs/Official_Tally_Runbook.md](docs/Official_Tally_Runbook.md) | Escrutinio, quórum y doble aprobación |
| [docs/Public_Verification.md](docs/Public_Verification.md) | Verificación independiente `/verify` + CLI |
| [docs/Production_Ops.md](docs/Production_Ops.md) | Correo, HTTPS, backups, monitoreo |
| [docs/Ciclo_Electoral_Registro.md](docs/Ciclo_Electoral_Registro.md) | Ciclo de estados y alcance territorial |
| [docs/Padron_Administrativo.md](docs/Padron_Administrativo.md) | Padrón XLSX (columna Región) |
| [docs/Territorio_Geovisores.md](docs/Territorio_Geovisores.md) | N1–N5, PostGIS, Leaflet/DeckGL |

## Seguridad (resumen)

- `VOTER_TEST_MODE` solo en desarrollo local; nunca en producción
- `SECURE_COOKIES=true` y HTTPS obligatorio fuera de local
- Clave privada de urna **fuera** de API, DB, frontend, sesiones y logs
- Tallies con `pilot_override` no aparecen en resultados públicos
