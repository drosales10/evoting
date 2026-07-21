# Referencia eVoting: superficies, autenticación y autorización

Lee esta referencia cuando una tarea afecte más de una superficie, cambie claims de sesión, añada permisos o toque el flujo de emisión.

## Diagrama de confianza

```mermaid
flowchart LR
  PUBLIC[Portal público] --> PUBLIC_API[/api/v1/public]
  VOTER[Portal elector] --> VOTER_API[/api/v1/voter]
  PARTY[Portal apoderado] --> PARTY_API[/api/v1/party]
  ADMIN[Comisión electoral] --> ADMIN_API[/api/v1/admin]

  VOTER_API --> ROSTER[(Padrón y participación)]
  VOTER_API --> URN[(Urna cifrada)]
  PARTY_API --> DOMAIN[(Elecciones y planchas)]
  ADMIN_API --> DOMAIN
  ADMIN_API --> AUDIT[(Auditoría)]

  ROSTER -. sin FK de identidad .- URN
```

## Modelo conceptual de identidad

```text
organizations
├── admin_users ── admin_user_roles ── roles/permissions
├── members ── member_election_status
├── elections ── positions/slates/candidates
└── encrypted_ballots   # sin FK a members
```

Restricciones mínimas:
- `members`: unicidad de documento normalizado dentro de la organización.
- `member_election_status`: `UNIQUE(election_id, member_id)`.
- `encrypted_ballots`: `UNIQUE(election_id, receipt_hash)` y payload inmutable.
- Ninguna columna de urna puede contener identificadores de miembro, sesión o red.

## Claims y validación

```python
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

class Realm(StrEnum):
    ADMIN = "ADMIN"
    VOTER = "VOTER"

@dataclass(frozen=True)
class Principal:
    subject_id: UUID
    realm: Realm
    organization_id: UUID
    roles: frozenset[str]
    permissions: frozenset[str]
    mfa: bool
    session_id: UUID
```

No confiar en `organization_id` enviado en body o query cuando existe principal autenticado. Resolverlo desde el token y contrastarlo con el recurso.

### Dependency FastAPI administrativa

```python
from fastapi import Depends, HTTPException, status

async def require_admin_permission(
    permission: str,
    principal: Principal = Depends(get_current_principal),
) -> Principal:
    if principal.realm is not Realm.ADMIN:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    if permission not in principal.permissions and "SUPER_ADMIN" not in principal.roles:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Forbidden")
    return principal
```

En implementación real, usar una factory de dependencies para recibir `permission`; no aceptar permisos arbitrarios enviados por el cliente.

### Scope de repositorio

```python
async def get_election_for_update(
    session: AsyncSession,
    election_id: UUID,
    organization_id: UUID,
) -> Election:
    stmt = (
        select(Election)
        .where(
            Election.id == election_id,
            Election.organization_id == organization_id,
        )
        .with_for_update()
    )
    election = await session.scalar(stmt)
    if election is None:
        raise NotFoundError("Election not found")
    return election
```

Preferir `404` para recursos fuera del tenant, evitando confirmar su existencia.

## Matriz de permisos sugerida

| Recurso/acción | SUPER_ADMIN | ELECTORAL_JUSTICE | PARTY_PROXY | CANDIDATE | MEMBER |
|---|---:|---:|---:|---:|---:|
| Crear elección | Sí | Sí, en su org | No | No | No |
| Gestionar padrón | Sí | Sí, en su org | No | No | No |
| Editar plancha | Sí | Revisión | Solo propia y en registro | No | No |
| Ver perfil candidatura | Sí | Sí | Propia | Propia | Público aprobado |
| Autorizar emisión | No | No | No | Si actúa como elector | Sí, elegible |
| Cerrar elección | Sí | Sí, con ceremonia | No | No | No |
| Aportar share de descifrado | Según ceremonia | Custodio autorizado | No | No | No |
| Publicar resultados | Sí | Sí, tras validación | No | No | No |

Los roles son una primera condición. También se validan organización, ownership, estado de elección y separación de funciones.

## Estados y operaciones

```text
DRAFT
  -> REGISTRATION
  -> REVIEW
  -> FROZEN
  -> ACTIVE
  -> CLOSED
  -> TALLYING
  -> TALLIED
  -> PUBLISHED
  -> ARCHIVED
```

Ejemplos:
- Planchas editables solo en `REGISTRATION` y, con observación abierta, `REVIEW`.
- Padrón inmutable desde `FROZEN`.
- Autorizaciones de emisión solo en `ACTIVE` y dentro de ventana horaria.
- Descifrado solo desde `CLOSED` con quórum de custodios.
- Datos públicos de resultados solo en `PUBLISHED`.

## Token de emisión

El token de emisión no es una papeleta y no contiene la selección.

