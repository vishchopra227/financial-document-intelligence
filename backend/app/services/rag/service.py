"""Advanced RAG Pipeline Service.
Orchestrates query embedding, hybrid vector/BM25 retrieval, grounding verification, citation mapping, and persistence.
"""

import time
import logging
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from backend.app.config import settings
from backend.app.db.models import Conversation, Message
from backend.app.services.ai.embeddings import get_embedding_provider
from backend.app.services.ai.llm import get_llm_adapter, LLMAnswer
from backend.app.services.vector_store.persistent_store import get_vector_store
from backend.app.services.vector_store.base import SearchResult
from backend.app.api.schemas.chat import ChatResponse, Citation

logger = logging.getLogger("finsight.rag")


class RAGService:
    def __init__(self, db: Session):
        self.db = db
        self.embedding_provider = get_embedding_provider()
        self.llm_adapter = get_llm_adapter()
        self.vector_store = get_vector_store()

    def answer_query(
        self,
        query: str,
        document_ids: Optional[List[str]] = None,
        workspace_id: str = "default",
        conversation_id: Optional[str] = None,
        top_k: int = 4,
    ) -> ChatResponse:
        """Execute end-to-end grounded RAG workflow."""
        clean_query = query.strip()
        if len(clean_query) < 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query must contain at least 2 characters.",
            )

        # 1. Conversation Management
        if conversation_id:
            conv = self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
            if not conv:
                conv = Conversation(
                    id=conversation_id,
                    workspace_id=workspace_id,
                    title=clean_query[:50],
                    document_ids=document_ids or [],
                )
                self.db.add(conv)
                self.db.commit()
        else:
            conv = Conversation(
                workspace_id=workspace_id,
                title=clean_query[:50],
                document_ids=document_ids or [],
            )
            self.db.add(conv)
            self.db.commit()
            self.db.refresh(conv)

        # 2. Record User Message
        user_msg = Message(
            conversation_id=conv.id,
            role="user",
            content=clean_query,
            citations=[],
            retrieved_chunks=[],
        )
        self.db.add(user_msg)
        self.db.commit()

        # 3. Retrieval Step
        t_retrieval_start = time.time()
        query_embedding = self.embedding_provider.embed_query(clean_query)
        
        search_results: List[SearchResult] = self.vector_store.search(
            query_embedding=query_embedding,
            query_text=clean_query,
            top_k=top_k,
            document_ids=document_ids,
            workspace_id=workspace_id,
            use_hybrid=settings.RAG_ENABLE_HYBRID_SEARCH,
        )
        retrieval_latency_ms = round((time.time() - t_retrieval_start) * 1000, 2)

        # 4. Check Grounding Sufficiency
        # If no chunks found or zero relevant match
        has_sufficient_evidence = bool(search_results)
        if search_results:
            top_score = search_results[0].similarity_score
            top_bm25 = search_results[0].bm25_score
            # If top cosine similarity is very low and no exact BM25 keyword match occurred
            if top_score < 0.05 and top_bm25 == 0.0:
                has_sufficient_evidence = False

        # 5. Answer Generation via LLM Adapter
        context_chunks = [r.chunk for r in search_results] if has_sufficient_evidence else []
        llm_answer: LLMAnswer = self.llm_adapter.generate_grounded_answer(
            query=clean_query,
            context_chunks=context_chunks,
        )

        # 6. Build Citations linked directly to actual retrieved chunks
        citations: List[Citation] = []
        if has_sufficient_evidence:
            for r in search_results:
                excerpt = r.chunk.content[:220].replace("\n", " ").strip()
                if len(r.chunk.content) > 220:
                    excerpt += "..."
                citation = Citation(
                    chunk_id=r.chunk.chunk_id,
                    document_id=r.chunk.document_id,
                    filename=r.chunk.filename,
                    page_number=r.chunk.page_number,
                    excerpt=excerpt,
                    similarity_score=round(r.similarity_score, 4),
                )
                citations.append(citation)

        # 7. Record Assistant Message
        assistant_msg = Message(
            conversation_id=conv.id,
            role="assistant",
            content=llm_answer.answer,
            citations=[c.model_dump() for c in citations],
            retrieved_chunks=[r.chunk.chunk_id for r in search_results],
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=llm_answer.generation_latency_ms,
            model_name=llm_answer.model_name,
        )
        self.db.add(assistant_msg)
        self.db.commit()
        self.db.refresh(assistant_msg)

        logger.info(
            "RAG completed for query '%s...' [Chunks: %s, Retrieval: %sms, Gen: %sms, Model: %s]",
            clean_query[:30],
            len(search_results),
            retrieval_latency_ms,
            llm_answer.generation_latency_ms,
            llm_answer.model_name,
        )

        return ChatResponse(
            answer=llm_answer.answer,
            conversation_id=conv.id,
            message_id=assistant_msg.id,
            citations=citations,
            retrieved_chunk_count=len(search_results),
            has_sufficient_evidence=llm_answer.has_sufficient_evidence and has_sufficient_evidence,
            retrieval_latency_ms=retrieval_latency_ms,
            generation_latency_ms=llm_answer.generation_latency_ms,
            model_name=llm_answer.model_name,
        )

    def list_conversations(self, workspace_id: str = "default", limit: int = 50) -> List[Conversation]:
        return (
            self.db.query(Conversation)
            .filter(Conversation.workspace_id == workspace_id)
            .order_by(Conversation.updated_at.desc())
            .limit(limit)
            .all()
        )

    def get_conversation_messages(self, conversation_id: str) -> List[Message]:
        return (
            self.db.query(Message)
            .filter(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
            .all()
        )

    def delete_conversation(self, conversation_id: str) -> bool:
        conv = self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conv:
            return False
        self.db.delete(conv)
        self.db.commit()
        return True
