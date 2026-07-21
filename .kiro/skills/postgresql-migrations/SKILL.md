---
name: postgresql-migrations
description: >-
  PostgreSQL + Prisma 5 + PostGIS: migraciones seguras en modo deploy, seeders
  idempotentes y flujos dev/prod sin pérdida de datos. Usar al crear migraciones,
  aplicar schema en staging/producción, configurar seed, resolver drift, trabajar
  con geometrías PostGIS, o replicar el patrón db:migrate:safe en otros proyectos.
---

# PostgreSQL, Migraciones y Seed (SMyEG)

Patrón portable para migrar **sin borrar datos**. Detalle en [reference.md](reference.md).

## Regla de oro

| Entorno | Comando | ¿Borra datos? |
|---|---|---|
| Dev local (desde cero) | `pnpm db:migrate` | Puede (si aceptas reset) |
| Dev con datos / staging / prod | `pnpm db:migrate:safe` | **No** |
| Solo aplicar pendientes | `pnpm db:deploy` | **No** |
| Diagnóstico | `pnpm db:status` | No |
| Prototipado rápido | `pnpm db:push` | Riesgo — **nunca prod** |
| Reset total | `prisma migrate reset` | **Sí — solo dev vacío** |

```bash
# Flujo seguro (entornos con datos)
pnpm db:status
pnpm db:migrate:safe    # = db:preflight + db:deploy
pnpm db:generate        # si hubo cambios de schema
pnpm db:seed            # opcional, idempotente
```

## Comandos clave

```json
"db:generate": "prisma generate",
"db:preflight": "node scripts/db-preflight.mjs",
"db:migrate": "prisma migrate dev",
"db:migrate:safe": "pnpm db:preflight && pnpm db:deploy",
"db:deploy": "prisma migrate deploy",
"db:status": "prisma migrate status",
"db:push": "prisma db push",
"db:seed": "prisma db seed"
```

**Preflight** (`scripts/db-preflight.mjs`): valida `DATABASE_URL` + `migrate status`. No aplica migraciones.

## Dev vs Prod

### Setup local (desde cero)

```bash
docker compose up -d
cp .env.example .env
pnpm db:generate && pnpm db:migrate && pnpm db:seed
```

### Con datos que conservar

```bash
pnpm db:status          # revisar drift/pendientes
pnpm db:migrate:safe    # NUNCA db:migrate si migrate dev propone reset
```

### Staging / Producción

```bash
pnpm db:status
pnpm db:migrate:safe
# Seed solo si necesario (upserts, no trunca):
SEED_ADMIN_PASSWORD='...' pnpm db:seed
```

**Si `migrate dev` propone reset → cancelar.** Investigar drift con `db:status`.

## Crear migraciones seguras

Patrones que **no pierden datos**:

### 1. Columna nullable → backfill → NOT NULL

```sql
ALTER TABLE "LandUseType" ADD COLUMN "category" VARCHAR(150);
UPDATE "LandUseType" SET "category" = COALESCE(NULLIF(TRIM("name"), ''), 'NO BOSQUE');
ALTER TABLE "LandUseType" ALTER COLUMN "category" SET NOT NULL;
```

### 2. Columna NOT NULL con DEFAULT

```sql
ALTER TABLE "LandUseType" ADD COLUMN IF NOT EXISTS "surfaceHa" DECIMAL(14,4) NOT NULL DEFAULT 0;
```

### 3. Idempotencia

```sql
CREATE TABLE IF NOT EXISTS ...;
ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...;
-- Enums: DO $$ BEGIN IF NOT EXISTS ... ADD VALUE IF NOT EXISTS
```

### 4. Enum sin pérdida

Detectar valores existentes → `ADD VALUE IF NOT EXISTS` o `RENAME VALUE` → `UPDATE` filas → eliminar valor obsoleto.

### Anti-patrones en SQL de migración

| Evitar | Hacer |
|---|---|
| `DROP TABLE` / `TRUNCATE` en prod | `ALTER ADD` + backfill |
| `NOT NULL` sin DEFAULT ni backfill | Nullable primero, backfill, luego NOT NULL |
| `db:push` en prod | Migración SQL versionada |
| Aceptar reset de `migrate dev` | Cancelar → `db:status` → investigar |
| Cambiar enum sin UPDATE previo | Migrar valores fila a fila |

