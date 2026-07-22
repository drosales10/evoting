from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from typing import Any
from unicodedata import normalize
from uuid import UUID

from openpyxl import Workbook, load_workbook  # type: ignore[import-untyped]
from openpyxl.drawing.image import Image as ExcelImage  # type: ignore[import-untyped]
from PIL import Image as PilImage
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ElectoralRegion, ElectoralState, Member

EXCEL_SHEET_NAME = "Datos"
EXCEL_HEADERS = (
    "Código",
    "Nombre Completo",
    "Documento",
    "Correo electrónico",
    "Estatus",
    "Tipo",
    "Membresía",
    "Decada",
    "Año",
    "Sem",
    "Sexo",
    "Vivo",
    "Región",
    "Seccional",
    "Ubicación",
    "Mención",
    "Fecha Grado",
    "Foto",
)
MAX_IMPORT_BYTES = 20 * 1024 * 1024


@dataclass(frozen=True)
class ParsedMember:
    row_number: int
    registry_code: str
    full_name: str
    dni: str
    email: str
    status: str
    member_type: str | None
    membership_months: int
    decade: int | None
    graduation_year: int | None
    semester: str | None
    sex: str | None
    alive: bool | None
    region: str | None
    section: str | None
    location: str | None
    mention: str | None
    graduation_date: date | None
    photo_filename: str | None


@dataclass(frozen=True)
class ImportRowError:
    row_number: int
    registry_code: str | None
    message: str


@dataclass
class MemberImportResult:
    rows_read: int = 0
    created: int = 0
    updated: int = 0
    failed: int = 0
    errors: list[ImportRowError] = field(default_factory=list)


class MemberSpreadsheetError(ValueError):
    """Raised when the workbook structure cannot be interpreted safely."""


def _header_key(value: Any) -> str:
    return normalize("NFKC", str(value or "").strip()).casefold()


def _text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    text = str(value).strip()
    return text or None


def _required_text(value: Any, field_name: str) -> str:
    result = _text(value)
    if not result:
        raise ValueError(f"{field_name} is required")
    return result


def _optional_int(value: Any, field_name: str) -> int | None:
    text = _text(value)
    if text is None:
        return None
    try:
        return int(float(text))
    except ValueError as exc:
        raise ValueError(f"{field_name} must be an integer") from exc


def _optional_date(value: Any) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for pattern in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(text, pattern).date()
        except ValueError:
            continue
    raise ValueError("Fecha Grado has an unsupported date format")


def _optional_alive(value: Any) -> bool | None:
    text = _text(value)
    if text is None:
        return None
    normalized = text.casefold()
    if normalized in {"1", "true", "t", "si", "sí", "vivo", "activo"}:
        return True
    if normalized in {"0", "false", "f", "no", "muerto", "inactivo"}:
        return False
    raise ValueError("Vivo must be 0/1 or a boolean value")


def _status(value: Any) -> str:
    text = _required_text(value, "Estatus").casefold()
    if text in {"activo", "active"}:
        return "ACTIVE"
    if text in {"inactivo", "inactive"}:
        return "INACTIVE"
    raise ValueError("Estatus must be Activo or Inactivo")


def _parse_row(row: tuple[Any, ...], columns: dict[str, int], row_number: int) -> ParsedMember:
    def value(header: str) -> Any:
        key = _header_key(header)
        if key not in columns:
            return None
        index = columns[key]
        return row[index] if index < len(row) else None

    return ParsedMember(
        row_number=row_number,
        registry_code=_required_text(value("Código"), "Código"),
        full_name=_required_text(value("Nombre Completo"), "Nombre Completo"),
        dni=_required_text(value("Documento"), "Documento"),
        email=_required_text(value("Correo electrónico"), "Correo electrónico").lower(),
        status=_status(value("Estatus")),
        member_type=_text(value("Tipo")),
        membership_months=_optional_int(value("Membresía"), "Membresía") or 0,
        decade=_optional_int(value("Decada"), "Decada"),
        graduation_year=_optional_int(value("Año"), "Año"),
        semester=_text(value("Sem")),
        sex=_text(value("Sexo")),
        alive=_optional_alive(value("Vivo")),
        region=_text(value("Región")),
        section=_text(value("Seccional")),
        location=_text(value("Ubicación")),
        mention=_text(value("Mención")),
        graduation_date=_optional_date(value("Fecha Grado")),
        photo_filename=_text(value("Foto")),
    )


