# Referencia: PostgreSQL, Migraciones y Seed (SMyEG)

Documentación detallada para implementar o migrar patrones de BD en proyectos similares.

## Stack

| Componente | Versión / detalle |
|---|---|
| PostgreSQL | 15 |
| PostGIS | Extensión vía migración SQL |
| Prisma | 5.x, `engineType = "library"` |
| ORM client | `@prisma/client` singleton |
| Seed runner | `tsx prisma/seed.ts` |
| ~88 modelos | Auth/RBAC, multi-org, patrimonio forestal N1-N6, geo, assets, tarifas, SATAA, SINIIF |

## Diagrama de flujos

```mermaid
flowchart TB
  subgraph dev [Desarrollo local]
    SCHEMA["Editar schema.prisma"]
    MIGDEV["pnpm db:migrate<br/>(migrate dev)"]
    GEN["pnpm db:generate"]
    SEED["pnpm db:seed"]
  end

  subgraph safe [Entornos con datos]
    STATUS["pnpm db:status"]
    PRE["pnpm db:preflight"]
    DEPLOY["pnpm db:deploy"]
    SAFE["pnpm db:migrate:safe"]
  end

  subgraph forbidden [Prohibido con datos]
    RESET["migrate reset"]
    PUSH["db:push en prod"]
    ACCEPT["Aceptar reset interactivo"]
  end

  SCHEMA --> MIGDEV --> GEN
  MIGDEV --> SEED
  STATUS --> PRE --> DEPLOY
  STATUS --> SAFE
  SAFE --> DEPLOY
  SAFE --> GEN
```

## Comandos completos

| Comando | Implementación | Cuándo usar |
|---|---|---|
| `pnpm db:generate` | `prisma generate` | Tras cambio de schema o post-deploy |
| `pnpm db:preflight` | `node scripts/db-preflight.mjs` | Antes de deploy en entornos sensibles |
| `pnpm db:migrate` | `prisma migrate dev` | Dev local, crear migraciones |
| `pnpm db:migrate:dev` | alias de migrate | Igual que db:migrate |
| `pnpm db:migrate:safe` | preflight + deploy | **Recomendado con datos** |
| `pnpm db:deploy` | `prisma migrate deploy` | Staging/prod, CI/CD |
| `pnpm db:status` | `prisma migrate status` | Diagnóstico drift |
| `pnpm db:push` | `prisma db push` | Solo prototipado local |
| `pnpm db:seed` | `prisma db seed` | Datos base idempotentes |

Postinstall: `prisma generate` automático.

## db-preflight.mjs

```javascript
// scripts/db-preflight.mjs — flujo
1. Verificar DATABASE_URL definido
2. Si NODE_ENV=production → advertir usar solo db:deploy
3. Ejecutar npx prisma migrate status
4. Si status !== 0 → fail (no continúa)
5. OK → seguro ejecutar db:deploy
```

**No aplica migraciones.** Solo valida precondiciones.

## Evitar pérdida de datos

| Situación | Acción correcta |
|---|---|
| Staging/prod con datos | `db:migrate:safe` o `db:deploy` |
| `migrate dev` propone reset | **Cancelar** — investigar con `db:status` |
| Drift detectado | No reset; migración correctiva SQL |
| Enum change | Backup + UPDATE filas + ADD VALUE |
| Columna NOT NULL nueva | Nullable → backfill → NOT NULL |
| Seed en prod | Solo upserts; `SEED_ADMIN_PASSWORD` obligatorio |
| Prototipado schema | `db:push` solo local, nunca prod |

## Patrones de migración SQL (ejemplos reales)

### A) Nullable → backfill → NOT NULL

`prisma/migrations/0002_land_use_type_add_category/migration.sql`:

```sql
ALTER TABLE "LandUseType" ADD COLUMN "category" VARCHAR(150);
UPDATE "LandUseType" SET "category" = COALESCE(NULLIF(TRIM("name"), ''), 'NO BOSQUE');
ALTER TABLE "LandUseType" ALTER COLUMN "category" SET NOT NULL;
```

