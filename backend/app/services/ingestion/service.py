"""Document Ingestion Service.
Handles file validation, safe storage, text extraction, status tracking, and deletion cleanup.
"""

import os
import json
import uuid
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy.orm import Session
from fastapi import UploadFile, HTTPException, status

from backend.app.config import settings
from backend.app.db.models import Document, DocumentProcessingJob
from backend.app.services.ingestion.parser import extract_document_text, ExtractedDocument
from backend.app.services.ingestion.chunker import FinancialChunker
from backend.app.services.ai.embeddings import get_embedding_provider
from backend.app.services.vector_store.persistent_store import get_vector_store

logger = logging.getLogger("finsight.ingestion")

ALLOWED_EXTENSIONS = {"pdf", "txt", "docx"}


class DocumentIngestionService:
    def __init__(self, db: Session):
        self.db = db

    def validate_file(self, filename: str, file_size: int) -> str:
        """Validate file type extension and size limit."""
        if not filename or "." not in filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is missing or has no valid extension.",
            )

        ext = filename.rsplit(".", 1)[1].lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(ALLOWED_EXTENSIONS)).upper()}.",
            )

        max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
        if file_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size / (1024*1024):.1f}MB) exceeds configured maximum of {settings.MAX_UPLOAD_SIZE_MB}MB.",
            )

        return ext

    def ingest_document(
        self,
        file_bytes: bytes,
        original_filename: str,
        workspace_id: str = "default",
    ) -> Document:
        """Execute full ingestion pipeline for an uploaded file."""
        file_size = len(file_bytes)
        ext = self.validate_file(original_filename, file_size)

        doc_id = str(uuid.uuid4())
        safe_filename = f"{doc_id}.{ext}"
        storage_path = settings.UPLOAD_DIR / safe_filename

        # Write raw uploaded file to safe storage path
        try:
            with open(storage_path, "wb") as f:
                f.write(file_bytes)
        except Exception as e:
            logger.error("Failed to write uploaded file to disk: %s", e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store uploaded document.",
            )

        # Create Document and Job in Database
        doc = Document(
            id=doc_id,
            workspace_id=workspace_id,
            original_filename=original_filename,
            storage_path=str(storage_path),
            file_type=ext,
            file_size_bytes=file_size,
            status="processing",
            page_count=0,
            chunk_count=0,
        )
        self.db.add(doc)

        job = DocumentProcessingJob(
            document_id=doc_id,
            stage="extracting",
            status="processing",
            progress_percent=20,
        )
        self.db.add(job)
        self.db.commit()
        self.db.refresh(doc)

        # Extract text and page boundaries
        try:
            extracted_doc: ExtractedDocument = extract_document_text(file_bytes, original_filename, ext)
            
            # Save extracted text cache JSON for fast retrieval & preview
            cache_path = settings.UPLOAD_DIR / f"{doc_id}_extracted.json"
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(extracted_doc.model_dump(), f, ensure_ascii=False)

            # Generate concise document summary preview
            first_page_text = extracted_doc.pages[0].text if extracted_doc.pages else ""
            summary_preview = (first_page_text[:400] + "...") if len(first_page_text) > 400 else first_page_text

            doc.page_count = extracted_doc.total_pages
            doc.document_summary = summary_preview

            # Stage 2: Chunking
            job.stage = "chunking"
            job.progress_percent = 60
            self.db.commit()

            chunker = FinancialChunker(
                chunk_size=settings.RAG_CHUNK_SIZE,
                chunk_overlap=settings.RAG_CHUNK_OVERLAP,
            )
            chunks = chunker.chunk_document(doc_id=doc_id, extracted_doc=extracted_doc)
            doc.chunk_count = len(chunks)

            # Stage 3: Embedding & Vector Storage
            if chunks:
                job.stage = "embedding"
                job.progress_percent = 80
                self.db.commit()

                embedder = get_embedding_provider()
                chunk_texts = [c.content for c in chunks]
                embeddings = embedder.embed_documents(chunk_texts)

                vector_store = get_vector_store()
                vector_store.add_chunks(chunks=chunks, embeddings=embeddings)

            # Complete Indexing
            doc.status = "indexed"
            job.stage = "indexed"
            job.status = "completed"
            job.progress_percent = 100
            job.completed_at = datetime.utcnow()

            self.db.commit()
            self.db.refresh(doc)
            logger.info("Successfully indexed document %s (%s pages, %s chunks)", original_filename, doc.page_count, doc.chunk_count)
            return doc

        except Exception as e:
            logger.error("Failed to extract document text for %s: %s", original_filename, e, exc_info=True)
            doc.status = "failed"
            doc.error_message = f"Extraction error: {str(e)}"
            job.stage = "failed"
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.utcnow()
            self.db.commit()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Failed to extract document text: {str(e)}",
            )

    def list_documents(
        self,
        workspace_id: str = "default",
        status_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Document], int, int]:
        """List documents with filtering and counts."""
        query = self.db.query(Document).filter(Document.workspace_id == workspace_id)

        if status_filter:
            query = query.filter(Document.status == status_filter)

        if search_query:
            query = query.filter(Document.original_filename.ilike(f"%{search_query}%"))

        total_count = query.count()
        indexed_count = self.db.query(Document).filter(
            Document.workspace_id == workspace_id,
            Document.status.in_(["extracted", "indexed"]),
        ).count()

        documents = query.order_by(Document.created_at.desc()).offset(skip).limit(limit).all()
        return documents, total_count, indexed_count

    def get_document(self, document_id: str) -> Optional[Document]:
        """Retrieve a document by ID."""
        return self.db.query(Document).filter(Document.id == document_id).first()

    def get_document_preview(self, document_id: str, page_number: Optional[int] = None) -> Dict[str, Any]:
        """Retrieve parsed document page text from cache."""
        doc = self.get_document(document_id)
        if not doc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found.")

        cache_path = settings.UPLOAD_DIR / f"{document_id}_extracted.json"
        if not cache_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Extracted document content not available.",
            )

        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if page_number is not None:
            matching = [p for p in data.get("pages", []) if p["page_number"] == page_number]
            if not matching:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Page {page_number} not found in document.",
                )
            return {
                "document_id": document_id,
                "filename": doc.original_filename,
                "total_pages": doc.page_count,
                "page": matching[0],
            }

        return {
            "document_id": document_id,
            "filename": doc.original_filename,
            "total_pages": doc.page_count,
            "pages": data.get("pages", [])[:10],  # Return first 10 pages for preview
        }

    def delete_document(self, document_id: str) -> bool:
        """Delete a document, its disk files, its cache, and its database records."""
        doc = self.get_document(document_id)
        if not doc:
            return False

        # 1. Delete physical raw file
        raw_file = Path(doc.storage_path)
        if raw_file.exists():
            try:
                raw_file.unlink()
            except Exception as e:
                logger.warning("Could not delete file %s: %s", raw_file, e)

        # 2. Delete extracted text cache
        cache_path = settings.UPLOAD_DIR / f"{document_id}_extracted.json"
        if cache_path.exists():
            try:
                cache_path.unlink()
            except Exception as e:
                logger.warning("Could not delete cache file %s: %s", cache_path, e)

        # 3. Delete indexed vector embeddings
        try:
            get_vector_store().delete_by_document_id(document_id)
        except Exception as e:
            logger.warning("Could not clean up vector store for %s: %s", document_id, e)

        # 4. Delete database record (cascading deletes jobs, metrics)
        self.db.delete(doc)
        self.db.commit()
        logger.info("Successfully deleted document %s and cleaned up disk storage.", document_id)
        return True
