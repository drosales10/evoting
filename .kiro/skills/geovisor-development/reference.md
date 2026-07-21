# Referencia: Desarrollo de Geovisores (SMyEG)

Documentación detallada para implementar, extender o dejar operativos los geovisores admin y cliente.

## Diagrama de arquitectura global

```mermaid
flowchart TB
  subgraph Surfaces["Superficies UI"]
    AG["/admin/geovisor\nLeaflet N1-N3"]
    DG["/dashboard\nGeoDashboardMap\nLeaflet N1-N4 CRUD"]
    CG["/cliente/geovisor\nDeckGL+Mapbox\nN1-N4 + GEE"]
  end

  subgraph APIs["API Layer"]
    AGEO["/api/admin/geo/*"]
    FGEO["/api/forest/geo/*"]
    GEE["/api/gee/*"]
  end

  subgraph Core["Core Services"]
    GIW[geo-import-worker.ts]
    GS[geo-service.ts]
    EES[ee-server.ts]
    GSR[geeScriptRegistry]
  end

  subgraph Infra["Infra"]
    PG[(PostgreSQL + PostGIS)]
    EE[Google Earth Engine]
    GW[geo-worker-scheduler]
  end

  AG --> AGEO
  DG --> AGEO & FGEO
  CG --> GEE

  AGEO --> PG
  FGEO --> PG
  GEE --> GS --> PG
  GEE --> EES --> EE
  GEE --> GSR --> EE

  AGEO --> GIW
  FGEO --> GIW
  GW --> GIW --> PG
```

## Jerarquía patrimonial N1–N4

| Nivel | Tabla PostGIS | Entidad | Admin geovisor | Cliente | Dashboard |
|---|---|---|---|---|---|
| N1 | `forest_geometry_n1` | Organización/ABRAE | Import + ver | Ver + filtrar | Full GIS |
| N2 | `forest_geometry_n2` | Finca/Predio | Import + ver | Ver + filtrar | Full GIS |
| N3 | `forest_geometry_n3` | Lote/Compartimiento | Import + ver | Ver + filtrar | Full GIS |
| N4 | `forest_geometry_n4` | Rodal/Parcela | **No** | Ver + filtrar | CRUD + import |

Triggers PostGIS (SQL, no Prisma):
```sql
CREATE OR REPLACE FUNCTION public.fn_calculate_forest_metrics()
RETURNS TRIGGER AS $$
BEGIN
  NEW.geom := ST_Multi(ST_MakeValid(NEW.geom));
  NEW.centroid := ST_PointOnSurface(NEW.geom);
  NEW.superficie_ha := ST_Area(NEW.geom::geography) / 10000;
  NEW.updated_at := NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;
```

## Admin geovisor — detalle

### Estructura de archivos

```
src/app/admin/geovisor/
├── page.tsx                    # dynamic ssr:false
└── components/
    ├── GeovisorLayout.tsx
    ├── AdminMapCanvas.tsx      # Leaflet MapContainer
    ├── LayerPanel.tsx
    ├── GeoImportPanel.tsx
    ├── JobStatusTracker.tsx    # poll 3s
    ├── LevelSelector.tsx
    ├── AdminToolbar.tsx        # export PNG/GeoJSON
    └── ImportTemplateDownload.tsx
```

### Protección

- Ruta `/admin/geovisor` en `adminProtectedRoutes` (`src/proxy.ts`)
- Requiere `userType === "ADMIN"` + RBAC módulo `dashboard`
- API: permiso `forest-patrimony` READ/CREATE/UPDATE

### Carga lazy de capas

```typescript
// AdminMapCanvas.tsx
const fetchLayerData = async (level: AdminLevel) => {
  const layer = useGeovisorStore.getState().adminLayers[level];
  if (layer.data !== null || layer.loading) return;
  setAdminLayerLoading(level, true);
  const res = await fetch(`/api/admin/geo/import/${level}/features`);
  if (res.ok) setAdminLayerData(level, (await res.json()).data);
  setAdminLayerLoading(level, false);
};
```

- Basemap: OpenStreetMap (no Mapbox)
- Panes por nivel con z-index según `order`
- Simbología: `SymbologyPicker` → `localStorage` `smyeg:geovisor:symbology:{orgId}`

### API admin geo

