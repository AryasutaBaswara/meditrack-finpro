from fastapi import APIRouter

from app.api.v1.routes.ai import router as ai_router
from app.api.v1.routes.dispensations import router as dispensations_router
from app.api.v1.routes.doctors import router as doctors_router
from app.api.v1.routes.drugs import router as drugs_router
from app.api.v1.routes.patients import router as patients_router
from app.api.v1.routes.prescriptions import router as prescriptions_router
from app.api.v1.routes.reports import router as reports_router
from app.api.v1.routes.storage import router as storage_router

router = APIRouter()
router.include_router(ai_router)
router.include_router(dispensations_router)
router.include_router(doctors_router)
router.include_router(drugs_router)
router.include_router(patients_router)
router.include_router(prescriptions_router)
router.include_router(reports_router)
router.include_router(storage_router)
