---
name: geovisor-development
description: >-
  Desarrollo de geovisores SMyEG: admin (Leaflet, import N1-N3) vs cliente
  (DeckGL, Mapbox, GEE scripts). Usar al implementar mapas, capas patrimoniales
  N1-N4, integrar Google Earth Engine, añadir scripts GEE al registry, workers
  geo, PostGIS, o dejar operativos los geovisores admin y cliente.
---

# Desarrollo de Geovisores (Admin vs Cliente)

Patrón SMyEG para mapas operativos. Detalle en [reference.md](reference.md).

## Tres superficies (no confundir)

| Superficie | Ruta | Motor | Rol |
|---|---|---|---|
| **Admin geovisor** | `/admin/geovisor` | Leaflet + OSM | Import/visualizar N1–N3 |
| **Dashboard GIS** | `/dashboard` → `GeoDashboardMap` | Leaflet | CRUD N4, split/merge, import masivo |
| **Cliente geovisor** | `/cliente/geovisor` | DeckGL + Mapbox + GEE | Visualizar N1–N4 + analítica satelital |

**Regla:** Admin opera datos (import). Cliente explora + GEE. Edición geométrica solo en dashboard.

## Stack por área

| Capa | Admin | Cliente |
|---|---|---|
| Mapa | `leaflet` + `react-leaflet` | `deck.gl` + `react-map-gl` + `mapbox-gl` |
| Basemap | OpenStreetMap | Mapbox (fallback CARTO) |
| Vector | GeoJSON vía `/api/admin/geo/*` | GeoJSON vía `/api/gee/vector` |
| Raster | — | GEE `TileLayer` + `BitmapLayer` |
| Estado | `useGeovisorStore.adminLayers` | `useGeovisorStore` (vector, AOI, GEE) |
| GEE | **No** | Scripts registry + ScriptRunner |

## Datos: PostGIS N1–N4

```
forest_geometry_n1  → Organización/ABRAE
forest_geometry_n2  → Finca/Predio
forest_geometry_n3  → Lote/Compartimiento
forest_geometry_n4  → Rodal/Parcela
```

- Geometrías: `Unsupported("geometry(MultiPolygon, 4326)")` en Prisma
- Queries espaciales: `$queryRaw` con PostGIS
- Cliente: `getGeoJsonForLandingOrganization()` → FeatureCollection unificada
- Cada feature debe tener `properties.level`: `"N1"`|`"N2"`|`"N3"`|`"N4"`

## Cliente: arquitectura en capas

```
page.tsx              → layout + sidebar redimensionable (ssr: false)
MapView.tsx           → DeckGL + capas vector/raster/AOI/selección
SidebarStats.tsx      → tabs: buscar, filtros, GIS, inspector, GEE
ScriptRunner.tsx      → ejecutar scripts GEE con AOI
LayerControl.tsx      → toggle N1-N4 + capas raster
useGeovisorStore.ts   → estado compartido
src/gee-scripts/      → registry + implementaciones GEE
/api/gee/*            → vector, tiles, run-script, proxy tiles
```

### Orden de capas DeckGL (MapView)

1. Raster base GEE (`GET /api/gee/tiles`) — oculto si hay script activo
2. Raster dinámico de script (`dynamicGeeRasterUrl`)
3. Contorno AOI del script (GeoJsonLayer rojo)
4. Vector patrimonial filtrado (`GeoJsonLayer`)
5. Halo animado del feature seleccionado

### Carga inicial

```typescript
const [vectorResult, tileResult] = await Promise.allSettled([
  fetch('/api/gee/vector'),
  fetch('/api/gee/tiles'),
]);
// vector → setVectorData (deriva AOI N1-N4/full en store)
// tiles → setTileUrl para TileLayer base
```

## Google Earth Engine — patrón de integración

### Inicialización server-side

```typescript
// src/lib/ee-server.ts
ee.data.authenticateViaPrivateKey({
  client_email: process.env.EE_CLIENT_EMAIL,
  private_key: process.env.EE_PRIVATE_KEY?.replace(/\\n/g, '\n'),
}, () => ee.initialize(...));
```

### APIs GEE

| Ruta | Función |
|---|---|
| `GET /api/gee/status` | Health check credenciales |
| `GET /api/gee/vector` | FeatureCollection N1–N4 (landing org) |
| `GET /api/gee/tiles?year=` | Raster Dynamic World base |
| `POST /api/gee/run-script` | Ejecuta script del registry |
| `GET /api/gee/run-script/tiles` | Proxy tiles EE (anti-CORS) |

**Org context:** todas usan `resolveActiveLandingOrganization()`, no sesión admin.

### Contrato de script GEE

