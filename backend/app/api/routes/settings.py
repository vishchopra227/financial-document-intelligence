"""Settings inspection endpoint (safe, non-secret)."""

from fastapi import APIRouter
from backend.app.config import settings

router = APIRouter(prefix="/api/settings", tags=["Settings"])




@router.get("")
def get_system_settings():
    """Return active system configuration without exposing secrets."""
    return {
        "project_name": settings.PROJECT_NAME,
        "environment": settings.ENVIRONMENT,
        "max_upload_size_mb": settings.MAX_UPLOAD_SIZE_MB,
        "vector_store_backend": settings.VECTOR_STORE_BACKEND,
        "rag": {
            "top_k": settings.RAG_TOP_K,
            "chunk_size": settings.RAG_CHUNK_SIZE,
            "chunk_overlap": settings.RAG_CHUNK_OVERLAP,
            "similarity_threshold": settings.RAG_SIMILARITY_THRESHOLD,
            "hybrid_search": settings.RAG_ENABLE_HYBRID_SEARCH,
        },
        "providers": {
            "llm": {
                "name": settings.LLM_PROVIDER,
                "model": settings.LLM_MODEL,
                "has_api_key": bool(settings.LLM_API_KEY) or settings.LLM_PROVIDER == "mock",
            },
            "embedding": {
                "name": settings.EMBEDDING_PROVIDER,
                "model": settings.EMBEDDING_MODEL,
                "has_api_key": bool(settings.EMBEDDING_API_KEY) or settings.EMBEDDING_PROVIDER == "mock",
            },
        },
        "security_note": "API keys and database passwords are configured securely through server environment variables and never exposed to the frontend.",
    }
