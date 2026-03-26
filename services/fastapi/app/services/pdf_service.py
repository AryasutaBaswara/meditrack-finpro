from __future__ import annotations

import asyncio
from io import BytesIO
from typing import Any
from uuid import UUID

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import PrescriptionNotFoundException
from app.db.models.doctor import Doctor
from app.db.models.patient import Patient
from app.db.models.prescription import Prescription, PrescriptionItem
from app.db.models.user import Profile, User


class PDFService:
    async def generate_prescription_pdf(
        self, prescription_id: UUID, db: AsyncSession
    ) -> bytes:
        prescription = await self._get_prescription(prescription_id, db)
        return await asyncio.to_thread(self._build_pdf, prescription)

    async def _get_prescription(
        self, prescription_id: UUID, db: AsyncSession
    ) -> Prescription:
        result = await db.execute(
            select(Prescription)
            .options(
                selectinload(Prescription.doctor)
                .selectinload(Doctor.user)
                .selectinload(User.profile),
                selectinload(Prescription.patient)
                .selectinload(Patient.user)
                .selectinload(User.profile),
                selectinload(Prescription.items).selectinload(PrescriptionItem.drug),
            )
            .where(
                Prescription.id == prescription_id,
                Prescription.deleted_at.is_(None),
            )
        )
        prescription = result.scalar_one_or_none()
        if prescription is None:
            raise PrescriptionNotFoundException(prescription_id)
        return prescription

    def _build_pdf(self, prescription: Prescription) -> bytes:
        buffer = BytesIO()
        document = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=18 * mm,
            leftMargin=18 * mm,
            topMargin=18 * mm,
            bottomMargin=18 * mm,
        )

        styles = getSampleStyleSheet()
        styles.add(
            ParagraphStyle(
                name="MetaLabel",
                parent=styles["BodyText"],
                fontName="Helvetica-Bold",
                spaceAfter=2,
            )
        )

        doctor_profile = self._get_profile(
            prescription.doctor.user if prescription.doctor else None
        )
        patient_profile = self._get_profile(
            prescription.patient.user if prescription.patient else None
        )

        elements = [
            Paragraph("MediTrack Prescription", styles["Title"]),
            Paragraph(f"Prescription ID: {prescription.id}", styles["Heading3"]),
            Spacer(1, 8),
            Paragraph("Patient Information", styles["Heading2"]),
            Paragraph(
                f"<b>Name:</b> {self._display_name(patient_profile, prescription.patient.user if prescription.patient else None)}",
                styles["BodyText"],
            ),
            Paragraph(
                f"<b>Date of Birth:</b> {self._format_date(getattr(patient_profile, 'date_of_birth', None))}",
                styles["BodyText"],
            ),
            Paragraph(
                f"<b>Blood Type:</b> {prescription.patient.blood_type if prescription.patient and prescription.patient.blood_type else '-'}",
                styles["BodyText"],
            ),
            Spacer(1, 8),
            Paragraph("Doctor Information", styles["Heading2"]),
            Paragraph(
                f"<b>Name:</b> {self._display_name(doctor_profile, prescription.doctor.user if prescription.doctor else None)}",
                styles["BodyText"],
            ),
            Paragraph(
                f"<b>SIP Number:</b> {prescription.doctor.sip_number if prescription.doctor else '-'}",
                styles["BodyText"],
            ),
            Paragraph(
                f"<b>Specialization:</b> {prescription.doctor.specialization if prescription.doctor and prescription.doctor.specialization else '-'}",
                styles["BodyText"],
            ),
            Spacer(1, 10),
            Paragraph("Prescribed Drugs", styles["Heading2"]),
            self._build_drug_table(prescription.items),
            Spacer(1, 10),
            Paragraph("Interaction Check", styles["Heading2"]),
            Paragraph(
                self._format_interaction_result(prescription.interaction_check_result),
                styles["BodyText"],
            ),
            Spacer(1, 16),
            Paragraph(
                f"Generated on {self._format_date(prescription.created_at)}",
                styles["BodyText"],
            ),
            Spacer(1, 12),
            Paragraph(
                "Pharmacist Signature: __________________________", styles["BodyText"]
            ),
        ]

        document.build(elements)
        return buffer.getvalue()

    def _build_drug_table(self, items: list[PrescriptionItem]) -> Table:
        rows: list[list[str]] = [
            ["Drug", "Dosage", "Frequency", "Duration", "Quantity"]
        ]
        for item in items:
            drug_name = item.drug.name if item.drug else "-"
            rows.append(
                [
                    drug_name,
                    item.dosage,
                    item.frequency,
                    item.duration,
                    str(item.quantity),
                ]
            )

        table = Table(
            rows, repeatRows=1, colWidths=[55 * mm, 28 * mm, 30 * mm, 30 * mm, 20 * mm]
        )
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#E5EEF8")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1F2937")),
                    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#CBD5E1")),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    (
                        "ROWBACKGROUNDS",
                        (0, 1),
                        (-1, -1),
                        [colors.white, colors.HexColor("#F8FAFC")],
                    ),
                    ("PADDING", (0, 0), (-1, -1), 6),
                ]
            )
        )
        return table

    def _format_interaction_result(self, result: dict[str, Any] | None) -> str:
        if not result:
            return "No interaction analysis recorded."

        severity = result.get("severity") or "unknown"
        details = result.get("details") or "No details provided."
        has_interactions = result.get("has_interactions")
        return (
            f"<b>Has Interactions:</b> {has_interactions}<br/>"
            f"<b>Severity:</b> {severity}<br/>"
            f"<b>Details:</b> {details}"
        )

    def _display_name(self, profile: Profile | None, user: User | None) -> str:
        if profile is not None:
            return profile.full_name
        if user is not None:
            return user.email
        return "-"

    def _get_profile(self, user: User | None) -> Profile | None:
        return user.profile if user is not None else None

    def _format_date(self, value: object) -> str:
        if value is None:
            return "-"
        if hasattr(value, "strftime"):
            return value.strftime("%Y-%m-%d")
        return str(value)
