"""add_elasticsearch_sync_webhook

Revision ID: fbe429ed2260
Revises: fea984861798
Create Date: 2026-03-30 18:56:36.518472
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fbe429ed2260"
down_revision: str | None = "fea984861798"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Hapus trigger lama jika ada supaya tidak bentrok
    op.execute("DROP TRIGGER IF EXISTS tr_audit_drug_stock_sync ON public.drugs;")

    # 2. Hapus fungsi manualmu jika sebelumnya sempat terbuat
    op.execute("DROP FUNCTION IF EXISTS public.handle_drug_sync();")

    # 3. Langsung buat Trigger menggunakan fungsi bawaan Supabase
    # PENTING: Semua argumen untuk fungsi trigger HARUS berupa string (pakai tanda kutip)
    op.execute(
        """
    CREATE TRIGGER tr_audit_drug_stock_sync
    AFTER INSERT OR UPDATE OR DELETE ON public.drugs
    FOR EACH ROW
    EXECUTE FUNCTION supabase_functions.http_request(
        'http://kong:8000/functions/v1/drug-sync', -- 1. URL Edge Function
        'POST',                                    -- 2. Method
        '{"Content-Type":"application/json"}',     -- 3. Headers
        '{}',                                      -- 4. Payload ({} berarti kirim semua record bawaan)
        '1000'                                     -- 5. Timeout (HARUS string '1000', bukan integer 1000)
    );
    """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tr_audit_drug_stock_sync ON public.drugs;")