def parse_member_workbook(content: bytes) -> tuple[list[ParsedMember], list[ImportRowError], int]:
    try:
        workbook = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except Exception as exc:
        raise MemberSpreadsheetError("The uploaded file is not a readable XLSX workbook") from exc

    if EXCEL_SHEET_NAME in workbook.sheetnames:
        sheet = workbook[EXCEL_SHEET_NAME]
    elif workbook.worksheets:
        sheet = workbook.worksheets[0]
    else:
        raise MemberSpreadsheetError("The workbook has no worksheets")

    rows = sheet.iter_rows(values_only=True)
    try:
        header_row = tuple(next(rows))
    except StopIteration as exc:
        raise MemberSpreadsheetError("The worksheet is empty") from exc

    columns = {
        _header_key(value): index for index, value in enumerate(header_row) if value is not None
    }
    required_headers = tuple(h for h in EXCEL_HEADERS if h != "Región")
    missing = [
        _header_key(header) for header in required_headers if _header_key(header) not in columns
    ]
    if missing:
        raise MemberSpreadsheetError(f"Missing required columns: {', '.join(missing)}")

    parsed: list[ParsedMember] = []
    errors: list[ImportRowError] = []
    seen_codes: set[str] = set()
    rows_read = 0
    for row_number, raw_row in enumerate(rows, start=2):
        row = tuple(raw_row)
        if not any(value is not None and str(value).strip() for value in row):
            continue
        rows_read += 1
        code: str | None = None
        try:
            code = _text(row[columns[_header_key("Código")]])
            if code and code in seen_codes:
                raise ValueError("Código is duplicated in the workbook")
            member = _parse_row(row, columns, row_number)
            seen_codes.add(member.registry_code)
            parsed.append(member)
        except (TypeError, ValueError, KeyError) as exc:
            errors.append(ImportRowError(row_number, code, str(exc)))

    return parsed, errors, rows_read


def _member_values(
    member: ParsedMember,
    *,
    region_id: UUID | None = None,
    state_id: UUID | None = None,
) -> dict[str, Any]:
    return {
        "registry_code": member.registry_code,
        "full_name": member.full_name,
        "dni": member.dni,
        "email": member.email,
        "status": member.status,
        "member_type": member.member_type,
        "membership_months": member.membership_months,
        "decade": member.decade,
        "graduation_year": member.graduation_year,
        "semester": member.semester,
        "sex": member.sex,
        "alive": member.alive,
        "region": member.region,
        "section": member.section,
        "location": member.location,
        "mention": member.mention,
        "graduation_date": member.graduation_date,
        "photo_filename": member.photo_filename,
        "region_id": region_id,
        "state_id": state_id,
    }


