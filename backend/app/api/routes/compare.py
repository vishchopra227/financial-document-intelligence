"""Multi-Document Comparison API routes and export endpoints."""

import csv
import io
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.rag.comparison_service import (
    MultiDocumentComparisonService,
    ComparisonResult,
)
from backend.app.services.metrics.extractor import FinancialMetricsExtractor
from backend.app.services.export import safe_csv_value
from backend.app.db.models import Document

router = APIRouter(prefix="/api/compare", tags=["Cross-Document Analysis"])


class ComparisonRequest(BaseModel):
    document_ids: List[str] = Field(..., min_length=2, description="At least two document IDs to compare")
    query: str = Field(..., min_length=3, description="Comparative question or topic")
    top_k_per_doc: Optional[int] = Field(default=3, ge=1, le=10)


@router.post("", response_model=ComparisonResult)
def compare_documents(
    request: ComparisonRequest,
    db: Session = Depends(get_db),
):
    """Compare multiple corporate financial reports side-by-side."""
    service = MultiDocumentComparisonService(db)
    return service.compare_documents(
        document_ids=request.document_ids,
        query=request.query,
        top_k_per_doc=request.top_k_per_doc or 3,
    )


@router.get("/metrics")
def compare_metrics_table(
    document_ids: str = Query(..., description="Comma-separated document IDs"),
    db: Session = Depends(get_db),
):
    """Fetch side-by-side financial metrics comparison table across documents."""
    doc_id_list = [d.strip() for d in document_ids.split(",") if d.strip()]
    if len(doc_id_list) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least two document IDs must be specified.",
        )
    if len(set(doc_id_list)) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="At least two distinct document IDs must be specified.",
        )
    found_ids = {
        doc_id for (doc_id,) in db.query(Document.id).filter(Document.id.in_(doc_id_list)).all()
    }
    if found_ids != set(doc_id_list):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="One or more documents were not found.",
        )
    extractor = FinancialMetricsExtractor(db)
    return extractor.compare_metrics(doc_id_list)


@router.post("/export")
def export_comparison_report(
    request: ComparisonRequest,
    format: str = Query("json", pattern="^(json|csv)$"),
    db: Session = Depends(get_db),
):
    """Export multi-document comparative analysis as downloadable CSV or JSON."""
    service = MultiDocumentComparisonService(db)
    extractor = FinancialMetricsExtractor(db)

    result = service.compare_documents(
        document_ids=request.document_ids,
        query=request.query,
        top_k_per_doc=request.top_k_per_doc or 3,
    )
    metrics_comp = extractor.compare_metrics(request.document_ids)

    if format == "json":
        report_data = {
            "title": "FinSight Intelligence - Cross-Document Financial Analysis Report",
            "query": result.query,
            "synthesis_analysis": result.analysis,
            "compared_documents": [d.model_dump() for d in result.documents],
            "metrics_comparison_table": metrics_comp["metrics_table"],
            "citations": [c.model_dump() for c in result.citations],
            "has_sufficient_evidence": result.has_sufficient_evidence,
            "model_used": result.model_name,
            "retrieval_latency_ms": result.retrieval_latency_ms,
            "generation_latency_ms": result.generation_latency_ms,
        }
        content = json.dumps(report_data, indent=2, ensure_ascii=False)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=finsight_comparison_report.json"},
        )

    # CSV Export
    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(["FINSIGHT INTELLIGENCE - MULTI-DOCUMENT FINANCIAL COMPARISON REPORT"])
    writer.writerow([safe_csv_value(value) for value in ["Query", result.query]])
    writer.writerow([safe_csv_value(value) for value in ["Model", result.model_name]])
    writer.writerow([])

    # Metrics Table Header
    doc_ids = [d.document_id for d in result.documents]
    doc_names = [d.filename for d in result.documents]
    headers = ["Metric Name", "Reporting Period"]
    for name in doc_names:
        headers.extend([
            f"{name} (Value)", f"{name} (Numeric Value)", f"{name} (Currency)", f"{name} (Unit)",
            f"{name} (Page)", f"{name} (Source Evidence)",
        ])
    writer.writerow([safe_csv_value(value) for value in headers])

    for row in metrics_comp["metrics_table"]:
        values = [row["metric_name"], row.get("reporting_period") or ""]
        for doc_id in doc_ids:
            metric = row["values"].get(doc_id, {})
            values.extend([
                metric.get("raw_value", "N/A"), metric.get("numeric_value"),
                metric.get("currency") or "",
                metric.get("unit") or "", metric.get("page_number") or "",
                json.dumps(metric.get("evidence", []), ensure_ascii=False),
            ])
        writer.writerow([safe_csv_value(value) for value in values])

    writer.writerow([])
    writer.writerow(["COMPARATIVE SYNTHESIS"])
    writer.writerow([safe_csv_value(result.analysis.replace("\n", " "))])

    writer.writerow([])
    writer.writerow(["CITATIONS"])
    writer.writerow(["Document ID", "Document", "Page", "Similarity Score", "Excerpt"])
    for c in result.citations:
        writer.writerow([safe_csv_value(value) for value in [
            c.document_id, c.filename, c.page_number, c.similarity_score,
            c.excerpt.replace("\n", " "),
        ]])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=finsight_comparison_report.csv"},
    )
