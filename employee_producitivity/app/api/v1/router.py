from fastapi import APIRouter

from app.api.v1.ingestion import router as ingestion_router
from app.api.v1.metrics import router as metrics_router
from app.api.v1.scores import router as scores_router
from app.api.v1.alerts import router as alerts_router
from app.api.v1.rules import router as rules_router

api_v1_router = APIRouter()
api_v1_router.include_router(
    ingestion_router, prefix="/ingestion", tags=["Ingestion"]
)
api_v1_router.include_router(
    metrics_router, prefix="/metrics", tags=["Metrics"]
)
api_v1_router.include_router(
    scores_router, prefix="/scores", tags=["Scores"]
)
api_v1_router.include_router(
    alerts_router, prefix="/alerts", tags=["Alerts"]
)
api_v1_router.include_router(
    rules_router, prefix="/rules", tags=["Alert Rules"]
)
