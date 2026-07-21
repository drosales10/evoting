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

## Activación de la votación

La transición `FREEZE → ACTIVE` se ejecuta exclusivamente mediante:

- `POST /api/v1/admin/elections/{election_id}/activate`

Payload:

```json
{
  "public_key": "-----BEGIN PUBLIC KEY-----\\n...\\n-----END PUBLIC KEY-----"
}
```

La clave debe ser una clave pública RSA en formato **SubjectPublicKeyInfo PEM**. No se acepta una clave privada (`BEGIN PRIVATE KEY`/`BEGIN RSA PRIVATE KEY`) ni el formato PKCS#1 `BEGIN RSA PUBLIC KEY`. Si FastAPI devuelve `422`, la UI muestra ahora la ruta y el detalle de validación sin imprimir el contenido de la clave.

Antes de activar, el backend verifica dentro de la organización del token ADMIN que:

- La elección está en `FREEZE` y dentro de su ventana programada.
- Existe un snapshot de elegibilidad y su cantidad coincide con el padrón actual.
- Existe al menos un elector elegible.
- Existe al menos una posición y una plancha.
- Cada plancha tiene candidato para todas las posiciones obligatorias.
- Existe al menos un candidato.
- La clave pública no está vacía y se almacena junto con el estado de la elección.

La activación escribe `activated_at`, cambia el estado a `ACTIVE` y agrega un evento `ELECTION_ACTIVATED` en `audit_logs`. La auditoría guarda únicamente el hash del actor, el hash SHA-256 de la clave pública y conteos agregados; nunca guarda la clave privada, tokens ni selecciones.

La respuesta devuelve conteos de la ceremonia y la huella de la clave pública, no la clave privada. La UI ADMIN muestra **Activar votación** únicamente en elecciones `FREEZE`. La emisión VOTER, los tokens de emisión y la escritura en `encrypted_ballots` siguen fuera de esta fase.

La migración `0006_election_activation` agrega de forma compatible `elections.activated_at` como columna nullable.

## Cierre y preparación del escrutinio

La elección puede cerrarse mediante `POST /api/v1/admin/elections/{election_id}/close`. En operación normal, el backend exige que termine la ventana de votación y que se cumpla el quórum. Para este piloto local existe un cierre explícito con `force_pilot=true`, permitido únicamente con `environment=development` y `VOTER_TEST_MODE=true`; queda registrado como `ELECTION_CLOSED` con conteos agregados y motivo, sin guardar identidad ni selección.

Con 2750 elegibles y un quórum configurado de 8%, se requieren 220 votos. Ocho votos representan una validación técnica del piloto, no el cumplimiento del quórum electoral. El reporte de preparación está disponible en:

```text
GET /api/v1/admin/elections/{election_id}/tally-readiness
```

El reporte indica que el escrutinio requiere una clave privada RSA conservada fuera de la API, que la verificación ZKP aún no está disponible y que no se puede marcar `TALLIED` desde el backend. No se debe pegar ni enviar la clave privada a ADMIN, VOTER o cualquier endpoint HTTP.

Después del cierre, si se conserva la clave privada correspondiente a la clave pública activada, el descifrado se ejecuta únicamente de forma local y de solo lectura:

```powershell
.\\.venv\\Scripts\\python.exe scripts/tally_encrypted_ballots.py `
  --election-id a1f63f11-ee57-4502-b75f-bd8eb6be1a74 `
  --private-key C:\\ruta\\segura\\clave-privada.pem
```

El script verifica que la clave coincida con la clave pública de la elección, valida cada `receipt_hash`, descifra el payload en memoria y muestra conteos por plancha. No escribe resultados, no cambia el estado a `TALLIED`, no guarda la clave privada y falla si alguna boleta no puede validarse o descifrarse.

## Piloto VOTER de ocho votos (solo desarrollo)

La superficie VOTER dispone de entrega OTP por correo mediante Mailtrap y de un fallback de desarrollo controlado. Para instalar el SDK oficial de Python desde `apps/backend`:

```powershell
.\\.venv\\Scripts\\python.exe -m pip install -r requirements.txt
```

Este backend FastAPI usa `mailtrap==2.6.1`, el SDK Python oficial. La versión npm `mailtrap@4.6.0` no debe instalarse en el frontend: el token de Mailtrap nunca puede llegar al navegador.

Configura estas variables en el `.env` local:

```env
MAILTRAP_API_TOKEN=
MAILTRAP_API_MODE=sending
APP_PUBLIC_URL=http://localhost:3000
SMTP_FROM="Entrega de OTP <no-reply@example.com>"
PASSWORD_RESET_TTL_HOURS=2
```

`SMTP_FROM` debe usar un remitente autorizado por el dominio configurado en Mailtrap. Con `MAILTRAP_API_MODE=sending`, una solicitud válida genera un OTP de seis dígitos y lo envía al correo del elector. `PASSWORD_RESET_TTL_HOURS` queda disponible para el flujo futuro de recuperación de contraseña y no modifica la expiración del OTP, que es de cinco minutos.

Para el piloto local, activa además:

```env
VOTER_TEST_MODE=true
VOTER_TEST_CODE=123456
```

`VOTER_TEST_CODE` debe tener seis dígitos y no debe reutilizarse fuera de desarrollo. Reinicia el backend después de cambiarlo. Cuando `VOTER_TEST_MODE=false` y Mailtrap no está configurado, el endpoint mantiene la respuesta anti-enumerable y no crea sesión.

Con `environment=development` y `VOTER_TEST_MODE=true`, cada solicitud válida imprime en la terminal del backend una línea como:

```text
[DEV ONLY] VOTER OTP issued: challenge_id=... code=654321 expires_at=... organization=... identifier=u***@dominio.test
```

El identificador se muestra enmascarado. En modo de prueba el código puede consultarse en la terminal; con Mailtrap configurado también se envía al correo. Si Mailtrap no está disponible, `development + VOTER_TEST_MODE=true` usa explícitamente la terminal como fallback y no bloquea la prueba; fuera de ese contexto el fallo de entrega devuelve `503`. El código solo se imprime bajo esas dos condiciones y nunca debe habilitarse en producción.

Flujo:

1. El elector entra a `/vote/login`, indica el `organization_slug` y su correo o documento, solicita OTP e introduce el código local.
2. La sesión VOTER se emite con cookie distinta de ADMIN y devuelve un token CSRF para las mutaciones.
3. En `/vote`, se introduce el UUID de la elección, se carga la boleta y se selecciona una plancha.
4. El navegador cifra la selección con la clave pública RSA-OAEP/AES-GCM de la elección y envía únicamente `encrypted_payload`, `receipt_hash`, `zkp_proof` de piloto y `key_version`.
5. El backend bloquea la fila de `MemberElectionStatus`, verifica elegibilidad, evita doble voto y registra la boleta sin `member_id`. La participación se marca en el snapshot dentro de la misma transacción.
6. Para probar ocho votos, se repite el flujo con ocho miembros elegibles distintos, usando sesiones de navegador separadas o solicitando OTP nuevamente para cada miembro. Una misma sesión solo puede votar una vez.

Endpoints VOTER:

- `GET /api/v1/voter/elections/{election_id}`
- `POST /api/v1/voter/elections/{election_id}/ballots`

Este piloto verifica la integridad del `receipt_hash` contra el payload, pero todavía no implementa verificación criptográfica de ZKP ni escrutinio/descifrado. Por eso sirve para probar autenticación, elegibilidad, doble voto, cifrado de cliente, recibos y aislamiento de la urna; no es aún una ceremonia electoral de producción.

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
