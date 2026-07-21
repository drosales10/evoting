---
name: git-workflow
description: >-
  Flujo Git seguro para el monorepo eVoting con Next.js y FastAPI: ramas, commits,
  pull requests, worktrees, reviewers y CI con Ruff, Black, mypy, pytest,
  TypeScript y Playwright. Usar al iniciar trabajo versionado, crear ramas o PRs,
  configurar GitHub Actions, preparar releases o validar cambios electorales,
  criptográficos, de seguridad, geografía o base de datos.
compatibility: "Git 2.40+, GitHub CLI opcional, Windows PowerShell, pnpm y Python 3.12+."
metadata:
  domain: evoting
  version: "2.0"
---

# Git workflow para eVoting

Aplica este flujo sin asumir ramas, scripts ni remotos: primero inspecciona el repositorio. Para plantillas y matrices completas, consulta `reference.md`.

## Guardrails no negociables

1. No crear commits, tags, PRs ni hacer push sin solicitud explícita del usuario.
2. No hacer push directo a `main`/`master` salvo petición explícita.
3. No usar `--force`, `reset --hard`, `clean -f`, `branch -D` ni saltar hooks sin autorización.
4. No modificar configuración Git global o local.
5. Stagear archivos específicos; evitar `git add .` y `git add -A`.
6. Tras fallo de hook, corregir, volver a stagear y crear un commit nuevo; no usar `--amend`.
7. Nunca incluir secretos, `.env`, padrones, claves criptográficas, shares o datos electorales reales.

## Inspección inicial

```powershell
git status --short --branch
git remote -v
git branch --all
git remote show origin
```

Determinar:
- rama activa y rama default remota;
- cambios preexistentes del usuario;
- si el trabajo corresponde a issue;
- scripts reales disponibles en `package.json` y `pyproject.toml`.

No sobrescribir ni revertir cambios ajenos.

## Branching

Rama estable prevista: `main`. Si el remoto indica otra, usar la real.

| Patrón | Uso |
|---|---|
| `feat/<issue>-<slug>` | Nueva capacidad |
| `fix/<issue>-<slug>` | Corrección |
| `security/<issue>-<slug>` | Endurecimiento o vulnerabilidad |
| `migration/<issue>-<slug>` | Cambio de esquema |
| `docs/<issue>-<slug>` | Documentación |
| `hotfix/<slug>` | Incidente crítico autorizado |

```powershell
git fetch origin
git switch main
git pull --ff-only origin main
git switch -c feat/42-voter-mfa
```

No mezclar en una rama cambios de dominio, upgrades de dependencias y migraciones no relacionadas.

## Commits

Usar Conventional Commits, preferentemente en español:

```text
feat(auth): agrega MFA del elector (#42)
fix(ballot): evita doble consumo del token (#57)
test(api): cubre aislamiento por organización (#61)
```

Tipos: `feat`, `fix`, `security`, `docs`, `refactor`, `test`, `chore`, `perf`, `build`, `ci`, `revert`.

En PowerShell, para mensajes multilínea:

```powershell
$msg = @"
feat(auth): agrega MFA del elector (#42)

Closes #42
"@
$msg | Out-File -Encoding utf8 commit-msg.txt
git commit -F commit-msg.txt
Remove-Item commit-msg.txt
```

## Gate local

Primero usar scripts del repositorio si existen, por ejemplo `pnpm qa`. Si aún no existen, ejecutar los comandos equivalentes.

### Backend Python

```powershell
python -m ruff check apps/backend
python -m black --check apps/backend
python -m mypy apps/backend/app
python -m pytest apps/backend/tests
```

Para cambios críticos exigir cobertura configurada en `pyproject.toml`.

### Frontend

```powershell
pnpm --dir apps/frontend lint
pnpm --dir apps/frontend exec tsc --noEmit
pnpm --dir apps/frontend build
pnpm --dir apps/frontend exec playwright test
```

No iniciar watchers ni servidores como parte del gate. Ejecutar Playwright contra el entorno de test definido por el proyecto.

## Gate según riesgo

