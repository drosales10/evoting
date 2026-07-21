# Registro de planchas y candidatos

## Alcance de esta fase

Esta primera implementación opera bajo la superficie ADMIN porque todavía no existe una relación segura entre `AdminUser` y una identidad de apoderado (`PARTY_PROXY`). Permite a `SUPER_ADMIN` y `ELECTORAL_JUSTICE` registrar y revisar planchas y candidatos dentro de su organización.

No modifica `encrypted_ballots` ni crea relaciones entre candidatos, miembros y papeletas.

## Reglas de estado

- Las planchas y candidatos se pueden crear únicamente cuando la elección está en `REGISTRATION`.
- Se pueden consultar durante `REGISTRATION` y `FREEZE`.
- En `FREEZE` la operación es de solo lectura.
- La elección debe pertenecer a la organización del token ADMIN.
- Una plancha se crea inicialmente con estado `PENDING`.
- Cada plancha solo puede tener un candidato por posición, según `uq_candidates_slate_position`.

## Planchas

Endpoints:

- `GET /api/v1/admin/elections/{election_id}/slates`
- `POST /api/v1/admin/elections/{election_id}/slates`

Payload de creación:

```json
{
  "name": "Nombre de la plancha",
  "slogan": "Lema opcional",
  "proxy_member_id": null
}
```

`proxy_member_id` es opcional. Si se proporciona, el miembro debe pertenecer a la organización del token. La propiedad operativa de un apoderado todavía no se deriva automáticamente del JWT; por eso esta fase queda limitada a roles electorales ADMIN.

## Candidatos

Endpoints:

- `GET /api/v1/admin/slates/{slate_id}/candidates`
- `POST /api/v1/admin/slates/{slate_id}/candidates`

Payload de creación:

```json
{
  "position_id": "...",
  "member_id": "...",
  "bio": "Biografía opcional"
}
```

El backend verifica que:

1. La plancha pertenezca a la organización del token.
2. La posición pertenezca a la misma elección de la plancha.
3. El miembro pertenezca a la organización.
4. El miembro tenga un snapshot `MemberElectionStatus` elegible para esa elección.
5. La plancha no tenga otro candidato en la posición seleccionada.

No se reciben bytes de foto en estos endpoints. La foto administrativa del miembro permanece en el padrón y la emisión de votos no se implementa en esta fase.

## UI ADMIN

En una elección `REGISTRATION` o `FREEZE`, el dashboard muestra **Gestionar planchas**. Desde allí se puede:

- Consultar las planchas registradas.
- Crear una plancha durante `REGISTRATION`.
- Consultar candidatos por plancha.
- Registrar un candidato seleccionando una posición y un miembro del padrón elegible durante `REGISTRATION`.
- Revisar la información en `FREEZE` sin formularios de mutación.

## Diagnóstico del mensaje de conexión

El mensaje genérico aparecía porque el frontend ejecutaba `response.json()` antes de revisar `response.ok`. Si la cookie `evoting_admin_access` faltaba o había expirado, la API respondía `401 Authentication required`; si la respuesta era vacía, HTML o bloqueada por CORS, el parseo lanzaba una excepción y todos esos casos terminaban mostrando el mismo texto.

La comprobación local confirmó que el backend no estaba caído:

- `GET http://localhost:8000/health` respondió `200`.
- `GET http://localhost:8000/health/ready` respondió `200` con la base de datos disponible.
- `GET /api/v1/admin/elections` sin cookie ADMIN respondió `401` con `Authentication required`.

El componente `apps/frontend/src/components/admin/admin-overview.tsx` ahora usa `requestApiJson`, que distingue:

- Error de red, URL incorrecta o CORS: muestra la URL de la API y una indicación de revisar backend/CORS.
- `401`: indica que la sesión administrativa no está activa o expiró.
- Otros errores HTTP (`403`, `404`, `409`, etc.): muestra el status y el `detail` del backend.
- Respuesta no JSON: indica que la API respondió con un formato inesperado.

La solución no desactiva autenticación, RBAC ni aislamiento organizacional. Para operar la gestión de planchas y candidatos se debe iniciar sesión en la superficie ADMIN y mantener el mismo host configurado entre frontend y backend (`localhost` y `127.0.0.1` no deben mezclarse). Si se usa otro origen para el frontend, debe agregarse explícitamente a `CORS_ORIGINS` manteniendo `allow_credentials=true`.

## Siguiente evolución

Para habilitar el portal real de apoderados se necesita modelar y validar ownership entre `AdminUser` con rol `PARTY_PROXY` y una plancha. Esa evolución debe crear un router `/api/v1/party`, sesión ADMIN separada por permisos y pruebas de ownership antes de permitir mutaciones fuera de la comisión electoral.
