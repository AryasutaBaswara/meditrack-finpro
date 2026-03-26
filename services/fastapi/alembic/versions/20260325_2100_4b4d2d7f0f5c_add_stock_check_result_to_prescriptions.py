"""add stock_check_result to prescriptions

Revision ID: 4b4d2d7f0f5c
Revises: a95299ee4f37
Create Date: 2026-03-25 21:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "4b4d2d7f0f5c"
down_revision: str | None = "a95299ee4f37"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "prescriptions",
        sa.Column("stock_check_result", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prescriptions", "stock_check_result")
