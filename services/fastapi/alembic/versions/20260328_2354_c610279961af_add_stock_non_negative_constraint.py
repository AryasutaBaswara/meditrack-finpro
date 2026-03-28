"""add_stock_non_negative_constraint

Ensures drugs.stock can never go below 0 at the database level.
This is a safety net for the atomic UPDATE pattern in DispensationService.
If the application logic fails to guard, the DB will reject the write.

Revision ID: c610279961af
Revises: 5446873836d4
Create Date: 2026-03-28 23:54:05.073842
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c610279961af"
down_revision: str | None = "5446873836d4"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE public.drugs "
        "ADD CONSTRAINT chk_drugs_stock_non_negative CHECK (stock >= 0);"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE public.drugs "
        "DROP CONSTRAINT IF EXISTS chk_drugs_stock_non_negative;"
    )