### B) Backfill con resolución de colisiones

`20260404223000_organization_code_and_rotation_snapshots`:
- ADD `code` nullable
- CTE con `ROW_NUMBER()` para unicidad
- SET NOT NULL + índice único

### C) Idempotencia total

`20260404120000_add_land_variation_causes`:
```sql
-- Enums condicionales
DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '...') THEN
  CREATE TYPE ...;
END IF; END $$;

CREATE TABLE IF NOT EXISTS ...;
ALTER TABLE ... ADD COLUMN IF NOT EXISTS ...;
-- FK condicional verificando pg_constraint
```

### D) Columnas opcionales

`20260519223000_add_image_observations_n1_n2_n3`:
```sql
ALTER TABLE public.forest_geometry_n1
  ADD COLUMN IF NOT EXISTS image_url TEXT,
  ADD COLUMN IF NOT EXISTS observations TEXT;
```

### E) NOT NULL con DEFAULT

`20260308230000_land_use_type_surface_ha`:
```sql
ADD COLUMN IF NOT EXISTS "surfaceHa" DECIMAL(14, 4) NOT NULL DEFAULT 0;
```

### F) Enum fix sin pérdida

`20260514190000_fix_bio_cubicacion_protocol_enum`:
- Detectar valores existentes en pg_enum
- ADD VALUE IF NOT EXISTS o RENAME VALUE
- UPDATE filas con typo
- Eliminar valor obsoleto solo tras migrar datos

## PostGIS

### Schema Prisma

```prisma
model ForestGeometryN4 {
  geom     Unsupported("geometry(MultiPolygon, 4326)")
  centroid Unsupported("geometry(Point, 4326)")?
  superficieHa Decimal @map("superficie_ha") @db.Decimal(12, 4)
  @@map("forest_geometry_n4")
}
```

### Extensiones (migración 0001 + geo)

```sql
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";
CREATE EXTENSION IF NOT EXISTS postgis;
```

### Triggers SQL (fuera de Prisma)

```sql
CREATE OR REPLACE FUNCTION public.fn_calculate_forest_metrics()
RETURNS TRIGGER AS $$
BEGIN
  NEW.geom := ST_Multi(ST_MakeValid(NEW.geom));
  NEW.centroid := ST_PointOnSurface(NEW.geom);
  NEW.superficie_ha := ST_Area(NEW.geom::geography) / 10000;
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

### Queries espaciales

Usar `$queryRaw` / `$executeRaw` en:
- `src/app/api/forest/geo/operations/route.ts`
- `src/lib/repositories/client-alerts-repository.ts`

Prisma **no** soporta tipos geometry en el client generado.

### Docker local

```yaml
# docker-compose.yml actual — SIN PostGIS
image: postgres:15-alpine

# Recomendado para desarrollo geo:
image: postgis/postgis:15-3.4-alpine
```

## Seed — detalle

### Configuración

```json
// package.json
"prisma": { "seed": "tsx prisma/seed.ts" }
```

### Variables

| Variable | Default | Comportamiento |
|---|---|---|
| `SEED_ADMIN_EMAIL` | `admin@example.com` | Usuario admin inicial |
| `SEED_ADMIN_PASSWORD` | — | Obligatoria si `NODE_ENV=production` |
| `SEED_RESET_ADMIN_PASSWORD` | `false` | Solo actualiza password si `true` |

### Datos sembrados (idempotente)

- Organizaciones: `default-org`, `fao`
- Módulos + permisos (6 acciones × módulo)
- Roles: SUPER_ADMIN, ADMIN, CLIENT_MANAGER, MANAGER, USER
- Usuario admin con SUPER_ADMIN
- SystemConfiguration (site_name, landing, submodules cliente)
- NIIF nivel 1 por organización
- Catálogos SATAA (amenazas, canales, estados, registros demo)

### Patrones de idempotencia

```typescript
await prisma.organization.upsert({ where: { code: "DEFAULTORG" }, ... });
await prisma.module.createMany({ data: modules, skipDuplicates: true });
await prisma.sataaThreatTypeCatalog.upsert({ where: { code: "..." }, ... });
```

### Seguridad producción

```typescript
const isProduction = process.env.NODE_ENV === "production";
if (!resolvedAdminPassword && isProduction) {
  throw new Error("SEED_ADMIN_PASSWORD es obligatorio en producción");
}
// Password conservado por defecto — no sobrescribe sin SEED_RESET_ADMIN_PASSWORD=true
```

**El seed nunca trunca tablas.**

## Cliente Prisma

```typescript
// src/lib/prisma.ts
if (!process.env.PRISMA_CLIENT_ENGINE_TYPE) {
  process.env.PRISMA_CLIENT_ENGINE_TYPE = "library";
}

