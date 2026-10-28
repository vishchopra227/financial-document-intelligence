"""Tests for database operations and models."""

from backend.app.db.session import SessionLocal
from backend.app.db.models import Document, DocumentProcessingJob, Conversation, Message, ExtractedMetric


def test_document_model_crud():
    db = SessionLocal()
    try:
        # Create
        doc = Document(
            original_filename="apple_10k_2023.pdf",
            storage_path="backend/data/uploads/test_apple.pdf",
            file_type="pdf",
            file_size_bytes=1048576,
            page_count=98,
            status="pending",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        assert doc.id is not None
        assert doc.status == "pending"
        doc_id = doc.id

        # Read
        retrieved = db.query(Document).filter(Document.id == doc_id).first()
        assert retrieved is not None
        assert retrieved.original_filename == "apple_10k_2023.pdf"

        # Update
        retrieved.status = "indexed"
        retrieved.chunk_count = 142
        db.commit()

        updated = db.query(Document).filter(Document.id == doc_id).first()
        assert updated.status == "indexed"
        assert updated.chunk_count == 142

        # Delete
        db.delete(updated)
        db.commit()

        deleted = db.query(Document).filter(Document.id == doc_id).first()
        assert deleted is None
    finally:
        db.close()


def test_conversation_and_message_relationship():
    db = SessionLocal()
    try:
        conv = Conversation(
            title="Q3 Revenue Analysis",
            document_ids=["doc-123", "doc-456"],
        )
        db.add(conv)
        db.commit()
        db.refresh(conv)

        msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content="Revenue grew by 8.4% YoY.",
            citations=[
                {
                    "chunk_id": "chunk-1",
                    "document_id": "doc-123",
                    "filename": "q3_report.pdf",
                    "page_number": 12,
                    "excerpt": "Total revenue reached $89.5B",
                }
            ],
        )
        db.add(msg)
        db.commit()

        # Verify relationship
        retrieved_conv = db.query(Conversation).filter(Conversation.id == conv.id).first()
        assert len(retrieved_conv.messages) == 1
        assert retrieved_conv.messages[0].citations[0]["page_number"] == 12

        # Cleanup
        db.delete(retrieved_conv)
        db.commit()
    finally:
        db.close()
