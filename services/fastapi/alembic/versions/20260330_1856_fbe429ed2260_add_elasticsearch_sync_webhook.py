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
    # 3. Buat Trigger hanya jika schema supabase_functions ada (Lokal/Docker)
    # Di Supabase Cloud, trigger semacam ini biasanya dikonfigurasi via Dashboard Webhooks
    op.execute(
        """
    DO $$ 
    BEGIN
        IF EXISTS (SELECT 1 FROM information_schema.schemata WHERE schema_name = 'supabase_functions') THEN
            CREATE TRIGGER tr_audit_drug_stock_sync
            AFTER INSERT OR UPDATE OR DELETE ON public.drugs
            FOR EACH ROW
            EXECUTE FUNCTION supabase_functions.http_request(
                'http://kong:8000/functions/v1/drug-sync',
                'POST',
                '{"Content-Type":"application/json"}',
                '{}',
                '1000'
            );
        END IF;
    END $$;
    """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tr_audit_drug_stock_sync ON public.drugs;")