| Ruta | Métodos | Descripción |
|---|---|---|
| `/api/admin/geo/import/[level]` | GET, POST | Plantilla + upload ZIP |
| `/api/admin/geo/import/[level]/features` | GET, PATCH | GeoJSON + media |
| `/api/admin/geo/import/[level]/jobs` | GET | Listado jobs |
| `/api/admin/geo/import/[level]/jobs/[jobId]` | GET | Detalle job |

Levels: `n1`, `n2`, `n3` solamente.

### Import workflow

1. Usuario sube ZIP (.shp/.shx/.dbf/.prj)
2. `POST /api/admin/geo/import/{level}` crea job
3. Sin `GEO_WORKER_SECRET`: procesamiento inline
4. Con secret: job `PENDING` → `geo-worker-scheduler` consume
5. `JobStatusTracker` polling → al completar invalida cache capa

## Dashboard GIS (GeoDashboardMap)

- Componente grande (~6200 líneas) en `src/components/GeoDashboardMap*.tsx`
- Leaflet + `/api/forest/geo/*`
- CRUD N4, split/merge, import masivo, edición draw
- **No integra GEE** — separado del cliente
- Usar para operaciones geométricas; no duplicar en admin geovisor simplificado

### API forest geo (dashboard)

| Ruta | Descripción |
|---|---|
| `/api/forest/geo/import` | Import masivo N4 |
| `/api/forest/geo/level4` | CRUD N4 desde mapa |
| `/api/forest/geo/layers/nivel4` | Features N4 por bbox |
| `/api/forest/geo/operations` | Split/merge rodales |

## Cliente geovisor — detalle

### Estructura de archivos

```
src/app/cliente/geovisor/
├── page.tsx                    # MapView + SidebarStats, ssr:false
└── components/
    ├── MapView.tsx             # DeckGL orquestador
    ├── SidebarStats.tsx        # 5 tabs
    ├── ScriptRunner.tsx        # GEE scripts
    ├── LayerControl.tsx
    ├── FeatureInspector.tsx
    ├── MapLegend.tsx
    └── storage.ts              # legacy helper
```

### Dependencias mapa cliente

```json
"deck.gl": "^9.3.1",
"@deck.gl/layers": "^9.3.1",
"@deck.gl/geo-layers": "^9.3.1",
"@deck.gl/react": "^9.3.1",
"mapbox-gl": "^3.22.0",
"react-map-gl": "^8.1.1",
"@google/earthengine": "^1.7.25",
"@turf/turf": "^7.3.4"
```

### MapView — capas DeckGL

```typescript
// Orden de render (de abajo a arriba)
const layers = [
  // 1. Raster base GEE (si no hay script activo)
  new TileLayer({ id: 'gee-base-raster', data: tileUrl, ... }),
  // 2. Raster dinámico script
  dynamicGeeRasterUrl && new TileLayer({ id: 'gee-script-raster', ... }),
  // 3. Contorno AOI script
  dynamicGeeRasterAOI && new GeoJsonLayer({ id: 'gee-aoi-outline', ... }),
  // 4. Vector patrimonial
  new GeoJsonLayer({ id: 'patrimonial-vector', data: filteredFeatures, ... }),
  // 5. Halo selección
  selectedFeature && new GeoJsonLayer({ id: 'selection-halo', ... }),
];
```

### Basemap Mapbox

```typescript
const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN || '';
const FALLBACK_MAP_STYLE = 'https://basemaps.cartocdn.com/gl/positron-gl-style/style.json';

// Sin token → CARTO + toast warning
// Con token → estilos Mapbox (satellite, dark, streets, etc.)
```

Basemaps disponibles: dark-v11, streets-v12, light-v11, outdoors-v12, satellite-v9, navigation-day/night.

### Colores por nivel (cliente)

```typescript
const DEFAULT_LEVEL_COLORS = {
  N1: [16, 185, 129, 100],   // verde
  N2: [59, 130, 246, 100],   // azul
  N3: [245, 158, 11, 100],  // ámbar
  N4: [168, 85, 247, 100],  // púrpura (configurable symbology)
};
```

## Google Earth Engine — guía completa

### Credenciales

```env
EE_CLIENT_EMAIL=service-account@project.iam.gserviceaccount.com
EE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
```

Health check: `GET /api/gee/status`

### Flujo ScriptRunner → MapView

