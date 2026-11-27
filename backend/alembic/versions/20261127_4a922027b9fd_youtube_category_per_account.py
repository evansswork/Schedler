"""youtube category per account

Revision ID: 4a922027b9fd
Revises: aeccc85fbcb0
Create Date: 2026-11-27 19:37:41.937738
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "4a922027b9fd"
down_revision: str | None = "aeccc85fbcb0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("account") as batch:
        batch.add_column(sa.Column("yt_category_id", sa.String(), nullable=True))
    # Owner's choices (2026-11-27): YT #1 = AI apps, YT #2 = personal vlog.
    op.execute("UPDATE account SET yt_category_id = '28' WHERE label = 'YT #1'")
    op.execute(
        "UPDATE account SET yt_category_id = '22' "
        "WHERE platform = 'youtube' AND yt_category_id IS NULL"
    )


def downgrade() -> None:
    with op.batch_alter_table("account") as batch:
        batch.drop_column("yt_category_id")
