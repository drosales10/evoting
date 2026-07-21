"""Persist the timestamp of the FREEZE to ACTIVE transition.

Revision ID: 0006_election_activation
Revises: 0005_eligibility_reason
Create Date: 2026-07-21

The column is nullable so existing elections remain compatible. Activation also
stores the public election key and an append-only audit event at application level.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0006_election_activation"
down_revision: str | None = "0005_eligibility_reason"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "elections",
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Election activation timestamps are not downgraded automatically; use a reviewed "
        "roll-forward."
    )
