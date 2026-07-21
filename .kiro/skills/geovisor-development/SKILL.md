---
name: geovisor-development
description: >-
  Geovisores electorales con Next.js, Leaflet o DeckGL, FastAPI y PostGIS para
  jerarquías territoriales N0-N4, importación geográfica y mapas agregados de
  participación. Usar al crear mapas, capas, GeoJSON, imports, workers, consultas
  espaciales o paneles territoriales, aplicando aislamiento organizacional,
  supresión de celdas pequeñas y prohibición de exponer identidad o voto.
compatibility: "Next.js 16+, FastAPI, PostgreSQL 15+ con PostGIS, Python 3.12+."
metadata:
  domain: evoting
  version: "2.0"
---

# Desarrollo de geovisores electorales

Usa esta skill para cualquier capacidad cartográfica de eVoting. La referencia extensa está en `reference.md`.

## Propósito y límites

El geovisor permite administrar territorios y visualizar **participación agregada**. No es una herramienta para rastrear electores ni revelar preferencias.

| Superficie | Ruta sugerida | Motor | Función |
|---|---|---|---|
| Administración territorial | `/admin/geography` | Leaflet | Importar, validar y mantener N1-N4 |
| Comisión electoral | `/admin/elections/{id}/participation` | DeckGL o Leaflet | Monitorear agregados autorizados |
| Portal público | `/elections/{id}/map` | DeckGL | Publicar agregados según política |

No mostrar resultados por opción mientras la elección esté `ACTIVE`. La publicación territorial de resultados requiere estado `PUBLISHED` y controles de privacidad.

## Jerarquía electoral N0-N4

| Nivel | Entidad | Geometría típica |
|---|---|---|
| N0 | Organización / ámbito nacional | MultiPolygon |
| N1 | Región / estado / provincia | MultiPolygon |
| N2 | Distrito / circuito / seccional | MultiPolygon |
| N3 | Centro o sede electoral | Point o Polygon |
| N4 | Mesa / urna digital | Sin geometría propia o Point heredado de N3 |

Toda entidad incluye `organization_id`, código estable, nombre, `parent_id`, estado activo y SRID 4326. Validar que cada nivel pertenece al padre y a la misma organización.

## Stack recomendado

- **Admin:** Leaflet + React Leaflet para edición/importación asistida.
- **Analítica:** DeckGL + Mapbox/CARTO para capas grandes y coropletas.
- **API:** FastAPI + Pydantic.
- **Persistencia:** PostgreSQL/PostGIS + SQLAlchemy/GeoAlchemy2.
- **Workers:** proceso Python asíncrono para ZIP shapefile/GeoJSON, validación y simplificación.
- **Tests:** pytest para API/SQL espacial y Playwright para interacción del mapa.

Google Earth Engine no forma parte del alcance electoral salvo requerimiento futuro independiente y aprobado.

## Estructura objetivo

```text
apps/frontend/src/
├── app/(admin)/admin/geography/
├── app/(admin)/admin/elections/[id]/participation/
├── app/(public)/elections/[id]/map/
├── components/geo/admin/
├── components/geo/participation/
└── stores/useElectionGeoStore.ts

apps/backend/app/
├── api/v1/admin/geography.py
├── api/v1/admin/participation.py
├── api/v1/public/maps.py
├── geo/models.py
├── geo/repository.py
├── geo/service.py
└── workers/geography_import.py
```

## Contrato GeoJSON

Cada feature debe incluir:

```json
{
  "type": "Feature",
  "geometry": { "type": "MultiPolygon", "coordinates": [] },
  "properties": {
    "id": "uuid",
    "level": "N2",
    "code": "DIST-001",
    "name": "Distrito 1",
    "parentId": "uuid",
    "eligibleCount": 1200,
    "participationCount": 430,
    "participationPct": 35.83,
    "suppressed": false,
    "updatedBucket": "2026-07-21T14:00:00Z"
  }
}
```

Los campos electorales dependen de la audiencia. La API pública omite conteos o marca `suppressed=true` cuando no se cumple el umbral configurado.

## Privacidad electoral obligatoria