```typescript
// src/gee-scripts/dynamicWorldLulc.ts — plantilla
export type AOI = { type: 'N1'|'N2'|'N3'|'N4'|'full'; geometry: GeoJSON.Geometry };
export type GEEJob = (aoi: AOI, params?: Record<string, unknown>) => Promise<GEEJobResult>;

export interface GEEJobResult {
  urlFormat: string;           // tiles para DeckGL
  warning?: string;
  metrics?: Record<string, unknown>;
  chart?: { byClass: Array<{ name, value, percent, color }> };
  table?: { classes: Array<...> };
}
```

### Añadir un script GEE (workflow)

1. Crear `src/gee-scripts/miScript.ts` implementando `GEEJob`
2. Registrar en `src/gee-scripts/geeScriptRegistry.ts`
3. Script debe: clip por AOI, `getMap()` → `urlFormat`, opcional `reduceRegion` → metrics/chart/table
4. ScriptRunner lo detecta automáticamente del registry
5. Proxy tiles: convertir `urlFormat` externo a `/api/gee/run-script/tiles?path=...&z={z}&x={x}&y={y}`
6. Actualizar store: `setDynamicGeeRasterResult(proxyUrl, aoiType)`

```typescript
// geeScriptRegistry.ts
export const geeScriptRegistry: GEERegisteredScript[] = [
  { id: 'dynamicWorldLulc', name: '...', description: '...', run: runDynamicWorldLULC },
  { id: 'ndviTrend', name: 'NDVI', description: '...', run: runNdviTrend }, // nuevo
];
```

### AOI en ScriptRunner

Prioridad:
1. Feature seleccionado N1–N4 (geometría puntual)
2. Geometría agregada del nivel elegido (`n1Geometry`…`n4Geometry`)
3. `fullExtent` (bbox de toda la org)

Store deriva geometrías agregadas en `setVectorData()` filtrando por `properties.level`.

### Proxy de tiles (obligatorio para scripts)

```typescript
// ScriptRunner — convertir URL externa EE a proxy local
const proxy = `/api/gee/run-script/tiles?path=${encodeURIComponent(mapPath)}&z={z}&x={x}&y={y}`;
setDynamicGeeRasterResult(proxy, effectiveAoi.type);
```

El proxy valida prefix `/v1/projects/earthengine-legacy/maps/` — no aceptar paths arbitrarios.

### Carbono (Server Action aparte)

`src/actions/carbon-analysis.ts` — `calculateCarbonStockAction(areaId)`:
- GEE Random Forest + Dynamic World + DEM SRTM
- Solo N4 seleccionado hoy
- Invocado desde SidebarStats al seleccionar feature N4

## Admin geovisor — patrón Leaflet

```
src/app/admin/geovisor/components/
├── GeovisorLayout.tsx      # mapa + panel 320px
├── AdminMapCanvas.tsx      # Leaflet + capas GeoJSON lazy
├── LayerPanel.tsx          # capas, import, jobs, toolbar
├── GeoImportPanel.tsx      # upload ZIP shapefile
├── JobStatusTracker.tsx    # polling job cada 3s
└── LevelSelector.tsx         # n1/n2/n3
```

### Flujo import N1–N3

```
GeoImportPanel → POST /api/admin/geo/import/{n1|n2|n3} (ZIP)
  → GeoImportJobN* (PENDING) → geo-worker procesa
  → JobStatusTracker polling GET .../jobs/{jobId}
  → completado → invalidate cache capa (setAdminLayerData(level, null))
```

Modos: `UPSERT_GEOMETRY` (default) | `CREATE_ONLY`.

**N4 no está en admin geovisor** — usar dashboard + `/api/forest/geo/*`.

## Store compartido

`src/store/useGeovisorStore.ts` (Zustand):

| Campo | Admin | Cliente |
|---|---|---|
| `adminLayers` n1/n2/n3 | ✓ | — |
| `vectorData` + AOI N1-N4 | — | ✓ |
| `visiblePatrimonialLevels` | — | ✓ |
| `dynamicGeeRasterUrl/AOI` | — | ✓ |
| `selectedFeature` | — | ✓ |

### Persistencia cliente (localStorage)

| Helper | Clave | Qué guarda |
|---|---|---|
| `geovisor-client-storage.ts` | `smyeg:geovisor:client-visible-levels:{org}:{user}` | Visibilidad N1–N4 |
| | `smyeg:geovisor:symbology:{orgId}` | Simbología (compartida admin/cliente) |
| `geovisor-client-sidebar-storage.ts` | `smyeg:cliente-geovisor:sidebar*` | Ancho, tab, filtros |
| `geovisor-client-mapview-storage.ts` | `smyeg:cliente-geovisor:mapview` | lon, lat, zoom, pitch, bearing |

Scope: `sessionStorage.OrganizacionUsuario` + `EmailUsuario`.

## Workers geo

```bash
pnpm worker:geo        # scheduler continuo
pnpm worker:geo:once   # un ciclo diagnóstico
```

