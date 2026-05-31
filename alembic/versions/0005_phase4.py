"""Phase 4: banners, rating prompts, support inbox.

Revision ID: 0005
Revises: 0004
Create Date: 2024-05-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE ratingactionenum AS ENUM ('shown', 'accepted', 'declined', 'later')")
    op.execute("CREATE TYPE conversationstatusenum AS ENUM ('open', 'waiting', 'resolved', 'closed')")
    op.execute("CREATE TYPE sendertypeenum AS ENUM ('user', 'admin')")

    op.create_table(
        "banner_campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.String(2000), nullable=False),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column("cta_label", sa.String(100), nullable=False),
        sa.Column("cta_url", sa.String(512), nullable=False),
        sa.Column("target_conditions", postgresql.JSON(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("frequency_cap", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("total_impressions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_clicks", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "banner_impressions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("banner_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("banner_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shown_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("clicked_at", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "rating_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("min_sessions", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("min_days_since_install", sa.Integer(), nullable=False, server_default="7"),
        sa.Column("cooldown_days", sa.Integer(), nullable=False, server_default="30"),
        sa.Column("exclude_negative_events", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("store_url_ios", sa.String(512), nullable=True),
        sa.Column("store_url_android", sa.String(512), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "mode_id", name="uq_rating_rule_project_mode"),
    )

    rating_action_enum = postgresql.ENUM("shown", "accepted", "declined", "later", name="ratingactionenum", create_type=False)

    op.create_table(
        "rating_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", rating_action_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    conversation_status_enum = postgresql.ENUM("open", "waiting", "resolved", "closed", name="conversationstatusenum", create_type=False)

    op.create_table(
        "support_conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("status", conversation_status_enum, nullable=False, server_default="open"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    sender_type_enum = postgresql.ENUM("user", "admin", name="sendertypeenum", create_type=False)

    op.create_table(
        "support_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("conversation_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("support_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_type", sender_type_enum, nullable=False),
        sa.Column("sender_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("attachment_url", sa.String(512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("support_messages")
    op.drop_table("support_conversations")
    op.drop_table("rating_events")
    op.drop_table("rating_rules")
    op.drop_table("banner_impressions")
    op.drop_table("banner_campaigns")
    op.execute("DROP TYPE IF EXISTS sendertypeenum")
    op.execute("DROP TYPE IF EXISTS conversationstatusenum")
    op.execute("DROP TYPE IF EXISTS ratingactionenum")
