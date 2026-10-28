"""Persistent Vector Store with Dense Cosine Similarity, BM25 Keyword Search, and RRF."""

import os
import json
import math
import re
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any, Tuple
import numpy as np

from backend.app.config import settings
from backend.app.services.ingestion.chunker import DocumentChunk
from backend.app.services.vector_store.base import BaseVectorStore, SearchResult

logger = logging.getLogger("finsight.vector_store")


class PersistentVectorStore(BaseVectorStore):
    def __init__(self, storage_dir: Optional[Path] = None):
        self.storage_dir = storage_dir or settings.VECTOR_STORE_DIR
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.vectors_file = self.storage_dir / "vectors.npy"
        self.chunks_file = self.storage_dir / "chunks.json"

        self.chunks: List[DocumentChunk] = []
        self.vectors: Optional[np.ndarray] = None  # Shape: (N, D)

        # BM25 statistics
        self.doc_lengths: List[int] = []
        self.avg_doc_len: float = 0.0
        self.doc_freqs: Dict[str, int] = {}
        self.tokenized_corpus: List[List[str]] = []

        self._load()

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"\b[A-Za-z0-9\$\%]+(?:[,\.][A-Za-z0-9]+)*\b", text.lower())

    def _load(self):
        """Load persisted vectors and chunks from disk."""
        if self.chunks_file.exists():
            try:
                with open(self.chunks_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.chunks = [DocumentChunk(**item) for item in data]
                logger.info("Loaded %s chunks from %s", len(self.chunks), self.chunks_file)
            except Exception as e:
                logger.error("Failed loading chunks: %s", e)
                self.chunks = []

        if self.vectors_file.exists() and len(self.chunks) > 0:
            try:
                self.vectors = np.load(self.vectors_file)
                logger.info("Loaded vectors array with shape %s", self.vectors.shape)
            except Exception as e:
                logger.error("Failed loading vectors: %s", e)
                self.vectors = None

        self._rebuild_bm25_index()

    def _save(self):
        """Persist vectors and chunks to disk."""
        try:
            with open(self.chunks_file, "w", encoding="utf-8") as f:
                json.dump([c.model_dump() for c in self.chunks], f, ensure_ascii=False)

            if self.vectors is not None and len(self.vectors) > 0:
                np.save(self.vectors_file, self.vectors)
            elif self.vectors_file.exists():
                self.vectors_file.unlink()
        except Exception as e:
            logger.error("Failed saving vector store: %s", e)

    def _rebuild_bm25_index(self):
        """Build in-memory BM25 index over the chunks."""
        self.tokenized_corpus = [self._tokenize(c.content) for c in self.chunks]
        self.doc_lengths = [len(tokens) for tokens in self.tokenized_corpus]
        total_tokens = sum(self.doc_lengths)
        self.avg_doc_len = (total_tokens / len(self.chunks)) if self.chunks else 0.0

        self.doc_freqs = {}
        for tokens in self.tokenized_corpus:
            unique_tokens = set(tokens)
            for token in unique_tokens:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

    def add_chunks(self, chunks: List[DocumentChunk], embeddings: List[List[float]]) -> None:
        """Add new chunks and embeddings, then persist."""
        if not chunks:
            return

        new_vectors = np.array(embeddings, dtype=np.float32)
        # Ensure L2 normalization
        norms = np.linalg.norm(new_vectors, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        new_vectors = new_vectors / norms

        if self.vectors is None or len(self.vectors) == 0:
            self.vectors = new_vectors
        else:
            self.vectors = np.vstack([self.vectors, new_vectors])

        self.chunks.extend(chunks)
        self._rebuild_bm25_index()
        self._save()
        logger.info("Added %s chunks to vector store. Total chunks: %s", len(chunks), len(self.chunks))

    def _compute_bm25_scores(self, query_tokens: List[str], candidate_indices: List[int]) -> Dict[int, float]:
        """Compute BM25 scores for query against candidate chunk indices."""
        k1 = 1.5
        b = 0.75
        N = len(self.chunks)
        scores: Dict[int, float] = {}

        if N == 0 or not query_tokens:
            return scores

        for idx in candidate_indices:
            doc_tokens = self.tokenized_corpus[idx]
            doc_len = self.doc_lengths[idx]
            len_norm = 1 - b + b * (doc_len / (self.avg_doc_len or 1.0))

            doc_tf: Dict[str, int] = {}
            for t in doc_tokens:
                doc_tf[t] = doc_tf.get(t, 0) + 1

            score = 0.0
            for qt in query_tokens:
                if qt in doc_tf:
                    df = self.doc_freqs.get(qt, 1)
                    # IDF with standard smoothing
                    idf = math.log((N - df + 0.5) / (df + 0.5) + 1.0)
                    tf = doc_tf[qt]
                    score += idf * ((tf * (k1 + 1)) / (tf + k1 * len_norm))

            scores[idx] = max(0.0, score)

        return scores

    def search(
        self,
        query_embedding: List[float],
        query_text: str,
        top_k: int = 4,
        document_ids: Optional[List[str]] = None,
        workspace_id: str = "default",
        use_hybrid: bool = True,
    ) -> List[SearchResult]:
        """Hybrid retrieval combining dense cosine similarity and BM25 via Reciprocal Rank Fusion."""
        if not self.chunks or self.vectors is None:
            return []

        # Step 1: Filter candidate indices by document_ids if specified
        doc_id_set = set(document_ids) if document_ids else None
        candidate_indices = [
            i for i, c in enumerate(self.chunks)
            if doc_id_set is None or c.document_id in doc_id_set
        ]

        if not candidate_indices:
            return []

        # Step 2: Dense Semantic Cosine Similarity
        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        sub_vectors = self.vectors[candidate_indices]  # Shape: (M, D)
        dense_scores = np.dot(sub_vectors, q_vec)  # Cosine similarities in range [-1, 1]

        # Rank candidates by dense similarity
        dense_ranked_pairs = sorted(
            zip(candidate_indices, dense_scores),
            key=lambda x: x[1],
            reverse=True,
        )

        if not use_hybrid:
            # Dense only
            results = []
            for rank, (idx, score) in enumerate(dense_ranked_pairs[:top_k]):
                results.append(SearchResult(
                    chunk=self.chunks[idx],
                    similarity_score=float(score),
                    dense_score=float(score),
                    bm25_score=0.0,
                    rank=rank + 1,
                ))
            return results

        # Step 3: Sparse BM25 Keyword Search
        query_tokens = self._tokenize(query_text)
        bm25_scores = self._compute_bm25_scores(query_tokens, candidate_indices)
        bm25_ranked_pairs = sorted(
            candidate_indices,
            key=lambda idx: bm25_scores.get(idx, 0.0),
            reverse=True,
        )

        # Step 4: Reciprocal Rank Fusion (RRF)
        # RRF_Score = 1 / (60 + dense_rank) + 1 / (60 + bm25_rank)
        rrf_constant = 60
        dense_ranks = {idx: rank + 1 for rank, (idx, _) in enumerate(dense_ranked_pairs)}
        bm25_ranks = {idx: rank + 1 for rank, idx in enumerate(bm25_ranked_pairs)}

        dense_score_dict = {idx: float(score) for idx, score in dense_ranked_pairs}

        fused_scores: List[Tuple[int, float]] = []
        for idx in candidate_indices:
            r_dense = dense_ranks[idx]
            r_bm25 = bm25_ranks[idx]
            rrf_score = (1.0 / (rrf_constant + r_dense)) + (1.0 / (rrf_constant + r_bm25))
            fused_scores.append((idx, rrf_score))

        fused_scores.sort(key=lambda x: x[1], reverse=True)

        results: List[SearchResult] = []
        for rank, (idx, rrf_score) in enumerate(fused_scores[:top_k]):
            results.append(SearchResult(
                chunk=self.chunks[idx],
                similarity_score=dense_score_dict.get(idx, 0.0),
                dense_score=dense_score_dict.get(idx, 0.0),
                bm25_score=bm25_scores.get(idx, 0.0),
                rank=rank + 1,
            ))

        return results

    def delete_by_document_id(self, document_id: str) -> int:
        """Remove all chunks and vectors belonging to a document."""
        if not self.chunks:
            return 0

        keep_indices = [i for i, c in enumerate(self.chunks) if c.document_id != document_id]
        deleted_count = len(self.chunks) - len(keep_indices)

        if deleted_count == 0:
            return 0

        self.chunks = [self.chunks[i] for i in keep_indices]
        if self.vectors is not None:
            self.vectors = self.vectors[keep_indices] if keep_indices else None

        self._rebuild_bm25_index()
        self._save()
        logger.info("Deleted %s chunks for document %s. Remaining: %s", deleted_count, document_id, len(self.chunks))
        return deleted_count

    def count(self, document_id: Optional[str] = None) -> int:
        if document_id:
            return sum(1 for c in self.chunks if c.document_id == document_id)
        return len(self.chunks)

    def clear(self) -> None:
        """Clear all stored vectors and chunks."""
        self.chunks = []
        self.vectors = None
        self._rebuild_bm25_index()
        self._save()


# Global singleton instance
_vector_store_instance: Optional[PersistentVectorStore] = None


def get_vector_store() -> PersistentVectorStore:
    global _vector_store_instance
    if _vector_store_instance is None:
        _vector_store_instance = PersistentVectorStore()
    return _vector_store_instance
