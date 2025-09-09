"""Knowledge service for permissioned retrieval."""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
import structlog
import redis.asyncio as redis

from apps.ingestion.core.vector_indexer import VectorIndexer
from apps.ingestion.core.embedding_service import EmbeddingService

logger = structlog.get_logger(__name__)


class KnowledgeService:
    """Service for permissioned knowledge retrieval."""
    
    def __init__(
        self,
        redis_client: redis.Redis,
        embedding_service: EmbeddingService,
        vector_indexer: VectorIndexer
    ):
        self.redis = redis_client
        self.embedding_service = embedding_service
        self.vector_indexer = vector_indexer
    
    async def search_knowledge(
        self,
        query: str,
        tenant_id: str,
        user_id: Optional[str] = None,
        roles: Optional[List[str]] = None,
        top_k: int = 10,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """Search knowledge base with permission filtering."""
        try:
            # Generate query embedding
            query_embedding = await self.embedding_service.generate_query_embedding(
                query, tenant_id
            )
            
            # Search for similar chunks
            similar_chunks = await self.vector_indexer.search_similar(
                query_embedding, tenant_id, top_k * 2, threshold  # Get more to filter
            )
            
            # Filter by permissions
            filtered_chunks = await self._filter_by_permissions(
                similar_chunks, tenant_id, user_id, roles
            )
            
            # Return top-k results
            result = filtered_chunks[:top_k]
            
            logger.info(
                "Knowledge search completed",
                tenant_id=tenant_id,
                user_id=user_id,
                query_length=len(query),
                results_count=len(result),
                total_candidates=len(similar_chunks)
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Knowledge search failed",
                error=str(e),
                tenant_id=tenant_id,
                user_id=user_id,
                query=query
            )
            return []
    
    async def _filter_by_permissions(
        self,
        chunks: List[Dict[str, Any]],
        tenant_id: str,
        user_id: Optional[str],
        roles: Optional[List[str]]
    ) -> List[Dict[str, Any]]:
        """Filter chunks by user permissions."""
        if not chunks:
            return []
        
        filtered_chunks = []
        
        for chunk in chunks:
            # Get chunk permissions
            chunk_permissions = await self._get_chunk_permissions(
                chunk['chunk_id'], tenant_id
            )
            
            # Check if user has access
            if await self._has_access(chunk_permissions, user_id, roles):
                filtered_chunks.append(chunk)
        
        return filtered_chunks
    
    async def _get_chunk_permissions(
        self,
        chunk_id: str,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Get permissions for a chunk."""
        try:
            chunk_key = f"chunk:{tenant_id}:{chunk_id}"
            chunk_data = await self.redis.hgetall(chunk_key)
            
            if not chunk_data:
                return {}
            
            # Parse permissions from metadata
            metadata = chunk_data.get('metadata', '{}')
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)
            
            return metadata.get('permissions', {})
            
        except Exception as e:
            logger.error(
                "Failed to get chunk permissions",
                error=str(e),
                chunk_id=chunk_id,
                tenant_id=tenant_id
            )
            return {}
    
    async def _has_access(
        self,
        permissions: Dict[str, Any],
        user_id: Optional[str],
        roles: Optional[List[str]]
    ) -> bool:
        """Check if user has access to chunk."""
        if not permissions:
            # No permissions set, allow access
            return True
        
        # Check user-specific permissions
        if user_id and 'users' in permissions:
            if user_id in permissions['users']:
                return True
        
        # Check role-based permissions
        if roles and 'roles' in permissions:
            for role in roles:
                if role in permissions['roles']:
                    return True
        
        # Check public access
        if permissions.get('public', False):
            return True
        
        # Check tenant access
        if permissions.get('tenant_access', False):
            return True
        
        return False
    
    async def get_document_chunks(
        self,
        doc_id: str,
        tenant_id: str,
        user_id: Optional[str] = None,
        roles: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """Get all chunks for a document with permission filtering."""
        try:
            # Get document chunks
            doc_chunks = await self._get_document_chunks(doc_id, tenant_id)
            
            # Filter by permissions
            filtered_chunks = await self._filter_by_permissions(
                doc_chunks, tenant_id, user_id, roles
            )
            
            logger.info(
                "Document chunks retrieved",
                doc_id=doc_id,
                tenant_id=tenant_id,
                user_id=user_id,
                chunks_count=len(filtered_chunks)
            )
            
            return filtered_chunks
            
        except Exception as e:
            logger.error(
                "Failed to get document chunks",
                error=str(e),
                doc_id=doc_id,
                tenant_id=tenant_id,
                user_id=user_id
            )
            return []
    
    async def _get_document_chunks(
        self,
        doc_id: str,
        tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Get all chunks for a document."""
        try:
            # Get chunk IDs for document
            doc_chunks_key = f"doc_chunks:{tenant_id}:{doc_id}"
            chunk_ids = await self.redis.smembers(doc_chunks_key)
            
            if not chunk_ids:
                return []
            
            chunks = []
            for chunk_id in chunk_ids:
                chunk_id = chunk_id.decode('utf-8')
                
                # Get chunk data
                chunk_key = f"chunk:{tenant_id}:{chunk_id}"
                chunk_data = await self.redis.hgetall(chunk_key)
                
                if chunk_data:
                    chunks.append({
                        'chunk_id': chunk_id,
                        'content': chunk_data.get('content', ''),
                        'start_index': int(chunk_data.get('start_index', 0)),
                        'end_index': int(chunk_data.get('end_index', 0)),
                        'chunk_index': int(chunk_data.get('chunk_index', 0)),
                        'metadata': chunk_data.get('metadata', {})
                    })
            
            # Sort by chunk index
            chunks.sort(key=lambda x: x.get('chunk_index', 0))
            
            return chunks
            
        except Exception as e:
            logger.error(
                "Failed to get document chunks",
                error=str(e),
                doc_id=doc_id,
                tenant_id=tenant_id
            )
            return []
    
    async def update_chunk_permissions(
        self,
        chunk_id: str,
        tenant_id: str,
        permissions: Dict[str, Any]
    ) -> bool:
        """Update permissions for a chunk."""
        try:
            chunk_key = f"chunk:{tenant_id}:{chunk_id}"
            
            # Get current metadata
            chunk_data = await self.redis.hgetall(chunk_key)
            if not chunk_data:
                return False
            
            # Update permissions in metadata
            metadata = chunk_data.get('metadata', '{}')
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)
            
            metadata['permissions'] = permissions
            
            # Update chunk data
            await self.redis.hset(chunk_key, 'metadata', json.dumps(metadata))
            
            logger.info(
                "Chunk permissions updated",
                chunk_id=chunk_id,
                tenant_id=tenant_id,
                permissions=permissions
            )
            
            return True
            
        except Exception as e:
            logger.error(
                "Failed to update chunk permissions",
                error=str(e),
                chunk_id=chunk_id,
                tenant_id=tenant_id
            )
            return False
    
    async def get_tenant_knowledge_stats(
        self,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Get knowledge base statistics for a tenant."""
        try:
            # Get index stats
            index_stats = await self.vector_indexer.get_index_stats(tenant_id)
            
            # Get document count
            doc_count = await self._get_document_count(tenant_id)
            
            # Get chunk count by document
            doc_chunks = await self._get_document_chunks_count(tenant_id)
            
            return {
                'tenant_id': tenant_id,
                'total_chunks': index_stats['chunk_count'],
                'total_documents': doc_count,
                'documents_chunks': doc_chunks,
                'memory_usage_bytes': index_stats['memory_usage_bytes'],
                'timestamp': time.time()
            }
            
        except Exception as e:
            logger.error(
                "Failed to get tenant knowledge stats",
                error=str(e),
                tenant_id=tenant_id
            )
            return {
                'tenant_id': tenant_id,
                'total_chunks': 0,
                'total_documents': 0,
                'documents_chunks': {},
                'memory_usage_bytes': 0,
                'timestamp': time.time()
            }
    
    async def _get_document_count(self, tenant_id: str) -> int:
        """Get total document count for tenant."""
        try:
            # Get all document keys
            pattern = f"doc_chunks:{tenant_id}:*"
            keys = await self.redis.keys(pattern)
            return len(keys)
        except Exception as e:
            logger.error("Failed to get document count", error=str(e), tenant_id=tenant_id)
            return 0
    
    async def _get_document_chunks_count(self, tenant_id: str) -> Dict[str, int]:
        """Get chunk count per document for tenant."""
        try:
            doc_chunks = {}
            pattern = f"doc_chunks:{tenant_id}:*"
            keys = await self.redis.keys(pattern)
            
            for key in keys:
                doc_id = key.decode('utf-8').split(':')[-1]
                chunk_count = await self.redis.scard(key)
                doc_chunks[doc_id] = chunk_count
            
            return doc_chunks
        except Exception as e:
            logger.error("Failed to get document chunks count", error=str(e), tenant_id=tenant_id)
            return {}