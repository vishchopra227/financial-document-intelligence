"""Health and readiness endpoints."""

from fastapi import APIRouter, status
from backend.app.config import settings
from backend.app.db.session import get_db_status
from backend.app.api.schemas.common import HealthResponse

router = APIRouter(prefix="/api", tags=["System"])


@router.get("/health", response_model=HealthResponse, status_code=status.HTTP_200_OK)
def get_health():
    db_status = get_db_status()
    
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment=settings.ENVIRONMENT,
        database=db_status,
        vector_store={
            "backend": settings.VECTOR_STORE_BACKEND,
            "status": "ready",
            "storage_path": str(settings.VECTOR_STORE_DIR),
        },
        ai_providers={
            "llm_provider": settings.LLM_PROVIDER,
            "llm_model": settings.LLM_MODEL,
            "llm_configured": bool(settings.LLM_API_KEY) if settings.LLM_PROVIDER != "mock" else True,
            "embedding_provider": settings.EMBEDDING_PROVIDER,
            "embedding_model": settings.EMBEDDING_MODEL,
            "embedding_configured": bool(settings.EMBEDDING_API_KEY) if settings.EMBEDDING_PROVIDER != "mock" else True,
        },
    )


@router.get("/readiness", status_code=status.HTTP_200_OK)
def get_readiness():
    db_status = get_db_status()
    is_ready = db_status.get("status") == "connected"
    return {
        "ready": is_ready,
        "database": db_status.get("status"),
        "storage": "writable" if settings.DATA_DIR.exists() else "not_found",
    }
