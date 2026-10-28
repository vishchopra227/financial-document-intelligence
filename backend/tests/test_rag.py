"""Automated unit and integration tests for Core RAG Pipeline."""

import io
import pytest
from backend.app.services.ingestion.parser import ExtractedDocument, ExtractedPage
from backend.app.services.ingestion.chunker import FinancialChunker
from backend.app.services.ai.embeddings import DeterministicFinancialEmbedding
from backend.app.services.vector_store.persistent_store import PersistentVectorStore
from backend.app.services.vector_store.base import SearchResult


def test_financial_chunker_page_attribution():
    """Verify chunker strictly preserves page numbers and attribution."""
    doc = ExtractedDocument(
        filename="10k_report.txt",
        file_type="txt",
        total_pages=2,
        pages=[
            ExtractedPage(page_number=1, text="Page 1: Apple Inc reported net sales of $383 billion.", char_count=52),
            ExtractedPage(page_number=2, text="Page 2: Operating expenses were $54 billion with gross margin of 44%.", char_count=69),
        ],
        total_characters=121,
    )

    chunker = FinancialChunker(chunk_size=300, chunk_overlap=50)
    chunks = chunker.chunk_document(doc_id="doc-test-1", extracted_doc=doc)

    assert len(chunks) == 2
    assert chunks[0].page_number == 1
    assert "Page 1:" in chunks[0].content
    assert chunks[1].page_number == 2
    assert "Page 2:" in chunks[1].content


def test_financial_chunker_table_preservation():
    """Verify table blocks [TABLE START] ... [TABLE END] are not split in the middle."""
    table_text = (
        "Narrative introduction to financial results.\n\n"
        "[TABLE START]\n"
        "Metric | FY2023 | FY2022\n"
        "Revenue | $383.2B | $394.3B\n"
        "Net Income | $96.9B | $99.8B\n"
        "[TABLE END]\n\n"
        "Following narrative discussion of operating performance."
    )
    doc = ExtractedDocument(
        filename="table_doc.txt",
        file_type="txt",
        total_pages=1,
        pages=[ExtractedPage(page_number=1, text=table_text, char_count=len(table_text))],
        total_characters=len(table_text),
    )

    chunker = FinancialChunker(chunk_size=150, chunk_overlap=30)
    chunks = chunker.chunk_document(doc_id="doc-table", extracted_doc=doc)

    # Find chunk containing the table
    table_chunks = [c for c in chunks if c.has_table]
    assert len(table_chunks) >= 1
    assert "[TABLE START]" in table_chunks[0].content
    assert "[TABLE END]" in table_chunks[0].content
    assert "Net Income | $96.9B" in table_chunks[0].content


def test_deterministic_embedding_similarity():
    """Verify semantic embedding yields higher cosine similarity for related financial queries."""
    embedder = DeterministicFinancialEmbedding()
    
    t1 = "Apple reports strong quarterly revenue and net income growth."
    t2 = "Company sales and profit margins increased significantly."
    t3 = "The recipes for chocolate chip cookies require butter and sugar."

    v1 = embedder.embed_query(t1)
    v2 = embedder.embed_query(t2)
    v3 = embedder.embed_query(t3)

    import numpy as np
    sim_financial = np.dot(v1, v2)
    sim_unrelated = np.dot(v1, v3)

    assert sim_financial > sim_unrelated
    assert sim_financial > 0.40


def test_vector_store_hybrid_retrieval(tmp_path):
    """Test vector store dense, BM25, and hybrid RRF search with metadata filtering."""
    store = PersistentVectorStore(storage_dir=tmp_path)
    embedder = DeterministicFinancialEmbedding()

    doc = ExtractedDocument(
        filename="cloud_earnings.txt",
        file_type="txt",
        total_pages=1,
        pages=[
            ExtractedPage(
                page_number=1,
                text="Google Cloud revenue reached $9.19 billion, growing 28% year-over-year. Operating income was $1.05 billion.",
                char_count=107,
            )
        ],
        total_characters=107,
    )
    chunker = FinancialChunker()
    chunks = chunker.chunk_document(doc_id="cloud-1", extracted_doc=doc)
    embeddings = embedder.embed_documents([c.content for c in chunks])

    store.add_chunks(chunks, embeddings)
    assert store.count() == 1

    # Search query
    q = "What was Google Cloud revenue?"
    q_vec = embedder.embed_query(q)
    results = store.search(query_embedding=q_vec, query_text=q, top_k=2, use_hybrid=True)

    assert len(results) == 1
    assert results[0].chunk.document_id == "cloud-1"
    assert results[0].chunk.page_number == 1
    assert "$9.19 billion" in results[0].chunk.content

    # Delete
    deleted = store.delete_by_document_id("cloud-1")
    assert deleted == 1
    assert store.count() == 0


def test_end_to_end_rag_chat_api(client):
    """Integration test: upload document, query via /api/chat, verify citations and latency."""
    report_text = (
        "MICROSOFT CORP ANNUAL FINANCIAL STATEMENT\n\n"
        "Revenue was $211.9 billion for fiscal year 2023, up 7% compared to fiscal year 2022.\n"
        "Operating income was $88.5 billion and net income was $72.4 billion.\n"
        "Diluted earnings per share was $9.68.\n"
    ).encode("utf-8")

    files = {"file": ("microsoft_fy23.txt", report_text, "text/plain")}
    upload_res = client.post("/api/documents/upload", files=files)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    try:
        # Ask question
        chat_payload = {
            "query": "What was Microsoft total revenue for fiscal year 2023?",
            "document_ids": [doc_id],
            "top_k": 3,
        }
        chat_res = client.post("/api/chat", json=chat_payload)
        assert chat_res.status_code == 200
        data = chat_res.json()

        assert "answer" in data
        assert len(data["answer"]) > 10
        assert data["retrieved_chunk_count"] >= 1
        assert data["has_sufficient_evidence"] is True
        assert data["retrieval_latency_ms"] >= 0
        assert data["generation_latency_ms"] >= 0

        # Citations check
        assert len(data["citations"]) >= 1
        citation = data["citations"][0]
        assert citation["document_id"] == doc_id
        assert citation["filename"] == "microsoft_fy23.txt"
        assert citation["page_number"] == 1
        assert "$211.9 billion" in citation["excerpt"]

        # Check conversations history
        conv_id = data["conversation_id"]
        history_res = client.get(f"/api/chat/conversations/{conv_id}/messages")
        assert history_res.status_code == 200
        messages = history_res.json()
        assert len(messages) == 2  # user + assistant
        assert messages[0]["role"] == "user"
        assert messages[1]["role"] == "assistant"

    finally:
        client.delete(f"/api/documents/{doc_id}")


def test_rag_insufficient_evidence_fallback(client):
    """Test that RAG explicitly abstains when retrieved evidence is absent or irrelevant."""
    payload = {
        "query": "Explain quantum cryptography protocols in satellite communications.",
        "top_k": 2,
    }
    res = client.post("/api/chat", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "insufficient evidence" in data["answer"].lower()
    assert data["has_sufficient_evidence"] is False
