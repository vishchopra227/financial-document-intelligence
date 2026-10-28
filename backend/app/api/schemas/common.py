"""Common API schemas."""

from typing import Generic, TypeVar, Optional, List, Any
from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    success: bool = True
    message: str = "Operation successful"
    data: Optional[T] = None
    error: Optional[str] = None


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    database: dict
    vector_store: dict
    ai_providers: dict
