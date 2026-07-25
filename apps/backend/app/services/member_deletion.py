"""Guards and helpers for hard-deleting roster members."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    BallotIssuanceToken,
    Candidate,
    MemberElectionStatus,
    Slate,
    VoterOtpChallenge,
)

DEACTIVATE_HINT = (
    "Desactívelo cambiando su estado a INACTIVE en lugar de eliminarlo."
)


@dataclass(frozen=True, slots=True)
class MemberDeletionBlockers:
    """Reference counts that prevent hard-deleting a member."""

    proxy_slates: int = 0
    candidacies: int = 0
    eligibility_snapshots: int = 0
    issuance_tokens: int = 0
    active_otp_challenges: int = 0

    @property
    def has_blockers(self) -> bool:
        return any(
            (
                self.proxy_slates,
                self.candidacies,
                self.eligibility_snapshots,
                self.issuance_tokens,
                self.active_otp_challenges,
            )
        )

    def reference_labels(self) -> list[str]:
        labels: list[str] = []
        if self.proxy_slates:
            labels.append(f"{self.proxy_slates} plancha(s) como apoderado")
        if self.candidacies:
            labels.append(f"{self.candidacies} candidatura(s)")
        if self.eligibility_snapshots:
            labels.append(
                f"{self.eligibility_snapshots} snapshot(s) de elegibilidad electoral"
            )
        if self.issuance_tokens:
            labels.append(f"{self.issuance_tokens} token(s) de emisión")
        if self.active_otp_challenges:
            labels.append(f"{self.active_otp_challenges} desafío(s) OTP activos")
        return labels


def format_member_deletion_conflict(blockers: MemberDeletionBlockers) -> str | None:
    """Build a Spanish 409 detail, or None when deletion is allowed."""
    if not blockers.has_blockers:
        return None
    return (
        "No se puede eliminar el miembro porque mantiene referencias: "
        + ", ".join(blockers.reference_labels())
        + f". {DEACTIVATE_HINT}"
    )


def race_condition_deletion_conflict() -> str:
    """Generic detail when a concurrent write wins the FK race."""
    return (
        "No se puede eliminar el miembro porque otra operación creó una "
        f"referencia electoral o de autenticación. {DEACTIVATE_HINT}"
    )


async def purge_stale_member_auth_records(
    session: AsyncSession,
    *,
    member_id: UUID,
    organization_id: UUID,
    now: datetime | None = None,
) -> int:
    """Remove consumed/expired OTP challenges so they do not block deletion.

    Ballot issuance tokens are never purged here: they belong to the electoral
    chain of custody even after consumption.
    """
    cutoff = now or datetime.now(UTC)
    result = await session.execute(
        delete(VoterOtpChallenge).where(
            VoterOtpChallenge.member_id == member_id,
            VoterOtpChallenge.organization_id == organization_id,
            (
                (VoterOtpChallenge.consumed_at.is_not(None))
                | (VoterOtpChallenge.expires_at < cutoff)
            ),
        )
    )
    return int(result.rowcount or 0)


async def collect_member_deletion_blockers(
    session: AsyncSession,
    *,
    member_id: UUID,
    organization_id: UUID,
    now: datetime | None = None,
) -> MemberDeletionBlockers:
    """Load all hard-delete blockers in a single database round-trip."""
    cutoff = now or datetime.now(UTC)

    proxy_count = (
        select(func.count())
        .select_from(Slate)
        .where(
            Slate.proxy_member_id == member_id,
            Slate.organization_id == organization_id,
        )
        .scalar_subquery()
    )
    candidacy_count = (
        select(func.count())
        .select_from(Candidate)
        .join(Slate, Candidate.slate_id == Slate.id)
        .where(
            Candidate.member_id == member_id,
            Slate.organization_id == organization_id,
        )
        .scalar_subquery()
    )
    eligibility_count = (
        select(func.count())
        .select_from(MemberElectionStatus)
        .where(
            MemberElectionStatus.member_id == member_id,
            MemberElectionStatus.organization_id == organization_id,
        )
        .scalar_subquery()
    )
    issuance_count = (
        select(func.count())
        .select_from(BallotIssuanceToken)
        .where(
            BallotIssuanceToken.member_id == member_id,
            BallotIssuanceToken.organization_id == organization_id,
        )
        .scalar_subquery()
    )
    active_otp_count = (
        select(func.count())
        .select_from(VoterOtpChallenge)
        .where(
            VoterOtpChallenge.member_id == member_id,
            VoterOtpChallenge.organization_id == organization_id,
            VoterOtpChallenge.consumed_at.is_(None),
            VoterOtpChallenge.expires_at >= cutoff,
        )
        .scalar_subquery()
    )

    row = (
        await session.execute(
            select(
                proxy_count,
                candidacy_count,
                eligibility_count,
                issuance_count,
                active_otp_count,
            )
        )
    ).one()

    return MemberDeletionBlockers(
        proxy_slates=int(row[0] or 0),
        candidacies=int(row[1] or 0),
        eligibility_snapshots=int(row[2] or 0),
        issuance_tokens=int(row[3] or 0),
        active_otp_challenges=int(row[4] or 0),
    )
