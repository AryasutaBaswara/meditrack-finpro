from __future__ import annotations

from io import BytesIO
from uuid import UUID

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import (
    TokenData,
    get_current_active_user,
    get_db,
    get_pdf_service,
    get_prescription_service,
)
from app.services.pdf_service import PDFService
from app.services.prescription_service import PrescriptionService

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/prescription/{prescription_id}")
async def download_prescription_report(
    prescription_id: UUID,
    current_user: TokenData = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    prescription_service: PrescriptionService = Depends(get_prescription_service),
    pdf_service: PDFService = Depends(get_pdf_service),
) -> StreamingResponse:
    await prescription_service.get_by_id(prescription_id, current_user)
    pdf_bytes = await pdf_service.generate_prescription_pdf(prescription_id, db)
    filename = f"prescription-{prescription_id}.pdf"
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
