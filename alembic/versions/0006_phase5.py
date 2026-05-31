"""Phase 5: analytics events, crash reports, experiments, deep links.

Revision ID: 0006
Revises: 0005
Create Date: 2024-06-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE crashgroupstatusenum AS ENUM ('open', 'resolved', 'ignored')")
    op.execute("CREATE TYPE experimentstatusenum AS ENUM ('draft', 'running', 'paused', 'completed')")

    op.create_table(
        "events",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("properties", postgresql.JSON(), nullable=True),
        sa.Column("session_id", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_events_project_name_created", "events", ["project_id", "name", "created_at"])

    crash_group_status_enum = postgresql.ENUM("open", "resolved", "ignored", name="crashgroupstatusenum", create_type=False)

    op.create_table(
        "crash_groups",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("fingerprint", sa.String(64), unique=True, nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", crash_group_status_enum, nullable=False, server_default="open"),
        sa.Column("assigned_to", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    op.create_table(
        "crash_reports",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="SET NULL"), nullable=True),
        sa.Column("group_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("crash_groups.id", ondelete="SET NULL"), nullable=True),
        sa.Column("error_type", sa.String(255), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=False),
        sa.Column("stacktrace", sa.Text(), nullable=False),
        sa.Column("app_version", sa.String(50), nullable=False),
        sa.Column("build_number", sa.String(50), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("os_version", sa.String(50), nullable=False),
        sa.Column("device_model", sa.String(100), nullable=False),
        sa.Column("extra", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    experiment_status_enum = postgresql.ENUM("draft", "running", "paused", "completed", name="experimentstatusenum", create_type=False)

    op.create_table(
        "experiments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", experiment_status_enum, nullable=False, server_default="draft"),
        sa.Column("traffic_pct", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "experiment_variants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("weight", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("payload", postgresql.JSON(), nullable=True),
    )

    op.create_table(
        "experiment_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("experiment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("experiment_variants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("experiment_id", "device_id", name="uq_experiment_device"),
    )

    op.create_table(
        "deep_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("slug", sa.String(100), unique=True, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("ios_url", sa.String(512), nullable=True),
        sa.Column("android_url", sa.String(512), nullable=True),
        sa.Column("web_url", sa.String(512), nullable=True),
        sa.Column("fallback_url", sa.String(512), nullable=False),
        sa.Column("utm_source", sa.String(255), nullable=True),
        sa.Column("utm_medium", sa.String(255), nullable=True),
        sa.Column("utm_campaign", sa.String(255), nullable=True),
        sa.Column("clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("deep_links")
    op.drop_table("experiment_assignments")
    op.drop_table("experiment_variants")
    op.drop_table("experiments")
    op.drop_table("crash_reports")
    op.drop_table("crash_groups")
    op.drop_index("ix_events_project_name_created", table_name="events")
    op.drop_table("events")
    op.execute("DROP TYPE IF EXISTS experimentstatusenum")
    op.execute("DROP TYPE IF EXISTS crashgroupstatusenum")
