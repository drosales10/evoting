---
name: admin-client-split
description: >-
  Arquitectura separada para administración electoral, apoderados, portal público y
  votantes usando Next.js App Router con FastAPI, JWT/MFA, RBAC y aislamiento por
  organización. Usar al crear rutas, sesiones, guards, APIs o shells; implementar
  login administrativo o del elector; proteger operaciones electorales; o evitar
  acoplamiento entre identidad del miembro y urna cifrada.
compatibility: "Next.js 16+, FastAPI, Python 3.12+, PostgreSQL 15+."
metadata:
  domain: evoting
  version: "2.0"
---

# Separación de superficies eVoting

Aplica esta skill para mantener fronteras estrictas entre operación electoral, participación del elector y consulta pública. Para contratos y ejemplos completos, consulta `reference.md`.

## Superficies obligatorias

| Superficie | Rutas UI | Audiencia | Autorización |
|---|---|---|---|
| Pública | `/`, `/elections/*`, `/slates/*`, `/verify/*` | Cualquier visitante | Solo datos publicables |
| Elector | `/vote/*`, `/receipt/*`, `/account/*` | `MEMBER` elegible | MFA + elección + token de emisión |
| Apoderado | `/party/*` | `PARTY_PROXY`, `CANDIDATE` | RBAC + ownership de plancha |
| Comisión | `/admin/*` | `ELECTORAL_JUSTICE`, `SUPER_ADMIN` | RBAC + organización activa |

No compartir layouts, navegación ni sesiones entre comisión y elector. Compartir únicamente componentes UI primitivos y lógica de dominio sin estado de autenticación.

## Arquitectura objetivo

```text
apps/frontend/src/app/
├── (public)/
├── (voter)/vote/[electionId]/
├── (party)/party/
└── (admin)/admin/

apps/backend/app/
├── api/v1/public/
├── api/v1/voter/
├── api/v1/party/
├── api/v1/admin/
├── auth/
├── domain/
└── repositories/
```

Los route groups de Next.js no agregan segmentos. Los prefijos visibles deben mantenerse explícitos para evitar colisiones.

## Identidades separadas

- `AdminUser`: usuarios operativos con organización, roles y permisos.
- `Member`: identidad del padrón y elegibilidad para votar.
- Un candidato o apoderado puede tener una cuenta operativa vinculada a un miembro, pero esa relación nunca llega a la urna.
- `EncryptedBallot` no contiene `member_id`, email, documento, sesión, IP, user-agent ni token de emisión.

## Sesiones y MFA

FastAPI es la autoridad de autenticación. Next.js consume sus APIs y no redefine permisos.

| Realm | Login | Claims mínimos |
|---|---|---|
| Admin/party | `/api/v1/auth/admin/login` | `sub`, `realm=ADMIN`, `org_id`, `roles`, `session_id`, `exp` |
| Elector | `/api/v1/auth/voter/request-otp` + `/verify-otp` | `sub`, `realm=VOTER`, `org_id`, `mfa=true`, `session_id`, `exp` |
| Emisión | `/api/v1/voter/elections/{id}/authorize` | `election_id`, `jti`, `purpose=CAST_BALLOT`, expiración corta |

Reglas:
1. Access token corto y refresh rotatorio en cookie `HttpOnly`, `Secure`, `SameSite=Strict`.
2. Protección CSRF en toda mutación autenticada por cookie.
3. OTP/TOTP/WebAuthn con límites de intentos y auditoría.
4. El token de emisión es de un solo uso; almacenar únicamente hash de `jti`.
5. Nunca guardar la opción votada en sesión, logs o analytics.

## Capas de protección

Implementar todas; ninguna reemplaza a otra:

1. **Next.js `proxy.ts`:** redirección y separación de realms para UX.
2. **Layouts/server components:** no renderizar navegación o datos no autorizados.
3. **FastAPI dependencies:** validar sesión, realm, organización, rol y permiso.
4. **Servicios/repositorios:** exigir `organization_id` y ownership explícitos.
5. **Base de datos:** claves, constraints, transacciones y políticas RLS si se adoptan.