| Cambio | Validación adicional |
|---|---|
| Auth, RBAC, tenant | pytest de permisos, realm, CSRF y organización |
| Urna/cifrado | vectores criptográficos, doble voto, atomicidad, no correlación |
| Migración | `alembic check`, upgrade en DB temporal y revisión SQL |
| Geografía | tests PostGIS, supresión y contrato público |
| Dependencias | lockfile, auditoría y compatibilidad |
| UI de votación | Playwright de MFA, confirmación, emisión y recibo |

## Pull requests

Título menor de 70 caracteres. Body mínimo:

```markdown
## Resumen
- Issue: Closes #42
- Riesgo: alto/medio/bajo

## Cambios
- ...

## Validación
- [x] Backend lint/format/typecheck
- [x] pytest
- [x] Frontend lint/typecheck/build
- [x] Playwright (si aplica)

## Seguridad electoral
- [x] Tenant y permisos revisados
- [x] Sin PII ni correlación identidad-voto
- [x] Migración/criptografía revisada si aplica
```

No marcar checks no ejecutados. Explicar claramente validaciones omitidas.

## Review gates

| Área | Revisión obligatoria |
|---|---|
| Todo cambio funcional | Iris (QA) |
| Auth, RBAC, tenant, urna, criptografía | Vera |
| PostgreSQL, Alembic, PostGIS | Dario |
| Geovisor y privacidad territorial | Gaia + Vera |
| Dependencias/lockfiles | Otto |
| Contratos y reglas electorales | Nadia |
| Documentación funcional | Maia |

El autor no es el único aprobador de cambios críticos.

## CI mínimo

Los workflows deben ejecutar, no solo validar checkboxes:

1. Backend: Ruff, Black check, mypy, pytest con cobertura.
2. Frontend: ESLint, TypeScript y build.
3. E2E: Playwright para flujos críticos.
4. Migraciones: Alembic contra PostgreSQL/PostGIS temporal.
5. Seguridad: dependency/secret scanning y permisos mínimos del workflow.
6. PR metadata: issue, no draft cuando entra a review y checklist real.

Pinear acciones GitHub por versión mayor confiable o SHA según política. Usar `permissions:` mínimos.

## Worktrees para trabajo paralelo

```powershell
git fetch origin
git worktree add "..\evoting-42" -b feat/42-voter-mfa origin/main
git worktree list
```

Cada worktree tiene una rama, alcance y PR independiente. No compartir virtualenv, `.next` o procesos entre worktrees.

Cleanup solo tras merge y confirmación:

```powershell
git worktree remove "..\evoting-42"
git branch -d feat/42-voter-mfa
git worktree prune
```

## Releases

- Versionar y desplegar desde commit revisado.
- Aplicar migraciones con Alembic antes o durante deploy según estrategia compatible.
- Documentar rollback de app; una migración de datos irreversible requiere roll-forward.
- No rotar claves electorales como efecto lateral de un release.
- Conservar artefactos, checksums, SBOM y evidencia de CI cuando la política lo exija.

## Anti-patrones

| Evitar | Hacer |
|---|---|
| Asumir rama `master` o `dev` | Inspeccionar default branch |
| PR con checks declarativos solamente | Ejecutar CI real |
| Commit de `.env` o padrón | Variables seguras y fixtures sintéticos |
| Upgrade de dependencias dentro de feature | PR dedicado |
| Migración destructiva junto a UI | Separar y revisar despliegue |
| `git add .` | Stagear rutas concretas |
| Reescribir historial compartido | Commit correctivo |
| Tests con datos electorales reales | Factories y datos sintéticos |

## Checklist antes de entregar

```text
- [ ] Rama y remoto verificados
- [ ] Cambios preexistentes preservados
- [ ] Diff limitado al alcance
- [ ] Sin secretos ni datos reales
- [ ] Gate backend ejecutado
- [ ] Gate frontend ejecutado
- [ ] Pruebas de riesgo ejecutadas
- [ ] Reviewers requeridos identificados
- [ ] Migración y rollback/roll-forward documentados
- [ ] No commit/push/PR sin autorización
```
