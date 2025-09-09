"""Knowledge service for document retrieval and management."""

import asyncio
from typing import List, Dict, Any, Optional
from uuid import UUID
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from apps.ingestion.core.embedding_service import EmbeddingService
from apps.ingestion.core.vector_indexer import VectorIndexer
from libs.clients.database import get_db_session

logger = structlog.get_logger(__name__)


class KnowledgeService:
    """Service for knowledge retrieval and management."""
    
    def __init__(self, embedding_service: EmbeddingService, vector_indexer: VectorIndexer):
        self.embedding_service = embedding_service
        self.vector_indexer = vector_indexer
    
    async def search_knowledge(
        self,
        query: str,
        tenant_id: UUID,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search knowledge base for relevant documents."""
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_embedding(query, tenant_id)
            
            # Search vector index
            results = await self.vector_indexer.search_documents(
                query=query,
                query_embedding=query_embedding,
                tenant_id=tenant_id,
                limit=limit,
                filters=filters
            )
            
            # Format results with relevance scores
            formatted_results = []
            for result in results:
                formatted_results.append({
                    "doc_id": result["doc_id"],
                    "content": result["content"],
                    "metadata": result["metadata"],
                    "relevance_score": 1.0 - result["distance"],  # Convert distance to relevance
                    "snippet": self._extract_snippet(result["content"], query)
                })
            
            logger.info("Knowledge search completed", 
                       query=query, 
                       result_count=len(formatted_results),
                       tenant_id=tenant_id)
            
            return formatted_results
            
        except Exception as e:
            logger.error("Knowledge search failed", 
                        query=query, 
                        tenant_id=tenant_id, 
                        error=str(e))
            return []
    
    async def get_document(
        self,
        doc_id: str,
        tenant_id: UUID
    ) -> Optional[Dict[str, Any]]:
        """Get specific document by ID."""
        try:
            # Search for document with exact ID match
            results = await self.vector_indexer.search_documents(
                query="",  # Empty query to get all
                query_embedding=[0.0] * 1536,  # Dummy embedding
                tenant_id=tenant_id,
                limit=1,
                filters={"doc_id": doc_id}
            )
            
            if results:
                result = results[0]
                return {
                    "doc_id": result["doc_id"],
                    "content": result["content"],
                    "metadata": result["metadata"]
                }
            
            return None
            
        except Exception as e:
            logger.error("Failed to get document", 
                        doc_id=doc_id, 
                        tenant_id=tenant_id, 
                        error=str(e))
            return None
    
    async def add_document(
        self,
        doc_id: str,
        tenant_id: UUID,
        content: str,
        metadata: Dict[str, Any]
    ) -> bool:
        """Add document to knowledge base."""
        try:
            # Generate embedding
            embedding = await self.embedding_service.generate_embedding(content, tenant_id)
            
            # Index document
            success = await self.vector_indexer.index_document(
                doc_id=doc_id,
                tenant_id=tenant_id,
                content=content,
                metadata=metadata,
                embedding=embedding
            )
            
            if success:
                logger.info("Document added to knowledge base", 
                           doc_id=doc_id, 
                           tenant_id=tenant_id)
            
            return success
            
        except Exception as e:
            logger.error("Failed to add document to knowledge base", 
                        doc_id=doc_id, 
                        tenant_id=tenant_id, 
                        error=str(e))
            return False
    
    async def remove_document(
        self,
        doc_id: str,
        tenant_id: UUID
    ) -> bool:
        """Remove document from knowledge base."""
        try:
            success = await self.vector_indexer.delete_document(doc_id, tenant_id)
            
            if success:
                logger.info("Document removed from knowledge base", 
                           doc_id=doc_id, 
                           tenant_id=tenant_id)
            
            return success
            
        except Exception as e:
            logger.error("Failed to remove document from knowledge base", 
                        doc_id=doc_id, 
                        tenant_id=tenant_id, 
                        error=str(e))
            return False
    
    async def get_tenant_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get knowledge base statistics for tenant."""
        try:
            # Get document count
            doc_count = await self.vector_indexer.get_document_count(tenant_id)
            
            # Get collection stats
            collection_stats = await self.vector_indexer.get_collection_stats()
            
            return {
                "tenant_id": str(tenant_id),
                "document_count": doc_count,
                "total_documents": collection_stats.get("total_documents", 0),
                "embedding_dimension": collection_stats.get("embedding_dimension", 1536)
            }
            
        except Exception as e:
            logger.error("Failed to get tenant stats", 
                        tenant_id=tenant_id, 
                        error=str(e))
            return {}
    
    def _extract_snippet(self, content: str, query: str, max_length: int = 200) -> str:
        """Extract relevant snippet from content."""
        try:
            # Find query terms in content (case-insensitive)
            query_lower = query.lower()
            content_lower = content.lower()
            
            # Find first occurrence of query
            query_index = content_lower.find(query_lower)
            
            if query_index == -1:
                # If query not found, return beginning of content
                return content[:max_length] + "..." if len(content) > max_length else content
            
            # Extract snippet around query
            start = max(0, query_index - max_length // 2)
            end = min(len(content), query_index + max_length // 2)
            
            snippet = content[start:end]
            
            # Add ellipsis if truncated
            if start > 0:
                snippet = "..." + snippet
            if end < len(content):
                snippet = snippet + "..."
            
            return snippet
            
        except Exception as e:
            logger.error("Failed to extract snippet", error=str(e))
            return content[:max_length] + "..." if len(content) > max_length else content
