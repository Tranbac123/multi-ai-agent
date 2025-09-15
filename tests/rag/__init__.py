"""RAG (Retrieval-Augmented Generation) tenant isolation tests."""

from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from datetime import datetime

class RAGIsolationLevel(Enum):
    """RAG isolation levels."""
    TENANT_ISOLATION = "tenant_isolation"
    USER_ISOLATION = "user_isolation"
    ROLE_ISOLATION = "role_isolation"
    DOCUMENT_ISOLATION = "document_isolation"

class VectorSimilarity(Enum):
    """Vector similarity types."""
    COSINE = "cosine"
    EUCLIDEAN = "euclidean"
    DOT_PRODUCT = "dot_product"

@dataclass
class RAGQuery:
    """RAG query structure."""
    query_id: str
    tenant_id: str
    user_id: str
    query_text: str
    filters: Dict[str, Any]
    max_results: int
    similarity_threshold: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'query_id': self.query_id,
            'tenant_id': self.tenant_id,
            'user_id': self.user_id,
            'query_text': self.query_text,
            'filters': self.filters,
            'max_results': self.max_results,
            'similarity_threshold': self.similarity_threshold
        }

@dataclass
class RAGResult:
    """RAG query result."""
    document_id: str
    tenant_id: str
    similarity_score: float
    content: str
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'document_id': self.document_id,
            'tenant_id': self.tenant_id,
            'similarity_score': self.similarity_score,
            'content': self.content,
            'metadata': self.metadata
        }
