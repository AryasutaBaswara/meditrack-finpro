"""fix_rls_identity_mapping_and_soft_delete

Fixes two issues in the original RLS foundation migration:

1. Identity mapping gap:
   The previous migration used auth.uid() directly against user_id columns,
   but this app authenticates via Keycloak — not Supabase Auth. The UUID from
   auth.uid() has no relation to users.id in our schema. The fix maps the
   Keycloak JWT `sub` claim (stored in users.keycloak_sub) to the internal
   user UUID via a helper function, making auth.jwt() ->> 'sub' the bridge.

2. Missing soft-delete filter:
   RLS SELECT policies did not filter deleted_at IS NULL, allowing direct
   Supabase reads to return soft-deleted rows. Fixed by adding the filter
   to all relevant policies and helper functions.

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
    # ----------------------------------------------------------------
    # Step 1: Drop all existing policies from the original migration
    # ----------------------------------------------------------------
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

    # ----------------------------------------------------------------
    # Step 2: Drop old helper functions
    # ----------------------------------------------------------------
    op.execute("DROP FUNCTION IF EXISTS public.current_user_has_role(text);")

    # ----------------------------------------------------------------
    # Step 3: Add current_app_user_id() — resolves JWT sub → users.id
    #
    # This is the bridge between Keycloak JWT (which is the auth source)
    # and the internal users.id UUID used in our schema.
    # auth.jwt() ->> 'sub' returns the Keycloak subject (keycloak_sub).
    # ----------------------------------------------------------------
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.current_app_user_id()
    RETURNS uuid
    LANGUAGE sql
    SECURITY DEFINER
    SET search_path = public
    STABLE
    AS $$
      SELECT id
      FROM public.users
      WHERE keycloak_sub = (auth.jwt() ->> 'sub')
        AND deleted_at IS NULL
      LIMIT 1;
    $$;
    """
    )

    # ----------------------------------------------------------------
    # Step 4: Add current_user_has_role() — uses keycloak_sub bridge
    # ----------------------------------------------------------------
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
        WHERE ur.user_id = public.current_app_user_id()
          AND r.name = role_name
      );
    $$;
    """
    )

    # ----------------------------------------------------------------
    # Step 5: Recreate policies — prescriptions
    # ----------------------------------------------------------------
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
          deleted_at IS NULL AND
          doctor_id IN (
            SELECT id FROM public.doctors
            WHERE user_id = public.current_app_user_id()
              AND deleted_at IS NULL
          )
        );
    """
    )

    op.execute(
        """
    CREATE POLICY "patient_view_prescriptions" ON public.prescriptions
        FOR SELECT TO authenticated
        USING (
          public.current_user_has_role('patient') AND
          deleted_at IS NULL AND
          patient_id IN (
            SELECT id FROM public.patients
            WHERE user_id = public.current_app_user_id()
              AND deleted_at IS NULL
          )
        );
    """
    )

    op.execute(
        """
    CREATE POLICY "pharmacist_view_prescriptions" ON public.prescriptions
        FOR SELECT TO authenticated
        USING (
          public.current_user_has_role('pharmacist') AND
          deleted_at IS NULL AND
          status::text NOT IN ('draft', 'cancelled')
        );
    """
    )

    # ----------------------------------------------------------------
    # Step 6: Recreate policies — patients
    # ----------------------------------------------------------------
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
        USING (
          public.current_user_has_role('doctor') AND
          deleted_at IS NULL
        );
    """
    )

    op.execute(
        """
    CREATE POLICY "patient_view_self" ON public.patients
        FOR SELECT TO authenticated
        USING (
          public.current_user_has_role('patient') AND
          deleted_at IS NULL AND
          user_id = public.current_app_user_id()
        );
    """
    )

    op.execute(
        """
    CREATE POLICY "pharmacist_view_patients" ON public.patients
        FOR SELECT TO authenticated
        USING (
          public.current_user_has_role('pharmacist') AND
          deleted_at IS NULL
        );
    """
    )

    # ----------------------------------------------------------------
    # Step 7: Recreate policies — storage_files
    # (storage_files has no deleted_at — no soft delete on this model)
    # ----------------------------------------------------------------
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
            uploaded_by = public.current_app_user_id() OR
            prescription_id IN (
              SELECT id FROM public.prescriptions
              WHERE deleted_at IS NULL AND
              patient_id IN (
                SELECT id FROM public.patients
                WHERE user_id = public.current_app_user_id()
                  AND deleted_at IS NULL
              )
            )
          )
        );
    """
    )


def downgrade() -> None:
    # Drop recreated policies
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

    # Drop fixed helper functions
    op.execute("DROP FUNCTION IF EXISTS public.current_user_has_role(text);")
    op.execute("DROP FUNCTION IF EXISTS public.current_app_user_id();")

    # Restore original (broken) functions — just so chain is reversible
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