Procesa: import N1/N2/N3/N4, recalc superficies, variaciones patrimoniales.

Env: `GEO_WORKER_INTERVAL_MS`, `GEO_N*_IMPORT_BATCH_SIZE`, `GEO_WORKER_SECRET`.

## Variables de entorno

| Variable | Área | Requerida |
|---|---|---|
| `EE_CLIENT_EMAIL` | Cliente GEE | Sí |
| `EE_PRIVATE_KEY` | Cliente GEE | Sí |
| `NEXT_PUBLIC_MAPBOX_TOKEN` | Cliente basemap | Recomendada (fallback CARTO) |
| `GEO_WORKER_SECRET` | Admin import async | Prod |
| `DATABASE_URL` | PostGIS | Sí |

## Checklist geovisor operativo

```
Datos:
- [ ] PostGIS con extensión postgis activa
- [ ] Geometrías N1-N4 importadas para org landing activa
- [ ] Worker geo corriendo (prod: PM2 confor-geo-worker)

Admin:
- [ ] Permiso forest-patrimony + acceso /admin/geovisor
- [ ] Import N1-N3 probado con shapefile ZIP

Cliente:
- [ ] EE_CLIENT_EMAIL + EE_PRIVATE_KEY configurados
- [ ] NEXT_PUBLIC_MAPBOX_TOKEN (o aceptar fallback CARTO)
- [ ] GET /api/gee/status OK
- [ ] GET /api/gee/vector devuelve features con level N1-N4
- [ ] ScriptRunner ejecuta y muestra raster en mapa
- [ ] Dark mode en componentes cliente

GEE scripts:
- [ ] Script registrado en geeScriptRegistry
- [ ] urlFormat proxificado vía /api/gee/run-script/tiles
- [ ] metrics/chart/table si aplica analítica lateral
```

## Mejoras GEE prioritarias

| Gap | Acción |
|---|---|
| Un solo script (`dynamicWorldLulc`) | Añadir NDVI, Hansen loss, etc. al registry |
| Raster base sin proxy | Aplicar proxy tiles a `/api/gee/tiles` también |
| MapLegend no persiste N4 | Guardar symbology en `buildClientGeovisorSymbologyStorageKey` |
| Carbono solo N4 | Extender action para AOI agregados N1–N3 |
| Sin caché scripts | Cache por hash(scriptId+aoi+params) server-side |
| Tiles base URL externa directa | Unificar patrón proxy para todas las capas GEE |

## Workflows para agentes

**Nuevo script GEE:**
> Crear `src/gee-scripts/{id}.ts` con contrato GEEJob → registrar en registry → probar ScriptRunner → verificar proxy tiles en MapView.

**Nueva capa vectorial cliente:**
> Asegurar datos en PostGIS → `getGeoJsonForLandingOrganization` incluye nivel → `properties.level` correcto → MapView filtra por `visiblePatrimonialLevels`.

**Import admin N1-N3:**
> GeoImportPanel → API admin → worker geo → invalidar adminLayers cache.

**Feature DeckGL:**
> Capa en MapView como `GeoJsonLayer`/`TileLayer` → estado en store → persistencia en `geovisor-client-*-storage.ts` → dark mode.

## Anti-patrones

| Evitar | Hacer |
|---|---|
| GEE en admin/dashboard | GEE solo en cliente vía `/api/gee/*` |
| Edición geom en cliente | Dashboard `/api/forest/geo/level4` |
| URL tiles EE directa en cliente | Proxy `/api/gee/run-script/tiles` |
| Lógica GEE en componente React | Scripts en `src/gee-scripts/`, exec server-side |
| Confundir admin geovisor con dashboard | Admin = import N1-N3; Dashboard = CRUD N4 |
| SSR en MapView | `dynamic(..., { ssr: false })` |
| Org de sesión en APIs GEE | `resolveActiveLandingOrganization()` |

## Referencia SMyEG

| Tema | Archivo |
|---|---|
| Cliente mapa | `src/app/cliente/geovisor/components/MapView.tsx` |
| ScriptRunner | `src/app/cliente/geovisor/components/ScriptRunner.tsx` |
| GEE registry | `src/gee-scripts/geeScriptRegistry.ts` |
| Script ejemplo | `src/gee-scripts/dynamicWorldLulc.ts` |
| EE init | `src/lib/ee-server.ts` |
| GeoJSON service | `src/lib/geo-service.ts` |
| Store | `src/store/useGeovisorStore.ts` |
| Admin mapa | `src/app/admin/geovisor/components/AdminMapCanvas.tsx` |
| Worker | `src/workers/geo-worker-scheduler.ts` |
| Plan interno | `internal-docs/agents/17-plan-implementacion-geovisor-cliente-deckgl.md` |
