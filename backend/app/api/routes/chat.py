"""Chat and RAG Q&A endpoints."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.app.db.session import get_db
from backend.app.services.rag.service import RAGService
from backend.app.api.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ConversationResponse,
    MessageResponse,
)

router = APIRouter(prefix="/api/chat", tags=["Chat & RAG"])


@router.post("", response_model=ChatResponse, status_code=status.HTTP_200_OK)
def ask_question(
    request: ChatRequest,
    db: Session = Depends(get_db),
):
    """Execute grounded question-answering over indexed financial documents."""
    rag_service = RAGService(db)
    return rag_service.answer_query(
        query=request.query,
        document_ids=request.document_ids,
        workspace_id=request.workspace_id,
        conversation_id=request.conversation_id,
        top_k=request.top_k or 4,
    )


@router.get("/conversations", response_model=List[ConversationResponse])
def list_conversations(
    workspace_id: str = "default",
    limit: int = 50,
    db: Session = Depends(get_db),
):
    """List recent chat conversations in workspace."""
    rag_service = RAGService(db)
    return rag_service.list_conversations(workspace_id=workspace_id, limit=limit)


@router.get("/conversations/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_history(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Retrieve message history with citations for a conversation."""
    rag_service = RAGService(db)
    messages = rag_service.get_conversation_messages(conversation_id)
    if not messages:
        # Check if conversation exists
        convs = rag_service.list_conversations()
        if not any(c.id == conversation_id for c in convs):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Conversation '{conversation_id}' not found.",
            )
    return messages


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_200_OK)
def delete_conversation(
    conversation_id: str,
    db: Session = Depends(get_db),
):
    """Delete a conversation and its messages."""
    rag_service = RAGService(db)
    success = rag_service.delete_conversation(conversation_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found.",
        )
    return {"success": True, "message": "Conversation deleted."}
