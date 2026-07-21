from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CreatedAtMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )


class Organization(CreatedAtMixin, Base):
    __tablename__ = "organizations"

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)


class Member(CreatedAtMixin, Base):
    __tablename__ = "members"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_members_organization_email"),
        UniqueConstraint("organization_id", "dni", name="uq_members_organization_dni"),
        UniqueConstraint(
            "organization_id", "registry_code", name="uq_members_organization_registry_code"
        ),
        Index("ix_members_organization_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    dni: Mapped[str] = mapped_column(String(50), nullable=False)
    registry_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="ACTIVE")
    member_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    membership_months: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    decade: Mapped[int | None] = mapped_column(Integer, nullable=True)
    graduation_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    semester: Mapped[str | None] = mapped_column(String(10), nullable=True)
    sex: Mapped[str | None] = mapped_column(String(10), nullable=True)
    alive: Mapped[bool | None] = mapped_column(nullable=True)
    section: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(50), nullable=True)
    mention: Mapped[str | None] = mapped_column(String(255), nullable=True)
    graduation_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    photo_data: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    photo_content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    photo_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    photo_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    photo_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Election(CreatedAtMixin, Base):
    __tablename__ = "elections"
    __table_args__ = (Index("ix_elections_organization_status", "organization_id", "status"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    voting_type: Mapped[str] = mapped_column(String(50), nullable=False, default="SLATE_PLURALITY")
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    quorum_threshold_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("30.00")
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="DRAFT")
    public_key: Mapped[str | None] = mapped_column(Text, nullable=True)
    frozen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Position(CreatedAtMixin, Base):
    __tablename__ = "positions"
    __table_args__ = (UniqueConstraint("election_id", "code", name="uq_positions_election_code"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    election_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("elections.id"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    is_required: Mapped[bool] = mapped_column(nullable=False, default=True)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Slate(CreatedAtMixin, Base):
    __tablename__ = "slates"
    __table_args__ = (
        UniqueConstraint("election_id", "name", name="uq_slates_election_name"),
        Index("ix_slates_organization_status", "organization_id", "status"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    election_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("elections.id"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    slogan: Mapped[str | None] = mapped_column(String(255), nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    work_plan_pdf_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    proxy_member_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("members.id"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="PENDING")
    validation_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class Candidate(CreatedAtMixin, Base):
    __tablename__ = "candidates"
    __table_args__ = (
        UniqueConstraint("slate_id", "position_id", name="uq_candidates_slate_position"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    slate_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("slates.id", ondelete="CASCADE"),
        nullable=False,
    )
    position_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("positions.id"),
        nullable=False,
    )
    member_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("members.id"),
        nullable=False,
    )
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_url: Mapped[str | None] = mapped_column(Text, nullable=True)


class MemberElectionStatus(CreatedAtMixin, Base):
    __tablename__ = "member_election_status"
    __table_args__ = (
        UniqueConstraint("election_id", "member_id", name="uq_member_election_status"),
        Index("ix_member_election_status_organization", "organization_id", "election_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    election_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("elections.id"),
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


class EncryptedBallot(CreatedAtMixin, Base):
    __tablename__ = "encrypted_ballots"
    __table_args__ = (
        UniqueConstraint("election_id", "receipt_hash", name="uq_encrypted_ballots_receipt"),
        Index("ix_encrypted_ballots_organization_election", "organization_id", "election_id"),
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    election_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("elections.id"),
        nullable=False,
    )
    encrypted_payload: Mapped[str] = mapped_column(Text, nullable=False)
    receipt_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    zkp_proof: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_version: Mapped[str | None] = mapped_column(String(50), nullable=True)


class AuditLog(CreatedAtMixin, Base):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_logs_organization_created", "organization_id", "created_at"),)

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    organization_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("organizations.id"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    actor_id_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
