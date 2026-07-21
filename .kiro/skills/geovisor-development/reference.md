# Referencia eVoting: geografía y participación agregada

Usa esta referencia al diseñar tablas PostGIS, contratos GeoJSON, imports o visualizaciones de participación/resultados.

## Arquitectura

```mermaid
flowchart TB
  ADMIN[Admin Geography] --> ADMIN_API[/api/v1/admin/geography]
  BOARD[Commission Map] --> BOARD_API[/api/v1/admin/elections/id/participation-map]
  PUBLIC[Public Map] --> PUBLIC_API[/api/v1/public/elections/id/*-map]

  ADMIN_API --> WORKER[Python import worker]
  WORKER --> POSTGIS[(PostgreSQL + PostGIS)]
  BOARD_API --> AGG[Aggregation service] --> POSTGIS
  PUBLIC_API --> PRIVACY[Publication + suppression policy] --> AGG
```

## Modelo de datos sugerido

Puede usarse una tabla jerárquica o tablas por nivel. Una tabla única simplifica navegación y constraints comunes:

```python
class ElectoralArea(Base):
    __tablename__ = "electoral_areas"

    id: Mapped[UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id"), nullable=False, index=True
    )
    parent_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("electoral_areas.id"), nullable=True
    )
    level: Mapped[str] = mapped_column(String(2), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    geom = mapped_column(Geometry("MULTIPOLYGON", srid=4326), nullable=True)
    point = mapped_column(Geometry("POINT", srid=4326), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    __table_args__ = (
        UniqueConstraint("organization_id", "level", "code"),
        CheckConstraint("level IN ('N0','N1','N2','N3','N4')"),
        Index("ix_electoral_areas_geom", "geom", postgresql_using="gist"),
        Index("ix_electoral_areas_point", "point", postgresql_using="gist"),
    )
```

Relaciones electorales:

```text
members -> electoral_area_id (área de elegibilidad)
voting_assignments -> member_id + election_id + voting_table_id
election_area_snapshots -> election_id + area_id + eligible_count
election_participation -> election_id + area_id + participation_count
```

Los snapshots congelan denominadores al cerrar el padrón. No calcular participación histórica contra el padrón actual.

## Constraints y validaciones

- N0 no tiene padre.
- N1 es hijo de N0; N2 de N1; N3 de N2; N4 de N3.
- Padre e hijo comparten `organization_id`.
- N0-N2 requieren `geom`; N3 requiere `point` o `geom`; N4 puede heredar ubicación de N3.
- Geometrías válidas, no vacías y con SRID 4326.
- Áreas de una organización no pueden referenciar elecciones de otra.

La validación de parentesco entre filas suele implementarse en servicio o trigger; cubrirla con tests.

## Índices PostGIS

```sql
CREATE INDEX ix_electoral_areas_geom
ON electoral_areas USING GIST (geom);

CREATE INDEX ix_electoral_areas_point
ON electoral_areas USING GIST (point);

CREATE INDEX ix_participation_election_area
ON election_participation (election_id, area_id);
```

Para BBOX:

```sql
SELECT id, level, code, name,
       ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, :tolerance))::json AS geometry
FROM electoral_areas
WHERE organization_id = :organization_id
  AND level = ANY(:levels)
  AND geom && ST_MakeEnvelope(:west, :south, :east, :north, 4326);
```

Parametrizar valores. No interpolar BBOX, IDs ni nombres de nivel en SQL.

## Snapshot de participación

Fórmula base:

```text
participation_pct = 100 * participation_count / eligible_count
```

Reglas:
- `eligible_count` proviene del snapshot congelado de la elección.
- `participation_count` cuenta estados de participación, no papeletas descifradas.
- La suma territorial puede diferir si hay miembros sin asignación; reportar categoría `UNASSIGNED` internamente.
- La urna no se une con miembros para construir el mapa.

Consulta conceptual:

```sql
SELECT s.area_id,
       s.eligible_count,
       COALESCE(p.participation_count, 0) AS participation_count,
       CASE WHEN s.eligible_count = 0 THEN 0
            ELSE ROUND(100.0 * COALESCE(p.participation_count, 0) / s.eligible_count, 2)
       END AS participation_pct
FROM election_area_snapshots s
LEFT JOIN election_participation p
  ON p.election_id = s.election_id
 AND p.area_id = s.area_id
WHERE s.election_id = :election_id;
```

## Política de publicación y supresión

Configurar por organización/elección:

```env
PUBLIC_MAP_MIN_GROUP_SIZE=20
PUBLIC_MAP_TIME_BUCKET_MINUTES=60
PUBLIC_MAP_MAX_LEVEL=N2
```

Son valores operativos, no universales. Deben revisarse conforme a normativa y threat model.

Algoritmo recomendado:

```python
def public_metric(row: ParticipationRow, policy: MapPrivacyPolicy) -> dict:
    should_suppress = (
        row.eligible_count < policy.min_group_size
        or row.participation_count < policy.min_participation_count
        or level_rank(row.level) > level_rank(policy.max_public_level)
    )
    if should_suppress:
        return {
            "suppressed": True,
            "eligibleCount": None,
            "participationCount": None,
            "participationPct": None,
        }
    return serialize_public_row(row)
```

Evitar que el total padre menos hijos visibles revele una celda suprimida. Aplicar supresión complementaria o no publicar desgloses incompatibles.

