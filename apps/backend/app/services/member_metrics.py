"""Aggregate roster metrics for admin overview (estatus vs tipo)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

# Canonical membership categories (Tipo). Distinct from estatus ACTIVE/INACTIVE.
# "Activo" here means full member with voice+vote; other types may have voice only.
KNOWN_MEMBER_TYPES: tuple[str, ...] = (
    "Activo",
    "Asociado",
    "Correspondiente",
    "Colectivo",
)

UNTITLED_MEMBER_TYPE = "Sin tipo"


def normalize_member_type_label(raw: str | None) -> str:
    text = (raw or "").strip()
    return text if text else UNTITLED_MEMBER_TYPE


def build_member_type_counts(
    rows: Iterable[tuple[str | None, int]],
    *,
    known_types: Sequence[str] = KNOWN_MEMBER_TYPES,
) -> list[tuple[str, int]]:
    """Merge DB group-by rows into ordered (label, count) pairs.

    Always includes known types (even at 0). Unknown labels from data follow,
    sorted by descending count then name. Null/blank become \"Sin tipo\".
    """
    by_label: dict[str, int] = {}
    for raw, count in rows:
        label = normalize_member_type_label(raw)
        by_label[label] = by_label.get(label, 0) + int(count)

    result: list[tuple[str, int]] = []
    consumed: set[str] = set()

    for known in known_types:
        match = next(
            (label for label in by_label if label.casefold() == known.casefold()),
            None,
        )
        if match is not None:
            result.append((known, by_label.pop(match)))
            consumed.add(known.casefold())
        else:
            result.append((known, 0))
            consumed.add(known.casefold())

    extras = sorted(
        ((label, count) for label, count in by_label.items() if label.casefold() not in consumed),
        key=lambda item: (-item[1], item[0].casefold()),
    )
    result.extend(extras)
    return result
