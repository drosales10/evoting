"""Add member_id indexes used by hard-delete reference checks.

Revision ID: 0013_member_deletion_indexes
Revises: 0012_election_broadcasts
Create Date: 2026-07-24
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0013_member_deletion_indexes"
down_revision: str | None = "0012_election_broadcasts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("ix_slates_proxy_member_id", "slates", ["proxy_member_id"])
    op.create_index("ix_candidates_member_id", "candidates", ["member_id"])
    op.create_index(
        "ix_member_election_status_member_id",
        "member_election_status",
        ["member_id"],
    )
    op.create_index(
        "ix_ballot_issuance_tokens_member_id",
        "ballot_issuance_tokens",
        ["member_id"],
    )
    op.create_index(
        "ix_voter_otp_challenges_member_id",
        "voter_otp_challenges",
        ["member_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_voter_otp_challenges_member_id", table_name="voter_otp_challenges")
    op.drop_index(
        "ix_ballot_issuance_tokens_member_id",
        table_name="ballot_issuance_tokens",
    )
    op.drop_index(
        "ix_member_election_status_member_id",
        table_name="member_election_status",
    )
    op.drop_index("ix_candidates_member_id", table_name="candidates")
    op.drop_index("ix_slates_proxy_member_id", table_name="slates")
