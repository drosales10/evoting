"""Add encrypted TOTP credentials for administrative MFA.

Revision ID: 0003_admin_mfa_credentials
Revises: 0002_auth_schema
Create Date: 2026-07-21

The secret is encrypted by the application before persistence. The encryption key
must be supplied outside the database through MFA_ENCRYPTION_KEY.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003_admin_mfa_credentials"
down_revision: str | None = "0002_auth_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_mfa_credentials",
        sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("encrypted_secret", sa.String(512), nullable=False),
        sa.Column("last_used_counter", sa.BigInteger(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("admin_user_id"),
    )
    op.create_index(
        "ix_admin_mfa_credentials_organization",
        "admin_mfa_credentials",
        ["organization_id"],
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Authentication schema is not downgraded automatically; use a reviewed roll-forward."
    )
