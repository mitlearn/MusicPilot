"""Initial MusicPilot schema.

Revision ID: 20260614_0001
Revises:
Create Date: 2026-06-14
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260614_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "subscriptions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("kind", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("external_id", sa.String(length=256), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "torrent_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("torrent_hash", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=512), nullable=False),
        sa.Column("source", sa.String(length=128), nullable=False),
        sa.Column("download_url", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("save_path", sa.Text(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("torrent_hash"),
    )
    op.create_index(
        op.f("ix_torrent_records_torrent_hash"),
        "torrent_records",
        ["torrent_hash"],
        unique=False,
    )
    op.create_table(
        "media_files",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("torrent_hash", sa.String(length=64), nullable=True),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("library_path", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=True),
        sa.Column("artist", sa.String(length=512), nullable=True),
        sa.Column("album", sa.String(length=512), nullable=True),
        sa.Column("year", sa.Integer(), nullable=True),
        sa.Column("track_number", sa.Integer(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("library_path"),
    )
    op.create_index(op.f("ix_media_files_torrent_hash"), "media_files", ["torrent_hash"])


def downgrade() -> None:
    op.drop_index(op.f("ix_media_files_torrent_hash"), table_name="media_files")
    op.drop_table("media_files")
    op.drop_index(op.f("ix_torrent_records_torrent_hash"), table_name="torrent_records")
    op.drop_table("torrent_records")
    op.drop_table("subscriptions")
