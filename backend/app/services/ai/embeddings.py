"""Embedding provider abstraction and adapters for FinSight Intelligence."""

import abc
import hashlib
import math
import re
from typing import List, Dict, Set
import numpy as np

from backend.app.config import settings


class BaseEmbeddingProvider(abc.ABC):
    @abc.abstractmethod
    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Generate dense embeddings for a list of document chunks."""
        pass

    @abc.abstractmethod
    def embed_query(self, text: str) -> List[float]:
        """Generate dense embedding for a user query."""
        pass

    @property
    @abc.abstractmethod
    def dimension(self) -> int:
        """Vector dimensionality."""
        pass


# Semantic financial concept clusters mapped to dedicated dimensions
FINANCIAL_CONCEPT_CLUSTERS = [
    # Concept 0: Revenue / Sales / Top-line
    {"revenue", "sales", "turnover", "receipts", "topline", "billings"},
    # Concept 1: Profit / Income / Earnings / Net
    {"profit", "income", "earnings", "net", "bottomline", "ebitda", "ebit", "operating_income"},
    # Concept 2: Expenses / Costs / Opex / Capex
    {"expense", "expenses", "costs", "cost", "spending", "outlays", "opex", "capex", "overheads"},
    # Concept 3: Margins / Profitability
    {"margin", "margins", "profitability", "gross_margin", "operating_margin", "net_margin"},
    # Concept 4: Growth / Increase / Improvement / Rise
    {"growth", "increase", "increased", "growing", "higher", "rose", "expansion", "up", "gain"},
    # Concept 5: Decline / Loss / Drop / Decrease
    {"decline", "declined", "decrease", "decreased", "loss", "losses", "drop", "dropped", "down", "lower"},
    # Concept 6: Assets / Balance Sheet / Cash / Capital
    {"assets", "asset", "cash", "capital", "liquidity", "reserves", "investments"},
    # Concept 7: Debt / Liabilities / Leverage
    {"debt", "debts", "liabilities", "liability", "leverage", "borrowings", "loans", "obligations"},
    # Concept 8: Equity / Shares / Stock / EPS / Diluted
    {"equity", "shares", "share", "stock", "eps", "per_share", "diluted", "dividend", "dividends"},
    # Concept 9: Forecast / Guidance / Outlook
    {"guidance", "outlook", "forecast", "projection", "target", "expected", "anticipate"},
    # Concept 10: Risks / Inflation / Market Uncertainty
    {"risk", "risks", "uncertainty", "inflation", "macroeconomic", "headwinds", "volatility"},
]


class DeterministicFinancialEmbedding(BaseEmbeddingProvider):
    """High-performance, deterministic semantic embedding generator for financial text.
    Produces 384-dimensional L2-normalized dense embeddings without external network calls.
    Features semantic concept cluster projection and subword n-gram hashing.
    """
    def __init__(self, dimension: int = 384):
        self._dim = dimension
        
        # Inverted index from term -> cluster index
        self.term_to_cluster: Dict[str, int] = {}
        for c_idx, cluster in enumerate(FINANCIAL_CONCEPT_CLUSTERS):
            for term in cluster:
                self.term_to_cluster[term] = c_idx

    @property
    def dimension(self) -> int:
        return self._dim

    def _text_to_vector(self, text: str) -> List[float]:
        if not text:
            vec = np.zeros(self._dim, dtype=np.float32)
            vec[0] = 1.0
            return vec.tolist()

        vec = np.zeros(self._dim, dtype=np.float32)
        words = re.findall(r"\b[A-Za-z0-9\$\%]+(?:[,\.][A-Za-z0-9]+)*\b", text.lower())

        for i, word in enumerate(words):
            # 1. Semantic Concept Cluster Activation (first 32 dimensions reserved)
            if word in self.term_to_cluster:
                cluster_id = self.term_to_cluster[word]
                vec[cluster_id] += 3.5  # Strong positive weight on shared semantic concept

            # 2. Financial numbers & currency weighting
            num_match = re.match(r"^\$?(\d+[\d,]*\.?\d*)\%?$", word)
            if num_match:
                # Project numbers into dimensions 32-64
                h_num = int(hashlib.md5(word.encode("utf-8")).hexdigest(), 16)
                vec[32 + (h_num % 32)] += 2.5

            # 3. Word hashing into remainder of dimensions (64 - 384)
            h_word = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
            idx_word = 64 + (h_word % (self._dim - 64))
            vec[idx_word] += 1.0

            # 4. Bigram activation
            if i < len(words) - 1:
                bigram = f"{word}_{words[i+1]}"
                h_bi = int(hashlib.md5(bigram.encode("utf-8")).hexdigest(), 16)
                idx_bi = 64 + (h_bi % (self._dim - 64))
                vec[idx_bi] += 0.8

        # L2 Normalization so dot product == Cosine Similarity
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        else:
            vec[0] = 1.0

        return vec.tolist()

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._text_to_vector(t) for t in texts]

    def embed_query(self, text: str) -> List[float]:
        return self._text_to_vector(text)


def get_embedding_provider() -> BaseEmbeddingProvider:
    """Factory returning the active embedding provider."""
    return DeterministicFinancialEmbedding()