```mermaid
sequenceDiagram
  participant SR as ScriptRunner
  participant API as POST /api/gee/run-script
  participant REG as geeScriptRegistry
  participant EE as Earth Engine
  participant Store as useGeovisorStore
  participant MV as MapView

  SR->>SR: getEffectiveAOI()
  SR->>API: { scriptId, aoi, params }
  API->>REG: getGEEJobById(scriptId)
  REG->>EE: script.run(aoi, params)
  EE-->>API: { urlFormat, metrics, chart, table }
  API-->>SR: result
  SR->>SR: toProxyTileTemplate(urlFormat)
  SR->>Store: setDynamicGeeRasterResult(proxyUrl, aoiType)
  Store->>MV: re-render TileLayer script
```

### Plantilla para nuevo script GEE

```typescript
// src/gee-scripts/ndviTrend.ts
import ee from '@google/earthengine';
import type { GEEJob, AOI, GEEJobResult } from './dynamicWorldLulc';

export const runNdviTrend: GEEJob = async (aoi, params = {}) => {
  const eeGeometryFactory = ee as unknown as { Geometry: (g: object) => unknown };
  const region = (eeGeometryFactory.Geometry(aoi.geometry) as { simplify: (n: number) => unknown })
    .simplify(100);

  const startDate = (params.startDate as string) ?? '2020-01-01';
  const endDate = (params.endDate as string) ?? new Date().toISOString().slice(0, 10);

  const collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
    .filterDate(startDate, endDate)
    .filterBounds(region)
    .map((img: unknown) => {
      // calcular NDVI por imagen
      return img;
    });

  const median = collection.median().clip(region);

  const visParams = { min: -0.2, max: 0.8, palette: ['red', 'yellow', 'green'] };

  const mapInfo = await new Promise<{ urlFormat: string }>((resolve, reject) => {
    (median as { getMap: (v: unknown, cb: (r: { urlFormat: string }, e: unknown) => void) => void })
      .getMap(visParams, (res, err) => err ? reject(err) : resolve(res));
  });

  return {
    urlFormat: mapInfo.urlFormat,
    metrics: { script: 'ndviTrend', aoiType: aoi.type, startDate, endDate },
    // chart/table opcionales para panel lateral
  };
};
```

Registrar:
```typescript
// geeScriptRegistry.ts
import { runNdviTrend } from './ndviTrend';

export const geeScriptRegistry = [
  // ... existentes
  {
    id: 'ndviTrend',
    name: 'NDVI (Sentinel-2)',
    description: 'Índice de vegetación mediano en el periodo seleccionado.',
    run: runNdviTrend,
  },
];
```

### Parámetros UI en ScriptRunner

Para scripts con params custom, extender ScriptRunner:
- Detectar `scriptId` y mostrar inputs (fechas, año, bandas)
- Pasar en body: `{ scriptId, aoi, params: { startDate, endDate, year } }`
- `dynamicWorldLulc` ya soporta `startDate`, `endDate`, `year`

### Proxy tiles — seguridad

```typescript
// /api/gee/run-script/tiles/route.ts
const ALLOWED_PREFIX = '/v1/projects/earthengine-legacy/maps/';
// Solo paths que empiecen con ALLOWED_PREFIX y contengan /tiles/
// Fetch a https://earthengine.googleapis.com{tilePath}
// Cache-Control: private, max-age=60
```

### Raster base vs script — unificar proxy

**Gap actual:** tiles base (`/api/gee/tiles`) devuelven URL externa consumida directamente por DeckGL. Scripts usan proxy.

**Mejora recomendada:**
```typescript
// Opción A: proxy en API tiles
return NextResponse.json({
  urlFormat: `/api/gee/run-script/tiles?path=${encodeURIComponent(mapPath)}&z={z}&x={x}&y={y}`
});

// Opción B: endpoint dedicado /api/gee/tiles/proxy/{z}/{x}/{y}
```

### Caché de scripts (mejora)

```typescript
// Pseudocódigo server-side
const cacheKey = crypto.createHash('sha256')
  .update(`${scriptId}:${JSON.stringify(aoi)}:${JSON.stringify(params)}`)
  .digest('hex');

const cached = await redis.get(`gee:script:${cacheKey}`);
if (cached) return JSON.parse(cached);

const result = await script.run(aoi, params);
await redis.setex(`gee:script:${cacheKey}`, 3600, JSON.stringify(result));
return result;
```

### Carbono — extender a AOI agregados

Hoy: solo N4 via `calculateCarbonStockAction(areaId)`.

