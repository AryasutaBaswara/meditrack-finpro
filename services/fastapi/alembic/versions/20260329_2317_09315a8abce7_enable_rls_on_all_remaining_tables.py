"""enable_rls_on_all_remaining_tables

Enforces RLS on all remaining backend tables to complete the Zero Trust model.
Most tables will have NO policies, meaning they are accessible ONLY via 
FastAPI (Service Role) or SECURITY DEFINER RPCs. 

Specific policies are added for 'drugs' and 'profiles' to allow limited 
frontend-side reading where necessary.

Revision ID: 09315a8abce7
Revises: d3f80a352f89
Create Date: 2026-03-29 23:17:10.000000
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "09315a8abce7"
down_revision: str | None = "d3f80a352f89"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ----------------------------------------------------------------
    # 1. Enable RLS on all remaining tables
    # ----------------------------------------------------------------
    op.execute("ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.profiles ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.roles ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.user_roles ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.doctors ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.drugs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.dispensations ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.stock_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.prescription_items ENABLE ROW LEVEL SECURITY;")

    # ----------------------------------------------------------------
    # 2. Add Read-Only Policies for Catalog tables
    # ----------------------------------------------------------------

    # Authenticated users can browse the drug catalog but not change it
    op.execute(
        """
    CREATE POLICY "authenticated_view_drugs" ON public.drugs
        FOR SELECT TO authenticated
        USING (deleted_at IS NULL);
    """
    )

    # Authenticated users can see doctor info
    op.execute(
        """
    CREATE POLICY "authenticated_view_doctors" ON public.doctors
        FOR SELECT TO authenticated
        USING (deleted_at IS NULL);
    """
    )

    # ----------------------------------------------------------------
    # 3. Add Identity-based Policies
    # ----------------------------------------------------------------

    # Users can only see their own profile
    op.execute(
        """
    CREATE POLICY "user_view_own_profile" ON public.profiles
        FOR SELECT TO authenticated
        USING (user_id = public.current_app_user_id());
    """
    )

    # ----------------------------------------------------------------
    # 4. Default Deny Tables (Backend-Only)
    # ----------------------------------------------------------------
    # Tables with RLS ENABLED but NO policies (only accessible via service_role):
    # - users
    # - roles
    # - user_roles
    # - dispensations
    # - stock_logs
    # - prescription_items (items are queried via RPC which is SECURITY DEFINER)
    # ----------------------------------------------------------------


def downgrade() -> None:
    # 1. Drop added policies
    op.execute('DROP POLICY IF EXISTS "user_view_own_profile" ON public.profiles;')
    op.execute('DROP POLICY IF EXISTS "authenticated_view_doctors" ON public.doctors;')
    op.execute('DROP POLICY IF EXISTS "authenticated_view_drugs" ON public.drugs;')

    # 2. Disable RLS
    op.execute("ALTER TABLE public.prescription_items DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.stock_logs DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.dispensations DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.drugs DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.doctors DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.user_roles DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.roles DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.profiles DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.users DISABLE ROW LEVEL SECURITY;")
