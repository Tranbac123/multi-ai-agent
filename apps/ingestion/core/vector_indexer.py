"""Vector indexer for document storage and retrieval."""

import asyncio
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID
import structlog
import chromadb
from chromadb.config import Settings

logger = structlog.get_logger(__name__)


class VectorIndexer:
    """Vector indexer using ChromaDB for document storage and retrieval."""
    
    def __init__(self, host: str = "localhost", port: int = 8000):
        self.client = chromadb.HttpClient(
            host=host,
            port=port,
            settings=Settings(allow_reset=True)
        )
        self.collection_name = "documents"
        self.collection = None
    
    async def initialize(self):
        """Initialize the vector indexer."""
        try:
            # Get or create collection
            try:
                self.collection = self.client.get_collection(self.collection_name)
                logger.info("Connected to existing collection", collection=self.collection_name)
            except Exception:
                self.collection = self.client.create_collection(
                    name=self.collection_name,
                    metadata={"description": "Document embeddings for multi-tenant AIaaS"}
                )
                logger.info("Created new collection", collection=self.collection_name)
                
        except Exception as e:
            logger.error("Failed to initialize vector indexer", error=str(e))
            raise
    
    async def index_document(
        self,
        doc_id: str,
        tenant_id: UUID,
        content: str,
        metadata: Dict[str, Any],
        embedding: List[float]
    ) -> bool:
        """Index document with embedding."""
        try:
            if not self.collection:
                await self.initialize()
            
            # Prepare document data
            document_data = {
                "ids": [f"{tenant_id}:{doc_id}"],
                "embeddings": [embedding],
                "documents": [content],
                "metadatas": [{
                    **metadata,
                    "tenant_id": str(tenant_id),
                    "doc_id": doc_id
                }]
            }
            
            # Add to collection
            self.collection.add(**document_data)
            
            logger.info("Document indexed", 
                       doc_id=doc_id, 
                       tenant_id=tenant_id,
                       content_length=len(content))
            
            return True
            
        except Exception as e:
            logger.error("Failed to index document", 
                        doc_id=doc_id, 
                        tenant_id=tenant_id, 
                        error=str(e))
            return False
    
    async def search_documents(
        self,
        query: str,
        query_embedding: List[float],
        tenant_id: UUID,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Search documents by query."""
        try:
            if not self.collection:
                await self.initialize()
            
            # Prepare search parameters
            search_params = {
                "query_embeddings": [query_embedding],
                "n_results": limit,
                "where": {
                    "tenant_id": str(tenant_id)
                }
            }
            
            # Add additional filters
            if filters:
                search_params["where"].update(filters)
            
            # Search collection
            results = self.collection.query(**search_params)
            
            # Format results
            documents = []
            if results["ids"] and results["ids"][0]:
                for i, doc_id in enumerate(results["ids"][0]):
                    documents.append({
                        "doc_id": doc_id.split(":", 1)[1] if ":" in doc_id else doc_id,
                        "content": results["documents"][0][i],
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if "distances" in results else 0.0
                    })
            
            logger.info("Document search completed", 
                       query_length=len(query), 
                       result_count=len(documents),
                       tenant_id=tenant_id)
            
            return documents
            
        except Exception as e:
            logger.error("Failed to search documents", 
                        query=query, 
                        tenant_id=tenant_id, 
                        error=str(e))
            return []
    
    async def delete_document(
        self,
        doc_id: str,
        tenant_id: UUID
    ) -> bool:
        """Delete document from index."""
        try:
            if not self.collection:
                await self.initialize()
            
            # Delete from collection
            self.collection.delete(
                ids=[f"{tenant_id}:{doc_id}"],
                where={"tenant_id": str(tenant_id)}
            )
            
            logger.info("Document deleted from index", 
                       doc_id=doc_id, 
                       tenant_id=tenant_id)
            
            return True
            
        except Exception as e:
            logger.error("Failed to delete document from index", 
                        doc_id=doc_id, 
                        tenant_id=tenant_id, 
                        error=str(e))
            return False
    
    async def get_document_count(self, tenant_id: UUID) -> int:
        """Get document count for tenant."""
        try:
            if not self.collection:
                await self.initialize()
            
            # Count documents for tenant
            results = self.collection.get(
                where={"tenant_id": str(tenant_id)},
                include=["metadatas"]
            )
            
            count = len(results["ids"]) if results["ids"] else 0
            
            logger.debug("Document count retrieved", 
                        tenant_id=tenant_id, 
                        count=count)
            
            return count
            
        except Exception as e:
            logger.error("Failed to get document count", 
                        tenant_id=tenant_id, 
                        error=str(e))
            return 0
    
    async def get_collection_stats(self) -> Dict[str, Any]:
        """Get collection statistics."""
        try:
            if not self.collection:
                await self.initialize()
            
            # Get collection info
            collection_info = self.collection.get()
            
            stats = {
                "total_documents": len(collection_info["ids"]) if collection_info["ids"] else 0,
                "collection_name": self.collection_name,
                "embedding_dimension": 1536  # Default for text-embedding-ada-002
            }
            
            # Count by tenant
            tenant_counts = {}
            if collection_info["metadatas"]:
                for metadata in collection_info["metadatas"]:
                    tenant_id = metadata.get("tenant_id", "unknown")
                    tenant_counts[tenant_id] = tenant_counts.get(tenant_id, 0) + 1
            
            stats["tenant_counts"] = tenant_counts
            
            logger.info("Collection stats retrieved", stats=stats)
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get collection stats", error=str(e))
            return {}
    
    async def reset_collection(self) -> bool:
        """Reset collection (delete all documents)."""
        try:
            if not self.collection:
                await self.initialize()
            
            # Delete all documents
            self.collection.delete(where={})
            
            logger.info("Collection reset completed")
            
            return True
            
        except Exception as e:
            logger.error("Failed to reset collection", error=str(e))
            return False
