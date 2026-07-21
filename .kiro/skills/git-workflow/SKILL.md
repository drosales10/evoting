---
name: git-workflow
description: >-
  Flujo Git, branching, commits, PRs y guardrails CI basado en SMyEG/Squad.
  Usar al crear ramas, commits, pull requests, configurar workflows GitHub Actions,
  labels de issues, worktrees multi-agente, promoción de releases, o replicar
  el pipeline issue→PR→merge en otros proyectos Node/Next.js.
---

# Git Workflow (SMyEG / Squad)

Patrón portable de control de versiones. Detalle completo en [reference.md](reference.md).

## Dos capas del modelo

| Capa | Qué es | Estado en SMyEG |
|---|---|---|
| **Operativa** | `master` + feature branches + PR Guardrails | Activa hoy |
| **Squad (plantilla)** | `dev → preview → main` + releases tagged | Documentada, no siempre activa |

Antes de crear ramas, verificar qué modelo usa el clone: `git branch -a` y `origin/HEAD`.

## Flujo consolidado (SMyEG actual)

```
1. Issue desde .github/ISSUE_TEMPLATE/ + labels squad/area/needs
2. Triage → asignación squad:{member}
3. Branch desde master: squad/{n}-{slug} o feat/{descripcion}
4. Desarrollo + pnpm qa:module (obligatorio local)
5. PR con PULL_REQUEST_TEMPLATE.md completo
6. Marcar Ready for review (no Draft)
7. Limpiar labels needs:* pendientes
8. PR Guardrails en verde
9. Review (Iris + especialistas por área)
10. Merge a master
```

## Branching

### Naming

| Patrón | Uso |
|---|---|
| `squad/{issue-number}-{kebab-slug}` | Estándar Squad (preferido) |
| `feat/{descripcion}` | Feature branches ad hoc |
| `hotfix/{slug}` | Urgentes desde main/master |
| `copilot/*` | GitHub Copilot agent |

### Crear rama (SMyEG)

```bash
git checkout master
git pull origin master
git checkout -b squad/42-add-profile-api
```

### Modelo Squad (cuando existan dev/preview/main)

```bash
git checkout dev && git pull origin dev
git checkout -b squad/42-add-profile-api
gh pr create --base dev --draft
# ... trabajo ...
git push -u origin squad/42-add-profile-api
gh pr ready
```

## Commits

### Formato (Conventional Commits)

```
{type}({scope}): {descripcion} (#{issue})

Closes #{issue}
```

