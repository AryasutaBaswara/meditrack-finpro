from fastapi import APIRouter

from app.api.v1.routes.doctors import router as doctors_router
from app.api.v1.routes.drugs import router as drugs_router
from app.api.v1.routes.patients import router as patients_router

router = APIRouter()
router.include_router(doctors_router)
router.include_router(drugs_router)
router.include_router(patients_router)
