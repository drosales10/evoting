"""Persist the eligibility reason in election snapshots.

Revision ID: 0005_eligibility_reason
Revises: 0004_member_registry_fields
Create Date: 2026-07-21

The new column is nullable so existing election snapshots remain compatible. New snapshots
write the reason captured at registration opening; existing snapshots use the API fallback.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0005_eligibility_reason"
down_revision: str | None = "0004_member_registry_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "member_election_status",
        sa.Column("eligibility_reason", sa.String(255), nullable=True),
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Eligibility snapshot reasons are not downgraded automatically; use a reviewed "
        "roll-forward."
    )
