"""Add immutable aggregated election tally records.

Revision ID: 0007_election_tallies
Revises: 0006_election_activation
Create Date: 2026-07-21

The table stores only signed aggregate artifacts. It never stores a private key,
member identifier, session, receipt-to-member relation, or plaintext ballot.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0007_election_tallies"
down_revision: str | None = "0006_election_activation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "election_tallies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("election_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_sha256", sa.String(64), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("artifact", postgresql.JSONB(), nullable=False),
        sa.Column("eligible_member_count", sa.Integer(), nullable=False),
        sa.Column("voted_member_count", sa.Integer(), nullable=False),
        sa.Column("ballot_count", sa.Integer(), nullable=False),
        sa.Column("quorum_required", sa.Integer(), nullable=False),
        sa.Column("quorum_met", sa.Boolean(), nullable=False),
        sa.Column("pilot_override", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["election_id"], ["elections.id"]),
        sa.UniqueConstraint("election_id", name="uq_election_tallies_election"),
    )
    op.create_index(
        "ix_election_tallies_organization",
        "election_tallies",
        ["organization_id", "election_id"],
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Election tally records are not downgraded automatically; use a reviewed roll-forward."
    )
