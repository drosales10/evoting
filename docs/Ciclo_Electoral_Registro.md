# Ciclo electoral: registro y congelamiento

Esta fase implementa el paso controlado desde la configuración de una elección hasta el cierre del padrón de elegibilidad. La operación es exclusivamente ADMIN y siempre queda limitada a la organización del token.

## Estados implementados

- `DRAFT`: se pueden configurar posiciones. La elección todavía no tiene snapshot de elegibilidad.
- `REGISTRATION`: se abrió el registro y se creó un snapshot de todos los miembros de la organización.
- `FREEZE`: el snapshot quedó congelado y ya no se puede modificar mediante estos endpoints.

Las transiciones permitidas son únicamente `DRAFT → REGISTRATION → FREEZE`.

## Elegibilidad

Al abrir el registro se crea una fila `member_election_status` por cada miembro de la organización. Un miembro es elegible cuando:

- `members.status = ACTIVE`; y
- `members.alive = true`.

Los miembros inactivos, fallecidos o cuyo campo `Vivo` no esté confirmado como `true` quedan en el snapshot como no elegibles. El snapshot conserva `has_voted = false` y no escribe ninguna referencia en `encrypted_ballots`.

## Endpoints ADMIN

Todos requieren realm ADMIN, rol `SUPER_ADMIN` o `ELECTORAL_JUSTICE`, y aislamiento por `claims.org_id`.

- `POST /api/v1/admin/elections/{election_id}/open-registration`
  - Solo acepta elecciones `DRAFT`.
  - Crea el snapshot de elegibilidad.
  - Cambia el estado a `REGISTRATION`.
- `POST /api/v1/admin/elections/{election_id}/freeze`
  - Solo acepta elecciones `REGISTRATION`.
  - Cambia el estado a `FREEZE`.
  - Registra `frozen_at` en UTC.
- `GET /api/v1/admin/elections/{election_id}/eligibility`
  - Devuelve únicamente conteos agregados: total del snapshot, elegibles y no elegibles.
  - No devuelve nombres, documentos, correos ni relaciones con papeletas.

Respuesta agregada:

```json
{
  "election_id": "...",
  "election_status": "FREEZE",
  "snapshot_member_count": 0,
  "eligible_member_count": 0,
  "ineligible_member_count": 0
}
```

La UI ADMIN muestra `Abrir registro` para elecciones `DRAFT` y `Congelar padrón` para elecciones `REGISTRATION`. Una elección `FREEZE` se presenta como padrón congelado.

## Separación de la urna

`MemberElectionStatus` permite controlar elegibilidad y participación por elección, pero `EncryptedBallot` continúa sin `member_id`, email, documento, sesión o token de emisión. La emisión VOTER/OTP permanece bloqueada hasta configurar un proveedor de entrega y una fase específica de autorización criptográfica.

## Detalle individual de elegibilidad

`GET /api/v1/admin/elections/{election_id}/eligibility/members` permite revisar el snapshot registro por registro. Es una ruta exclusivamente ADMIN, tenant-scoped y no está disponible en las superficies pública o VOTER.

Filtro opcional:

- `?eligible=true`: solo elegibles.
- `?eligible=false`: solo no elegibles.
- Sin parámetro: todos los registros del snapshot.

Cada elemento incluye el código, nombre, documento, correo, estado administrativo, valor de `Vivo`, indicador `eligible` y `reason`. Los motivos actuales son:

- `Cumple: miembro ACTIVE y Vivo confirmado`.
- `Miembro INACTIVE`.
- `Vivo marcado como 0`.
- `Vivo no confirmado`.

El motivo se captura al abrir el registro en `member_election_status.eligibility_reason`. Los snapshots creados antes de la migración `0005_eligibility_reason` usan un fallback calculado para poder revisarse sin reescribir snapshots históricos.

La UI ADMIN muestra el botón **Ver elegibilidad** para elecciones `REGISTRATION` o `FREEZE`, con filtros de todos, solo elegibles y solo no elegibles.

## Migración

`apps/backend/alembic/versions/0005_eligibility_reason.py` agrega de forma expand la columna nullable `eligibility_reason`. No modifica snapshots existentes ni tiene downgrade destructivo automático. Verificar/aplicar con:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```