```json
{
  "sub": "member-uuid",
  "org_id": "organization-uuid",
  "election_id": "election-uuid",
  "purpose": "CAST_BALLOT",
  "jti": "random-128-bit",
  "mfa": true,
  "exp": 1780000000
}
```

Persistir:
- `sha256(jti)`
- elección y miembro en el ledger de autorización
- expiración, estado `ISSUED|CONSUMED|REVOKED`

No persistir:
- JWT completo
- payload cifrado junto al ledger
- `receipt_hash` en la fila del miembro

## Transacción de emisión

```python
async with session.begin():
    authorization = await lock_valid_authorization(
        session=session,
        token_hash=token_hash,
        election_id=election_id,
    )
    await lock_and_mark_member_as_voted(
        session=session,
        member_id=authorization.member_id,
        election_id=election_id,
    )
    await consume_authorization(session, authorization)
    await insert_anonymous_ballot(
        session=session,
        election_id=election_id,
        encrypted_payload=encrypted_payload,
        proof=proof,
        receipt_hash=receipt_hash,
    )
```

La operación debe ser atómica para impedir doble voto. Si la política de anonimato exige separación física, usar una cola transaccional/outbox diseñada y auditada; no improvisar dos commits independientes.

## Cookies y CSRF

Usar nombres diferentes, por ejemplo:
- `ev_admin_session`
- `ev_voter_session`
- `ev_csrf`

Reglas:
- `HttpOnly` en cookies de sesión.
- `Secure` fuera de desarrollo local.
- `SameSite=Strict` salvo flujo externo justificado.
- Path restringido cuando sea viable.
- Double-submit o token sincronizado para CSRF.
- Rotación de refresh token y revocación por familia.

## Frontend Next.js

```text
apps/frontend/src/
├── app/(public)/
├── app/(voter)/vote/
├── app/(party)/party/
├── app/(admin)/admin/
├── components/public/
├── components/voter/
├── components/party/
├── components/admin/
└── lib/api/
```

Reglas:
- `proxy.ts` distingue cookies/realms y redirige, pero no decide permisos definitivos.
- Server components pueden hacer checks de presentación.
- No guardar access tokens en `localStorage`.
- `fetch` sensible usa `cache: "no-store"`.
- Evitar analytics de terceros en `/vote/*` y `/receipt/*`.

## APIs recomendadas

```text
POST /api/v1/auth/admin/login
POST /api/v1/auth/voter/request-otp
POST /api/v1/auth/voter/verify-otp
POST /api/v1/auth/refresh
POST /api/v1/auth/logout

GET  /api/v1/public/elections
GET  /api/v1/public/elections/{id}/slates
GET  /api/v1/public/receipts/{receipt_hash}

GET  /api/v1/voter/elections/{id}/eligibility
GET  /api/v1/voter/elections/{id}/ballot
POST /api/v1/voter/elections/{id}/authorize
POST /api/v1/voter/elections/{id}/ballots

GET  /api/v1/party/slates/mine
PATCH /api/v1/party/slates/{id}
POST /api/v1/party/slates/{id}/submit

GET  /api/v1/admin/elections
POST /api/v1/admin/elections
POST /api/v1/admin/elections/{id}/freeze
POST /api/v1/admin/elections/{id}/close
POST /api/v1/admin/elections/{id}/tally
POST /api/v1/admin/elections/{id}/publish
```

## Auditoría

Registrar:
- actor seudonimizado o ID administrativo según el evento
- organización, acción, recurso, resultado, request ID
- cambios administrativos con before/after sanitizado
- eventos MFA, bloqueos, freeze, close, tally y publish

No registrar:
- selección del voto
- payload descifrado individual
- OTP o tokens
- combinación de timestamp exacto de elector y papeleta
- secretos o shares de descifrado

## Pruebas mínimas

### pytest
- Realm incorrecto devuelve 403.
- Recurso de otra organización parece inexistente.
- Apoderado no edita plancha ajena.
- Freeze bloquea cambios aunque el rol sea válido.
- Dos emisiones concurrentes producen exactamente una participación y una papeleta.
- Fallo de inserción revierte consumo de autorización.
- La representación de `EncryptedBallot` no contiene identificadores personales.

### Playwright
- Login admin no autentica portal del elector.
- Login elector MFA no abre `/admin`.
- Flujo de emisión muestra confirmación y recibo.
- Recarga o doble clic no duplica papeleta.
- Sesión expirada vuelve a autenticación sin conservar selección.

## Checklist de revisión de seguridad

```text
- [ ] Threat model actualizado
- [ ] Separación de realms verificada
- [ ] Tenant scope en cada query sensible
- [ ] Estado electoral validado en dominio
- [ ] Urna sin PII ni correladores
- [ ] Tokens y cookies endurecidos
- [ ] Rate limits y anti-enumeración
- [ ] Logs sanitizados
- [ ] Pruebas de concurrencia y doble voto
- [ ] Revisión Vera + QA Iris/Nico
```
