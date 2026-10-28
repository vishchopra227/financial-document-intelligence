"""Multi-Document Comparative Intelligence Service.
Retrieves evidence separately from each document, performs structured contrast, and generates grounded comparative analysis.
"""

import time
import logging
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.config import settings
from backend.app.db.models import Document
from backend.app.services.ai.embeddings import get_embedding_provider
from backend.app.services.ai.llm import get_llm_adapter, LLMAnswer
from backend.app.services.vector_store.persistent_store import get_vector_store
from backend.app.services.vector_store.base import SearchResult
from backend.app.services.ingestion.chunker import DocumentChunk
from backend.app.api.schemas.chat import Citation

logger = logging.getLogger("finsight.comparison")


class DocumentEvidenceSummary(BaseModel):
    document_id: str
    filename: str
    page_count: int
    company_name: Optional[str] = None
    reporting_period: Optional[str] = None
    top_chunks: List[str]
    pages_cited: List[int]


class ComparisonResult(BaseModel):
    query: str
    documents: List[DocumentEvidenceSummary]
    analysis: str
    citations: List[Citation]
    has_sufficient_evidence: bool
    retrieval_latency_ms: float
    generation_latency_ms: float
    model_name: str


COMPARISON_SYSTEM_PROMPT = """You are FinSight Intelligence, an expert financial analyst comparing multiple corporate financial reports.

CRITICAL COMPARATIVE ANALYSIS RULES:
1. DOCUMENT SEPARATION: Analyze the retrieved evidence from EACH document independently.
2. FINANCIAL METRICS COMPARISON: Compare reported figures (revenue, net income, margins, debt, etc.) across the documents.
3. CONTEXT & REPORTING PERIODS: Explicitly state the reporting periods (e.g. FY2022 vs FY2023) and currencies ($ USD, € EUR). Never assume two figures are directly comparable without verifying reporting period, units, and metric definitions.
4. CITATIONS: Cite the exact source document and page number for every claim using: [Doc: {filename}, Page {page_number}].
5. INSUFFICIENT OR MISSING DATA: If one document mentions a metric but another does not, explicitly explain that the data is absent in that document. Do not invent missing numbers.
6. STRUCTURE: Format your answer with clear sections:
   - Overview & Reporting Periods
   - Key Financial Metrics Comparison (with explicit values and changes)
   - Strategic & Risk Differences
   - Conclusion / Summary
"""


class MultiDocumentComparisonService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding_provider = get_embedding_provider()
        self.llm_adapter = get_llm_adapter()
        self.vector_store = get_vector_store()

    def compare_documents(
        self,
        document_ids: List[str],
        query: str,
        top_k_per_doc: int = 3,
    ) -> ComparisonResult:
        if len(document_ids) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least two document IDs are required for cross-document comparison.",
            )

        # Verify documents exist
        docs_by_id = {
            doc.id: doc
            for doc in self.db.query(Document).filter(Document.id.in_(document_ids)).all()
        }
        docs = [docs_by_id[doc_id] for doc_id in document_ids if doc_id in docs_by_id]
        if len(docs) < len(document_ids):
            found_ids = {d.id for d in docs}
            missing = set(document_ids) - found_ids
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Documents not found: {list(missing)}",
            )

        t_start = time.time()
        query_embedding = self.embedding_provider.embed_query(query)

        # Retrieve evidence from each document SEPARATELY to avoid starvation
        all_retrieved_chunks: List[DocumentChunk] = []
        all_search_results: List[SearchResult] = []
        doc_summaries: List[DocumentEvidenceSummary] = []
        all_citations: List[Citation] = []

        for doc in docs:
            doc_results = self.vector_store.search(
                query_embedding=query_embedding,
                query_text=query,
                top_k=top_k_per_doc,
                document_ids=[doc.id],
                use_hybrid=True,
            )

            all_search_results.extend(doc_results)
            doc_chunks = [r.chunk for r in doc_results]
            all_retrieved_chunks.extend(doc_chunks)

            pages_cited = sorted(list({c.page_number for c in doc_chunks}))
            top_excerpts = [c.content[:200].replace("\n", " ").strip() for c in doc_chunks]

            doc_summaries.append(DocumentEvidenceSummary(
                document_id=doc.id,
                filename=doc.original_filename,
                page_count=doc.page_count,
                company_name=doc.company_name,
                reporting_period=doc.reporting_period,
                top_chunks=top_excerpts,
                pages_cited=pages_cited,
            ))

            for r in doc_results:
                all_citations.append(Citation(
                    chunk_id=r.chunk.chunk_id,
                    document_id=r.chunk.document_id,
                    filename=r.chunk.filename,
                    page_number=r.chunk.page_number,
                    excerpt=(
                        r.chunk.content[:220].replace("\n", " ").strip()
                        + ("..." if len(r.chunk.content) > 220 else "")
                    ),
                    similarity_score=round(r.similarity_score, 4),
                ))

        retrieval_latency_ms = round((time.time() - t_start) * 1000, 2)

        # Call LLM Adapter with Comparative Prompt
        t_gen_start = time.time()
        llm_answer: LLMAnswer = self.llm_adapter.generate_grounded_answer(
            query=f"Compare the following documents regarding: {query}",
            context_chunks=all_retrieved_chunks,
            system_prompt=COMPARISON_SYSTEM_PROMPT,
        )
        generation_latency_ms = round((time.time() - t_gen_start) * 1000, 2)

        return ComparisonResult(
            query=query,
            documents=doc_summaries,
            analysis=llm_answer.answer,
            citations=all_citations,
            has_sufficient_evidence=bool(all_retrieved_chunks) and llm_answer.has_sufficient_evidence,
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=generation_latency_ms,
            model_name=llm_answer.model_name,
        )
