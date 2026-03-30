"""add_stock_audit_trigger

Revision ID: fea984861798
Revises: 09315a8abce7
Create Date: 2026-03-30 16:56:21.009741
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "fea984861798"
down_revision: str | None = "09315a8abce7"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Buat fungsi audit yang cerdas
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.handle_stock_audit()
    RETURNS TRIGGER AS $$
    DECLARE
        v_reason TEXT;
        v_ref_id UUID;
        v_change INTEGER;
    BEGIN
        v_change := NEW.stock - OLD.stock;
        
        -- Ambil konteks dari session variabel (set dari FastAPI)
        v_reason := COALESCE(
            NULLIF(current_setting('app.log_reason', true), ''), 
            'manual_update'
        );
        
        BEGIN
            v_ref_id := NULLIF(current_setting('app.log_reference_id', true), '')::UUID;
        EXCEPTION WHEN OTHERS THEN
            v_ref_id := NULL;
        END;

        INSERT INTO public.stock_logs (
            id, drug_id, change_amount, reason, 
            reference_id, stock_before, stock_after, 
            created_at, updated_at
        ) VALUES (
            gen_random_uuid(), NEW.id, v_change, v_reason,
            v_ref_id, OLD.stock, NEW.stock,
            NOW(), NOW()
        );

        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql SECURITY DEFINER;
    """
    )

    # 2. Pasang trigger di tabel drugs
    op.execute("DROP TRIGGER IF EXISTS tr_audit_drug_stock ON public.drugs;")
    op.execute(
        """
    CREATE TRIGGER tr_audit_drug_stock
    AFTER UPDATE ON public.drugs
    FOR EACH ROW
    WHEN (OLD.stock IS DISTINCT FROM NEW.stock)
    EXECUTE FUNCTION public.handle_stock_audit();
    """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS tr_audit_drug_stock ON public.drugs;")
    op.execute("DROP FUNCTION IF EXISTS public.handle_stock_audit();")
