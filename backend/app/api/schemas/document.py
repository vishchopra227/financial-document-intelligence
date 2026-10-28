"""Pydantic schemas for Document operations."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class DocumentBase(BaseModel):
    original_filename: str
    file_type: str
    file_size_bytes: int
    workspace_id: str = "default"


class DocumentResponse(DocumentBase):
    id: str
    page_count: int = 0
    chunk_count: int = 0
    status: str
    error_message: Optional[str] = None
    document_summary: Optional[str] = None
    reporting_period: Optional[str] = None
    company_name: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentListResponse(BaseModel):
    documents: List[DocumentResponse]
    total_count: int
    indexed_count: int


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    stage: str
    progress_percent: int
    error_message: Optional[str] = None
