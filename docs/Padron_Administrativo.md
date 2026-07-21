# Padrón administrativo

## Propósito

El padrón administrativo es el registro organizacional que usan los operadores autorizados para administrar miembros, validar su estado y preparar procesos electorales. No es la urna ni contiene votos. Un miembro del padrón puede ser elegible para una elección, representante o candidato según las reglas del proceso, pero su identidad no se relaciona con `encrypted_ballots`.

Todos los endpoints de esta funcionalidad requieren sesión ADMIN, filtran por la organización (`org_id`) incluida en el token y aplican RBAC. La administración del padrón está limitada a los roles `SUPER_ADMIN` y `ELECTORAL_JUSTICE`.

## Contrato XLSX

El archivo de referencia es `docs/Padron_Administrativo.xlsx`, hoja `Datos`. La importación acepta la hoja `Datos` o, si no existe, la primera hoja del libro. Los encabezados se comparan normalizados, pero el contrato conceptual conserva estos nombres y orden:

| Columna XLSX | Campo `members` / uso | Tipo y notas |
|---|---|---|
| `Código` | `registry_code` | Texto obligatorio; identificador del registro, único por organización. |
| `Nombre Completo` | `full_name` | Texto obligatorio. |
| `Documento` | `dni` | Texto obligatorio; único por organización. |
| `Correo electrónico` | `email` | Texto obligatorio; se normaliza a minúsculas. No se exige una dirección con `@` porque el archivo fuente contiene identificadores que no tienen formato de correo convencional. |
| `Estatus` | `status` | `Activo` → `ACTIVE`; `Inactivo` → `INACTIVE`. |
| `Tipo` | `member_type` | Texto opcional. |
| `Membresía` | `membership_months` | Entero; vacío equivale a `0`. |
| `Decada` | `decade` | Entero opcional. |
| `Año` | `graduation_year` | Entero opcional. |
| `Sem` | `semester` | Texto opcional, por ejemplo `U`, `B` o `A`. |
| `Sexo` | `sex` | Texto opcional. |
| `Vivo` | `alive` | `1`/`true`/`sí` → `true`; `0`/`false`/`no` → `false`; vacío → `null`. |
| `Seccional` | `section` | Texto opcional. |
| `Ubicación` | `location` | Texto opcional. |
| `Mención` | `mention` | Texto opcional. |
| `Fecha Grado` | `graduation_date` | Fecha; acepta `YYYY-MM-DD`, `DD/MM/YYYY`, `DD-MM-YYYY` y `MM/DD/YYYY`. |
| `Foto` | `photo_filename`; imagen mediante endpoint | El XLSX conserva el nombre/metadato. Los bytes se guardan en `photo_data` (`BYTEA`) cuando se cargan por el endpoint de fotos. |

El archivo proporcionado contiene 3.084 filas de datos, fue validado con `rows_read=3084`, `parsed=3084` y `errors=0`. Su columna `Foto` está vacía y el recurso gráfico incrustado es solo un placeholder transparente; por tanto, no se importó ninguna foto real automáticamente.

## Importar XLSX

`POST /api/v1/admin/members/import` usa `multipart/form-data`:

- `file`: archivo `.xlsx` obligatorio.
- `dry_run`: booleano opcional; `true` valida y reconcilia en una transacción revertida, sin guardar cambios.

El límite del archivo es 20 MiB. La respuesta contiene:

```json
{
  "rows_read": 0,
  "created": 0,
  "updated": 0,
  "failed": 0,
  "dry_run": true,
  "errors": [
    {"row_number": 2, "registry_code": "...", "message": "..."}
  ]
}
```

Los valores existentes se reconcilian en este orden dentro de la organización: `registry_code`, luego `dni`, luego `email`. Si no se encuentra coincidencia, se crea un miembro; si se encuentra, se actualizan los campos del contrato. Los errores de filas individuales se devuelven con número de fila y el lote continúa con las filas válidas. Las restricciones únicas de organización para código, documento y correo siguen vigentes, por lo que una colisión no se acepta silenciosamente.

Antes de persistir el archivo de referencia se recomienda ejecutar `dry_run=true` y revisar `failed` y `errors`. La interfaz ADMIN incluye la opción **Solo validar, no guardar cambios**.

## Exportar XLSX

`GET /api/v1/admin/members/export` devuelve un archivo descargable con:

- Hoja `Datos`.
- Las mismas 17 columnas del contrato.
- Filas únicamente de la organización del token ADMIN.
- Estados exportados como `Activo`/`Inactivo`.
- Metadatos de foto en la columna `Foto`.
- Fotos existentes intentadas como imágenes incrustadas en la celda de la columna `Foto`; si una foto histórica no puede convertirse, se conserva al menos la fila y su metadato.

El endpoint no expone los bytes de fotos en JSON y responde con `Cache-Control: no-store`.

## Carga y consulta de fotos

`POST /api/v1/admin/members/{member_id}/photo` recibe `multipart/form-data` con el campo `file`. Solo se permiten `JPEG`, `PNG`, `WEBP` y `GIF`, con un máximo de 5 MiB. Pillow verifica que el contenido sea una imagen válida antes de guardarlo.

La imagen se almacena en PostgreSQL como `members.photo_data` (`BYTEA`) junto con:

- `photo_content_type`;
- `photo_filename`;
- `photo_sha256`;
- `photo_size_bytes`.

`GET /api/v1/admin/members/{member_id}/photo` devuelve el binario solo si el miembro pertenece a la organización del token y el actor tiene permisos de padrón. La UI permite cargar la imagen por miembro y abrir la foto almacenada en una pestaña separada.

## Campos y migración PostgreSQL

La migración `apps/backend/alembic/versions/0004_member_registry_fields.py` agrega los campos del contrato como columnas nullable para mantener compatibilidad con miembros existentes y crea `uq_members_organization_registry_code`. La migración usa estrategia expand; no elimina datos ni define downgrade automático. El modelo SQLAlchemy correspondiente está en `apps/backend/app/models/core.py`.

Aplicar/verificar en el backend:

```powershell
.\.venv\Scripts\python.exe -m alembic upgrade head
.\.venv\Scripts\python.exe -m alembic check
```

Desde la raíz del repositorio, el entorno virtual del backend está en `apps/backend`:

```powershell
.\apps\backend\.venv\Scripts\python.exe -m alembic upgrade head
```

## Límites y aislamiento

- Importación XLSX: 20 MiB.
- Foto individual: 5 MiB.
- Formatos de foto: JPEG, PNG, WEBP y GIF.
- El listado, importación, exportación y fotos siempre aplican `organization_id == claims.org_id`.
- Los datos del padrón no se copian a `encrypted_ballots`; esa tabla mantiene su diseño de anonimato.
- No se crean ni configuran credenciales OTP de VOTER mediante esta funcionalidad.

## Dependencias

Las dependencias fijadas para esta funcionalidad son `openpyxl==3.1.5`, `pillow==11.1.0` y `python-multipart==0.0.20`, declaradas en `apps/backend/pyproject.toml` y `apps/backend/requirements.txt`.