Mejora:
```typescript
// Nueva action o extensión
export async function calculateCarbonStockForAOI(aoi: AOI) {
  // Usar aoi.geometry directamente sin query N4
  // Invocar desde SidebarStats cuando AOI = N1/N2/N3/full
}
```

## geo-service.ts — vector cliente

```typescript
export async function getGeoJsonForLandingOrganization(organizationId: string) {
  const [n1Rows, n2Rows, n3Rows, n4Rows] = await Promise.all([
    // queries PostGIS con ST_AsGeoJSON(ST_Simplify(geom, 0.001))
    // is_active = TRUE, organization_id = orgId
  ]);
  return {
    type: 'FeatureCollection',
    features: [...n1Features, ...n2Features, ...n3Features, ...n4Features],
  };
}
```

Cada feature:
```typescript
properties: {
  level: 'N1' | 'N2' | 'N3' | 'N4',  // MAYÚSCULAS — crítico para store
  superficieHa: number,
  code, name, type, // según nivel
}
```

## useGeovisorStore — derivación AOI

```typescript
setVectorData: (data) => {
  // Filtra features por properties.level
  // Calcula n1Geometry, n2Geometry, n3Geometry, n4Geometry (union/bbox)
  // Calcula fullExtent (bbox de toda la colección)
  // Usado por ScriptRunner para AOI agregada
}
```

Estado GEE dinámico:
```typescript
dynamicGeeRasterUrl: string | null;
dynamicGeeRasterAOI: GeeScriptAOIType | null;
setDynamicGeeRasterResult: (url, aoiType) => void;
clearDynamicGeeRasterResult: () => void;
```

## SidebarStats — tabs

| Tab | Componente | Función |
|---|---|---|
| Buscar | búsqueda texto | Filtra features por nombre/código |
| Filtros | nivel + visibilidad | `visiblePatrimonialLevels`, `activeLevel` |
| GIS | LayerControl | Toggle capas vector/raster |
| Inspector | FeatureInspector | Props del feature seleccionado |
| GEE | ScriptRunner | Ejecutar scripts + ver métricas/gráficos |

Persistencia tab/filtros: `geovisor-client-sidebar-storage.ts`.

## Workers geo — detalle

**Scheduler:** `src/workers/geo-worker-scheduler.ts`

| Función | Job | Tabla |
|---|---|---|
| `processNextN1ImportJob` | Import N1 | `GeoImportJobN1` |
| `processNextN2ImportJob` | Import N2 | `GeoImportJobN2` |
| `processNextN3ImportJob` | Import N3 | `GeoImportJobN3` |
| `processNextPendingImportJob` | Import N4 legacy | `GeoImportJob` |
| `processNextRecalcJob` | Recalc superficies | `forest_geometry_recalc_jobs` |
| `processNextGeoVariationJob` | Variaciones | `GeoLandVariationJob` |

**PM2:** `ecosystem.config.cjs` → `confor-geo-worker`

Env vars:
```
GEO_WORKER_INTERVAL_MS=4000
GEO_N1_IMPORT_BATCH_SIZE=...
GEO_N2_IMPORT_BATCH_SIZE=...
GEO_N3_IMPORT_BATCH_SIZE=...
GEO_IMPORT_BATCH_SIZE=...        # N4
GEO_RECALC_BATCH_SIZE=...
GEO_VARIATION_BATCH_SIZE=...
GEO_WORKER_RUN_ONCE=true         # diagnóstico
GEO_WORKER_SECRET=...            # delegar import HTTP
```

## Simbología compartida

- Admin N1–N3: `initializeAdminLayers(orgId)` lee/escribe `smyeg:geovisor:symbology:{orgId}`
- Cliente N4: `loadN4Symbology()` lee misma clave, campo `.n4`
- Componente: `SymbologyPicker` (`src/components/SymbologyPicker.tsx`)
- **Gap:** `MapLegend` no persiste cambios N4 al modificar — solo lee al cargar

Fix recomendado:
```typescript
// MapLegend onChange
const { organizationId } = resolveClientGeovisorStorageScope();
const key = buildClientGeovisorSymbologyStorageKey({ organizationId });
const existing = JSON.parse(localStorage.getItem(key) ?? '{}');
localStorage.setItem(key, JSON.stringify({ ...existing, n4: newSymbology }));
```

## Dark mode (cliente)

