# 🏗️ Estructura del Proyecto eVoting-Platform

## Visión General

```
evoting-platform/
├── .kiro/                          # Configuración Kiro (steering, agents, rules)
├── apps/                           # Aplicaciones principales
│   ├── frontend/                   # Next.js Frontend
│   └── backend/                    # FastAPI Backend
├── packages/                       # Paquetes compartidos
│   ├── shared/                     # Tipos y utilidades compartidas
│   ├── database/                   # Configuración de base de datos
│   └── crypto/                     # Utilidades criptográficas
├── infra/                          # Infraestructura
├── docs/                           # Documentación
└── .github/                        # Configuración GitHub
```

## 🎯 Aplicación Frontend (Next.js)

### Estructura Principal
```
apps/frontend/
├── src/
│   ├── app/                        # App Router de Next.js
│   │   ├── (auth)/                 # Rutas de autenticación
│   │   │   ├── login/
│   │   │   ├── register/
│   │   │   └── mfa/
│   │   ├── (public)/               # Rutas públicas
│   │   │   ├── slates/             # Planchas electorales
│   │   │   ├── elections/          # Información de elecciones
│   │   │   └── compare/            # Comparador de propuestas
│   │   ├── (member)/               # Área de miembros
│   │   │   ├── dashboard/
│   │   │   ├── vote/               # Votación
│   │   │   └── receipt/            # Comprobantes
│   │   ├── (admin)/                # Área administrativa
│   │   │   ├── elections/
│   │   │   ├── members/
│   │   │   ├── slates/
│   │   │   └── results/
│   │   ├── (electoral-board)/      # Comisión Electoral
│   │   │   ├── tally/
│   │   │   ├── audit/
│   │   │   └── results/
│   │   ├── api/                    # API routes de Next.js
│   │   │   ├── auth/
│   │   │   ├── ballot/
│   │   │   └── webhooks/
│   │   ├── layout.tsx              # Layout principal
│   │   └── page.tsx                # Página principal
│   ├── components/                 # Componentes React
│   │   ├── ui/                     # Componentes UI reutilizables
│   │   │   ├── button/
│   │   │   ├── card/
│   │   │   ├── dialog/
│   │   │   └── table/
│   │   ├── ballot/                 # Componentes de boleta
│   │   │   ├── BallotWizard.tsx
│   │   │   ├── BallotPreview.tsx
│   │   │   └── BallotReceipt.tsx
│   │   ├── auth/                   # Autenticación
│   │   │   ├── LoginForm.tsx
│   │   │   ├── MFASetup.tsx
│   │   │   └── SessionGuard.tsx
│   │   ├── election/               # Elecciones
│   │   │   ├── ElectionCard.tsx
│   │   │   ├── SlateGrid.tsx
│   │   │   └── ResultsChart.tsx
│   │   ├── admin/                  # Administración
│   │   │   ├── MemberTable.tsx
│   │   │   ├── ElectionForm.tsx
│   │   │   └── AuditLog.tsx
│   │   └── layout/                 # Layout components
│   │       ├── Header.tsx
│   │       ├── Sidebar.tsx
│   │       └── TenantShell.tsx
│   ├── hooks/                      # Custom hooks
│   │   ├── use-auth.ts
│   │   ├── use-ballot.ts
│   │   ├── use-election.ts
│   │   └── use-geospatial.ts
│   ├── lib/                        # Librerías y configuraciones
│   │   ├── api-client.ts           # Cliente HTTP
│   │   ├── sileo.ts                # Configuración de notificaciones
│   │   ├── encryption.ts           # Web Crypto utilities
│   │   └── validation.ts           # Validaciones Zod
│   ├── types/                      # Tipos TypeScript
│   │   ├── ballot.ts
│   │   ├── election.ts
│   │   ├── member.ts
│   │   └── api.ts
│   ├── utils/                      # Funciones utilitarias
│   │   ├── date.ts
│   │   ├── format.ts
│   │   └── encryption-helpers.ts
│   └── styles/                     # Estilos globales
│       ├── globals.css
│       └── tailwind.css
├── public/                         # Assets estáticos
│   ├── images/
│   ├── fonts/
│   └── favicon.ico
├── package.json
├── tsconfig.json
├── next.config.js
└── tailwind.config.js
```

## ⚙️ Aplicación Backend (FastAPI)

