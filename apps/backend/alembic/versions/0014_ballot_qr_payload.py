"""Add qr_payload to encrypted_ballots for public receipt verification.

Revision ID: 0014_ballot_qr_payload
Revises: 0013_member_deletion_indexes
Create Date: 2026-07-25
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014_ballot_qr_payload"
down_revision: str | None = "0013_member_deletion_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "encrypted_ballots",
        sa.Column("qr_payload", sa.Text(), nullable=True),
    )
    op.create_index(
        "ix_encrypted_ballots_receipt_hash",
        "encrypted_ballots",
        ["receipt_hash"],
    )


def downgrade() -> None:
    op.drop_index("ix_encrypted_ballots_receipt_hash", table_name="encrypted_ballots")
    op.drop_column("encrypted_ballots", "qr_payload")