1. Nunca devolver miembro, documento, email, IP, recibo o timestamp individual.
2. Agregar por territorio y ventana temporal, no por evento de voto.
3. Suprimir celdas con denominador o participación por debajo de `PUBLIC_MAP_MIN_GROUP_SIZE`.
4. No permitir filtros que, combinados, reconstruyan grupos pequeños.
5. Redondear timestamps públicos a buckets configurables.
6. No publicar selección o resultado territorial antes de `PUBLISHED`.
7. Aplicar `organization_id` y elección en cada consulta.
8. Auditar exportaciones y consultas administrativas de alta granularidad.

## APIs por audiencia

| Endpoint | Audiencia | Datos |
|---|---|---|
| `/api/v1/admin/geography/*` | Admin | CRUD/import N0-N4 |
| `/api/v1/admin/elections/{id}/participation-map` | Comisión | Agregados internos autorizados |
| `/api/v1/public/elections/{id}/participation-map` | Pública | Agregados suprimidos y cacheables |
| `/api/v1/public/elections/{id}/results-map` | Pública | Solo elección `PUBLISHED` |

No reutilizar directamente el serializer administrativo en endpoints públicos.

## Importación geográfica

1. Aceptar ZIP shapefile o GeoJSON con límite de tamaño.
2. Escanear nombres/extensiones y almacenar fuera del web root.
3. Validar CRS; transformar a EPSG:4326.
4. Ejecutar `ST_MakeValid`, normalizar MultiPolygon y rechazar geometrías vacías.
5. Validar códigos, padres y pertenencia organizacional.
6. Procesar en worker; exponer estado de job sin rutas internas.
7. Publicar cambios solo tras validación completa y transacción.
8. Conservar reporte de errores por fila/feature.

## Capas del mapa de participación

Orden recomendado:
1. Basemap.
2. Polígonos N1/N2 según zoom.
3. Centros N3 agrupados.
4. Mesas N4 solo para comisión y con nivel autorizado.
5. Coropleta de participación.
6. Selección/hover y leyenda.

Evitar renderizar todos los niveles simultáneamente. Usar BBOX, simplificación y clustering.

## Tiempo real

- Preferir SSE para métricas agregadas unidireccionales.
- Mensajes contienen versión de dataset y agregados, nunca eventos individuales.
- Aplicar throttle/debounce y buckets temporales.
- Ante desconexión, reconsultar snapshot por API.
- No usar el canal para resultados antes de publicación.

## Workflow de implementación

### Nueva capa territorial
1. Definir nivel, geometría, padre y constraints.
2. Crear migración PostGIS segura.
3. Implementar repositorio con `organization_id`, `election_id` y BBOX.
4. Exponer DTO administrativo y DTO público separados.
5. Añadir capa, leyenda y accesibilidad en frontend.
6. Añadir pytest espacial y Playwright del mapa.

### Nuevo indicador
1. Definir fórmula, denominador y audiencia.
2. Revisar riesgo de inferencia y umbral de supresión.
3. Agregar en SQL, no en el navegador.
4. Versionar contrato y leyenda.
5. Verificar estados electorales permitidos.

## Anti-patrones

| Evitar | Hacer |
|---|---|
| Puntos por elector | Agregados por territorio |
| Resultado en vivo por opción | Publicar solo tras `PUBLISHED` |
| Consulta sin tenant | Scope org + elección desde el inicio |
| GeoJSON completo sin BBOX | Tiles/BBOX/simplificación |
| Cálculo de privacidad en frontend | Supresión en backend |
| URL pública a archivos importados | Storage privado + worker |
| GEE o capas forestales heredadas | Modelo territorial electoral N0-N4 |
| N4 público sin umbral | Suprimir o subir nivel de agregación |

## Checklist de salida

```text
- [ ] Jerarquía N0-N4 y parentesco validados
- [ ] SRID 4326 y geometrías válidas
- [ ] Tenant y elección aplicados en consultas
- [ ] DTO admin y público separados
- [ ] Supresión de grupos pequeños en backend
- [ ] Estado electoral controla publicación
- [ ] Sin PII, recibos ni eventos individuales
- [ ] BBOX, índices GiST y simplificación
- [ ] Import worker con reporte y límites
- [ ] pytest espacial + Playwright del mapa
```
