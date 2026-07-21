# Referencia eVoting: SQLAlchemy, Alembic, PostgreSQL y PostGIS

Consulta esta referencia para configurar Alembic, diseñar migraciones complejas o validar invariantes electorales.

## Configuración SQLAlchemy 2

```python
# app/db/base.py
from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
```

La convención evita nombres inestables y permite que Alembic elimine constraints de forma determinista.

## Configuración Alembic async

```python
# alembic/env.py
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config
from app.db.base import Base
from app import models  # noqa: F401: registra metadata

target_metadata = Base.metadata

async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        context.config.get_section(context.config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()
```

No hardcodear `DATABASE_URL` en `alembic.ini`; cargarla desde settings/entorno y ocultarla de logs.

## Modelo electoral mínimo

```text
organizations
admin_users / roles / permissions
members
member_election_status
elections
positions
slates
candidates
voting_authorizations
encrypted_ballots
audit_events
electoral_areas
election_area_snapshots
election_participation
```

### Urna

```python
class EncryptedBallot(Base):
    __tablename__ = "encrypted_ballots"

    id: Mapped[UUID]
    organization_id: Mapped[UUID]
    election_id: Mapped[UUID]
    encrypted_payload: Mapped[bytes]
    proof: Mapped[bytes | None]
    receipt_hash: Mapped[str]
    encryption_key_version: Mapped[str]
    received_bucket: Mapped[datetime]

    __table_args__ = (
        UniqueConstraint("election_id", "receipt_hash"),
        Index("ix_ballots_election", "election_id"),
    )
```

No agregar `member_id`, authorization ID, IP, user-agent o timestamp de alta precisión. Si la organización usa `organization_id`, no debe permitir correlación adicional; evaluar separación física/esquema conforme al threat model.

### Participación

```python
class MemberElectionStatus(Base):
    __tablename__ = "member_election_status"

    election_id: Mapped[UUID] = mapped_column(primary_key=True)
    member_id: Mapped[UUID] = mapped_column(primary_key=True)
    eligible: Mapped[bool]
    has_voted: Mapped[bool]
    voted_bucket: Mapped[datetime | None]
```

No almacenar `receipt_hash`. El bucket temporal reduce correlación y se define por política.

## Nombres de revisiones

Archivo:

```text
YYYYMMDD_HHMM_<revision>_<slug>.py
```

Mensaje:

```text
add member election status uniqueness
add electoral area gist index
expand encrypted ballot key version
```

Mantener una sola cabeza. Si aparecen múltiples heads por trabajo paralelo, crear merge revision deliberada y revisar el orden semántico.

## Plantilla de migración

```python
"""add election timezone

Revision ID: 20260721_add_timezone
Revises: <previous>
"""

from alembic import op
import sqlalchemy as sa

revision = "20260721_add_timezone"
down_revision = "<previous>"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "elections",
        sa.Column("timezone", sa.String(length=64), nullable=True),
    )
    op.execute("UPDATE elections SET timezone = 'UTC' WHERE timezone IS NULL")
    op.alter_column("elections", "timezone", existing_type=sa.String(64), nullable=False)


def downgrade() -> None:
    op.drop_column("elections", "timezone")
```

El downgrade elimina datos. En producción debe considerarse irreversible aunque exista técnicamente.

## Backfill por lotes

No ejecutar actualizaciones gigantes dentro de una migración DDL si bloquean la tabla. Crear job reanudable:

```python
async def backfill_timezone(session: AsyncSession, batch_size: int = 1000) -> int:
    stmt = (
        select(Election.id)
        .where(Election.timezone.is_(None))
        .order_by(Election.id)
        .limit(batch_size)
        .with_for_update(skip_locked=True)
    )
    ids = list(await session.scalars(stmt))
    if not ids:
        return 0
    await session.execute(
        update(Election).where(Election.id.in_(ids)).values(timezone="UTC")
    )
    await session.commit()
    return len(ids)
```

Requisitos:
- métrica de pendientes/procesados/errores;
- reintentos idempotentes;
- límite de carga;
- validación antes de contract.

## Índices concurrentes

Para tablas grandes:

```python
def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS "
            "ix_audit_events_org_created "
            "ON audit_events (organization_id, created_at)"
        )
```

`CONCURRENTLY` no corre dentro de una transacción. Una migración fallida puede dejar índice inválido; incluir diagnóstico y limpieza controlada.

## Constraint NOT VALID

Para FKs/checks en tablas grandes:

```sql
ALTER TABLE member_election_status
ADD CONSTRAINT fk_mes_election
FOREIGN KEY (election_id) REFERENCES elections(id) NOT VALID;

ALTER TABLE member_election_status
VALIDATE CONSTRAINT fk_mes_election;
```

Permite separar creación y validación, reduciendo bloqueo. Medir en un dataset representativo.

## Transición de estado electoral

Evitar enum rígido si el workflow puede evolucionar. Con CHECK:

```python
op.create_check_constraint(
    "election_status_valid",
    "elections",
    "status IN ('DRAFT','REGISTRATION','REVIEW','FROZEN','ACTIVE',"
    "'CLOSED','TALLYING','TALLIED','PUBLISHED','ARCHIVED')",
)
```

Para agregar estado:
1. Expandir constraint aceptando viejo+nuevo.
2. Desplegar código que comprenda ambos.
3. Migrar filas si aplica.
4. Retirar estado obsoleto posteriormente.