## Estados electorales

| Estado | Comisión | Público |
|---|---|---|
| DRAFT/REGISTRATION/FROZEN | Datos de configuración | Sin métricas |
| ACTIVE | Participación agregada según permiso | Solo participación si política lo permite |
| CLOSED/TALLYING | Participación final | Participación final, sin resultados |
| TALLIED | Resultados internos | Sin resultados hasta aprobación |
| PUBLISHED | Resultados agregados | Resultados publicados y suprimidos |

Nunca incluir selección individual ni dataset que permita reconstruirla.

## Contratos Pydantic separados

```python
class AdminAreaMetric(BaseModel):
    id: UUID
    level: Literal["N0", "N1", "N2", "N3", "N4"]
    eligible_count: int
    participation_count: int
    participation_pct: Decimal
    updated_at: datetime

class PublicAreaMetric(BaseModel):
    id: UUID
    level: Literal["N0", "N1", "N2", "N3", "N4"]
    suppressed: bool
    participation_pct: Decimal | None
    updated_bucket: datetime | None
```

No construir `PublicAreaMetric` serializando primero el DTO administrativo.

## Endpoints

### Administración geográfica

```text
POST /api/v1/admin/geography/imports
GET  /api/v1/admin/geography/imports/{job_id}
GET  /api/v1/admin/geography/areas?levels=N1,N2&bbox=...
PATCH /api/v1/admin/geography/areas/{area_id}
POST /api/v1/admin/geography/validate
```

### Mapas electorales

```text
GET /api/v1/admin/elections/{election_id}/participation-map
GET /api/v1/public/elections/{election_id}/participation-map
GET /api/v1/public/elections/{election_id}/results-map
GET /api/v1/public/elections/{election_id}/map-stream
```

El stream público solo emite agregados ya suprimidos.

## Worker de importación

```text
UPLOADED -> VALIDATING -> PROCESSING -> COMPLETED
                 \-> FAILED
```

Validaciones:
1. ZIP sin path traversal ni archivos ejecutables.
2. Componentes shapefile requeridos y tamaño máximo.
3. CRS presente y transformable.
4. Geometrías válidas tras reparación controlada.
5. Códigos únicos dentro de org/nivel.
6. Padres existentes o incluidos en lote.
7. Conteos de creados, actualizados, rechazados.
8. Publicación transaccional.

No conservar indefinidamente archivos originales con datos sensibles. Aplicar política de retención.

## Frontend

### Store mínimo

```typescript
type ElectionGeoState = {
  featureCollection: GeoJSON.FeatureCollection | null;
  visibleLevels: Array<'N0' | 'N1' | 'N2' | 'N3' | 'N4'>;
  metric: 'participation' | 'results';
  selectedFeatureId: string | null;
  datasetVersion: string | null;
};
```

No guardar en localStorage métricas sensibles ni tokens. Se puede persistir basemap, zoom y niveles visibles.

### Capas DeckGL

```typescript
const layers = [
  new GeoJsonLayer({ id: 'electoral-areas', data: featureCollection }),
  new ScatterplotLayer({ id: 'voting-centers', data: centers }),
  selectedFeature && new GeoJsonLayer({ id: 'selection', data: selectedFeature }),
];
```

- Color accesible y no ambiguo.
- Leyenda indica periodo, versión, supresión y denominador.
- Tooltip no muestra conteos suprimidos.
- Tabla alternativa accesible para teclado/lector de pantalla.

## Rendimiento

- BBOX y niveles por zoom.
- `ST_SimplifyPreserveTopology` según escala.
- ETag o `datasetVersion` para snapshots.
- Cache pública solo para datos ya publicables.
- Cache administrativa privada y corta.
- Clustering para N3/N4.
- Considerar vector tiles cuando GeoJSON exceda el presupuesto acordado.

## Seguridad

- Validar límites BBOX y número de features.
- Rate limiting en exports y mapas públicos.
- `Content-Disposition` seguro en descargas.
- No usar URLs firmadas de larga vida para imports.
- Sanitizar propiedades usadas en tooltips.
- CSP compatible con proveedor de basemap.
- Tokens Mapbox públicos restringidos por dominio y alcance.

## Testing

### pytest
- Parentesco N0-N4 correcto e incorrecto.
- Tenant isolation en BBOX y exports.
- `ST_MakeValid` y transformación de CRS.
- Suppression policy y supresión complementaria.
- Estados electorales bloquean resultados prematuros.
- Snapshot usa padrón congelado.
- Endpoint público nunca incluye campos administrativos.

### Playwright
- Navegación, zoom, filtros y leyenda.
- Tooltip de celda suprimida no revela conteos.
- Tabla accesible coincide con mapa.
- Stream reconecta y recupera snapshot.
- Usuario público no puede abrir capas N4 restringidas.

## Checklist deploy

```text
- [ ] PostGIS habilitado
- [ ] Índices GiST creados
- [ ] Snapshots de elegibilidad generados
- [ ] Política pública configurada
- [ ] Worker y storage privado disponibles
- [ ] Basemap token restringido
- [ ] API admin no cacheable públicamente
- [ ] API pública aplica supresión
- [ ] Mapa no muestra resultados antes de PUBLISHED
- [ ] Tests espaciales y de privacidad en verde
```
