"""fix_rls_identity_mapping_and_soft_delete

Fixes two issues in the original RLS foundation migration:
1. Identity mapping gap (Keycloak sub vs users.id)
2. Missing soft-delete filters

Revision ID: 28a6e949ed7b
Revises: c610279961af
Create Date: 2026-03-29 11:18:29.655950
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "28a6e949ed7b"
down_revision: str | None = "c610279961af"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # 1. Drop existing policies
    op.execute(
        'DROP POLICY IF EXISTS "admin_all_prescriptions" ON public.prescriptions;'
    )
    op.execute(
        'DROP POLICY IF EXISTS "doctor_view_prescriptions" ON public.prescriptions;'
    )
    op.execute(
        'DROP POLICY IF EXISTS "patient_view_prescriptions" ON public.prescriptions;'
    )
    op.execute(
        'DROP POLICY IF EXISTS "pharmacist_view_prescriptions" ON public.prescriptions;'
    )
    op.execute('DROP POLICY IF EXISTS "admin_all_patients" ON public.patients;')
    op.execute('DROP POLICY IF EXISTS "doctor_view_patients" ON public.patients;')
    op.execute('DROP POLICY IF EXISTS "patient_view_self" ON public.patients;')
    op.execute('DROP POLICY IF EXISTS "pharmacist_view_patients" ON public.patients;')
    op.execute('DROP POLICY IF EXISTS "admin_all_storage" ON public.storage_files;')
    op.execute(
        'DROP POLICY IF EXISTS "doctor_pharmacist_view_storage" ON public.storage_files;'
    )
    op.execute('DROP POLICY IF EXISTS "patient_view_storage" ON public.storage_files;')

    # 2. Drop old helper
    op.execute("DROP FUNCTION IF EXISTS public.current_user_has_role(text);")

    # 3. Add current_app_user_id() helper
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.current_app_user_id()
    RETURNS uuid LANGUAGE sql SECURITY DEFINER SET search_path = public STABLE AS $$
      SELECT id FROM public.users WHERE keycloak_sub = (auth.jwt() ->> 'sub') AND deleted_at IS NULL LIMIT 1;
    $$;
    """
    )

    # 4. Add fixed current_user_has_role()
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.current_user_has_role(role_name text)
    RETURNS boolean LANGUAGE sql SECURITY DEFINER SET search_path = public STABLE AS $$
      SELECT EXISTS (
        SELECT 1 FROM public.user_roles ur JOIN public.roles r ON ur.role_id = r.id
        WHERE ur.user_id = public.current_app_user_id() AND r.name = role_name
      );
    $$;
    """
    )

    # 5. Recreate policies with soft-delete filters and fixed identity
    op.execute(
        "CREATE POLICY \"admin_all_prescriptions\" ON public.prescriptions FOR ALL TO authenticated USING (public.current_user_has_role('admin')) WITH CHECK (public.current_user_has_role('admin'));"
    )
    op.execute(
        "CREATE POLICY \"doctor_view_prescriptions\" ON public.prescriptions FOR SELECT TO authenticated USING (public.current_user_has_role('doctor') AND deleted_at IS NULL AND doctor_id IN (SELECT id FROM public.doctors WHERE user_id = public.current_app_user_id() AND deleted_at IS NULL));"
    )
    op.execute(
        "CREATE POLICY \"patient_view_prescriptions\" ON public.prescriptions FOR SELECT TO authenticated USING (public.current_user_has_role('patient') AND deleted_at IS NULL AND patient_id IN (SELECT id FROM public.patients WHERE user_id = public.current_app_user_id() AND deleted_at IS NULL));"
    )
    op.execute(
        "CREATE POLICY \"pharmacist_view_prescriptions\" ON public.prescriptions FOR SELECT TO authenticated USING (public.current_user_has_role('pharmacist') AND deleted_at IS NULL AND status::text NOT IN ('draft', 'cancelled'));"
    )

    op.execute(
        "CREATE POLICY \"admin_all_patients\" ON public.patients FOR ALL TO authenticated USING (public.current_user_has_role('admin')) WITH CHECK (public.current_user_has_role('admin'));"
    )
    op.execute(
        "CREATE POLICY \"doctor_view_patients\" ON public.patients FOR SELECT TO authenticated USING (public.current_user_has_role('doctor') AND deleted_at IS NULL);"
    )
    op.execute(
        "CREATE POLICY \"patient_view_self\" ON public.patients FOR SELECT TO authenticated USING (public.current_user_has_role('patient') AND deleted_at IS NULL AND user_id = public.current_app_user_id());"
    )
    op.execute(
        "CREATE POLICY \"pharmacist_view_patients\" ON public.patients FOR SELECT TO authenticated USING (public.current_user_has_role('pharmacist') AND deleted_at IS NULL);"
    )

    op.execute(
        "CREATE POLICY \"admin_all_storage\" ON public.storage_files FOR ALL TO authenticated USING (public.current_user_has_role('admin')) WITH CHECK (public.current_user_has_role('admin'));"
    )
    op.execute(
        "CREATE POLICY \"doctor_pharmacist_view_storage\" ON public.storage_files FOR SELECT TO authenticated USING (public.current_user_has_role('doctor') OR public.current_user_has_role('pharmacist'));"
    )
    op.execute(
        "CREATE POLICY \"patient_view_storage\" ON public.storage_files FOR SELECT TO authenticated USING (public.current_user_has_role('patient') AND (uploaded_by = public.current_app_user_id() OR prescription_id IN (SELECT id FROM public.prescriptions WHERE deleted_at IS NULL AND patient_id IN (SELECT id FROM public.patients WHERE user_id = public.current_app_user_id() AND deleted_at IS NULL))));"
    )


def downgrade() -> None:
    # 1. Drop fixed policies
    op.execute('DROP POLICY IF EXISTS "patient_view_storage" ON public.storage_files;')
    op.execute(
        'DROP POLICY IF EXISTS "doctor_pharmacist_view_storage" ON public.storage_files;'
    )
    op.execute('DROP POLICY IF EXISTS "admin_all_storage" ON public.storage_files;')
    op.execute('DROP POLICY IF EXISTS "pharmacist_view_patients" ON public.patients;')
    op.execute('DROP POLICY IF EXISTS "patient_view_self" ON public.patients;')
    op.execute('DROP POLICY IF EXISTS "doctor_view_patients" ON public.patients;')
    op.execute('DROP POLICY IF EXISTS "admin_all_patients" ON public.patients;')
    op.execute(
        'DROP POLICY IF EXISTS "pharmacist_view_prescriptions" ON public.prescriptions;'
    )
    op.execute(
        'DROP POLICY IF EXISTS "patient_view_prescriptions" ON public.prescriptions;'
    )
    op.execute(
        'DROP POLICY IF EXISTS "doctor_view_prescriptions" ON public.prescriptions;'
    )
    op.execute(
        'DROP POLICY IF EXISTS "admin_all_prescriptions" ON public.prescriptions;'
    )

    # 2. Drop fixed helpers
    op.execute("DROP FUNCTION IF EXISTS public.current_user_has_role(text);")
    op.execute("DROP FUNCTION IF EXISTS public.current_app_user_id();")

    # 3. Restore ORIGINAL (broken) helper
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.current_user_has_role(role_name text)
    RETURNS boolean LANGUAGE sql SECURITY DEFINER SET search_path = public STABLE AS $$
      SELECT EXISTS (
        SELECT 1 FROM public.user_roles ur JOIN public.roles r ON ur.role_id = r.id
        WHERE ur.user_id = auth.uid() AND r.name = role_name
      );
    $$;
    """
    )

    # 4. Restore ORIGINAL (broken) policies (from 5446873836d4)
    op.execute(
        "CREATE POLICY \"admin_all_prescriptions\" ON public.prescriptions FOR ALL TO authenticated USING (public.current_user_has_role('admin')) WITH CHECK (public.current_user_has_role('admin'));"
    )
    op.execute(
        "CREATE POLICY \"doctor_view_prescriptions\" ON public.prescriptions FOR SELECT TO authenticated USING (public.current_user_has_role('doctor') AND doctor_id IN (SELECT id FROM public.doctors WHERE user_id = auth.uid()));"
    )
    op.execute(
        "CREATE POLICY \"patient_view_prescriptions\" ON public.prescriptions FOR SELECT TO authenticated USING (public.current_user_has_role('patient') AND patient_id IN (SELECT id FROM public.patients WHERE user_id = auth.uid()));"
    )
    op.execute(
        "CREATE POLICY \"pharmacist_view_prescriptions\" ON public.prescriptions FOR SELECT TO authenticated USING (public.current_user_has_role('pharmacist') AND status::text NOT IN ('draft', 'cancelled'));"
    )

    op.execute(
        "CREATE POLICY \"admin_all_patients\" ON public.patients FOR ALL TO authenticated USING (public.current_user_has_role('admin')) WITH CHECK (public.current_user_has_role('admin'));"
    )
    op.execute(
        "CREATE POLICY \"doctor_view_patients\" ON public.patients FOR SELECT TO authenticated USING (public.current_user_has_role('doctor'));"
    )
    op.execute(
        "CREATE POLICY \"patient_view_self\" ON public.patients FOR SELECT TO authenticated USING (public.current_user_has_role('patient') AND user_id = auth.uid());"
    )
    op.execute(
        "CREATE POLICY \"pharmacist_view_patients\" ON public.patients FOR SELECT TO authenticated USING (public.current_user_has_role('pharmacist'));"
    )

    op.execute(
        "CREATE POLICY \"admin_all_storage\" ON public.storage_files FOR ALL TO authenticated USING (public.current_user_has_role('admin')) WITH CHECK (public.current_user_has_role('admin'));"
    )
    op.execute(
        "CREATE POLICY \"doctor_pharmacist_view_storage\" ON public.storage_files FOR SELECT TO authenticated USING (public.current_user_has_role('doctor') OR public.current_user_has_role('pharmacist'));"
    )
    op.execute(
        "CREATE POLICY \"patient_view_storage\" ON public.storage_files FOR SELECT TO authenticated USING (public.current_user_has_role('patient') AND (uploaded_by = auth.uid() OR prescription_id IN (SELECT id FROM public.prescriptions WHERE patient_id IN (SELECT id FROM public.patients WHERE user_id = auth.uid()))));"
    )
