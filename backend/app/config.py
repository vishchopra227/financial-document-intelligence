"""Configuration management for FinSight Intelligence backend."""

import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent

# Load .env file from project root if present
load_dotenv(ROOT_DIR / ".env")


def get_bool(key: str, default: bool) -> bool:
    val = os.getenv(key)
    if val is None:
        return default
    return val.strip().lower() in ("true", "1", "yes", "on")


def get_int(key: str, default: int) -> int:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return int(val.strip())
    except ValueError:
        return default


def get_float(key: str, default: float) -> float:
    val = os.getenv(key)
    if val is None:
        return default
    try:
        return float(val.strip())
    except ValueError:
        return default


def get_list(key: str, default: List[str]) -> List[str]:
    val = os.getenv(key)
    if not val:
        return default
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        import json
        try:
            return json.loads(val)
        except Exception:
            pass
    return [item.strip() for item in val.split(",") if item.strip()]


class Settings(BaseModel):
    PROJECT_NAME: str = os.getenv("PROJECT_NAME", "FinSight Intelligence")
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production-32bytes")

    # Server & CORS
    BACKEND_HOST: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    BACKEND_PORT: int = get_int("BACKEND_PORT", 8000)
    FRONTEND_URL: str = os.getenv("FRONTEND_URL", "http://localhost:5173")
    CORS_ORIGINS: List[str] = get_list(
        "CORS_ORIGINS",
        ["http://localhost:5173", "http://127.0.0.1:5173", "http://localhost:3000"],
    )

    # Database
    DATABASE_URL: Optional[str] = os.getenv(
        "DATABASE_URL",
        "mysql+pymysql://root:password@localhost:3306/finsight_intelligence",
    )
    SQLITE_DB_PATH: str = os.getenv("SQLITE_DB_PATH", str(BASE_DIR / "data" / "finsight.db"))

    # Storage Paths
    DATA_DIR: Path = BASE_DIR / "data"
    UPLOAD_DIR: Path = BASE_DIR / "data" / "uploads"
    VECTOR_STORE_DIR: Path = BASE_DIR / "data" / "vector_store"
    MAX_UPLOAD_SIZE_MB: int = get_int("MAX_UPLOAD_SIZE_MB", 30)

    # Vector Store
    VECTOR_STORE_BACKEND: str = os.getenv("VECTOR_STORE_BACKEND", "persistent_numpy")

    # AI Providers
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq" if os.getenv("GROQ_API_KEY") else "mock")
    LLM_MODEL: str = os.getenv("LLM_MODEL", os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY", os.getenv("GROQ_API_KEY"))

    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

    EMBEDDING_PROVIDER: str = os.getenv("EMBEDDING_PROVIDER", "mock")
    EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "default")
    EMBEDDING_API_KEY: Optional[str] = os.getenv("EMBEDDING_API_KEY")

    # RAG Settings
    RAG_TOP_K: int = get_int("RAG_TOP_K", 4)
    RAG_CHUNK_SIZE: int = get_int("RAG_CHUNK_SIZE", 800)
    RAG_CHUNK_OVERLAP: int = get_int("RAG_CHUNK_OVERLAP", 150)
    RAG_SIMILARITY_THRESHOLD: float = get_float("RAG_SIMILARITY_THRESHOLD", 0.35)
    RAG_ENABLE_HYBRID_SEARCH: bool = get_bool("RAG_ENABLE_HYBRID_SEARCH", True)


settings = Settings()

# Ensure directories exist
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.VECTOR_STORE_DIR.mkdir(parents=True, exist_ok=True)