**Tipos:** `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `perf`, `style`, `build`, `ci`

**Idioma:** español (convención SMyEG).

**Enforcement:** ninguno automatizado (sin commitlint ni husky). Disciplina del autor.

### Windows (PowerShell)

```powershell
# NO usar git commit -m con \n — falla silenciosamente
$msg = @"
fix(api): corrige filtro de org (#42)

Closes #42
"@
$msg | Out-File -Encoding utf8 commit-msg.txt
git commit -F commit-msg.txt
Remove-Item commit-msg.txt
```

## Gate de calidad pre-PR

No hay hooks Git locales. El gate es **manual**:

```bash
pnpm qa:module   # lint → tsc → test:all → build
```

PR Guardrails **valida checkboxes** en el body del PR, no ejecuta los comandos.

Checklist obligatorio en PR:
- [ ] `pnpm lint`
- [ ] `pnpm exec tsc --noEmit`
- [ ] `pnpm test:all`
- [ ] `pnpm build`

## PR Guardrails (CI)

Workflow: `.github/workflows/pr-guardrails.yml`

Bloquea merge si:
1. PR es **Draft**
2. Labels `needs:*` pendientes
3. Sin referencia a issue (`Issue relacionado: #123`, `Closes #123`, o `#123`)
4. Faltan checkboxes `[x]` de los 4 comandos pnpm

## Plantilla de PR

Usar `.github/PULL_REQUEST_TEMPLATE.md`. Secciones clave:
- Summary (issue, tipo, módulos)
- Technical validation (4 checks pnpm)
- Security (Vera), Data platform (Dario), Tests (Iris/Nico)
- Documentation (Maia), Dependencies (Otto)
- Reviewer checklist + Notes for merge

## Labels e issues

### Flujo automático

```
Issue + label squad → squad-triage.yml → squad:{member}
squad:{member} → squad-issue-assign.yml → asignación
```

### Namespaces

| Namespace | Ejemplos |
|---|---|
| `squad`, `squad:{member}` | helena, bruno, vera, iris |
| `go:` | yes, no, needs-research |
| `type:` | feature, bug, docs, chore |
| `priority:` | p0, p1, p2 |
| `area:` | crud, geo, deps, security, cliente |
| `needs:` | permissions-check, data-platform-check, mintlify-update |

Solo un label por namespace (`go:`, `release:`, `type:`, `priority:`).

Issues solo vía plantilla (`blank_issues_enabled: false`).

## Reviewers obligatorios por área

| Cambio | Reviewer gate |
|---|---|
| Todo PR | **Iris** |
| Permisos/multiorg | Vera |
| Prisma/PostGIS | Dario |
| Geoespacial | Gaia |
| Docs funcionales | Maia (mintlify-docs) |
| Dependencias | Otto |

## Worktrees (multi-agente)

Cuando 2+ issues en paralelo en el mismo repo:

```bash
git fetch origin master   # o dev
git worktree add ../proyecto-42 -b squad/42-fix-bug origin/master
cd ../proyecto-42
# trabajar, commit, push, PR independiente
```

Naming: `../{repo-name}-{issue-number}`

Regla `.squad/`: **append only** en archivos con `merge=union` (`.gitattributes`).

Cleanup post-merge:
```bash
git worktree remove ../proyecto-42
git branch -d squad/42-fix-bug
git push origin --delete squad/42-fix-bug
```

## .gitignore — categorías clave

| Qué | Patrones |
|---|---|
| Dependencias/build | `node_modules`, `.next/`, `/build` |
| Secrets | `.env*` (excepto `.env.example`) |
| Squad runtime | `.squad/orchestration-log/`, `.squad/log/`, `.squad/sessions/` |
| Uploads | `/public/uploads` |
| Scripts | `/scripts` (whitelist explícita) |

Estado operativo Squad **no se commitea**; sí charters, routing, team.md.

## Workflows GitHub Actions

| Workflow | Trigger | Función |
|---|---|---|
| `pr-guardrails.yml` | PR events | Valida metadatos PR |
| `squad-triage.yml` | Issue labeled `squad` | Auto-triage |
| `sync-squad-labels.yml` | Push a `.squad/team.md` | Sync labels |
| `squad-label-enforce.yml` | Issue labeled | Exclusividad labels |
| `squad-promote.yml` | Manual | dev→preview→main |
| `squad-release.yml` | Push a main | Tag + GitHub Release |
| `squad-ci.yml` | PR/push | Tests básicos (`node --test`) |

## Anti-patrones

| Evitar | Hacer |
|---|---|
| Merge con PR Draft | `gh pr ready` antes de review |
| Dejar labels `needs:*` | Limpiar antes de merge |
| Asumir dev/preview/main existen | Verificar ramas reales |
| Confiar solo en CI parcial | Ejecutar `pnpm qa:module` local |
| Commits sin referencia a issue | Incluir `(#n)` y `Closes #n` |
| `git commit -m` multilínea en PowerShell | Usar `-F` con archivo |
| Auto-revisar tras rechazo | Otro agente debe intervenir |

## Checklist para replicar en otro proyecto

```
- [ ] PULL_REQUEST_TEMPLATE.md con checklist técnica
- [ ] pr-guardrails.yml (draft, needs:*, issue ref, checkboxes)
- [ ] ISSUE_TEMPLATE/ con labels default
- [ ] sync-squad-labels.yml (o equivalente)
- [ ] Gate local documentado (qa:module o similar)
- [ ] Convención de commits documentada
- [ ] .gitattributes merge=union para estado compartido
- [ ] AGENTS.md con reglas de PR y ownership
- [ ] Verificar rama default real del repo
```

## Referencia SMyEG

| Tema | Archivo |
|---|---|
| PR template | `.github/PULL_REQUEST_TEMPLATE.md` |
| PR Guardrails | `.github/workflows/pr-guardrails.yml` |
| Issue templates | `.github/ISSUE_TEMPLATE/` |
| Routing/ownership | `.squad/routing.md`, `.squad/team.md` |
| Git workflow Squad | `.squad/templates/skills/git-workflow/SKILL.md` |
| Issue lifecycle | `.squad/templates/issue-lifecycle.md` |
| Merge strategy | `.gitattributes` |
| Gate calidad | `pnpm qa:module` en AGENTS.md |
