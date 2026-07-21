---
name: postgresql-migrations
description: >-
  PostgreSQL 15, PostGIS, SQLAlchemy 2 y Alembic para eVoting: migraciones seguras,
  expand/backfill/contract, seeds idempotentes y despliegues sin pérdida de datos.
  Usar al cambiar modelos o constraints, crear o aplicar migraciones, resolver drift,
  preparar PostgreSQL/PostGIS, modificar urna/padrón/auditoría, o diseñar rollback y
  roll-forward en desarrollo, CI, staging o producción.
compatibility: "Python 3.12+, FastAPI, SQLAlchemy 2+, Alembic, PostgreSQL 15+, PostGIS."
metadata:
  domain: evoting
  version: "2.0"
---

# PostgreSQL y migraciones seguras para eVoting

Esta skill establece el patrón de persistencia Python con SQLAlchemy/Alembic. Consulta `reference.md` para plantillas SQL, modelos y validación avanzada.

## Regla de seguridad

- No aplicar migraciones en staging/producción sin solicitud y confirmación explícitas.
- No ejecutar `DROP`, `TRUNCATE`, `DELETE` masivo, downgrade destructivo o reset con datos sin plan aprobado, backup verificado y ventana de cambio.
- En producción, un rollback de aplicación suele requerir **roll-forward** de esquema; no asumir que `alembic downgrade` es seguro.
- Nunca migrar usando credenciales embebidas en archivos o comandos versionados.

## Stack y estructura

```text
apps/backend/
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
├── app/db/base.py
├── app/db/session.py
├── app/models/
├── app/seeds/
└── tests/migrations/
```

- PostgreSQL 15+ con `pgcrypto` y PostGIS cuando haya geografía.
- SQLAlchemy 2 async para runtime.
- Alembic para historial DDL.
- GeoAlchemy2 para tipos geometry.
- Scripts Python idempotentes para catálogos y bootstrap.

## Comandos por escenario

Ejecutar desde `apps/backend` o con el cwd equivalente.

### Inspección

```powershell
python -m alembic current
python -m alembic heads
python -m alembic history
python -m alembic check
```

### Crear migración en desarrollo

```powershell
python -m alembic revision --autogenerate -m "add election freeze fields"
```

Autogenerate es un borrador: revisar completamente `upgrade()` y `downgrade()` antes de aplicar.

### Aplicar

```powershell
python -m alembic upgrade head
```

- Local/CI: base efímera o backup prescindible.
- Staging/prod: un solo job de migración, advisory lock, backup según riesgo y verificación posterior.

### Downgrade

```powershell
python -m alembic downgrade -1
```

Solo en desarrollo o cuando la reversión esté diseñada y probada. No usar como respuesta automática a una migración de datos.

## Estrategia expand → backfill → contract

Para cambios compatibles y sin downtime:

1. **Expand:** agregar columna/tabla nullable o con default seguro.
2. Desplegar código que escriba formato viejo y nuevo si hace falta.
3. **Backfill:** completar datos por lotes, observable y reanudable.
4. Validar conteos, nulos, constraints y rendimiento.
5. Cambiar lecturas al nuevo formato.
6. **Contract:** imponer `NOT NULL`, retirar columna vieja o constraint obsoleto en release posterior.

No combinar expand y contract incompatibles en un único deploy si puede existir más de una versión de la app.

## Invariantes electorales

### Urna anónima

`encrypted_ballots`:
- no tiene FK ni columna hacia `members`, sesiones, tokens o red;
- `receipt_hash` es único por elección;
- payload, proof y key version quedan inmutables tras inserción;
- cualquier cambio de formato conserva compatibilidad con papeletas existentes.

### Participación

`member_election_status`:
- `UNIQUE(election_id, member_id)`;
- registra elegibilidad/participación sin receipt ni selección;
- cambio a `has_voted=true` ocurre en la misma transacción de emisión.

### Elecciones y congelamiento

- Padrón, planchas, candidatos y clave pública se versionan o congelan antes de `ACTIVE`.
- Migraciones no deben recalcular ni reescribir snapshots de elecciones activas sin ceremonia aprobada.
- Constraints de estado deben ser compatibles con los valores ya persistidos.

### Auditoría

- Logs append-only; no hacer updates/deletes ordinarios.
- Particiones y retención se cambian sin perder cadena de integridad.
- Nunca guardar voto, OTP, token o share privado en auditoría.

## Patrones seguros

### Columna requerida con datos existentes

