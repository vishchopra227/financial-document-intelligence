"""Pydantic schemas for Financial Metrics."""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class MetricResponse(BaseModel):
    id: str
    document_id: str
    metric_name: str
    raw_value: str
    numeric_value: Optional[float] = None
    unit: Optional[str] = None
    currency: Optional[str] = None
    reporting_period: Optional[str] = None
    page_number: Optional[int] = None
    source_excerpt: Optional[str] = None
    confidence: float = 1.0
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentMetricsResponse(BaseModel):
    document_id: str
    document_name: str
    metrics: List[MetricResponse]
