"""default posting slots

Revision ID: aeccc85fbcb0
Revises: 0858ba70b14e
Create Date: 2026-11-27 19:05:38.934462
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "aeccc85fbcb0"
down_revision: str | None = "0858ba70b14e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Literal copy of the owner's defaults at the time of this migration (not imported, so
# later changes to app.models.DEFAULT_SLOTS do not rewrite history).
SLOTS = '["19:30", "20:30", "21:30", "22:30", "23:30"]'


def upgrade() -> None:
    op.execute(
        sa.text("UPDATE account SET slots = :slots WHERE slots IS NULL OR slots = '[]'").bindparams(
            slots=SLOTS
        )
    )


def downgrade() -> None:
    pass  # data-only: the previous empty slot lists are not worth restoring
