"""Add members.title for academic/professional title.

Revision ID: 0011_member_title
Revises: 0010_organization_geojson
Create Date: 2026-07-22
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011_member_title"
down_revision: str | None = "0010_organization_geojson"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("members", sa.Column("title", sa.String(255), nullable=True))


def downgrade() -> None:
    op.drop_column("members", "title")