export const prisma = globalForPrisma.prisma ?? new PrismaClient({
  log: process.env.NODE_ENV === "development"
    ? ["query", "error", "warn"]
    : ["error"],
});
```

Singleton global en dev (hot reload). Workers (`geo-worker`, `assets-worker`) importan el mismo client y llaman `$disconnect()` al cerrar.

## Estructura de migraciones

```
prisma/migrations/
├── migration_lock.toml          # provider = "postgresql"
├── 0001_init/
├── 0002_land_use_type_add_category/
├── 20260302183000_geo_spatial_jobs/
├── ... (45+ migraciones timestamp + descripción)
└── migrations_backup_20260224_132859/  # histórico, NO activo
```

Nomenclatura:
1. Secuencial inicial: `0001_init`, `0002_...`
2. Timestamp: `YYYYMMDDHHMMSS_descripcion`

## Convenciones schema.prisma

| Patrón | Ejemplo |
|---|---|
| Legacy PascalCase | `Organization`, `User`, `ForestPatrimonyLevel4` |
| Nuevo snake_case | `@@map("forest_geometry_n4")`, `@@map("client_users")` |
| Columnas | `@map("organization_id")`, `@map("superficie_ha")` |
| Tipos SQL | `@db.Uuid`, `@db.VarChar(n)`, `@db.Decimal(p,s)` |
| Índices | `@@index([organizationId], map: "idx_...")` |
| Enums | `UserStatus`, `PatrimonyLevel4Type` |

## Variables de entorno

```env
# .env.example
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/app_dev?schema=public
PRISMA_CLIENT_ENGINE_TYPE=library