## Seed idempotente

Archivo: `prisma/seed.ts` — **no trunca tablas**. Usa `upsert` y `createMany({ skipDuplicates: true })`.

| Variable | Uso |
|---|---|
| `SEED_ADMIN_EMAIL` | Email admin (default: `admin@example.com`) |
| `SEED_ADMIN_PASSWORD` | **Obligatoria en producción** |
| `SEED_RESET_ADMIN_PASSWORD` | `true` para forzar cambio de password |

```typescript
// Producción: falla si no hay password
if (isProduction && !SEED_ADMIN_PASSWORD) {
  throw new Error("SEED_ADMIN_PASSWORD es obligatorio en producción");
}
// Password: conservado por defecto (SEED_RESET_ADMIN_PASSWORD=false)
```

Siembra: organizaciones, módulos, permisos, roles, admin SUPER_ADMIN, config sistema, catálogos SATAA/NIIF.

## PostGIS

- Geometrías en schema: `Unsupported("geometry(MultiPolygon, 4326)")`
- Operaciones espaciales: `$queryRaw` / `$executeRaw` (Prisma no gestiona geometry)
- Triggers SQL para centroid/superficie (no en schema Prisma)
- Extensión: `CREATE EXTENSION postgis` en migración

**Gap Docker:** `postgres:15-alpine` no incluye PostGIS. Para geo local usar `postgis/postgis:15-3.4-alpine`.

## Schema Prisma — convenciones

```
prisma/schema.prisma     # ~88 modelos, PostgreSQL only
prisma/migrations/       # cadena activa (45+ migraciones)
prisma/seed.ts             # seeder idempotente
```

- IDs: `@db.Uuid` con `@default(uuid())`
- Tablas nuevas: `@@map("snake_case")`
- Índices: `@@index(..., map: "idx_...")`
- `engineType = "library"` en generator + runtime (`src/lib/prisma.ts`)

## Variables de entorno

```env
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app_dev?schema=public
PRISMA_CLIENT_ENGINE_TYPE=library
```

## Workflows para agentes

### Nueva migración (dev)

1. Editar `prisma/schema.prisma`
2. `pnpm db:migrate --name descripcion_cambio` (genera SQL)
3. Revisar SQL generado — aplicar patrones seguros si hay datos
4. `pnpm db:generate`
5. PR con checklist Dario: `db:status` verificado, `db:deploy` en entornos con datos

### Aplicar en staging/prod

1. `pnpm db:status`
2. `pnpm db:migrate:safe`
3. Verificar app + workers
4. Seed solo si faltan catálogos base

### Drift detectado

1. **No** aceptar reset
2. `pnpm db:status` — identificar migración pendiente o divergente
3. Si schema diverge: crear migración correctiva SQL manual
4. `pnpm db:deploy` para aplicar
5. Escalar a Dario si hay conflicto en historial

### Cambio con PostGIS

1. SQL raw en migración para geometry/triggers
2. Declarar `Unsupported("geometry(...)")` en schema
3. Queries espaciales vía `$queryRaw` con parametrización
4. Verificar extensión PostGIS disponible en target DB

## Checklist pre-PR (cambios de schema)

```
- [ ] Migración SQL revisada (sin DROP/TRUNCATE destructivo)
- [ ] Backfill para columnas NOT NULL nuevas
- [ ] pnpm db:status sin errores
- [ ] pnpm db:deploy probado (no db:migrate en entornos con datos)
- [ ] pnpm db:generate ejecutado
- [ ] Dario revisó (Prisma/PostGIS)
- [ ] Backup recomendado si hay cambios de enum/estructural
```

## Referencia SMyEG

| Tema | Archivo |
|---|---|
| Schema | `prisma/schema.prisma` |
| Seed | `prisma/seed.ts` |
| Migraciones | `prisma/migrations/` |
| Preflight | `scripts/db-preflight.mjs` |
| Cliente Prisma | `src/lib/prisma.ts` |
| Docker | `docker-compose.yml` |
| Env | `.env.example` |
| Reglas | `AGENTS.md`, `README.md` |
