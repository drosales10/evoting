# eVoting

**Elecciones digitales con voto cifrado en el navegador, urna sin identidad y verificación pública del escrutinio.**

> Participación — **Hackathon IA Masivo Online AWS × Código Facilito (Kiro)**  
> **Demo:** https://evoting.dennyrosales.com · **Material de entrega:** [docs/hackaton/](docs/hackaton/00_INDICE.md)

## ¿Qué problema resuelve?

Las elecciones internas de gremios, cooperativas y asociaciones suelen depender de encuestas o de proveedores opacos: la preferencia queda ligada a la identidad, y el resultado no se puede auditar de forma independiente.

**eVoting** ofrece un ciclo electoral completo donde:

1. El voto se **cifra en el cliente** (RSA-OAEP + AES-256-GCM) antes de salir del navegador  
2. La **urna no guarda `member_id`** (la participación vive aparte, en el snapshot de elegibilidad)  
3. El **escrutinio es offline y firmado** (RSA-PSS); cualquiera puede verificar el artefacto  
4. El elector recibe un **recibo por hash/QR** que confirma existencia **sin revelar la plancha**

## Demo en vivo

| Superficie | URL |
|------------|-----|
| Portal | https://evoting.dennyrosales.com |
| Área ciudadana | https://evoting.dennyrosales.com/cliente |
| Acceso elector | https://evoting.dennyrosales.com/vote/login |
| Health | https://evoting.dennyrosales.com/health |

## Stack

| Capa | Tecnología |
|------|------------|
| Frontend | Next.js 15, React 19 (`apps/frontend`) |
| Backend | FastAPI, SQLAlchemy async, Alembic (`apps/backend`) |
| DB | PostgreSQL + PostGIS |
| Workspace | pnpm |
| IA / agentic | **Kiro** (steering, skills, multiagente) |
| Cloud | Piloto en VPS · **Google Gemini 3.5 Flash** (asistente FAQ) |

## Arquitectura (resumen)

```
Internet → nginx :443
            ├─ /api/*, /health*  → FastAPI (realms ADMIN / VOTER / public)
            └─ /*                → Next.js
                    ↓
              PostgreSQL + PostGIS
```

Ciclo electoral: `DRAFT → REGISTRATION → FREEZE → ACTIVE → CLOSED → TALLIED`.

Diagramas, casos de uso y guion del vídeo: [`docs/hackaton/`](docs/hackaton/00_INDICE.md).

## Desarrollado con Kiro

Kiro no fue un autocomplete puntual: fue el sistema de orquestación del producto.

- Steering de metodología electoral y UX de boleta  
- Skills de separación **admin/cliente**, **geovisores** y migraciones PostgreSQL  
- Equipo multiagente (seguridad, API, datos, geo, QA, docs)  

Detalle para el jurado: [docs/hackaton/05_ESTRATEGIA_AWS_KIRO.md](docs/hackaton/05_ESTRATEGIA_AWS_KIRO.md).

## Arranque local

```bash
# Dependencias
pnpm install
cd apps/backend && pip install -e ".[dev]"

# Variables (copia y completa)
cp .env.example .env

# Migraciones
cd apps/backend && alembic upgrade head

# Seed admin (opcional)
cd apps/backend && python -m scripts.seed_admin

# Seed territorio N2–N5 (opcional; exportar desde otro entorno con
# python -m scripts.export_territory — no usar la plantilla inventada)
cd apps/backend && python -m scripts.seed_territory

# Seed padrón / elecciones / planchas (siempre desde export local):
#   python -m scripts.export_members --out members-export.json
#   python -m scripts.export_elections --out elections-export.json
#   python -m scripts.export_slates --out slates-export.json
# Luego en el servidor:
#   SEED_MEMBERS_FILE=... python -m scripts.seed_members
#   SEED_ELECTIONS_FILE=... python -m scripts.seed_elections
#   SEED_SLATES_FILE=... python -m scripts.seed_slates

# API
uvicorn app.main:app --reload --app-dir apps/backend --port 8000

# UI
pnpm dev:frontend
```

Con Docker: `docker compose up --build` (ver `docker-compose.yml`).

Producción (nginx + PM2): ver [deploy/README.md](deploy/README.md).

## Documentación operativa

| Documento | Contenido |
|-----------|-----------|
| [docs/hackaton/00_INDICE.md](docs/hackaton/00_INDICE.md) | **Pack hackathon** (pitch, vídeo, arquitectura, checklist) |
| [docs/hackaton/08_GEMINI_ASISTENTE.md](docs/hackaton/08_GEMINI_ASISTENTE.md) | Asistente FAQ con **Google Gemini 3.5 Flash** |
| [deploy/README.md](deploy/README.md) | Droplet, nginx, SSL, dominio `evoting.dennyrosales.com` |
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

**No publiques resultados de un piloto** como oficiales.
