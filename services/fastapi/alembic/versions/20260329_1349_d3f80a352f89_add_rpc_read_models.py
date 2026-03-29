"""add_rpc_read_models

Implements four SECURITY INVOKER read-model RPCs for client-side consumption.
All functions respect the RLS policies established in previous migrations.

Design principles:
- SECURITY INVOKER: runs with caller's permissions → RLS enforced automatically
- SELECT only: no mutations, no business logic
- Stable (no side effects): safe for caching and repeated reads
- prescription_items accessed only via parent prescription (controlled via RLS on prescriptions)

Functions:
  1. get_prescription_detail(uuid)  → full prescription view with items as JSONB
  2. get_my_prescriptions(...)      → paginated list for the calling patient
  3. get_pharmacist_queue(...)      → validated prescriptions ready to dispense
  4. get_patient_files(...)         → storage files owned by the calling patient

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
    # 1. get_prescription_detail
    #
    # Returns a single prescription with full joins:
    # doctor summary, patient summary, and items as JSONB array.
    # prescription_items is not directly accessible by clients (no RLS),
    # but safe here because access is gated by the parent prescriptions RLS.
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
    LANGUAGE sql
    SECURITY INVOKER
    STABLE
    SET search_path = public
    AS $$
      SELECT
        p.id                           AS prescription_id,
        p.status::text,
        p.notes,
        p.interaction_check_result::jsonb,
        p.stock_check_result::jsonb,
        p.doctor_id,
        doc_profile.full_name          AS doctor_name,
        doc.sip_number                 AS doctor_sip,
        doc.specialization             AS doctor_specialization,
        p.patient_id,
        pat_profile.full_name          AS patient_name,
        pat.blood_type                 AS patient_blood_type,
        pat.allergies                  AS patient_allergies,
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
        )                              AS items,
        p.created_at,
        p.updated_at
      FROM public.prescriptions p
      JOIN public.doctors doc
        ON p.doctor_id = doc.id
      JOIN public.users doc_user
        ON doc.user_id = doc_user.id
      JOIN public.profiles doc_profile
        ON doc_user.id = doc_profile.user_id
      JOIN public.patients pat
        ON p.patient_id = pat.id
      JOIN public.users pat_user
        ON pat.user_id = pat_user.id
      JOIN public.profiles pat_profile
        ON pat_user.id = pat_profile.user_id
      LEFT JOIN public.prescription_items pi
        ON pi.prescription_id = p.id
      LEFT JOIN public.drugs dr
        ON pi.drug_id = dr.id
      WHERE p.id = p_prescription_id
        AND p.deleted_at IS NULL
      GROUP BY
        p.id, p.status, p.notes,
        p.interaction_check_result::text, p.stock_check_result::text,
        p.doctor_id, doc_profile.full_name, doc.sip_number, doc.specialization,
        p.patient_id, pat_profile.full_name, pat.blood_type, pat.allergies,
        p.created_at, p.updated_at;
    $$;
    """
    )

    # ----------------------------------------------------------------
    # 2. get_my_prescriptions
    #
    # Returns a paginated list of prescriptions for the calling user.
    # RLS on prescriptions filters to only the caller's own records,
    # so no explicit patient filter is needed here.
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
    LANGUAGE sql
    SECURITY INVOKER
    STABLE
    SET search_path = public
    AS $$
      SELECT
        p.id                  AS prescription_id,
        p.status::text,
        doc_profile.full_name AS doctor_name,
        p.notes,
        COUNT(pi.id)          AS item_count,
        p.created_at,
        p.updated_at
      FROM public.prescriptions p
      JOIN public.doctors doc
        ON p.doctor_id = doc.id
      JOIN public.users doc_user
        ON doc.user_id = doc_user.id
      JOIN public.profiles doc_profile
        ON doc_user.id = doc_profile.user_id
      LEFT JOIN public.prescription_items pi
        ON pi.prescription_id = p.id
      WHERE p.deleted_at IS NULL
        AND (p_status IS NULL OR p.status::text = p_status)
      GROUP BY
        p.id, p.status, doc_profile.full_name, p.notes, p.created_at, p.updated_at
      ORDER BY p.created_at DESC
      LIMIT  p_limit
      OFFSET p_offset;
    $$;
    """
    )

    # ----------------------------------------------------------------
    # 3. get_pharmacist_queue
    #
    # Returns prescriptions in 'validated' status, ordered oldest first
    # so pharmacists process in FIFO order.
    # RLS on prescriptions allows pharmacist role to see validated records.
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
    LANGUAGE sql
    SECURITY INVOKER
    STABLE
    SET search_path = public
    AS $$
      SELECT
        p.id                   AS prescription_id,
        p.status::text,
        pat_profile.full_name  AS patient_name,
        doc_profile.full_name  AS doctor_name,
        COUNT(pi.id)           AS item_count,
        p.created_at
      FROM public.prescriptions p
      JOIN public.patients pat
        ON p.patient_id = pat.id
      JOIN public.users pat_user
        ON pat.user_id = pat_user.id
      JOIN public.profiles pat_profile
        ON pat_user.id = pat_profile.user_id
      JOIN public.doctors doc
        ON p.doctor_id = doc.id
      JOIN public.users doc_user
        ON doc.user_id = doc_user.id
      JOIN public.profiles doc_profile
        ON doc_user.id = doc_profile.user_id
      LEFT JOIN public.prescription_items pi
        ON pi.prescription_id = p.id
      WHERE p.deleted_at IS NULL
        AND p.status::text = 'validated'
      GROUP BY
        p.id, p.status, pat_profile.full_name, doc_profile.full_name, p.created_at
      ORDER BY p.created_at ASC
      LIMIT  p_limit
      OFFSET p_offset;
    $$;
    """
    )

    # ----------------------------------------------------------------
    # 4. get_patient_files
    #
    # Returns storage files owned by the calling patient —
    # either directly uploaded by them, or linked to their prescriptions.
    # Uses current_app_user_id() to resolve identity.
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
    LANGUAGE sql
    SECURITY INVOKER
    STABLE
    SET search_path = public
    AS $$
      SELECT
        sf.id               AS file_id,
        sf.file_name,
        sf.file_url,
        sf.file_size,
        sf.mime_type,
        sf.prescription_id,
        sf.created_at       AS uploaded_at
      FROM public.storage_files sf
      WHERE (
        sf.uploaded_by = public.current_app_user_id()
        OR sf.prescription_id IN (
          SELECT id FROM public.prescriptions
          WHERE deleted_at IS NULL
            AND patient_id IN (
              SELECT id FROM public.patients
              WHERE user_id = public.current_app_user_id()
                AND deleted_at IS NULL
            )
        )
      )
      ORDER BY sf.created_at DESC
      LIMIT  p_limit
      OFFSET p_offset;
    $$;
    """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.get_patient_files(int, int);")
    op.execute("DROP FUNCTION IF EXISTS public.get_pharmacist_queue(int, int);")
    op.execute("DROP FUNCTION IF EXISTS public.get_my_prescriptions(text, int, int);")
    op.execute("DROP FUNCTION IF EXISTS public.get_prescription_detail(uuid);")