async def import_members(
    session: AsyncSession,
    organization_id: UUID,
    members: Sequence[ParsedMember],
    errors: list[ImportRowError],
    rows_read: int,
    dry_run: bool,
) -> MemberImportResult:
    regions = (
        await session.scalars(
            select(ElectoralRegion).where(ElectoralRegion.organization_id == organization_id)
        )
    ).all()
    states = (
        await session.scalars(
            select(ElectoralState).where(ElectoralState.organization_id == organization_id)
        )
    ).all()
    region_by_code = {r.code.strip().upper(): r.id for r in regions}
    region_by_name = {r.name.strip().upper(): r.id for r in regions}
    state_by_code = {s.code.strip().upper(): s for s in states}
    state_by_name = {s.name.strip().upper(): s for s in states}

    def resolve_region_id(label: str | None) -> UUID | None:
        if not label:
            return None
        key = label.strip().upper()
        return region_by_code.get(key) or region_by_name.get(key)

    def resolve_state(label: str | None) -> ElectoralState | None:
        if not label:
            return None
        key = label.strip().upper()
        return state_by_code.get(key) or state_by_name.get(key)

    result = MemberImportResult(rows_read=rows_read, errors=list(errors))
    for parsed in members:
        existing = await session.scalar(
            select(Member).where(
                Member.organization_id == organization_id,
                Member.registry_code == parsed.registry_code,
            )
        )
        if existing is None:
            existing = await session.scalar(
                select(Member).where(
                    Member.organization_id == organization_id,
                    Member.dni == parsed.dni,
                )
            )
        if existing is None:
            existing = await session.scalar(
                select(Member).where(
                    Member.organization_id == organization_id,
                    Member.email == parsed.email,
                )
            )

        try:
            created_this = False
            updated_this = False
            region_id = resolve_region_id(parsed.region)
            state = resolve_state(parsed.section)
            state_id = state.id if state else None
            if state is not None and region_id is None:
                region_id = state.region_id
            async with session.begin_nested():
                if existing is None:
                    session.add(
                        Member(
                            organization_id=organization_id,
                            **_member_values(parsed, region_id=region_id, state_id=state_id),
                        )
                    )
                    result.created += 1
                    created_this = True
                else:
                    values = _member_values(parsed, region_id=region_id, state_id=state_id)
                    if values["photo_filename"] is None and existing.photo_data:
                        values.pop("photo_filename")
                    for field, value in values.items():
                        setattr(existing, field, value)
                    result.updated += 1
                    updated_this = True
                await session.flush()
        except IntegrityError:
            result.errors.append(
                ImportRowError(
                    parsed.row_number,
                    parsed.registry_code,
                    "Duplicate email, document or registry code in this organization",
                )
            )
            if created_this:
                result.created -= 1
            if updated_this:
                result.updated -= 1

    if dry_run:
        await session.rollback()
    else:
        await session.commit()
    result.failed = len(result.errors or [])
    return result


def _export_status(status: str) -> str:
    return "Activo" if status == "ACTIVE" else "Inactivo" if status == "INACTIVE" else status


def build_member_workbook(members: Iterable[Member]) -> BytesIO:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = EXCEL_SHEET_NAME
    sheet.append(EXCEL_HEADERS)
    sheet.freeze_panes = "A2"

    photo_buffers: list[BytesIO] = []
    for row_number, member in enumerate(members, start=2):
        sheet.append(
            [
                member.registry_code,
                member.full_name,
                member.dni,
                member.email,
                _export_status(member.status),
                member.member_type,
                member.membership_months,
                member.decade,
                member.graduation_year,
                member.semester,
                member.sex,
                1 if member.alive is True else 0 if member.alive is False else None,
                member.region,
                member.section,
                member.location,
                member.mention,
                member.graduation_date,
                member.photo_filename,
            ]
        )
        if member.photo_data:
            try:
                with PilImage.open(BytesIO(member.photo_data)) as source:
                    source.load()
                    image = source.convert("RGB")
                    buffer = BytesIO()
                    image.save(buffer, format="PNG")
                    buffer.seek(0)
                    photo_buffers.append(buffer)
                    excel_image = ExcelImage(buffer)
                    excel_image.width = 80
                    excel_image.height = 80
                    sheet.add_image(excel_image, f"Q{row_number}")
                    sheet.row_dimensions[row_number].height = 60
            except Exception:
                # Keep the metadata row even if a legacy photo cannot be embedded.
                pass

    sheet.auto_filter.ref = sheet.dimensions
    for column in "ABCDEFGHIJKLMNOPQ":
        sheet.column_dimensions[column].width = 18
    sheet.column_dimensions["B"].width = 32
    sheet.column_dimensions["D"].width = 30
    sheet.column_dimensions["Q"].width = 24

    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    return output
