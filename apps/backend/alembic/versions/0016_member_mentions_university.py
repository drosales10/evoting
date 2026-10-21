"""Several career mentions and the university of the degree.

Revision ID: 0016_member_mentions_university
Revises: 0015_statute_consultations
Create Date: 2026-10-20
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0016_member_mentions_university"
down_revision: str | None = "0015_statute_consultations"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "members",
        "mention",
        existing_type=sa.String(length=255),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.add_column("members", sa.Column("university", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("members", "university")
    op.alter_column(
        "members",
        "mention",
        existing_type=sa.Text(),
        type_=sa.String(length=255),
        existing_nullable=True,
    )
