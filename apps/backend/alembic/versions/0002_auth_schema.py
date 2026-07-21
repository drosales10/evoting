"""Add separated administrative and voter authentication persistence.

Revision ID: 0002_auth_schema
Revises: 0001_core_schema
Create Date: 2026-07-21

This revision is prepared for review and is not applied automatically.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002_auth_schema"
down_revision: str | None = "0001_core_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "admin_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("status", sa.String(50), server_default="ACTIVE", nullable=False),
        sa.Column("mfa_enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint(
            "organization_id",
            "email",
            name="uq_admin_users_organization_email",
        ),
    )
    op.create_index(
        "ix_admin_users_organization_status",
        "admin_users",
        ["organization_id", "status"],
    )

    op.create_table(
        "admin_user_roles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("admin_user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["admin_user_id"], ["admin_users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("admin_user_id", "role", name="uq_admin_user_roles_user_role"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("principal_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("realm", sa.String(20), nullable=False),
        sa.Column("refresh_token_hash", sa.String(128), nullable=False),
        sa.Column("csrf_token_hash", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )
    op.create_index(
        "ix_auth_sessions_organization_realm",
        "auth_sessions",
        ["organization_id", "realm"],
    )

    op.create_table(
        "voter_otp_challenges",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("code_hash", sa.String(128), nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("purpose", sa.String(30), server_default="LOGIN", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
    )
    op.create_index(
        "ix_voter_otp_challenges_organization_expires",
        "voter_otp_challenges",
        ["organization_id", "expires_at"],
    )


def downgrade() -> None:
    raise NotImplementedError(
        "Authentication schema is not downgraded automatically; use a reviewed roll-forward."
    )
