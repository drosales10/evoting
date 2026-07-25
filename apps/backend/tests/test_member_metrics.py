"""Unit tests for padrón status/type metric helpers."""

from __future__ import annotations

from app.services.member_metrics import (
    KNOWN_MEMBER_TYPES,
    UNTITLED_MEMBER_TYPE,
    build_member_type_counts,
    normalize_member_type_label,
)


def test_normalize_blank_member_type() -> None:
    assert normalize_member_type_label(None) == UNTITLED_MEMBER_TYPE
    assert normalize_member_type_label("  ") == UNTITLED_MEMBER_TYPE
    assert normalize_member_type_label("Asociado") == "Asociado"


def test_build_member_type_counts_includes_known_zeros() -> None:
    counts = dict(build_member_type_counts([("Asociado", 4), (None, 2)]))
    assert counts["Activo"] == 0
    assert counts["Asociado"] == 4
    assert counts["Correspondiente"] == 0
    assert counts["Colectivo"] == 0
    assert counts[UNTITLED_MEMBER_TYPE] == 2
    assert list(counts)[: len(KNOWN_MEMBER_TYPES)] == list(KNOWN_MEMBER_TYPES)


def test_build_member_type_counts_merges_case_variants() -> None:
    counts = dict(build_member_type_counts([("activo", 3), ("Activo", 2)]))
    assert counts["Activo"] == 5


def test_build_member_type_counts_appends_unknown_types() -> None:
    ordered = build_member_type_counts([("Honorario", 7), ("Vitalicio", 1)])
    labels = [label for label, _ in ordered]
    assert labels[:4] == list(KNOWN_MEMBER_TYPES)
    assert labels[4:] == ["Honorario", "Vitalicio"]
