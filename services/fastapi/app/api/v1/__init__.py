from fastapi import APIRouter

from app.api.v1.routes.drugs import router as drugs_router

router = APIRouter()
router.include_router(drugs_router)
