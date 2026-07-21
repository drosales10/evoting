"""Create the initial tenant-aware eVoting schema.

Revision ID: 0001_core_schema
Revises:
Create Date: 2026-07-21

This revision is prepared for review. It has not been applied automatically.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001_core_schema"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slug", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    op.create_table(
        "members",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("dni", sa.String(50), nullable=False),
        sa.Column("status", sa.String(50), server_default="ACTIVE", nullable=False),
        sa.Column("membership_months", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("organization_id", "email", name="uq_members_organization_email"),
        sa.UniqueConstraint("organization_id", "dni", name="uq_members_organization_dni"),
    )
    op.create_index("ix_members_organization_status", "members", ["organization_id", "status"])

    op.create_table(
        "elections",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("voting_type", sa.String(50), server_default="SLATE_PLURALITY", nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("quorum_threshold_pct", sa.Numeric(5, 2), server_default="30.00", nullable=False),
        sa.Column("status", sa.String(50), server_default="DRAFT", nullable=False),
        sa.Column("public_key", sa.Text(), nullable=True),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )
    op.create_index("ix_elections_organization_status", "elections", ["organization_id", "status"])

    op.create_table(
        "positions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("election_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("is_required", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["election_id"], ["elections.id"]),
        sa.UniqueConstraint("election_id", "code", name="uq_positions_election_code"),
    )

    op.create_table(
        "slates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("election_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("slogan", sa.String(255), nullable=True),
        sa.Column("logo_url", sa.Text(), nullable=True),
        sa.Column("work_plan_pdf_url", sa.Text(), nullable=True),
        sa.Column("video_url", sa.Text(), nullable=True),
        sa.Column("proxy_member_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(50), server_default="PENDING", nullable=False),
        sa.Column("validation_hash", sa.String(64), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["election_id"], ["elections.id"]),
        sa.ForeignKeyConstraint(["proxy_member_id"], ["members.id"]),
        sa.UniqueConstraint("election_id", "name", name="uq_slates_election_name"),
    )
    op.create_index("ix_slates_organization_status", "slates", ["organization_id", "status"])

    op.create_table(
        "candidates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("slate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("bio", sa.Text(), nullable=True),
        sa.Column("photo_url", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["slate_id"], ["slates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.UniqueConstraint("slate_id", "position_id", name="uq_candidates_slate_position"),
    )

    op.create_table(
        "member_election_status",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("election_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("eligible", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("has_voted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("voted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["election_id"], ["elections.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.UniqueConstraint("election_id", "member_id", name="uq_member_election_status"),
    )
    op.create_index(
        "ix_member_election_status_organization",
        "member_election_status",
        ["organization_id", "election_id"],
    )

    op.create_table(
        "encrypted_ballots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("election_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("receipt_hash", sa.String(64), nullable=False),
        sa.Column("zkp_proof", sa.Text(), nullable=True),
        sa.Column("key_version", sa.String(50), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["election_id"], ["elections.id"]),
        sa.UniqueConstraint("election_id", "receipt_hash", name="uq_encrypted_ballots_receipt"),
    )
    op.create_index(
        "ix_encrypted_ballots_organization_election",
        "encrypted_ballots",
        ["organization_id", "election_id"],
    )

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("actor_id_hash", sa.String(64), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),  # type: ignore[no-untyped-call]
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )
    op.create_index(
        "ix_audit_logs_organization_created",
        "audit_logs",
        ["organization_id", "created_at"],
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Initial eVoting schema is not downgraded automatically; use a reviewed roll-forward."
    )