### Estructura Principal
```
apps/backend/
├── src/
│   ├── api/                        # Endpoints API
│   │   ├── v1/                     # Versión 1 de API
│   │   │   ├── auth/
│   │   │   │   ├── router.py
│   │   │   │   ├── dependencies.py
│   │   │   │   └── schemas.py
│   │   │   ├── elections/
│   │   │   ├── ballots/
│   │   │   ├── slates/
│   │   │   ├── members/
│   │   │   ├── audit/
│   │   │   └── geo/                # Endpoints geoespaciales
│   │   └── webhooks/               # Webhooks
│   ├── core/                       # Configuración core
│   │   ├── config.py               # Configuración aplicación
│   │   ├── security.py             # Seguridad y autenticación
│   │   ├── database.py             # Configuración base de datos
│   │   └── dependencies.py         # Dependencias FastAPI
│   ├── domain/                     # Lógica de dominio
│   │   ├── elections/              # Lógica de elecciones
│   │   │   ├── models.py
│   │   │   ├── services.py
│   │   │   └── rules.py
│   │   ├── voting/                 # Lógica de votación
│   │   ├── tally/                  # Lógica de escrutinio
│   │   └── audit/                  # Lógica de auditoría
│   ├── infrastructure/             # Infraestructura
│   │   ├── repositories/           # Patrón repositorio
│   │   │   ├── base.py
│   │   │   ├── election_repository.py
│   │   │   ├── ballot_repository.py
│   │   │   └── member_repository.py
│   │   ├── database/               # Modelos de base de datos
│   │   │   ├── models.py
│   │   │   ├── migrations/
│   │   │   └── session.py
│   │   └── external/               # Servicios externos
│   │       ├── email.py
│   │       ├── storage.py
│   │       └── crypto.py
│   ├── shared/                     # Utilidades compartidas
│   │   ├── schemas.py              # Schemas Pydantic
│   │   ├── exceptions.py           # Excepciones personalizadas
│   │   ├── types.py                # Tipos TypeScript
│   │   └── utils.py                # Funciones utilitarias
│   └── workers/                    # Workers asíncronos
│       ├── ballot_processor.py
│       ├── tally_worker.py
│       └── geo_worker.py
├── tests/                          # Tests
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── alembic/                        # Migraciones de base de datos
│   ├── versions/
│   └── env.py
├── requirements.txt
├── pyproject.toml
├── Dockerfile
└── main.py
```

## 📦 Paquetes Compartidos

### `packages/shared`
```
packages/shared/
├── src/
│   ├── types/                      # Tipos compartidos
│   │   ├── ballot.ts
│   │   ├── election.ts
│   │   ├── member.ts
│   │   └── index.ts
│   ├── schemas/                    # Schemas Zod compartidos
│   │   ├── ballot.zod.ts
│   │   ├── election.zod.ts
│   │   └── index.ts
│   ├── constants/                  # Constantes compartidas
│   │   ├── voting-status.ts
│   │   ├── election-types.ts
│   │   └── index.ts
│   └── utils/                      # Utilidades compartidas
│       ├── validation.ts
│       ├── encryption-types.ts
│       └── index.ts
├── package.json
└── tsconfig.json
```

### `packages/database`
```
packages/database/
├── prisma/                         # Esquema Prisma
│   ├── schema.prisma
│   ├── migrations/
│   └── seed.ts
├── src/
│   ├── client.ts                   # Cliente Prisma
│   ├── types.ts                    # Tipos generados
│   └── utils.ts                    # Utilidades de base de datos
├── package.json
└── tsconfig.json
```

### `packages/crypto`
```
packages/crypto/
├── src/
│   ├── web/                        # Criptografía web (frontend)
│   │   ├── ballot-encryption.ts
│   │   ├── key-management.ts
│   │   └── zkp-proofs.ts
│   ├── server/                     # Criptografía server (backend)
│   │   ├── threshold.ts
│   │   ├── homomorphic.ts
│   │   └── key-sharing.ts
│   └── shared/                     # Criptografía compartida
│       ├── types.ts
│       ├── constants.ts
│       └── utils.ts
├── package.json
└── tsconfig.json
```

## 🏗️ Infraestructura

### Configuración Docker
```
infra/docker/
├── frontend/
│   ├── Dockerfile
│   └── nginx.conf
├── backend/
│   ├── Dockerfile
│   └── gunicorn.conf.py
├── database/
│   ├── Dockerfile
│   ├── init.sql
│   └── postgis.conf
├── redis/
│   └── Dockerfile
└── docker-compose.yml
```

### Kubernetes
```
infra/kubernetes/
├── base/                           # Configuración base
│   ├── namespace.yaml
│   ├── configmap.yaml
│   └── secrets.yaml
├── apps/                           # Aplicaciones
│   ├── frontend/
│   │   ├── deployment.yaml
│   │   ├── service.yaml
│   │   └── ingress.yaml
│   ├── backend/
│   │   ├── deployment.yaml
│   │   └── service.yaml
│   └── database/
│       ├── statefulset.yaml
│       └── service.yaml
├── monitoring/                     # Monitoreo
│   ├── prometheus/
│   └── grafana/
└── kustomization.yaml
```

## 📚 Documentación

### Documentación Técnica
```
docs/
├── api/                            # Documentación API
│   ├── openapi.yaml                # Especificación OpenAPI
│   ├── endpoints/                  # Documentación por endpoint
│   │   ├── auth.md
│   │   ├── ballots.md
│   │   └── elections.md
│   └── examples/                   # Ejemplos de uso
├── architecture/                   # Arquitectura
│   ├── system-overview.md
│   ├── database-schema.md
│   ├── security-model.md
│   └── deployment-guide.md
├── development/                    # Desarrollo
│   ├── setup-guide.md
│   ├── coding-standards.md
│   ├── testing-guide.md
│   └── debugging-guide.md
├── user-guides/                    # Guías de usuario
│   ├── voter-guide.md
│   ├── admin-guide.md
│   └── electoral-board-guide.md
└── operations/                     # Operaciones
    ├── monitoring.md
    ├ backup-guide.md
    └── disaster-recovery.md
```