`proxy.ts` no es un control de seguridad suficiente: la API siempre vuelve a autorizar.

## Convenciones de API

| Prefijo | Uso |
|---|---|
| `/api/v1/public/*` | Convocatorias, planchas aprobadas, resultados ya publicados, verificación de recibos |
| `/api/v1/voter/*` | Elegibilidad, boleta, autorización y emisión cifrada |
| `/api/v1/party/*` | Plancha propia, candidatos, documentos y subsanaciones |
| `/api/v1/admin/*` | Padrón, elecciones, revisión, cierre, escrutinio y auditoría |

Toda respuesta sensible debe tener `Cache-Control: no-store`. Los errores no revelan si un documento o correo pertenece al padrón.

## Flujo de emisión seguro

1. Autenticar al miembro con MFA.
2. Verificar organización, elección activa, padrón congelado y elegibilidad.
3. Crear autorización de emisión corta y de un solo uso.
4. Cifrar la selección en el cliente con la clave pública de la elección.
5. En una transacción, consumir autorización, registrar participación y guardar la papeleta cifrada anónima.
6. Emitir recibo verificable que no permita demostrar la selección.
7. Escribir eventos de auditoría sin datos capaces de correlacionar identidad y papeleta.

## RBAC y ownership

- `SUPER_ADMIN`: configuración global; cualquier bypass debe ser explícito y auditado.
- `ELECTORAL_JUSTICE`: administra elecciones de su organización y ejecuta ceremonias autorizadas.
- `PARTY_PROXY`: modifica solo su plancha durante `REGISTRATION` o `CORRECTION`.
- `CANDIDATE`: lectura de su candidatura; sin edición de la elección.
- `MEMBER`: consulta pública y emisión única si es elegible.

Los estados de la elección son parte de la autorización: tener rol no permite editar una plancha congelada ni escrutar una elección activa.

## Reglas de implementación

### Feature administrativa
1. Página bajo `/admin` con shell administrativo.
2. Endpoint bajo `/api/v1/admin`.
3. Dependency FastAPI para realm, organización y permiso.
4. Servicio con validación de estado electoral.
5. Auditoría y tests pytest de permisos/tenant.

### Feature del elector
1. Página bajo `/vote` o `/account` con shell de elector.
2. Endpoint bajo `/api/v1/voter`.
3. MFA y elegibilidad cuando corresponda.
4. Sin acceso directo a CRUD administrativo.
5. Tests pytest del flujo y Playwright del recorrido crítico.

### Feature pública
1. Publicar solo campos aprobados.
2. No exponer padrón, participación individual ni resultados antes del estado permitido.
3. Aplicar rate limiting, cache segura y protección anti-enumeración.

## Anti-patrones

| Evitar | Hacer |
|---|---|
| Una sesión con roles admin y elector mezclados | Realms y cookies separados |
| Confiar solo en guard frontend | Reautorizar siempre en FastAPI |
| `member_id` en `encrypted_ballots` | Tablas y transacciones desacopladas |
| Filtrar tenant después de consultar | Incluir `organization_id` en la consulta |
| Ocultar botones como autorización | Validar permisos en API y dominio |
| Resultados en vivo con granularidad individual | Agregación, umbrales y estados de publicación |
| Reutilizar shell admin en votación | Shells, navegación y copy separados |

## Checklist de salida

```text
- [ ] Superficies pública, elector, apoderado y comisión separadas
- [ ] Realms ADMIN y VOTER separados
- [ ] MFA y refresh rotation configurados
- [ ] API autoriza realm + org + permiso + estado electoral
- [ ] Emission token de un solo uso
- [ ] Urna sin referencias directas o indirectas al miembro
- [ ] Logs y analytics sin selección ni correladores
- [ ] pytest cubre permisos, tenant, doble voto y estados
- [ ] Playwright cubre login MFA, emisión y recibo
- [ ] Cabeceras no-store, CSRF y rate limiting verificados
```
