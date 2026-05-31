"""Phase 3: localization, legal documents, onboarding.

Revision ID: 0004
Revises: 0003
Create Date: 2024-04-01 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE TYPE legaldoctypeenum AS ENUM ('privacy_policy', 'terms_of_service', 'custom')")
    op.execute("CREATE TYPE onboardingtriggerenum AS ENUM ('first_launch', 'version_update', 'manual')")

    op.create_table(
        "localization_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("locale", sa.String(20), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "mode_id", "key", "locale", name="uq_localization_entry"),
    )

    legal_doc_type_enum = postgresql.ENUM("privacy_policy", "terms_of_service", "custom", name="legaldoctypeenum", create_type=False)

    op.create_table(
        "legal_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("type", legal_doc_type_enum, nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("locale", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("requires_acceptance", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("project_id", "mode_id", "type", "version", "locale", name="uq_legal_document"),
    )

    op.create_table(
        "legal_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("legal_documents.id", ondelete="CASCADE"), nullable=False),
        sa.Column("device_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ip", sa.String(45), nullable=True),
    )

    onboarding_trigger_enum = postgresql.ENUM("first_launch", "version_update", "manual", name="onboardingtriggerenum", create_type=False)

    op.create_table(
        "onboarding_flows",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("mode_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("project_modes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("trigger", onboarding_trigger_enum, nullable=False),
        sa.Column("target_version", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "onboarding_slides",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("flow_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("onboarding_flows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("image_url", sa.String(512), nullable=True),
        sa.Column("bg_color", sa.String(20), nullable=True),
        sa.Column("action_label", sa.String(100), nullable=True),
        sa.Column("action_url", sa.String(512), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("onboarding_slides")
    op.drop_table("onboarding_flows")
    op.drop_table("legal_acceptances")
    op.drop_table("legal_documents")
    op.drop_table("localization_entries")
    op.execute("DROP TYPE IF EXISTS onboardingtriggerenum")
    op.execute("DROP TYPE IF EXISTS legaldoctypeenum")
