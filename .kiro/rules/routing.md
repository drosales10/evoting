# Work Routing

How to decide who handles what.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| Scope and orchestration | Helena | definir secuencia 00->14, dividir modulos, fijar criterios de salida, coordinar handoffs |
| Domain modeling and Zod contracts | Nadia | jerarquia N0-N6, reglas NIC 41, contratos de formulario, invariantes de calculo y validaciones de entrada |
| CRUD API and persistence | Bruno | handlers GET/POST/PATCH/DELETE, Prisma, AuditLog, filtros, paginacion, relaciones y reglas de negocio |
| Repository pattern (build and maintenance) | Bruno | diseno de interfaces repositorio, implementaciones Prisma, extraccion de acceso a datos y reduccion de acoplamiento en handlers (con soporte de Dario) |
| Security and permissions | Vera | organizationId filters, ownership checks, SUPER_ADMIN bypass, fallback READ/CREATE/UPDATE/DELETE, operaciones sensibles |
| Dashboard and CRUD UI | Alma | formularios, tablas operativas simples, edicion inline, estados de carga, flujos con `sileo` |
| Landing and org submodules | Livia | landing current/default, menu cliente, navegacion por submodulos, filtrado por organizacion activa |
| Tables and import/export | Teo | import CSV/Excel, export, sort asc/desc, normalizacion de headers ES/EN, FK por id/codigo/nombre |
| Geospatial and workers | Gaia | shapefiles, PostGIS, BBOX, workers de import/recalculo, dashboard map, overlays React sobre Leaflet |
| Platform data modeling | Dario | Prisma schema, migrations, SQL tuning, PostgreSQL constraints, PostGIS model governance y soporte tecnico para Patron Repositorio |
| Code review | Iris | revisar riesgos, regresiones, cobertura faltante, evidencia tecnica y brechas de permisos |
| Testing | Iris | QA CRUD, QA landing, QA permisos/roles, smoke tests, evidencia de lint/types/tests/build |
| Unit and integration automation | Nico | pruebas unitarias, integrales, helpers de test, fixtures, cobertura por modulo |
| Docs and Mintlify | Maia | documentacion de features y APIs en `mintlify-docs`, guias de uso, changelog tecnico |
| Dependency compatibility | Otto | auditoria de `package.json`, lockfile, upgrades, riesgos de breaking changes |
| Scope & priorities | Helena | que construir despues, dependencias, trade-offs, riesgos por fase |
| Session logging | Scribe | Automatic — never needs routing |

## Module Routing (SMyEG)

| Module / Area | Primary | Secondary | Notes |
|---------------|---------|-----------|-------|
| `/activities` | Bruno | Nadia, Iris, Nico | blueprint CRUD operativo con validaciones Zod y pruebas asociadas |
| `/departament` + positions/service-companies | Bruno | Alma, Teo, Iris, Nico | CRUD modular con import/export y cuenta contable vinculada |
| `/contabilidad-tierras` + tarifas catalog/scenarios | Bruno | Dario, Teo, Iris, Nico | persistencia Prisma, API multiorg, pruebas de regresion y build |
| `/cliente/tarifas` | Livia | Alma, Bruno, Iris, Nico | experiencia cliente por organizacion activa y navegacion dedicada |
| geoespacial Nivel 4 (`/api/forest/geo/*`) | Gaia | Dario, Vera, Iris, Nico | PostGIS + workers + BBOX + aislamiento por organizacion |
| seguridad multiorganizacion | Vera | Bruno, Dario, Iris | filtros organizationId, ownership checks, bypass controlado |
| documentacion producto/API (`mintlify-docs`) | Maia | Nadia, Bruno, Gaia | reflejar estado implementado y ejemplos de uso reales |
| salud de dependencias | Otto | Dario, Iris | upgrades controlados de libs, lockfile consistente, validacion tecnica |

## Ownership Matrix (Repo Areas)

