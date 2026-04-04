"""add_prescription_list_indexes

Revision ID: b8d4a4d5b2d1
Revises: 09315a8abce7
Create Date: 2026-04-04 15:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "b8d4a4d5b2d1"
down_revision: str | None = "09315a8abce7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_prescriptions_doctor_active_created_at
        ON public.prescriptions (doctor_id, created_at DESC)
        WHERE deleted_at IS NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_prescriptions_patient_active_created_at
        ON public.prescriptions (patient_id, created_at DESC)
        WHERE deleted_at IS NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_prescriptions_status_active_created_at
        ON public.prescriptions (status, created_at DESC)
        WHERE deleted_at IS NULL;
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_prescription_items_prescription_id
        ON public.prescription_items (prescription_id);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS public.ix_prescription_items_prescription_id;")
    op.execute("DROP INDEX IF EXISTS public.ix_prescriptions_status_active_created_at;")
    op.execute(
        "DROP INDEX IF EXISTS public.ix_prescriptions_patient_active_created_at;"
    )
    op.execute("DROP INDEX IF EXISTS public.ix_prescriptions_doctor_active_created_at;")
