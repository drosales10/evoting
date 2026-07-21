---
name: admin-client-split
description: >-
  Patrón de arquitectura dual Admin/Cliente para Next.js App Router con NextAuth,
  RBAC y landing multi-org. Usar al dividir una app en backoffice y área cliente,
  implementar auth dual (User vs ClientUser), guards por capas, shells separados,
  APIs con prefijos admin/cliente, o migrar un monolito a dos superficies de producto.
---

# División Admin / Cliente

Patrón portable basado en SMyEG (Next.js 16 + App Router + NextAuth v5 + Prisma).
Para detalle completo, ver [reference.md](reference.md).

## Modelo mental

No es solo `/admin` vs `/cliente`. Hay **tres superficies**:

| Superficie | Carpeta | URL | Usuario | Autorización |
|---|---|---|---|---|
| Backoffice | `(dashboard)/` | `/dashboard`, `/users`… | `User` | RBAC + CASL |
| Admin puntual | `admin/` | `/admin/login`, `/admin/geovisor` | `User` | Login + permisos |
| Cliente | `cliente/` + `welcome/` | `/cliente/*`, `/welcome/*` | `ClientUser` (opcional) | Org vía landing |

**Regla:** Admin opera con RBAC. Cliente consume datos filtrados por **org activa de landing**, no por rol.

## Estructura de rutas

```
src/app/
├── (auth)/          → /login, /registro-cliente
├── (dashboard)/     → /dashboard, /users (backoffice, sin prefijo URL)
├── admin/           → /admin/login, /admin/geovisor
├── cliente/         → /cliente/{modulo}
└── welcome/         → landing pública por org
```

Route groups `(auth)` y `(dashboard)` **no añaden segmento** a la URL.

## Auth dual (NextAuth)

```typescript
providers: [
  Credentials({ id: "admin-credentials" /* User + organizationId */ }),
  Credentials({ id: "client-credentials" /* ClientUser */ }),
  // OAuth solo para ClientUser
]
// JWT: userType = "ADMIN" | "CLIENT" | "SERVICE"
```

- Dos tablas Prisma: `User` (org + RBAC) y `ClientUser` (sin roles en sesión).
- Logins separados: `/admin/login` vs `/login`.
- Nunca mezclar flujos de autenticación.

## Capas de protección (implementar todas)

| Capa | Ubicación | Función |
|---|---|---|
| 1 | `proxy.ts` | Rutas admin: `userType === "ADMIN"` + RBAC |
| 2 | `(dashboard)/layout.tsx` | Redirect + nav filtrada CASL |
| 3 | `page.tsx` | Checks inline en páginas sensibles |
| 4 | API handlers | `requireAuth()` + `requirePermission()` |
| 5 | APIs cliente | `requireClientAreaOrganization()` |

```typescript
// proxy.ts — lista explícita
const adminProtectedRoutes = ["/dashboard", "/users", "/roles", ...];
const clientProtectedRoutes: string[] = []; // cliente mayormente público
```

En Next.js 16 el guard de red vive en `proxy.ts`, no en `middleware.ts`.

## Autorización por área

**Admin:** RBAC modular → `{moduleSlug}:{ACTION}` + CASL (`ability.can("read", module)`).

**Cliente:** `resolveLandingContext()` resuelve org activa:
1. Query `?organizationId=`
2. Config global `activeLandingOrganizationId`
3. Org por defecto
4. Primera org activa

Nav admin estática filtrada por permisos. Nav cliente **dinámica** desde submodules activos de la org.

## Convenciones de API

| Prefijo | Audiencia | Auth |
|---|---|---|
| `/api/admin/*`, `/api/forest/*`, `/api/users/*` | Admin | RBAC |
| `/api/cliente/*` | Cliente (público) | Org vía landing |
| `/api/client/*` | Cliente autenticado | `userType=CLIENT` |
| `/api/client-auth/*` | Registro/login cliente | Público |
| `/api/client-users/*` | Admin gestiona / cliente self | RBAC o CLIENT |

## Componentes

```
src/components/
├── ui/                    # Compartido (shadcn)
├── DashboardShell.tsx     # Admin
├── client/                # Cliente — prefijo Client*
│   ├── ClientExperienceShell.tsx
│   ├── ClientNavbar.tsx
│   └── ClientModuleShell.tsx
```

No reutilizar `DashboardShell` en cliente. Cada área tiene shell y design system propios.
Todo componente en `components/client/` debe soportar **dark mode** (`dark:`).

## Workflows para agentes

### Nueva feature admin

1. Página en `(dashboard)/{ruta}/`
2. Registrar módulo RBAC `{slug}` en `routeModuleMap` de `proxy.ts`
3. API con `requireAuth()` + `requirePermission(module, action)`
4. Añadir ítem a nav del layout con `module: "{slug}"`

### Nueva feature cliente

1. Página en `cliente/{modulo}/` con `ClientModuleShell`
2. API en `/api/cliente/{modulo}/` con `requireClientAreaOrganization()`
3. Registrar ruta en submodules conocidos (config admin)
4. Nav dinámica vía landing context
5. Dark mode en todos los componentes

### Feature en ambas áreas

Separar implementaciones (`admin/` vs `cliente/`). Compartir solo lógica de dominio en `src/lib/`, nunca UI.

### Migrar monolito

1. Extraer `ClientUser` a tabla propia
2. Crear route groups y prefijos
3. Mover guards a `proxy.ts`
4. Separar shells admin/cliente
5. Migrar APIs por prefijo

## Anti-patrones

| Evitar | Hacer |
|---|---|
| Una tabla `User` con flag `isAdmin` | Dos tablas con responsabilidades claras |
| RBAC en `/cliente/*` | Scope por landing org |
| CRUD operativo en páginas cliente | Admin configura, cliente consume |
| Un layout para todo | Shells separados |
| `/admin/users` para backoffice | Route group → `/users` |
| Org del ClientUser en sesión | Org vía landing context |

## Checklist de implementación

```
- [ ] Modelos User + ClientUser en Prisma
- [ ] NextAuth dual con userType en JWT
- [ ] Route groups + prefijos admin/cliente/welcome
- [ ] proxy.ts con adminProtectedRoutes + routeModuleMap
- [ ] Layout admin con redirect + nav CASL
- [ ] requireClientAreaOrganization en APIs cliente
- [ ] Shells separados (DashboardShell vs ClientExperienceShell)
- [ ] Logins separados
- [ ] Página /unauthorized
- [ ] Dark mode en componentes cliente
- [ ] Tests integration por prefijo API
```

## Referencia SMyEG

| Tema | Archivo |
|---|---|
| Auth | `src/lib/auth.ts` |
| Proxy | `src/proxy.ts` |
| RBAC/CASL | `src/lib/permissions.ts`, `src/lib/ability.ts` |
| Landing | `src/lib/landing-context.ts` |
| Guard API cliente | `src/lib/cliente/require-client-area-organization.ts` |
| Layout admin | `src/app/(dashboard)/layout.tsx` |
| Shell cliente | `src/components/client/ClientExperienceShell.tsx` |
