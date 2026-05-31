"""Phase 2: push notifications, devices, announcements.

Revision ID: 0003
Revises: 0002
Create Date: 2024-03-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE pushproviderenum AS ENUM ('fcm', 'apns')")
    op.execute("CREATE TYPE campaignstatusenum AS ENUM ('draft', 'scheduled', 'sending', 'sent', 'failed')")
    op.execute("CREATE TYPE announcementtypeenum AS ENUM ('banner', 'modal', 'card')")

    push_provider_enum = postgresql.ENUM("fcm", "apns", name="pushproviderenum", create_type=False)
    campaign_status_enum = postgresql.ENUM("draft", "scheduled", "sending", "sent", "failed", name="campaignstatusenum", create_type=False)
    announcement_type_enum = postgresql.ENUM("banner", "modal", "card", name="announcementtypeenum", create_type=False)

    op.create_table(
        "push_credentials",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("provider", push_provider_enum, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("encrypted_creds", sa.LargeBinary(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "devices",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("install_id", sa.String(255), nullable=False),
        sa.Column("user_ref", sa.String(255), nullable=True),
        sa.Column("push_token", sa.String(512), nullable=True),
        sa.Column("push_provider", push_provider_enum, nullable=True),
        sa.Column("platform", sa.String(50), nullable=False),
        sa.Column("os_version", sa.String(50), nullable=True),
        sa.Column("device_model", sa.String(100), nullable=True),
        sa.Column("app_version", sa.String(50), nullable=True),
        sa.Column("build_number", sa.Integer(), nullable=True),
        sa.Column("locale", sa.String(20), nullable=True),
        sa.Column("timezone", sa.String(100), nullable=True),
        sa.Column("country", sa.String(10), nullable=True),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("attributes", postgresql.JSONB(), nullable=True),
        sa.UniqueConstraint("project_id", "mode_id", "install_id", name="uq_device_install"),
    )

    op.create_table(
        "push_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.String(2000), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=True),
        sa.Column("status", campaign_status_enum, nullable=False, server_default="draft"),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_value", sa.String(500), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("total_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_opened", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "push_campaign_targets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("push_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "push_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("push_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )

    op.create_table(
        "announcements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.String(5000), nullable=False),
        sa.Column("type", announcement_type_enum, nullable=False),
        sa.Column("action_url", sa.String(512), nullable=True),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column("target_conditions", postgresql.JSONB(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "announcement_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("announcement_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("announcements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("dismissed_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("announcement_views")
    op.drop_table("announcements")
    op.drop_table("push_deliveries")
    op.drop_table("push_campaign_targets")
    op.drop_table("push_campaigns")
    op.drop_table("devices")
    op.drop_table("push_credentials")
    op.execute("DROP TYPE IF EXISTS announcementtypeenum")
    op.execute("DROP TYPE IF EXISTS campaignstatusenum")
    op.execute("DROP TYPE IF EXISTS pushproviderenum")
