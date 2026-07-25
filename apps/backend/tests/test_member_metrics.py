"""Unit tests for padrón status/type metric helpers and voting eligibility."""

from __future__ import annotations

from app.services.member_metrics import (
    KNOWN_MEMBER_TYPES,
    UNTITLED_MEMBER_TYPE,
    build_member_type_counts,
    evaluate_voter_eligibility,
    member_type_grants_vote,
    normalize_member_type_label,
)


def test_normalize_blank_member_type() -> None:
    assert normalize_member_type_label(None) == UNTITLED_MEMBER_TYPE
    assert normalize_member_type_label("  ") == UNTITLED_MEMBER_TYPE
    assert normalize_member_type_label("Asociado") == "Asociado"


def test_known_member_types_match_estatutos() -> None:
    assert KNOWN_MEMBER_TYPES == (
        "Activo",
        "Temporal",
        "Asociado",
        "Aspirante",
        "Colectivo",
        "Correspondiente",
        "Honorario",
    )


def test_build_member_type_counts_includes_known_zeros() -> None:
    counts = dict(build_member_type_counts([("Asociado", 4), (None, 2)]))
    assert counts["Activo"] == 0
    assert counts["Temporal"] == 0
    assert counts["Asociado"] == 4
    assert counts["Aspirante"] == 0
    assert counts["Colectivo"] == 0
    assert counts["Correspondiente"] == 0
    assert counts["Honorario"] == 0
    assert counts[UNTITLED_MEMBER_TYPE] == 2
    assert list(counts)[: len(KNOWN_MEMBER_TYPES)] == list(KNOWN_MEMBER_TYPES)


def test_build_member_type_counts_merges_case_variants() -> None:
    counts = dict(build_member_type_counts([("activo", 3), ("Activo", 2)]))
    assert counts["Activo"] == 5


def test_build_member_type_counts_appends_unknown_types() -> None:
    ordered = build_member_type_counts([("Honorario", 7), ("Vitalicio", 1), ("Fundador", 3)])
    labels = [label for label, _ in ordered]
    assert labels[: len(KNOWN_MEMBER_TYPES)] == list(KNOWN_MEMBER_TYPES)
    assert dict(ordered)["Honorario"] == 7
    assert labels[len(KNOWN_MEMBER_TYPES) :] == ["Fundador", "Vitalicio"]


def test_member_type_grants_vote_for_organ_elections() -> None:
    assert member_type_grants_vote("Activo") is True
    assert member_type_grants_vote("temporal") is True
    assert member_type_grants_vote("Fundador") is True
    assert member_type_grants_vote(None) is True
    assert member_type_grants_vote("Asociado") is False
    assert member_type_grants_vote("Aspirante") is False
    assert member_type_grants_vote("Colectivo") is False
    assert member_type_grants_vote("Correspondiente") is False
    assert member_type_grants_vote("Honorario") is False


def test_evaluate_voter_eligibility_requires_status_alive_and_type() -> None:
    ok = evaluate_voter_eligibility(status="ACTIVE", alive=True, member_type="Activo")
    assert ok.eligible is True
    assert "Tipo 'Activo'" in ok.reason

    inactive = evaluate_voter_eligibility(status="INACTIVE", alive=True, member_type="Activo")
    assert inactive.eligible is False
    assert inactive.reason == "Miembro INACTIVE"

    dead = evaluate_voter_eligibility(status="ACTIVE", alive=False, member_type="Temporal")
    assert dead.eligible is False

    aspirant = evaluate_voter_eligibility(status="ACTIVE", alive=True, member_type="Aspirante")
    assert aspirant.eligible is False
    assert "Aspirante" in aspirant.reason