```python
def upgrade() -> None:
    op.add_column("elections", sa.Column("timezone", sa.String(64), nullable=True))
    op.execute("UPDATE elections SET timezone = 'UTC' WHERE timezone IS NULL")
    op.alter_column("elections", "timezone", nullable=False)
```

Para tablas grandes, separar backfill en job por lotes en vez de un `UPDATE` monolítico.

### Constraint único

1. Buscar duplicados.
2. Definir resolución determinista.
3. Limpiar datos con evidencia.
4. Crear índice/constraint.

En tablas grandes, considerar `CREATE UNIQUE INDEX CONCURRENTLY` con bloque `autocommit`; entender que no puede ejecutarse dentro de la transacción normal.

### Enum

Preferir `VARCHAR + CHECK` si el dominio cambia con frecuencia. Para enum PostgreSQL:
- agregar valores de forma compatible;
- desplegar código;
- migrar filas;
- retirar valores solo en migración posterior y con plan explícito.

## PostGIS

```python
op.execute('CREATE EXTENSION IF NOT EXISTS postgis')
op.create_index(
    "ix_electoral_areas_geom",
    "electoral_areas",
    ["geom"],
    postgresql_using="gist",
)
```

- SRID canónico 4326.
- Transformar datos entrantes explícitamente.
- Probar geometrías inválidas y vacías.
- Usar imagen `postgis/postgis` en CI/local, no una imagen PostgreSQL sin extensión.

## Multi-tenancy

Cada tabla organizacional incluye `organization_id` no nullable e índices compuestos según acceso:

```text
UNIQUE(organization_id, code)
INDEX(organization_id, status)
INDEX(organization_id, election_id)
```

Las foreign keys deben impedir cruces de tenant cuando sea viable mediante claves compuestas o validación robusta. Si se adopta RLS, migrar políticas y probar roles de conexión.

## Seed idempotente

Seeds solo para:
- roles y permisos base;
- configuración no secreta;
- catálogos electorales;
- organización/admin bootstrap controlados.

Usar `INSERT ... ON CONFLICT DO UPDATE/NOTHING`. Nunca truncar, crear elecciones reales ni cambiar passwords existentes salvo flag explícito.

Variables sugeridas:

```env
SEED_ADMIN_EMAIL=admin@example.test
SEED_ADMIN_PASSWORD=<secret-manager>
SEED_RESET_ADMIN_PASSWORD=false
```

En producción, fallar si falta un secreto obligatorio; no usar passwords por defecto.

## Workflow de una migración

1. Leer modelos, historial Alembic y cabeza actual.
2. Definir compatibilidad con versión desplegada.
3. Crear revision con mensaje claro.
4. Revisar autogenerate: tipos, defaults, FKs, índices y operaciones destructivas.
5. Probar upgrade desde base vacía.
6. Probar upgrade desde snapshot sintético de versión anterior.
7. Ejecutar `alembic check`.
8. Ejecutar pytest afectado y tests de invariantes.
9. Documentar duración, locks, backfill y roll-forward.
10. Revisión Dario; Vera si afecta identidad, urna, auditoría o RLS.

## Anti-patrones

| Evitar | Hacer |
|---|---|
| Confiar ciegamente en autogenerate | Revisar SQL y semántica |
| `DROP/TRUNCATE` en deploy normal | Expand/contract y archivo posterior |
| `NOT NULL` inmediato en tabla grande | Nullable + backfill + constraint |
| Downgrade destructivo automático | Roll-forward planificado |
| FK de urna a miembro | Separación criptográfica |
| Seed con datos reales | Datos sintéticos/idempotentes |
| Dos procesos aplicando Alembic | Job único + advisory lock |
| PostgreSQL sin PostGIS | Imagen/extensión correcta |
| Cambiar snapshots activos | Inmutabilidad por elección |

## Checklist pre-merge

```text
- [ ] revision_id y down_revision forman una sola cabeza
- [ ] upgrade revisado, sin pérdida accidental
- [ ] downgrade honesto o marcado irreversible con justificación
- [ ] compatibilidad app/schema documentada
- [ ] upgrade desde cero y desde versión anterior probado
- [ ] alembic check en verde
- [ ] constraints e índices evaluados
- [ ] tenant y secreto del voto preservados
- [ ] PostGIS probado si aplica
- [ ] seed idempotente si cambió catálogo
- [ ] plan de backfill/roll-forward/observabilidad
- [ ] revisión Dario y Vera cuando corresponda
```
