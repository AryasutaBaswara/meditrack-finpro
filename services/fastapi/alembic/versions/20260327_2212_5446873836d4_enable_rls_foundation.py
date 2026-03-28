"""enable_rls_foundation

Revision ID: 5446873836d4
Revises: 4b4d2d7f0f5c
Create Date: 2026-03-27 22:12:13.636867
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "5446873836d4"
down_revision: str | None = "4b4d2d7f0f5c"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.current_user_has_role(role_name text)
    RETURNS boolean
    LANGUAGE sql
    SECURITY DEFINER
    SET search_path = public
    STABLE
    AS $$
      SELECT EXISTS (
        SELECT 1 
        FROM public.user_roles ur
        JOIN public.roles r ON ur.role_id = r.id
        WHERE ur.user_id = auth.uid()
          AND r.name = role_name
      );
    $$;
    """
    )

    op.execute("ALTER TABLE public.prescriptions ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.patients ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.storage_files ENABLE ROW LEVEL SECURITY;")

    op.execute(
        """
    CREATE POLICY "admin_all_prescriptions" ON public.prescriptions
        AS PERMISSIVE FOR ALL TO authenticated
        USING (public.current_user_has_role('admin'))
        WITH CHECK (public.current_user_has_role('admin'));
    """
    )

    op.execute(
        """
    CREATE POLICY "doctor_view_prescriptions" ON public.prescriptions
        FOR SELECT TO authenticated
        USING (
          public.current_user_has_role('doctor') AND 
          doctor_id IN (SELECT id FROM public.doctors WHERE user_id = auth.uid())
        );
    """
    )

    op.execute(
        """
    CREATE POLICY "patient_view_prescriptions" ON public.prescriptions
        FOR SELECT TO authenticated
        USING (
          public.current_user_has_role('patient') AND 
          patient_id IN (SELECT id FROM public.patients WHERE user_id = auth.uid())
        );
    """
    )

    op.execute(
        """
    CREATE POLICY "pharmacist_view_prescriptions" ON public.prescriptions
        FOR SELECT TO authenticated
        USING (
          public.current_user_has_role('pharmacist') AND 
          status::text NOT IN ('draft', 'cancelled')
        );
    """
    )

    op.execute(
        """
    CREATE POLICY "admin_all_patients" ON public.patients
        AS PERMISSIVE FOR ALL TO authenticated
        USING (public.current_user_has_role('admin'))
        WITH CHECK (public.current_user_has_role('admin'));
    """
    )

    op.execute(
        """
    CREATE POLICY "doctor_view_patients" ON public.patients
        FOR SELECT TO authenticated
        USING (public.current_user_has_role('doctor'));
    """
    )

    op.execute(
        """
    CREATE POLICY "patient_view_self" ON public.patients
        FOR SELECT TO authenticated
        USING (
          public.current_user_has_role('patient') AND 
          user_id = auth.uid()
        );
    """
    )

    op.execute(
        """
    CREATE POLICY "pharmacist_view_patients" ON public.patients
        FOR SELECT TO authenticated
        USING (public.current_user_has_role('pharmacist'));
    """
    )

    op.execute(
        """
    CREATE POLICY "admin_all_storage" ON public.storage_files
        AS PERMISSIVE FOR ALL TO authenticated
        USING (public.current_user_has_role('admin'))
        WITH CHECK (public.current_user_has_role('admin'));
    """
    )

    op.execute(
        """
    CREATE POLICY "doctor_pharmacist_view_storage" ON public.storage_files
        FOR SELECT TO authenticated
        USING (
          public.current_user_has_role('doctor') OR 
          public.current_user_has_role('pharmacist')
        );
    """
    )

    op.execute(
        """
    CREATE POLICY "patient_view_storage" ON public.storage_files
        FOR SELECT TO authenticated
        USING (
          public.current_user_has_role('patient') AND 
          (
            uploaded_by = auth.uid() OR
            prescription_id IN (
              SELECT id FROM public.prescriptions WHERE patient_id IN (
                SELECT id FROM public.patients WHERE user_id = auth.uid()
              )
            )
          )
        );
    """
    )


def downgrade() -> None:
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
    op.execute("ALTER TABLE public.storage_files DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.patients DISABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE public.prescriptions DISABLE ROW LEVEL SECURITY;")
    op.execute("DROP FUNCTION IF EXISTS public.current_user_has_role(text);")
