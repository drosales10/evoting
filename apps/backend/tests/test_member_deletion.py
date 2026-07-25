"""Unit tests for roster member hard-delete guards."""

from __future__ import annotations

from app.services.member_deletion import (
    DEACTIVATE_HINT,
    MemberDeletionBlockers,
    format_member_deletion_conflict,
    race_condition_deletion_conflict,
)


def test_format_conflict_returns_none_without_blockers() -> None:
    assert format_member_deletion_conflict(MemberDeletionBlockers()) is None


def test_format_conflict_lists_all_reference_types() -> None:
    detail = format_member_deletion_conflict(
        MemberDeletionBlockers(
            proxy_slates=2,
            candidacies=1,
            eligibility_snapshots=3,
            issuance_tokens=4,
            active_otp_challenges=1,
        )
    )
    assert detail is not None
    assert "2 plancha(s) como apoderado" in detail
    assert "1 candidatura(s)" in detail
    assert "3 snapshot(s) de elegibilidad electoral" in detail
    assert "4 token(s) de emisión" in detail
    assert "1 desafío(s) OTP activos" in detail
    assert DEACTIVATE_HINT in detail
    assert "INACTIVE" in detail


def test_has_blockers_property() -> None:
    assert not MemberDeletionBlockers().has_blockers
    assert MemberDeletionBlockers(issuance_tokens=1).has_blockers
    assert MemberDeletionBlockers(active_otp_challenges=1).has_blockers


def test_race_condition_message_points_to_deactivate() -> None:
    detail = race_condition_deletion_conflict()
    assert "otra operación" in detail
    assert DEACTIVATE_HINT in detail
