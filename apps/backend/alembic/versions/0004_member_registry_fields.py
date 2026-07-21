"""Expand members to the administrative roster contract.

Revision ID: 0004_member_registry_fields
Revises: 0003_admin_mfa_credentials
Create Date: 2026-07-21

New fields are nullable for expand/backfill compatibility with existing members.
Photos are stored as PostgreSQL BYTEA with content metadata and a SHA-256 digest.
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0004_member_registry_fields"
down_revision: str | None = "0003_admin_mfa_credentials"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_MEMBER_FIELDS = (
    ("registry_code", sa.String(50)),
    ("member_type", sa.String(50)),
    ("decade", sa.Integer()),
    ("graduation_year", sa.Integer()),
    ("semester", sa.String(10)),
    ("sex", sa.String(10)),
    ("alive", sa.Boolean()),
    ("section", sa.String(100)),
    ("location", sa.String(50)),
    ("mention", sa.String(255)),
    ("graduation_date", sa.Date()),
    ("photo_data", sa.LargeBinary()),
    ("photo_content_type", sa.String(100)),
    ("photo_filename", sa.String(255)),
    ("photo_sha256", sa.String(64)),
    ("photo_size_bytes", sa.Integer()),
)


def upgrade() -> None:
    for name, column_type in _MEMBER_FIELDS:
        op.add_column("members", sa.Column(name, column_type, nullable=True))
    op.create_unique_constraint(
        "uq_members_organization_registry_code",
        "members",
        ["organization_id", "registry_code"],
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Member registry schema is not downgraded automatically; use a reviewed roll-forward."
    )
