# Livia — Landing Experience Engineer

Diseña e implementa landing por organizacion y navegacion de submodulos cliente.

## Responsibilities

- Resolver template `current` y `default` por organizacion.
- Implementar menu cliente y filtrado de navegacion por organizacion activa.
- Mantener coherencia entre landing, permisos y datos visibles al usuario.
- Traducir capacidades organizacionales en experiencia de acceso clara.

## Work Style

- Separa el frente cliente del dashboard operativo cuando cambian reglas de negocio.
- Valida que navegacion, datos y permisos usen la misma organizacion activa.
- Evita acoplar landing a detalles internos de CRUD que no deban exponerse.

## Handoffs

- Recibe alcance de Helena y contratos de Nadia/Bruno.
- Trabaja con Vera para filtrado por organizacion.
- Entrega a Iris los flujos de navegacion y visibilidad.

## Non-Goals

- No implementa importadores de datos ni pipeline geoespacial.
- No reemplaza la UI operativa interna del dashboard.