"""Financial Metrics Extraction & Export API endpoints."""

import csv
import io
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Response, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.db.models import Document
from backend.app.services.metrics.extractor import FinancialMetricsExtractor
from backend.app.services.export import safe_csv_value
from backend.app.api.schemas.metrics import MetricResponse, DocumentMetricsResponse

router = APIRouter(prefix="/api/metrics", tags=["Financial Metrics"])


@router.get("/document/{document_id}", response_model=DocumentMetricsResponse)
def get_document_metrics(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve structured extracted financial metrics for a document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    extractor = FinancialMetricsExtractor(db)
    metrics = extractor.get_document_metrics(document_id)
    return DocumentMetricsResponse(
        document_id=doc.id,
        document_name=doc.original_filename,
        metrics=metrics,
    )


@router.post("/document/{document_id}/extract", response_model=DocumentMetricsResponse)
def trigger_metric_extraction(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Re-run financial metrics extraction on a document."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    extractor = FinancialMetricsExtractor(db)
    metrics = extractor.extract_and_store_metrics(document_id)
    return DocumentMetricsResponse(
        document_id=doc.id,
        document_name=doc.original_filename,
        metrics=metrics,
    )


@router.get("/document/{document_id}/export")
def export_document_metrics(
    document_id: str,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    """Download extracted financial metrics for a document as JSON or CSV."""
    doc = db.query(Document).filter(Document.id == document_id).first()
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

    extractor = FinancialMetricsExtractor(db)
    metrics = extractor.get_document_metrics(document_id)

    if format == "json":
        data = {
            "document_id": doc.id,
            "filename": doc.original_filename,
            "page_count": doc.page_count,
            "metrics": [
                {
                    "metric_name": m.metric_name,
                    "raw_value": m.raw_value,
                    "numeric_value": m.numeric_value,
                    "currency": m.currency,
                    "unit": m.unit,
                    "reporting_period": m.reporting_period,
                    "page_number": m.page_number,
                    "source_excerpt": m.source_excerpt,
                    "confidence": m.confidence,
                }
                for m in metrics
            ],
        }
        return Response(
            content=json.dumps(data, indent=2),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=financial_metrics.json"},
        )

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Metric Name", "Value", "Numeric Value", "Currency", "Unit",
        "Reporting Period", "Page Number", "Source Excerpt",
    ])
    for m in metrics:
        writer.writerow([safe_csv_value(value) for value in [
            m.metric_name,
            m.raw_value,
            m.numeric_value,
            m.currency,
            m.unit,
            m.reporting_period,
            m.page_number,
            (m.source_excerpt or "").replace("\n", " "),
        ]])

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=financial_metrics.csv"},
    )