# Seed (producción)
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=<obligatorio-en-prod>
SEED_RESET_ADMIN_PASSWORD=false
```

`.env` gitignored. Nunca commitear credenciales.

## Flujos por escenario

### Dev local desde cero

```bash
corepack enable && pnpm install
docker compose up -d
cp .env.example .env
pnpm db:generate
pnpm db:migrate
pnpm db:seed
pnpm dev
```

### Dev local conservando datos

```bash
pnpm db:status
pnpm db:migrate:safe
```

### Staging / Producción (deploy)

```bash
pnpm db:status
pnpm db:migrate:safe
pnpm db:generate   # si hubo cambios
# Seed opcional:
SEED_ADMIN_PASSWORD='secure' pnpm db:seed
```

### CI/CD pipeline típico

```bash
pnpm install
pnpm db:generate
pnpm db:deploy          # nunca migrate dev
pnpm build
```

### Crear nueva migración (autor en dev)

```bash
# 1. Editar prisma/schema.prisma
# 2. Generar migración
pnpm db:migrate --name add_new_field
# 3. Revisar SQL en prisma/migrations/YYYYMMDDHHMMSS_add_new_field/
# 4. Ajustar SQL si hay riesgo con datos existentes
pnpm db:generate
pnpm qa:module
```

## PR checklist (cambios Prisma)

De `.github/PULL_REQUEST_TEMPLATE.md`:

- Cambios de schema/migraciones revisados por Dario
- Índices/constraints evaluados
- Plan de rollback para cambios estructurales
- Verificado `pnpm db:status` antes de migrar en entornos con datos
- Para entornos con datos: **`pnpm db:deploy`** (no `db:migrate`)

## Tests e integración

- `vitest.integration.config.ts`: timeout 30s
- ~98 archivos `*.integration.test.ts`
- **Mayoría mockea Prisma** — no son tests de BD real
- `AGENTS.md` documenta PostgreSQL requerido, pero en práctica los tests no dependen funcionalmente de BD

## Deuda técnica conocida

| Issue | Detalle |
|---|---|
| Docker sin PostGIS | `postgres:15-alpine` vs migraciones que requieren PostGIS |
| `db:sync-modules` | Referenciado en package.json pero script no existe |
| `create-audit-partition.ts` | Mencionado en README, no presente |
| Naming mixto | PascalCase legacy vs snake_case en módulos nuevos |
| Backup migraciones | `migrations_backup_20260224_132859/` no es cadena activa |

## Anti-patrones

| Anti-patrón | Riesgo | Alternativa |
|---|---|---|
| `db:migrate` en prod | Reset interactivo | `db:deploy` |
| `db:push` en prod | Bypass historial | Migración SQL versionada |
| Aceptar reset en migrate dev | Pérdida total de datos | Cancelar → investigar |
| `migrate reset` fuera de dev | Borra todo | Solo dev vacío |
| DROP/TRUNCATE en migración prod | Pérdida irreversible | ALTER ADD + backfill |
| NOT NULL sin backfill | Falla en filas existentes | Nullable → UPDATE → NOT NULL |
| Seed sin password en prod | Error controlado | `SEED_ADMIN_PASSWORD` |
| Imagen Docker sin PostGIS | Falla migración geo | `postgis/postgis:15-*` |

## Plantilla mínima para otro proyecto

### package.json scripts

```json
{
  "scripts": {
    "db:generate": "prisma generate",
    "db:preflight": "node scripts/db-preflight.mjs",
    "db:migrate": "prisma migrate dev",
    "db:migrate:safe": "pnpm db:preflight && pnpm db:deploy",
    "db:deploy": "prisma migrate deploy",
    "db:status": "prisma migrate status",
    "db:seed": "prisma db seed"
  },
  "prisma": { "seed": "tsx prisma/seed.ts" }
}
```

### AGENTS.md sección Prisma

```markdown
## Prisma
- Dev: `pnpm db:migrate` (interactivo)
- Prod/staging: `pnpm db:deploy` o `pnpm db:migrate:safe`
- Nunca `db:push` en producción
- Si migrate dev propone reset → cancelar; usar `db:status`
- Reset local (borra datos): `prisma migrate reset` — solo dev vacío
```

## Prompts sugeridos para agentes

**Nueva columna con datos existentes:**
> Migración en 3 pasos: ADD nullable, UPDATE backfill, SET NOT NULL. Revisar SQL antes de PR.

**Deploy en staging:**
> `pnpm db:status` → `pnpm db:migrate:safe` → verificar app. No usar migrate dev.

**Drift detectado:**
> No reset. `db:status` para diagnóstico. Migración correctiva SQL manual si necesario.

**Seed en prod:**
> Solo upserts. `SEED_ADMIN_PASSWORD` obligatorio. No `SEED_RESET_ADMIN_PASSWORD` salvo rotación planificada.

**Cambio PostGIS:**
> SQL raw para geometry/triggers. `Unsupported()` en schema. `$queryRaw` para queries. Verificar PostGIS en target.

**Nuevo proyecto desde SMyEG:**
> Copiar scripts db:*, db-preflight.mjs, seed.ts pattern, AGENTS.md rules, PR checklist Dario.

## Mapa de archivos SMyEG

```
prisma/schema.prisma
prisma/seed.ts
prisma/migrations/
scripts/db-preflight.mjs
src/lib/prisma.ts
docker-compose.yml
.env.example
package.json
AGENTS.md
README.md
src/workers/geo-worker-scheduler.ts
src/workers/asset-measurement-worker-scheduler.ts
ecosystem.config.cjs
```