| Repo Area | DRI (owner) | Co-owners | Reviewer Gate |
|-----------|-------------|-----------|---------------|
| `src/app/api/**` | Bruno | Vera, Dario | Iris |
| `src/validations/**` | Nadia | Bruno | Iris |
| `src/app/**` (UI operativa) | Alma | Livia, Teo | Iris |
| `src/app/cliente/**` | Livia | Alma, Bruno | Iris |
| `src/components/**` | Alma | Teo, Livia | Iris |
| `src/workers/**` | Gaia | Dario, Bruno | Iris |
| `prisma/**` | Dario | Bruno, Gaia | Iris |
| `mintlify-docs/**` | Maia | Nadia, Bruno | Iris |
| `package.json` + lockfile | Otto | Dario | Iris |

### Ownership Conventions

1. DRI define el plan tecnico y aprueba cambios de su area.
2. Co-owners pueden implementar, pero no saltan el gate del reviewer.
3. Iris valida evidencia tecnica y riesgo de regresion antes de cierre.
4. Si hay permisos o aislamiento multiorganizacion, Vera entra como co-review obligatorio.
5. Si hay migraciones o SQL espacial, Dario entra como co-review obligatorio.

## Issue Routing

| Label | Action | Who |
|-------|--------|-----|
| `squad` | Triage: analyze issue, assign `squad:{member}` label | Helena |
| `squad:{name}` | Pick up issue and complete the work | Named member |

### Label Playbook (GitHub)

| Label | Purpose | Owner |
|-------|---------|-------|
| `squad` | inbox de triage inicial | Helena |
| `squad:helena` | orquestacion, alcance, prioridades | Helena |
| `squad:nadia` | modelado funcional y contratos Zod | Nadia |
| `squad:bruno` | API CRUD, persistencia, auditoria | Bruno |
| `squad:vera` | seguridad, permisos, multiorganizacion | Vera |
| `squad:alma` | dashboard UI, formularios, edicion inline | Alma |
| `squad:livia` | landing y submodulos cliente | Livia |
| `squad:teo` | tablas, import/export, compatibilidad de headers | Teo |
| `squad:gaia` | geoespacial, workers, BBOX, mapa | Gaia |
| `squad:iris` | QA/review gate y cumplimiento de evidencias | Iris |
| `squad:nico` | pruebas unitarias/integrales automatizadas | Nico |
| `squad:maia` | documentacion en mintlify-docs | Maia |
| `squad:otto` | dependencias, package.json y lockfile | Otto |
| `squad:dario` | Prisma, PostgreSQL, PostGIS y migraciones | Dario |
| `squad:copilot` | issues aptos para coding agent autonomo | @copilot |

Nota operativa: los labels `squad:*`, `area:*`, `needs:*`, `type:*`, `priority:*`, `go:*` y `release:*` se sincronizan automaticamente desde `.github/workflows/sync-squad-labels.yml`.

### Recommended Label Combinations

1. Feature CRUD: `squad` + `area:crud` + `priority:*`.
2. Security-sensitive: `squad` + `area:security` + `needs:permissions-check`.
3. Geo feature: `squad` + `area:geo` + `needs:data-platform-check`.
4. Dependency update: `squad` + `area:deps` + `needs:compatibility-check`.
5. Docs sync: `squad` + `area:docs` + `needs:mintlify-update`.

### Triage Checklist (Helena)

1. Asignar exactamente un owner principal `squad:{member}`.
2. Asignar co-labels de riesgo cuando aplique: `needs:permissions-check`, `needs:data-platform-check`, `needs:compatibility-check`, `needs:mintlify-update`.
3. Definir criterio de salida: lint, tsc, test:all, build y evidencia funcional.
4. Si el issue mezcla areas, dividir en sub-issues antes de ejecutar.

### Issue Templates (GitHub)

- `.github/ISSUE_TEMPLATE/01-crud-feature.md` para trabajo CRUD funcional.
- `.github/ISSUE_TEMPLATE/02-geospatial-change.md` para cambios espaciales/workers/mapa.
- `.github/ISSUE_TEMPLATE/03-dependency-update.md` para upgrades de librerias y `package.json`.
- `.github/ISSUE_TEMPLATE/04-security-permissions-incident.md` para incidentes de permisos y aislamiento multiorganizacion.
- `.github/ISSUE_TEMPLATE/05-client-tarifas-regression.md` para regresiones en `/cliente/tarifas`.
- `.github/ISSUE_TEMPLATE/config.yml` para guiar apertura estandarizada.