## Inmutabilidad de urna

La aplicación debe impedir UPDATE/DELETE. Puede reforzarse con permisos DB o trigger:

```sql
CREATE FUNCTION prevent_ballot_mutation() RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'encrypted ballots are immutable';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER encrypted_ballots_immutable
BEFORE UPDATE OR DELETE ON encrypted_ballots
FOR EACH ROW EXECUTE FUNCTION prevent_ballot_mutation();
```

Antes de adoptarlo, diseñar procedimientos auditados de recuperación y retención. Las migraciones futuras necesitarán deshabilitación controlada o tablas nuevas, no bypass improvisado.

## Auditoría append-only

- Permisos DB: usuario runtime con `INSERT/SELECT`, sin `UPDATE/DELETE` sobre audit log si la arquitectura lo permite.
- Hash chain opcional: `event_hash = H(previous_hash || canonical_event)`.
- Partición por fecha/elección solo si retención e integridad están documentadas.
- Índices por organización, tipo y timestamp; no indexar secretos.

## PostGIS y GeoAlchemy2

```python
from geoalchemy2 import Geometry

geom = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
```

Migración:

```python
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")
    op.add_column(
        "electoral_areas",
        sa.Column(
            "geom",
            Geometry("MULTIPOLYGON", srid=4326),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_electoral_areas_geom",
        "electoral_areas",
        ["geom"],
        postgresql_using="gist",
    )
```

Algunos diffs de GeoAlchemy2 requieren revisión manual. Verificar que autogenerate no cree/drop tables auxiliares inesperadas.

## Row-Level Security opcional

Si se adopta RLS:

```sql
ALTER TABLE elections ENABLE ROW LEVEL SECURITY;
CREATE POLICY elections_by_org ON elections
USING (organization_id = current_setting('app.organization_id')::uuid);
```

Requisitos:
- setear contexto por transacción, no globalmente en pool;
- usuario runtime sin `BYPASSRLS`;
- política para jobs administrativos explícita;
- tests con dos organizaciones;
- migraciones ejecutadas por rol controlado.

RLS complementa, no reemplaza, filtros de servicio.

## Seed idempotente en Python

```python
from sqlalchemy.dialects.postgresql import insert

stmt = insert(Role).values(code="SUPER_ADMIN", name="Super Admin")
stmt = stmt.on_conflict_do_update(
    index_elements=[Role.code],
    set_={"name": stmt.excluded.name},
)
await session.execute(stmt)
```

Separar:
- `seed_catalogs`: seguro y repetible.
- `bootstrap_admin`: requiere secreto y confirmación.
- `demo_data`: prohibido en producción.

## Preflight de despliegue

```text
1. Confirmar target y versión actual (`alembic current`).
2. Verificar una sola head.
3. Revisar migraciones pendientes y SQL.
4. Confirmar backup/restore según riesgo.
5. Estimar locks, tamaño y duración.
6. Confirmar compatibilidad con app actual.
7. Aplicar desde job único.
8. Verificar `alembic current == head`.
9. Ejecutar smoke checks y métricas.
10. Registrar evidencia sin secretos.
```

## Advisory lock

Evitar dos migradores simultáneos. El pipeline puede adquirir lock PostgreSQL antes de Alembic:

```sql
SELECT pg_advisory_lock(74201901);
-- ejecutar migraciones
SELECT pg_advisory_unlock(74201901);
```

Asegurar unlock en finally/conexión cerrada y timeout operacional.

## Testing de migraciones

### Base vacía

```powershell
python -m alembic upgrade head
python -m alembic check
```

### Upgrade desde versión anterior

1. Crear DB PostGIS efímera.
2. Migrar hasta revisión publicada.
3. Insertar fixtures sintéticos que cubran nulls, duplicados y elecciones en distintos estados.
4. Migrar a head.
5. Validar conteos e invariantes.

### Tests esenciales

- No hay `member_id` ni FK equivalente en urna.
- `receipt_hash` único por elección.
- Doble participación bloqueada.
- Elecciones activas conservan snapshots.
- Tenant cruzado falla.
- Geometrías e índices PostGIS existen.
- Seed repetido produce el mismo estado.

## Diagnóstico de drift

```powershell
python -m alembic current
python -m alembic heads
python -m alembic history --verbose
python -m alembic check
```

No marcar una revisión como aplicada (`stamp`) para ocultar un fallo. `alembic stamp` solo se usa al baselinar o reconciliar con evidencia, revisión Dario y plan documentado.

## Operaciones irreversibles

Una revision puede declarar:

```python
def downgrade() -> None:
    raise RuntimeError("Irreversible data migration; use documented roll-forward")
```

Es más honesto que un downgrade que elimina o corrompe datos. Documentar el procedimiento de recuperación.

## Checklist final

```text
- [ ] Base metadata y naming convention estables
- [ ] Una sola Alembic head
- [ ] Autogenerate revisado manualmente
- [ ] Sin FK identidad -> urna
- [ ] Expand/backfill/contract cuando aplica
- [ ] Locks e índices evaluados
- [ ] PostGIS/GeoAlchemy2 probado
- [ ] Seeds idempotentes y sin defaults inseguros
- [ ] Upgrade desde versión anterior validado
- [ ] Roll-forward y observabilidad documentados
- [ ] Confirmación explícita antes de staging/prod
```
