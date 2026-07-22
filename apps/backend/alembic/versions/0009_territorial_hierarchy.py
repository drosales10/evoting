"""Territorial hierarchy N1-N5, member.region, election scope."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_territorial_hierarchy"
down_revision: str | None = "0008_production_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS postgis")

    op.add_column("members", sa.Column("region", sa.String(length=100), nullable=True))

    op.create_table(
        "electoral_regions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("organization_id", "code", name="uq_electoral_regions_org_code"),
    )
    op.execute(
        "ALTER TABLE electoral_regions ADD COLUMN IF NOT EXISTS geom geometry(MultiPolygon, 4326)"
    )

    op.create_table(
        "electoral_states",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "region_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("electoral_regions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("organization_id", "code", name="uq_electoral_states_org_code"),
    )
    op.execute(
        "ALTER TABLE electoral_states ADD COLUMN IF NOT EXISTS geom geometry(MultiPolygon, 4326)"
    )

    op.create_table(
        "electoral_municipalities",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "state_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("electoral_states.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_electoral_municipalities_org_code"
        ),
    )
    op.execute(
        "ALTER TABLE electoral_municipalities "
        "ADD COLUMN IF NOT EXISTS geom geometry(MultiPolygon, 4326)"
    )

    op.create_table(
        "electoral_polling_places",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column(
            "organization_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("organizations.id"),
            nullable=False,
        ),
        sa.Column(
            "municipality_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("electoral_municipalities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("geojson", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "organization_id", "code", name="uq_electoral_polling_places_org_code"
        ),
    )
    op.execute(
        "ALTER TABLE electoral_polling_places "
        "ADD COLUMN IF NOT EXISTS geom geometry(Point, 4326)"
    )

    op.add_column(
        "members",
        sa.Column(
            "region_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("electoral_regions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "members",
        sa.Column(
            "state_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("electoral_states.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "members",
        sa.Column(
            "municipality_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("electoral_municipalities.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "members",
        sa.Column(
            "polling_place_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("electoral_polling_places.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_members_org_region", "members", ["organization_id", "region_id"])
    op.create_index("ix_members_org_state", "members", ["organization_id", "state_id"])

    op.add_column(
        "elections",
        sa.Column(
            "scope_level",
            sa.String(length=20),
            server_default="NATIONAL",
            nullable=False,
        ),
    )
    op.add_column(
        "elections",
        sa.Column(
            "region_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("electoral_regions.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.add_column(
        "elections",
        sa.Column(
            "state_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("electoral_states.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    raise NotImplementedError("Roll-forward only")