### Operations Runbook

- `.squad/operations/helena-ralph-runbook.md` define el flujo diario de apertura, triage, ejecucion, gates y cierre.
- `.github/workflows/pr-guardrails.yml` aplica gate automatizado para labels `needs:*` pendientes y checklist tecnico minimo en PR.

### How Issue Assignment Works

1. When a GitHub issue gets the `squad` label, **Helena** triages it — analyzing content, assigning the right `squad:{member}` label, and commenting with triage notes.
2. When a `squad:{member}` label is applied, that member picks up the issue in their next session.
3. Members can reassign by removing their label and adding another member's label.
4. The `squad` label is the "inbox" — untriaged issues waiting for Helena review.

## Rules

1. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work.
2. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
3. **Quick facts → coordinator answers directly.** Don't spawn an agent for "what port does the server run on?"
4. **When two agents could handle it**, pick the one whose domain is the primary concern.
5. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel as `mode: "background"`.
6. **Anticipate downstream work.** If a feature is being built, spawn Iris y Nico para pruebas (manual + automatizada) y Vera cuando existan permisos, ownership o aislamiento organizacional.
7. **Landing and CRUD split intentionally.** Si el trabajo afecta dashboard operativo y landing cliente, Helena debe separar entregables y asignar a Alma/Livia con un contrato comun desde Nadia.
8. **Geospatial work is specialized.** Si intervienen shapefiles, BBOX, centroides, PostGIS o workers, Gaia debe ser owner tecnico aunque haya cambios UI en dashboard.
9. **Issue-labeled work** — when a `squad:{member}` label is applied to an issue, route to that member. Helena handles all `squad` (base label) triage.
10. **Docs are part of done.** Todo cambio funcional relevante debe incluir actualizacion de `mintlify-docs` con Maia antes del cierre.
11. **Dependency updates require gate.** Otto revisa cambios de librerias y `package.json` antes de merge cuando haya upgrades o nuevas dependencias.

## SATAA Module Playbook

Aplicar este playbook para todo el trabajo del modulo de Alertas Tempranas y Amenazas Ambientales (SATAA) integrado en SMyEG.

### Scope

1. Cliente alertas y amenazas (dashboard, mapa, series, reportes, comunitario).
2. Tablas auxiliares en configuracion ambiental (admin).
3. Dominio y protocolos de ingreso en activo biologico.
4. Aplicacion movil React Native (offline-first).

### Phase Ownership

| Fase | Owner | Co-owners | Reviewer gate |
|---|---|---|---|
| Arquitectura y contratos | Helena | Nadia, Vera, Dario | Iris |
| Datos y backend base | Bruno | Dario, Vera | Iris |
| UI web cliente/admin | Alma | Livia, Teo, Bruno | Iris |
| Protocolos activo biologico | Bruno | Nadia, Teo, Dario | Iris |
| Movil MVP React Native | Livia | Alma, Bruno, Nico | Iris |

### Mandatory Co-Review Rules

1. Si hay permisos, ownership checks o filtros por organizacion: Vera obligatorio.
2. Si hay Prisma, migraciones, SQL o PostGIS: Dario obligatorio.
3. Todo PR SATAA: Iris obligatorio.

### Label Routing for SATAA

1. `squad` + `area:sataa` + `type:feature` para nuevas capacidades.
2. `squad` + `area:sataa` + `area:security` + `needs:permissions-check` para cambios de permisos.
3. `squad` + `area:sataa` + `area:data` + `needs:data-platform-check` para Prisma/SQL/PostGIS.
4. `squad` + `area:sataa` + `area:mobile` para React Native.
5. `squad` + `area:sataa` + `area:docs` + `needs:mintlify-update` para cierre documental.

### Done Criteria for SATAA

1. Evidencia funcional de flujo end-to-end de la historia.
2. Evidencia de seguridad multiorganizacion aplicada.
3. Evidencia de pruebas automatizadas nuevas o reporte explicito de brechas.
4. Gate tecnico completo: `pnpm lint`, `pnpm exec tsc --noEmit`, `pnpm test:all`, `pnpm build`.