## 🔧 Configuración GitHub

```
.github/
├── workflows/                      # GitHub Actions
│   ├── ci.yml                      # CI Pipeline
│   ├── cd.yml                      # CD Pipeline
│   ├── security-scan.yml           # Security scanning
│   └── sync-labels.yml             # Sincronización de labels
├── ISSUE_TEMPLATE/                 # Templates de issues
│   ├── 01-crud-feature.md
│   ├── 02-geospatial-change.md
│   ├── 03-dependency-update.md
│   ├── 04-security-incident.md
│   └── config.yml
└── PULL_REQUEST_TEMPLATE/          # Templates de PR
    └── default.md
```

## 📊 Estructura de Base de Datos

### Esquema Principal
```
database/
├── public/                         # Esquema principal
│   ├── members/                    # Tabla de miembros
│   ├── elections/                  # Elecciones
│   ├── positions/                  # Cargos/posiciones
│   ├── slates/                     # Planchas electorales
│   ├── candidates/                 # Candidatos
│   ├── encrypted_ballots/          # Boletas cifradas
│   ├── audit_logs/                 # Logs de auditoría
│   └── organization_members/       # Relación organización-miembro
├── geo/                            # Datos geoespaciales
│   ├── regions/                    # Regiones (N1)
│   ├── districts/                  # Distritos (N2)
│   ├── voting_centers/             # Centros de votación (N3)
│   └── voting_tables/              # Mesas de votación (N4)
└── config/                         # Configuración
    ├── organizations/              # Organizaciones
    ├── election_config/            # Configuración de elecciones
    └── security_config/            # Configuración de seguridad
```

## 🎯 Responsabilidades por Agente

### Helena (Lead Orchestrator)
- `apps/frontend/src/app/layout.tsx`
- `.github/workflows/ci.yml`
- `docs/architecture/system-overview.md`

### Nadia (Functional Architect)
- `packages/shared/src/schemas/`
- `docs/api/openapi.yaml`
- `apps/backend/src/shared/schemas.py`

### Bruno (API Engineer)
- `apps/backend/src/api/v1/`
- `apps/backend/src/infrastructure/repositories/`
- `packages/database/prisma/`

### Vera (Security Engineer)
- `apps/backend/src/core/security.py`
- `apps/frontend/src/lib/encryption.ts`
- `.github/workflows/security-scan.yml`

### Alma (Frontend Engineer)
- `apps/frontend/src/components/ui/`
- `apps/frontend/src/components/admin/`
- `apps/frontend/src/app/(admin)/`

### Livia (Landing Experience Engineer)
- `apps/frontend/src/app/(public)/`
- `apps/frontend/src/components/election/`
- `apps/frontend/src/app/(member)/`

### Teo (Data Grid Engineer)
- `apps/frontend/src/components/ui/table/`
- `apps/frontend/src/lib/api-client.ts`
- `apps/backend/src/api/v1/export/`

### Gaia (Geospatial Engineer)
- `apps/backend/src/api/v1/geo/`
- `apps/frontend/src/hooks/use-geospatial.ts`
- `infra/docker/database/postgis.conf`

### Iris (QA Engineer)
- `apps/frontend/tests/`
- `apps/backend/tests/`
- `.github/workflows/ci.yml` (test steps)

### Nico (Test Automation)
- `apps/frontend/tests/e2e/`
- `apps/backend/tests/integration/`
- `packages/shared/tests/`

### Maia (Documentation)
- `docs/`
- `mintlify-docs/`
- `.github/ISSUE_TEMPLATE/`

### Otto (Dependency)
- `package.json` (root y packages)
- `requirements.txt`
- `.github/workflows/dependency-review.yml`

### Dario (Data Platform)
- `packages/database/prisma/schema.prisma`
- `apps/backend/alembic/`
- `infra/docker/database/`

## 📋 Checklist de Estructura

### Frontend
- [ ] App Router organizado por roles
- [ ] Componentes modulares y reutilizables
- [ ] Hooks personalizados para lógica compleja
- [ ] Tipos TypeScript compartidos
- [ ] Configuración de Tailwind completa

### Backend
- [ ] API organizada por dominio
- [ ] Patrón repositorio implementado
- [ ] Schemas Pydantic para validación
- [ ] Migraciones de base de datos
- [ ] Workers para procesamiento async

### Compartido
- [ ] Tipos TypeScript sincronizados
- [ ] Schemas Zod/Pydantic consistentes
- [ ] Utilidades criptográficas unificadas

### Infraestructura
- [ ] Docker Compose para desarrollo
- [ ] Kubernetes para producción
- [ ] Configuración de monitoreo
- [ ] Pipeline CI/CD completo

---

**Responsable:** Helena (Lead Orchestrator)  
**Última actualización:** 2026-07-21  
**Siguiente revisión:** 2026-08-21
