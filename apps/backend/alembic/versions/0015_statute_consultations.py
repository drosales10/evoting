"""Statute consultations: titles, chapters, articles and nominal sealed ballots.

Revision ID: 0015_statute_consultations
Revises: 0014_ballot_qr_payload
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0015_statute_consultations"
down_revision: str | None = "0014_ballot_qr_payload"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _created_at() -> sa.Column:
    return sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        server_default=sa.text("now()"),
        nullable=False,
    )


def upgrade() -> None:
    op.create_table(
        "statute_consultations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "quorum_threshold_pct",
            sa.Numeric(5, 2),
            server_default="30.00",
            nullable=False,
        ),
        sa.Column(
            "approval_threshold_pct",
            sa.Numeric(5, 2),
            server_default="50.00",
            nullable=False,
        ),
        sa.Column("status", sa.String(50), server_default="DRAFT", nullable=False),
        sa.Column("public_key", sa.Text(), nullable=True),
        sa.Column("signing_public_key", sa.Text(), nullable=True),
        sa.Column("article_set_hash", sa.String(64), nullable=True),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )
    op.create_index(
        "ix_statute_consultations_org_status",
        "statute_consultations",
        ["organization_id", "status"],
    )

    op.create_table(
        "statute_titles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["consultation_id"], ["statute_consultations.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "consultation_id", "number", name="uq_statute_titles_consultation_number"
        ),
    )
    op.create_index(
        "ix_statute_titles_consultation",
        "statute_titles",
        ["consultation_id", "display_order"],
    )

    op.create_table(
        "statute_chapters",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("description", sa.String(255), server_default="", nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["consultation_id"], ["statute_consultations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["title_id"], ["statute_titles.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("title_id", "number", name="uq_statute_chapters_title_number"),
    )
    op.create_index(
        "ix_statute_chapters_consultation",
        "statute_chapters",
        ["consultation_id", "display_order"],
    )

    op.create_table(
        "statute_articles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chapter_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), server_default="0", nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["consultation_id"], ["statute_consultations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["chapter_id"], ["statute_chapters.id"], ondelete="CASCADE"),
        sa.UniqueConstraint(
            "consultation_id", "number", name="uq_statute_articles_consultation_number"
        ),
    )
    op.create_index(
        "ix_statute_articles_chapter",
        "statute_articles",
        ["chapter_id", "display_order"],
    )

    op.create_table(
        "statute_member_status",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("eligible", sa.Boolean(), nullable=False),
        sa.Column("eligibility_reason", sa.String(255), nullable=True),
        sa.Column("has_voted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("voted_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["consultation_id"], ["statute_consultations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.UniqueConstraint(
            "consultation_id",
            "member_id",
            name="uq_statute_member_status_consultation_member",
        ),
    )
    op.create_index(
        "ix_statute_member_status_org",
        "statute_member_status",
        ["organization_id", "consultation_id"],
    )

    op.create_table(
        "statute_issuance_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["consultation_id"], ["statute_consultations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.UniqueConstraint("token_hash", name="uq_statute_issuance_token_hash"),
    )
    op.create_index(
        "ix_statute_issuance_consultation_member",
        "statute_issuance_tokens",
        ["consultation_id", "member_id"],
    )

    op.create_table(
        "statute_ballots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encrypted_payload", sa.Text(), nullable=False),
        sa.Column("receipt_hash", sa.String(64), nullable=False),
        sa.Column("zkp_proof", sa.Text(), nullable=True),
        sa.Column("key_version", sa.String(50), nullable=True),
        sa.Column("qr_payload", sa.Text(), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["consultation_id"], ["statute_consultations.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.UniqueConstraint(
            "consultation_id", "member_id", name="uq_statute_ballots_consultation_member"
        ),
        sa.UniqueConstraint(
            "consultation_id", "receipt_hash", name="uq_statute_ballots_receipt"
        ),
    )
    op.create_index("ix_statute_ballots_receipt_hash", "statute_ballots", ["receipt_hash"])
    op.create_index(
        "ix_statute_ballots_org_consultation",
        "statute_ballots",
        ["organization_id", "consultation_id"],
    )

    op.create_table(
        "statute_tallies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("artifact", postgresql.JSONB(), nullable=False),
        sa.Column("eligible_member_count", sa.Integer(), nullable=False),
        sa.Column("voted_member_count", sa.Integer(), nullable=False),
        sa.Column("ballot_count", sa.Integer(), nullable=False),
        sa.Column("quorum_required", sa.Integer(), nullable=False),
        sa.Column("quorum_met", sa.Boolean(), nullable=False),
        sa.Column("pilot_override", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("acta", postgresql.JSONB(), nullable=True),
        sa.Column("first_approver_hash", sa.String(64), nullable=True),
        sa.Column("second_approver_hash", sa.String(64), nullable=True),
        _created_at(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["consultation_id"], ["statute_consultations.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint("consultation_id", name="uq_statute_tallies_consultation"),
    )
    op.create_index(
        "ix_statute_tallies_org",
        "statute_tallies",
        ["organization_id", "consultation_id"],
    )

    op.create_table(
        "statute_tally_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("consultation_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact", postgresql.JSONB(), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("proposer_hash", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("pilot_override", sa.Boolean(), server_default=sa.false(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(
            ["consultation_id"], ["statute_consultations.id"], ondelete="CASCADE"
        ),
        sa.UniqueConstraint(
            "consultation_id", name="uq_statute_tally_proposals_consultation"
        ),
    )


def downgrade() -> None:
    op.drop_table("statute_tally_proposals")
    op.drop_index("ix_statute_tallies_org", table_name="statute_tallies")
    op.drop_table("statute_tallies")
    op.drop_index("ix_statute_ballots_org_consultation", table_name="statute_ballots")
    op.drop_index("ix_statute_ballots_receipt_hash", table_name="statute_ballots")
    op.drop_table("statute_ballots")
    op.drop_index(
        "ix_statute_issuance_consultation_member", table_name="statute_issuance_tokens"
    )
    op.drop_table("statute_issuance_tokens")
    op.drop_index("ix_statute_member_status_org", table_name="statute_member_status")
    op.drop_table("statute_member_status")
    op.drop_index("ix_statute_articles_chapter", table_name="statute_articles")
    op.drop_table("statute_articles")
    op.drop_index("ix_statute_chapters_consultation", table_name="statute_chapters")
    op.drop_table("statute_chapters")
    op.drop_index("ix_statute_titles_consultation", table_name="statute_titles")
    op.drop_table("statute_titles")
    op.drop_index("ix_statute_consultations_org_status", table_name="statute_consultations")
    op.drop_table("statute_consultations")
