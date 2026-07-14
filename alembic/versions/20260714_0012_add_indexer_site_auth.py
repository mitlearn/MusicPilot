"""Add indexer site authentication fields.

Revision ID: 20260714_0012
Revises: 20260713_0011
Create Date: 2026-07-14
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260714_0012"
down_revision: str | None = "20260713_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("indexer_sites") as batch_op:
        batch_op.add_column(
            sa.Column("auth_type", sa.String(length=32), nullable=False, server_default="cookie"),
        )
        batch_op.add_column(sa.Column("api_key", sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("indexer_sites") as batch_op:
        batch_op.drop_column("api_key")
        batch_op.drop_column("auth_type")
