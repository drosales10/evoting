"""Production hardening: signing keys, audit chain, issuance tokens, dual tally approval, RLS."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008_production_hardening"
down_revision: str | None = "0007_election_tallies"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("elections", sa.Column("signing_public_key", sa.Text(), nullable=True))
    op.add_column("audit_logs", sa.Column("prev_hash", sa.String(length=64), nullable=True))
    op.add_column("audit_logs", sa.Column("entry_hash", sa.String(length=64), nullable=True))
    op.add_column(
        "election_tallies",
        sa.Column("acta", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    )
    op.add_column(
        "election_tallies",
        sa.Column("first_approver_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "election_tallies",
        sa.Column("second_approver_hash", sa.String(length=64), nullable=True),
    )

    op.create_table(
        "ballot_issuance_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("election_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("member_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("members.id"), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("token_hash", name="uq_ballot_issuance_token_hash"),
    )
    op.create_index(
        "ix_ballot_issuance_election_member",
        "ballot_issuance_tokens",
        ["election_id", "member_id"],
    )

    op.create_table(
        "election_tally_proposals",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("organization_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("election_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("artifact", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("signature", sa.Text(), nullable=False),
        sa.Column("artifact_sha256", sa.String(length=64), nullable=False),
        sa.Column("proposer_hash", sa.String(length=64), nullable=False),
        sa.Column("reason", sa.String(length=255), nullable=False),
        sa.Column("pilot_override", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("election_id", name="uq_election_tally_proposals_election"),
    )

    # Append-only enforcement at DB level for audit_logs
    op.execute("REVOKE UPDATE, DELETE ON audit_logs FROM PUBLIC")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION prevent_audit_mutation()
        RETURNS trigger AS $$
        BEGIN
          RAISE EXCEPTION 'audit_logs is append-only';
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    # asyncpg rejects multiple statements in one prepared execute
    op.execute("DROP TRIGGER IF EXISTS trg_audit_logs_immutable ON audit_logs")
    op.execute(
        """
        CREATE TRIGGER trg_audit_logs_immutable
        BEFORE UPDATE OR DELETE ON audit_logs
        FOR EACH ROW EXECUTE PROCEDURE prevent_audit_mutation()
        """
    )

    # Row Level Security scaffolding (application still sets app.organization_id)
    for table in (
        "members",
        "elections",
        "encrypted_ballots",
        "audit_logs",
        "member_election_status",
        "election_tallies",
        "slates",
        "ballot_issuance_tokens",
        "election_tally_proposals",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"DROP POLICY IF EXISTS tenant_isolation_{table} ON {table}")
        op.execute(
            f"""
            CREATE POLICY tenant_isolation_{table} ON {table}
            USING (
              current_setting('app.organization_id', true) IS NULL
              OR current_setting('app.organization_id', true) = ''
              OR organization_id::text = current_setting('app.organization_id', true)
            )
            """
        )


def downgrade() -> None:
    raise NotImplementedError("Roll-forward only")
