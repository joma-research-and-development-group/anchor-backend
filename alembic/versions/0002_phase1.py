"""Phase 1: versions, api keys, maintenance, remote config.

Revision ID: 0002
Revises: 0001
Create Date: 2024-02-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE platformenum AS ENUM ('ios', 'android', 'macos', 'windows', 'linux', 'web')")
    op.execute("CREATE TYPE apikeystatusenum AS ENUM ('active', 'revoked')")
    op.execute("CREATE TYPE configvaluetypeenum AS ENUM ('bool', 'string', 'int', 'double', 'json')")

    platform_enum = postgresql.ENUM("ios", "android", "macos", "windows", "linux", "web", name="platformenum", create_type=False)
    apikey_status_enum = postgresql.ENUM("active", "revoked", name="apikeystatusenum", create_type=False)
    config_value_type_enum = postgresql.ENUM("bool", "string", "int", "double", "json", name="configvaluetypeenum", create_type=False)

    op.create_table(
        "app_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("semver", sa.String(50), nullable=False),
        sa.Column("build_number", sa.Integer(), nullable=False),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "mode_id", "platform", "semver", "build_number", name="uq_app_version"),
    )

    op.create_table(
        "api_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_versions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("key_prefix", sa.String(30), nullable=False, index=True),
        sa.Column("key_hash", sa.String(128), nullable=False),
        sa.Column("status", apikey_status_enum, nullable=False, server_default="active"),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_reason", sa.String(500), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "mode_id", "version_id", name="uq_api_key_version"),
    )

    op.create_table(
        "version_policies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("platform", platform_enum, nullable=False),
        sa.Column("min_supported_semver", sa.String(50), nullable=True),
        sa.Column("latest_semver", sa.String(50), nullable=True),
        sa.Column("store_url", sa.String(512), nullable=True),
        sa.Column("message_force", sa.String(1000), nullable=True),
        sa.Column("message_soft", sa.String(1000), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "mode_id", "platform", name="uq_version_policy"),
    )

    op.create_table(
        "maintenance_windows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("message", sa.String(2000), nullable=False),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("allow_read_only", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "config_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value_type", config_value_type_enum, nullable=False),
        sa.Column("default_value", postgresql.JSONB(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "mode_id", "key", name="uq_config_entry_key"),
    )

    op.create_table(
        "config_overrides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("entry_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("config_entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("conditions", postgresql.JSONB(), nullable=False),
        sa.Column("value", postgresql.JSONB(), nullable=False),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("config_overrides")
    op.drop_table("config_entries")
    op.drop_table("maintenance_windows")
    op.drop_table("version_policies")
    op.drop_table("api_keys")
    op.drop_table("app_versions")
    op.execute("DROP TYPE IF EXISTS configvaluetypeenum")
    op.execute("DROP TYPE IF EXISTS apikeystatusenum")
    op.execute("DROP TYPE IF EXISTS platformenum")
