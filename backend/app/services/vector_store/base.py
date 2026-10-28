"""Vector store interface definition."""

import abc
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from backend.app.services.ingestion.chunker import DocumentChunk


class SearchResult(BaseModel):
    chunk: DocumentChunk
    similarity_score: float
    dense_score: float
    bm25_score: float
    rank: int


class BaseVectorStore(abc.ABC):
    @abc.abstractmethod
    def add_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> None:
        """Add chunks and corresponding dense embeddings to the index."""
        pass

    @abc.abstractmethod
    def search(
        self,
        query_embedding: List[float],
        query_text: str,
        top_k: int = 4,
        document_ids: Optional[List[str]] = None,
        workspace_id: str = "default",
        use_hybrid: bool = True,
    ) -> List[SearchResult]:
        """Perform semantic or hybrid retrieval."""
        pass

    @abc.abstractmethod
    def delete_by_document_id(self, document_id: str) -> int:
        """Delete all chunks belonging to a document."""
        pass

    @abc.abstractmethod
    def count(self, document_id: Optional[str] = None) -> int:
        """Return number of chunks in store."""
        pass