- `ClientExperienceShell` hereda tema root
- Clases `dark:` en panel geovisor, ScriptRunner, sidebar
- Mapbox: estilos `dark-v11`, `navigation-night-v1`
- DeckGL: colores RGBA con alpha para polígonos sobre basemap oscuro

## Mobile (sataa-mobile)

```
apps/sataa-mobile/src/components/GeovisorMap.tsx
apps/sataa-mobile/src/services/geovisor-cache.ts
```

Reutiliza `NEXT_PUBLIC_MAPBOX_TOKEN` / `EXPO_PUBLIC_MAPBOX_TOKEN`.

## Plan de implementación (fases)

Referencia: `internal-docs/agents/17-plan-implementacion-geovisor-cliente-deckgl.md`

| Fase | Contenido | Estado |
|---|---|---|
| 1 | Shell cliente + ssr:false | ✓ |
| 2 | DeckGL + Mapbox | ✓ |
| 3 | Sidebar funcional | ✓ |
| 4 | Store + persistencia | ✓ |
| 5 | GEE vector + raster + scripts | ✓ |
| 6 | Endurecimiento (proxy base, caché, tests) | Parcial |

## Scripts GEE sugeridos para registry

| ID | Dataset GEE | Uso |
|---|---|---|
| `dynamicWorldLulc` | GOOGLE/DYNAMICWORLD/V1 | ✓ Implementado |
| `ndviTrend` | COPERNICUS/S2_SR_HARMONIZED | Vegetación temporal |
| `forestLoss` | UMD/hansen/global_forest_change_2023_v1 | Pérdida bosque |
| `elevation` | USGS/SRTMGL1_003 | Topografía |
| `precipitation` | NASA/GPM_L3/IMERGR_V07 | Hidrología cliente |
| `fireRisk` | FIRMS o MODIS | Alertas SATAA |

Cada uno: mismo contrato `GEEJob`, clip AOI, getMap, reduceRegion opcional.

## Checklist deploy producción

```
Infra:
- [ ] PostgreSQL 15 + PostGIS (no postgres:15-alpine sin PostGIS)
- [ ] EE service account con Earth Engine activado
- [ ] NEXT_PUBLIC_MAPBOX_TOKEN en env
- [ ] GEO_WORKER_SECRET + PM2 geo-worker

Datos:
- [ ] Migraciones aplicadas (pnpm db:migrate:safe)
- [ ] Geometrías importadas para org landing activa
- [ ] Seed/config: activeLandingOrganizationId en system config

Validación:
- [ ] GET /api/gee/status → 200
- [ ] GET /api/gee/vector → FeatureCollection con N1-N4
- [ ] GET /api/gee/tiles → urlFormat válido
- [ ] POST /api/gee/run-script → raster visible en mapa
- [ ] Proxy tiles carga sin CORS errors
- [ ] Admin import N1-N3 completa job
- [ ] pnpm qa:module verde
```

## Prompts para agentes

**Añadir script GEE NDVI:**
> Crear `src/gee-scripts/ndviTrend.ts` con GEEJob, clip AOI, getMap, registrar en registry, verificar ScriptRunner + proxy tiles + dark mode panel resultados.

**Capa vectorial nueva en MapView:**
> Filtrar en store por level, GeoJsonLayer con getFillColor/getLineColor, toggle en LayerControl, persistir visibilidad en geovisor-client-storage.

**Fix raster base sin proxy:**
> Modificar `/api/gee/tiles` para devolver URL proxy local, actualizar MapView TileLayer data template.

**Import shapefile admin:**
> GeoImportPanel → validar ZIP → POST admin API → JobStatusTracker → test worker:geo:once.

**Carbono AOI N3:**
> Extender carbon-analysis.ts para aceptar geometría agregada del store, botón en SidebarStats cuando activeLevel=N3.

## Mapa de archivos

```
src/app/admin/geovisor/
src/app/cliente/geovisor/
src/components/GeoDashboardMap.tsx
src/components/SymbologyPicker.tsx
src/store/useGeovisorStore.ts
src/gee-scripts/
src/lib/ee-server.ts
src/lib/geo-service.ts
src/lib/geovisor-client-*.ts
src/app/api/gee/
src/app/api/admin/geo/
src/app/api/forest/geo/
src/workers/geo-worker-scheduler.ts
src/lib/geo-import-worker.ts
src/actions/carbon-analysis.ts
internal-docs/agents/17-plan-implementacion-geovisor-cliente-deckgl.md
ecosystem.config.cjs
docker-compose.yml
```
