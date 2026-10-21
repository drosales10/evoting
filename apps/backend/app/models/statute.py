"""Statute consultation: titles, chapters, articles and a nominal sealed ballot."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.core import CreatedAtMixin


class StatuteConsultation(CreatedAtMixin, Base):
    __tablename__ = "statute_consultations"
    __table_args__ = (
        Index("ix_statute_consultations_org_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quorum_threshold_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("30.00")
    )
    approval_threshold_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("50.00")
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    signing_public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    article_set_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StatuteTitle(CreatedAtMixin, Base):
    __tablename__ = "statute_titles"
    __table_args__ = (
        UniqueConstraint("consultation_id", "number", name="uq_statute_titles_consultation_number"),
        Index("ix_statute_titles_consultation", "consultation_id", "display_order"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    consultation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("statute_consultations.id", ondelete="CASCADE"),
        nullable=False,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StatuteChapter(CreatedAtMixin, Base):
    __tablename__ = "statute_chapters"
    __table_args__ = (
        UniqueConstraint("title_id", "number", name="uq_statute_chapters_title_number"),
        Index("ix_statute_chapters_consultation", "consultation_id", "display_order"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    consultation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("statute_consultations.id", ondelete="CASCADE"),
        nullable=False,
    )
    title_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("statute_titles.id", ondelete="CASCADE"),
        nullable=False,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StatuteArticle(CreatedAtMixin, Base):
    __tablename__ = "statute_articles"
    __table_args__ = (
        UniqueConstraint(
            "consultation_id", "number", name="uq_statute_articles_consultation_number"
        ),
        Index("ix_statute_articles_chapter", "chapter_id", "display_order"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    consultation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("statute_consultations.id", ondelete="CASCADE"),
        nullable=False,
    )
    chapter_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("statute_chapters.id", ondelete="CASCADE"),
        nullable=False,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class StatuteMemberStatus(CreatedAtMixin, Base):
    __tablename__ = "statute_member_status"
    __table_args__ = (
        UniqueConstraint(
            "consultation_id",
            "member_id",
            name="uq_statute_member_status_consultation_member",
        ),
        Index("ix_statute_member_status_org", "organization_id", "consultation_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    consultation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("statute_consultations.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("members.id"),
        nullable=False,
    )
    eligible: Mapped[bool] = mapped_column(nullable=False, default=False)
    eligibility_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    has_voted: Mapped[bool] = mapped_column(nullable=False, default=False)
    voted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StatuteIssuanceToken(CreatedAtMixin, Base):
    __tablename__ = "statute_issuance_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_statute_issuance_token_hash"),
        Index("ix_statute_issuance_consultation_member", "consultation_id", "member_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    consultation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("statute_consultations.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("members.id"),
        nullable=False,
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class StatuteBallot(CreatedAtMixin, Base):
    """Sealed ballot linked to the member. Content stays encrypted until offline tally."""

    __tablename__ = "statute_ballots"
    __table_args__ = (
        UniqueConstraint(
            "consultation_id", "member_id", name="uq_statute_ballots_consultation_member"
        ),
        UniqueConstraint(
            "consultation_id", "receipt_hash", name="uq_statute_ballots_receipt"
        ),
        Index("ix_statute_ballots_receipt_hash", "receipt_hash"),
        Index("ix_statute_ballots_org_consultation", "organization_id", "consultation_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    consultation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("statute_consultations.id", ondelete="CASCADE"),
        nullable=False,
    )
    member_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("members.id"),
        nullable=False,
    )
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    zkp_proof: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    qr_payload: Mapped[str | None] = mapped_column(Text, nullable=True)


class StatuteTally(CreatedAtMixin, Base):
    __tablename__ = "statute_tallies"
    __table_args__ = (
        UniqueConstraint("consultation_id", name="uq_statute_tallies_consultation"),
        Index("ix_statute_tallies_org", "organization_id", "consultation_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    consultation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("statute_consultations.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    artifact: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    eligible_member_count: Mapped[int] = mapped_column(Integer, nullable=False)
    voted_member_count: Mapped[int] = mapped_column(Integer, nullable=False)
    ballot_count: Mapped[int] = mapped_column(Integer, nullable=False)
    quorum_required: Mapped[int] = mapped_column(Integer, nullable=False)
    quorum_met: Mapped[bool] = mapped_column(nullable=False)
    pilot_override: Mapped[bool] = mapped_column(nullable=False, default=False)
    acta: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    first_approver_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    second_approver_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class StatuteTallyProposal(CreatedAtMixin, Base):
    __tablename__ = "statute_tally_proposals"
    __table_args__ = (
        UniqueConstraint("consultation_id", name="uq_statute_tally_proposals_consultation"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    consultation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("statute_consultations.id", ondelete="CASCADE"),
        nullable=False,
    )
    artifact: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    artifact_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    proposer_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    reason: Mapped[str] = mapped_column(String(255), nullable=False)
    pilot_override: Mapped[bool] = mapped_column(nullable=False, default=False)
