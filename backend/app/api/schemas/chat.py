"""Pydantic schemas for Chat and RAG operations."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class Citation(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: Optional[int] = None
    excerpt: str
    similarity_score: Optional[float] = None


class ChatRequest(BaseModel):
    query: str = Field(..., min_length=2, max_length=2000, description="Natural language question")
    document_ids: Optional[List[str]] = Field(default=None, description="Optional filter by document IDs")
    conversation_id: Optional[str] = Field(default=None, description="Existing conversation ID")
    workspace_id: str = Field(default="default", description="Workspace ID")
    top_k: Optional[int] = Field(default=4, ge=1, le=20)


class ChatResponse(BaseModel):
    answer: str
    conversation_id: str
    message_id: str
    citations: List[Citation]
    retrieved_chunk_count: int
    has_sufficient_evidence: bool
    retrieval_latency_ms: float
    generation_latency_ms: float
    model_name: str


class ConversationResponse(BaseModel):
    id: str
    title: str
    workspace_id: str
    document_ids: List[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MessageResponse(BaseModel):
    id: str
    conversation_id: str
    role: str
    content: str
    citations: List[Citation]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
