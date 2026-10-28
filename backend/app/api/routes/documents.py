"""Document Management API endpoints."""

from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.ingestion.service import DocumentIngestionService
from backend.app.api.schemas.document import (
    DocumentResponse,
    DocumentListResponse,
    DocumentStatusResponse,
)

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(..., description="Document file (PDF, TXT, DOCX)"),
    workspace_id: str = Form("default", description="Workspace ID"),
    db: Session = Depends(get_db),
):
    """Upload and parse a financial document."""
    service = DocumentIngestionService(db)
    
    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty.",
        )

    doc = service.ingest_document(
        file_bytes=file_bytes,
        original_filename=file.filename or "unknown_document",
        workspace_id=workspace_id,
    )
    return doc


@router.get("", response_model=DocumentListResponse)
def list_documents(
    workspace_id: str = Query("default"),
    status: Optional[str] = Query(None, description="Filter by status: pending, extracted, indexed, failed"),
    search: Optional[str] = Query(None, description="Search by filename"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """List documents in workspace with optional search and filters."""
    service = DocumentIngestionService(db)
    documents, total_count, indexed_count = service.list_documents(
        workspace_id=workspace_id,
        status_filter=status,
        search_query=search,
        skip=skip,
        limit=limit,
    )
    return DocumentListResponse(
        documents=documents,
        total_count=total_count,
        indexed_count=indexed_count,
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Get metadata for a specific document."""
    service = DocumentIngestionService(db)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return doc


@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
def get_document_status(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Get processing status and pipeline stage for a document."""
    service = DocumentIngestionService(db)
    doc = service.get_document(document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )

    # Get latest job if available
    latest_job = doc.jobs[-1] if doc.jobs else None
    stage = latest_job.stage if latest_job else doc.status
    progress = latest_job.progress_percent if latest_job else (100 if doc.status in ("indexed", "extracted") else 0)

    return DocumentStatusResponse(
        id=doc.id,
        status=doc.status,
        stage=stage,
        progress_percent=progress,
        error_message=doc.error_message,
    )


@router.get("/{document_id}/preview")
def get_document_preview(
    document_id: str,
    page: Optional[int] = Query(None, ge=1, description="Specific page number (1-indexed)"),
    db: Session = Depends(get_db),
):
    """Retrieve extracted text preview for a document."""
    service = DocumentIngestionService(db)
    return service.get_document_preview(document_id=document_id, page_number=page)


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
def delete_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Delete a document, its disk files, and its metadata."""
    service = DocumentIngestionService(db)
    success = service.delete_document(document_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID '{document_id}' not found.",
        )
    return {
        "success": True,
        "message": f"Document '{document_id}' and all associated assets deleted successfully.",
    }
