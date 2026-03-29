"""add_rpc_read_models

Implements four SECURITY DEFINER read-model RPCs.
Using SECURITY DEFINER allows these functions to join 'backend-only' tables 
(users, drug, items) without exposing those tables directly via SELECT grants.
Role and ownership checks are performed explicitly inside each function.

Functions:
  1. get_prescription_detail -> Detail with items (Doctor/Admin/Patient ownership check)
  2. get_my_prescriptions    -> Patient only
  3. get_pharmacist_queue    -> Pharmacist only
  4. get_patient_files       -> Patient ownership check

Revision ID: d3f80a352f89
Revises: 28a6e949ed7b
Create Date: 2026-03-29 13:49:52.464726
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "d3f80a352f89"
down_revision: str | None = "28a6e949ed7b"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    # ----------------------------------------------------------------
    # 1. get_prescription_detail (SECURITY DEFINER)
    # ----------------------------------------------------------------
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.get_prescription_detail(p_prescription_id uuid)
    RETURNS TABLE(
      prescription_id          uuid,
      status                   text,
      notes                    text,
      interaction_check_result jsonb,
      stock_check_result       jsonb,
      doctor_id                uuid,
      doctor_name              text,
      doctor_sip               text,
      doctor_specialization    text,
      patient_id               uuid,
      patient_name             text,
      patient_blood_type       text,
      patient_allergies        text,
      items                    jsonb,
      created_at               timestamptz,
      updated_at               timestamptz
    )
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public
    STABLE
    AS $$
    DECLARE
      v_user_id uuid := public.current_app_user_id();
    BEGIN
      -- Guard: must be authenticated
      IF v_user_id IS NULL THEN
        RAISE EXCEPTION 'Not authenticated' USING ERRCODE = '42501';
      END IF;

      RETURN QUERY
      SELECT
        p.id, p.status::text, p.notes,
        p.interaction_check_result::jsonb, p.stock_check_result::jsonb,
        p.doctor_id, doc_profile.full_name, doc.sip_number, doc.specialization,
        p.patient_id, pat_profile.full_name, pat.blood_type, pat.allergies,
        COALESCE(
          jsonb_agg(
            jsonb_build_object(
              'item_id',   pi.id,
              'drug_id',   pi.drug_id,
              'drug_name', dr.name,
              'drug_unit', dr.unit,
              'dosage',    pi.dosage,
              'frequency', pi.frequency,
              'duration',  pi.duration,
              'quantity',  pi.quantity
            ) ORDER BY dr.name
          ) FILTER (WHERE pi.id IS NOT NULL),
          '[]'::jsonb
        ),
        p.created_at, p.updated_at
      FROM public.prescriptions p
      JOIN public.doctors doc ON p.doctor_id = doc.id
      JOIN public.users doc_user ON doc.user_id = doc_user.id
      JOIN public.profiles doc_profile ON doc_user.id = doc_profile.user_id
      JOIN public.patients pat ON p.patient_id = pat.id
      JOIN public.users pat_user ON pat.user_id = pat_user.id
      JOIN public.profiles pat_profile ON pat_user.id = pat_profile.user_id
      LEFT JOIN public.prescription_items pi ON pi.prescription_id = p.id
      LEFT JOIN public.drugs dr ON pi.drug_id = dr.id
      WHERE p.id = p_prescription_id
        AND p.deleted_at IS NULL
        -- Ownership guard (explicit because SECURITY DEFINER bypasses RLS)
        AND (
          public.current_user_has_role('admin') OR
          public.current_user_has_role('pharmacist') OR
          (public.current_user_has_role('doctor') AND doc.user_id = v_user_id) OR
          (public.current_user_has_role('patient') AND pat.user_id = v_user_id)
        )
      GROUP BY p.id, doc_profile.full_name, doc.sip_number, doc.specialization,
               pat_profile.full_name, pat.blood_type, pat.allergies;
    END;
    $$;
    """
    )

    # ----------------------------------------------------------------
    # 2. get_my_prescriptions (SECURITY DEFINER + Patient Guard)
    # ----------------------------------------------------------------
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.get_my_prescriptions(
      p_status text  DEFAULT NULL,
      p_limit  int   DEFAULT 20,
      p_offset int   DEFAULT 0
    )
    RETURNS TABLE(
      prescription_id uuid,
      status          text,
      doctor_name     text,
      notes           text,
      item_count      bigint,
      created_at      timestamptz,
      updated_at      timestamptz
    )
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public
    STABLE
    AS $$
    DECLARE
      v_user_id uuid := public.current_app_user_id();
    BEGIN
      -- Guard: must be patient
      IF NOT public.current_user_has_role('patient') THEN
        RAISE EXCEPTION 'Only patients can access their prescriptions list via this RPC' USING ERRCODE = '42501';
      END IF;

      RETURN QUERY
      SELECT
        p.id, p.status::text, doc_profile.full_name, p.notes,
        COUNT(pi.id), p.created_at, p.updated_at
      FROM public.prescriptions p
      JOIN public.doctors doc ON p.doctor_id = doc.id
      JOIN public.profiles doc_profile ON doc.user_id = doc_profile.user_id
      JOIN public.patients pat ON p.patient_id = pat.id
      LEFT JOIN public.prescription_items pi ON pi.prescription_id = p.id
      WHERE pat.user_id = v_user_id
        AND p.deleted_at IS NULL
        AND (p_status IS NULL OR p.status::text = p_status)
      GROUP BY p.id, doc_profile.full_name
      ORDER BY p.created_at DESC
      LIMIT p_limit OFFSET p_offset;
    END;
    $$;
    """
    )

    # ----------------------------------------------------------------
    # 3. get_pharmacist_queue (SECURITY DEFINER + Pharmacist Guard)
    # ----------------------------------------------------------------
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.get_pharmacist_queue(
      p_limit  int DEFAULT 50,
      p_offset int DEFAULT 0
    )
    RETURNS TABLE(
      prescription_id uuid,
      status          text,
      patient_name    text,
      doctor_name     text,
      item_count      bigint,
      created_at      timestamptz
    )
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public
    STABLE
    AS $$
    BEGIN
      -- Guard: must be pharmacist or admin
      IF NOT (public.current_user_has_role('pharmacist') OR public.current_user_has_role('admin')) THEN
        RAISE EXCEPTION 'Access denied: pharmacist role required' USING ERRCODE = '42501';
      END IF;

      RETURN QUERY
      SELECT
        p.id, p.status::text, pat_profile.full_name, doc_profile.full_name,
        COUNT(pi.id), p.created_at
      FROM public.prescriptions p
      JOIN public.patients pat ON p.patient_id = pat.id
      JOIN public.profiles pat_profile ON pat.user_id = pat_profile.user_id
      JOIN public.doctors doc ON p.doctor_id = doc.id
      JOIN public.profiles doc_profile ON doc.user_id = doc_profile.user_id
      LEFT JOIN public.prescription_items pi ON pi.prescription_id = p.id
      WHERE p.deleted_at IS NULL
        AND p.status::text IN ('validated', 'dispensing')
      GROUP BY p.id, pat_profile.full_name, doc_profile.full_name
      ORDER BY p.created_at ASC
      LIMIT p_limit OFFSET p_offset;
    END;
    $$;
    """
    )

    # ----------------------------------------------------------------
    # 4. get_patient_files (SECURITY DEFINER + Ownership Guard)
    # ----------------------------------------------------------------
    op.execute(
        """
    CREATE OR REPLACE FUNCTION public.get_patient_files(
      p_limit  int DEFAULT 20,
      p_offset int DEFAULT 0
    )
    RETURNS TABLE(
      file_id         uuid,
      file_name       text,
      file_url        text,
      file_size       int,
      mime_type       text,
      prescription_id uuid,
      uploaded_at     timestamptz
    )
    LANGUAGE plpgsql
    SECURITY DEFINER
    SET search_path = public
    STABLE
    AS $$
    DECLARE
      v_user_id uuid := public.current_app_user_id();
    BEGIN
      RETURN QUERY
      SELECT
        sf.id, sf.file_name, sf.file_url, sf.file_size, sf.mime_type,
        sf.prescription_id, sf.created_at
      FROM public.storage_files sf
      WHERE (
        sf.uploaded_by = v_user_id
        OR sf.prescription_id IN (
          SELECT id FROM public.prescriptions
          WHERE deleted_at IS NULL
            AND patient_id IN (
              SELECT id FROM public.patients
              WHERE user_id = v_user_id AND deleted_at IS NULL
            )
        )
      )
      ORDER BY sf.created_at DESC
      LIMIT p_limit OFFSET p_offset;
    END;
    $$;
    """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.get_patient_files(int, int);")
    op.execute("DROP FUNCTION IF EXISTS public.get_pharmacist_queue(int, int);")
    op.execute("DROP FUNCTION IF EXISTS public.get_my_prescriptions(text, int, int);")
    op.execute("DROP FUNCTION IF EXISTS public.get_prescription_detail(uuid);")
