"""SQLAlchemy ORM models for FinSight Intelligence."""

import uuid
from datetime import datetime
from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    DateTime,
    Text,
    JSON,
    ForeignKey,
    Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def generate_uuid() -> str:
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(64), default="default", index=True, nullable=False)
    original_filename = Column(String(255), nullable=False)
    storage_path = Column(String(512), nullable=False)
    file_type = Column(String(32), nullable=False)  # pdf, txt, docx
    file_size_bytes = Column(Integer, nullable=False)
    page_count = Column(Integer, default=0)
    chunk_count = Column(Integer, default=0)
    
    # Status: pending, processing, indexed, failed
    status = Column(String(32), default="pending", index=True, nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Financial metadata summary if extracted
    document_summary = Column(Text, nullable=True)
    reporting_period = Column(String(64), nullable=True)
    company_name = Column(String(128), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    jobs = relationship("DocumentProcessingJob", back_populates="document", cascade="all, delete-orphan")
    metrics = relationship("ExtractedMetric", back_populates="document", cascade="all, delete-orphan")


class DocumentProcessingJob(Base):
    __tablename__ = "document_processing_jobs"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Status: pending, extracting, chunking, embedding, indexed, failed
    stage = Column(String(32), default="pending", nullable=False)
    status = Column(String(32), default="pending", nullable=False)
    progress_percent = Column(Integer, default=0)
    error_message = Column(Text, nullable=True)
    
    started_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)

    # Relationship
    document = relationship("Document", back_populates="jobs")


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    workspace_id = Column(String(64), default="default", index=True, nullable=False)
    title = Column(String(255), default="New Analysis", nullable=False)
    # Target document IDs associated with this conversation (JSON list)
    document_ids = Column(JSON, default=list, nullable=False)
    
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    conversation_id = Column(String(36), ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    role = Column(String(32), nullable=False)  # user, assistant, system
    content = Column(Text, nullable=False)
    
    # Evidence & Citations
    # citations: list of dicts: [{ "chunk_id": str, "document_id": str, "filename": str, "page_number": int, "excerpt": str }]
    citations = Column(JSON, default=list, nullable=False)
    retrieved_chunks = Column(JSON, default=list, nullable=False)
    
    # Observability
    retrieval_latency_ms = Column(Float, nullable=True)
    generation_latency_ms = Column(Float, nullable=True)
    model_name = Column(String(64), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    conversation = relationship("Conversation", back_populates="messages")


class ExtractedMetric(Base):
    __tablename__ = "extracted_metrics"

    id = Column(String(36), primary_key=True, default=generate_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    
    metric_name = Column(String(128), nullable=False, index=True)  # Revenue, Net Income, Operating Margin, EPS, etc.
    raw_value = Column(String(128), nullable=False)  # e.g., "$51.7B", "14.2%"
    numeric_value = Column(Float, nullable=True)     # Normalized float
    unit = Column(String(32), nullable=True)         # billions, millions, percent, ratio
    currency = Column(String(16), nullable=True)     # USD, EUR, GBP, etc.
    reporting_period = Column(String(64), nullable=True)  # FY2023, Q3 2024
    
    page_number = Column(Integer, nullable=True)
    source_excerpt = Column(Text, nullable=True)
    confidence = Column(Float, default=1.0)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Relationship
    document = relationship("Document", back_populates="metrics")
