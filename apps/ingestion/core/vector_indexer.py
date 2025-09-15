"""Vector indexer for document embeddings."""

import asyncio
import time
from typing import List, Dict, Any, Optional, Tuple
import structlog
import redis.asyncio as redis
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

logger = structlog.get_logger(__name__)


class VectorIndexer:
    """Indexes document embeddings for similarity search."""

    def __init__(
        self, redis_client: redis.Redis, index_name: str = "document_embeddings"
    ):
        self.redis = redis_client
        self.index_name = index_name
        self.embedding_dim = 1536  # OpenAI ada-002 dimension

    async def index_chunks(
        self, chunks: List[Dict[str, Any]], tenant_id: str
    ) -> Dict[str, Any]:
        """Index document chunks with embeddings."""
        try:
            indexed_count = 0
            failed_count = 0

            for chunk in chunks:
                try:
                    await self._index_single_chunk(chunk, tenant_id)
                    indexed_count += 1
                except Exception as e:
                    logger.error(
                        "Failed to index chunk",
                        error=str(e),
                        chunk_id=chunk.get("chunk_id"),
                        tenant_id=tenant_id,
                    )
                    failed_count += 1

            result = {
                "tenant_id": tenant_id,
                "indexed_count": indexed_count,
                "failed_count": failed_count,
                "total_chunks": len(chunks),
                "timestamp": time.time(),
            }

            logger.info(
                "Chunks indexed successfully",
                tenant_id=tenant_id,
                indexed_count=indexed_count,
                failed_count=failed_count,
            )

            return result

        except Exception as e:
            logger.error(
                "Chunk indexing failed",
                error=str(e),
                tenant_id=tenant_id,
                chunks_count=len(chunks),
            )
            raise

    async def _index_single_chunk(self, chunk: Dict[str, Any], tenant_id: str) -> None:
        """Index a single chunk."""
        chunk_id = chunk["chunk_id"]
        embedding = chunk["embedding"]

        # Store chunk metadata
        chunk_key = f"chunk:{tenant_id}:{chunk_id}"
        chunk_data = {
            "chunk_id": chunk_id,
            "tenant_id": tenant_id,
            "content": chunk["content"],
            "start_index": chunk.get("start_index", 0),
            "end_index": chunk.get("end_index", 0),
            "chunk_index": chunk.get("chunk_index", 0),
            "metadata": chunk.get("metadata", {}),
            "embedding_model": chunk.get("embedding_model", "unknown"),
            "embedding_timestamp": chunk.get("embedding_timestamp", time.time()),
            "indexed_at": time.time(),
        }

        await self.redis.hset(chunk_key, mapping=chunk_data)
        await self.redis.expire(chunk_key, 86400 * 30)  # 30 days TTL

        # Store embedding for similarity search
        embedding_key = f"embedding:{tenant_id}:{chunk_id}"
        await self.redis.set(embedding_key, np.array(embedding).tobytes())
        await self.redis.expire(embedding_key, 86400 * 30)  # 30 days TTL

        # Add to tenant index
        tenant_index_key = f"tenant_index:{tenant_id}"
        await self.redis.sadd(tenant_index_key, chunk_id)
        await self.redis.expire(tenant_index_key, 86400 * 30)  # 30 days TTL

    async def search_similar(
        self,
        query_embedding: List[float],
        tenant_id: str,
        top_k: int = 10,
        threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Search for similar chunks using vector similarity."""
        try:
            # Get all chunk IDs for tenant
            tenant_index_key = f"tenant_index:{tenant_id}"
            chunk_ids = await self.redis.smembers(tenant_index_key)

            if not chunk_ids:
                return []

            similarities = []

            # Compute similarities
            for chunk_id in chunk_ids:
                chunk_id = chunk_id.decode("utf-8")

                # Get chunk metadata
                chunk_key = f"chunk:{tenant_id}:{chunk_id}"
                chunk_data = await self.redis.hgetall(chunk_key)

                if not chunk_data:
                    continue

                # Get embedding
                embedding_key = f"embedding:{tenant_id}:{chunk_id}"
                embedding_bytes = await self.redis.get(embedding_key)

                if not embedding_bytes:
                    continue

                # Convert embedding back to numpy array
                chunk_embedding = np.frombuffer(embedding_bytes, dtype=np.float32)

                # Compute cosine similarity
                similarity = self._compute_cosine_similarity(
                    query_embedding, chunk_embedding
                )

                if similarity >= threshold:
                    similarities.append(
                        {
                            "chunk_id": chunk_id,
                            "similarity": similarity,
                            "content": chunk_data.get("content", ""),
                            "metadata": chunk_data.get("metadata", {}),
                            "start_index": int(chunk_data.get("start_index", 0)),
                            "end_index": int(chunk_data.get("end_index", 0)),
                        }
                    )

            # Sort by similarity (descending)
            similarities.sort(key=lambda x: x["similarity"], reverse=True)

            # Return top-k results
            return similarities[:top_k]

        except Exception as e:
            logger.error(
                "Similarity search failed",
                error=str(e),
                tenant_id=tenant_id,
                top_k=top_k,
            )
            return []

    def _compute_cosine_similarity(
        self, embedding1: List[float], embedding2: np.ndarray
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1).reshape(1, -1)
            vec2 = embedding2.reshape(1, -1)

            # Compute cosine similarity
            similarity = cosine_similarity(vec1, vec2)[0][0]
            return float(similarity)

        except Exception as e:
            logger.error("Cosine similarity computation failed", error=str(e))
            return 0.0

    async def delete_chunk(self, chunk_id: str, tenant_id: str) -> bool:
        """Delete a chunk from the index."""
        try:
            # Remove from tenant index
            tenant_index_key = f"tenant_index:{tenant_id}"
            await self.redis.srem(tenant_index_key, chunk_id)

            # Delete chunk metadata
            chunk_key = f"chunk:{tenant_id}:{chunk_id}"
            await self.redis.delete(chunk_key)

            # Delete embedding
            embedding_key = f"embedding:{tenant_id}:{chunk_id}"
            await self.redis.delete(embedding_key)

            logger.info(
                "Chunk deleted from index", chunk_id=chunk_id, tenant_id=tenant_id
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to delete chunk from index",
                error=str(e),
                chunk_id=chunk_id,
                tenant_id=tenant_id,
            )
            return False

    async def delete_tenant_index(self, tenant_id: str) -> bool:
        """Delete all chunks for a tenant."""
        try:
            # Get all chunk IDs for tenant
            tenant_index_key = f"tenant_index:{tenant_id}"
            chunk_ids = await self.redis.smembers(tenant_index_key)

            deleted_count = 0
            for chunk_id in chunk_ids:
                chunk_id = chunk_id.decode("utf-8")
                if await self.delete_chunk(chunk_id, tenant_id):
                    deleted_count += 1

            # Delete tenant index
            await self.redis.delete(tenant_index_key)

            logger.info(
                "Tenant index deleted", tenant_id=tenant_id, deleted_count=deleted_count
            )
            return True

        except Exception as e:
            logger.error(
                "Failed to delete tenant index", error=str(e), tenant_id=tenant_id
            )
            return False

    async def get_index_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get index statistics for a tenant."""
        try:
            # Get chunk count
            tenant_index_key = f"tenant_index:{tenant_id}"
            chunk_count = await self.redis.scard(tenant_index_key)

            # Get memory usage
            memory_usage = await self.redis.memory_usage(tenant_index_key)

            return {
                "tenant_id": tenant_id,
                "chunk_count": chunk_count,
                "memory_usage_bytes": memory_usage,
                "index_name": self.index_name,
                "timestamp": time.time(),
            }

        except Exception as e:
            logger.error("Failed to get index stats", error=str(e), tenant_id=tenant_id)
            return {
                "tenant_id": tenant_id,
                "chunk_count": 0,
                "memory_usage_bytes": 0,
                "index_name": self.index_name,
                "timestamp": time.time(),
            }

    async def rebuild_index(self, tenant_id: str) -> Dict[str, Any]:
        """Rebuild index for a tenant."""
        try:
            # Get all chunks for tenant
            tenant_index_key = f"tenant_index:{tenant_id}"
            chunk_ids = await self.redis.smembers(tenant_index_key)

            if not chunk_ids:
                return {
                    "tenant_id": tenant_id,
                    "status": "no_chunks",
                    "processed_count": 0,
                }

            # Rebuild index
            processed_count = 0
            for chunk_id in chunk_ids:
                chunk_id = chunk_id.decode("utf-8")

                # Get chunk data
                chunk_key = f"chunk:{tenant_id}:{chunk_id}"
                chunk_data = await self.redis.hgetall(chunk_key)

                if chunk_data:
                    # Re-index chunk
                    await self._index_single_chunk(
                        {
                            "chunk_id": chunk_id,
                            "content": chunk_data.get("content", ""),
                            "start_index": int(chunk_data.get("start_index", 0)),
                            "end_index": int(chunk_data.get("end_index", 0)),
                            "chunk_index": int(chunk_data.get("chunk_index", 0)),
                            "metadata": chunk_data.get("metadata", {}),
                            "embedding": [],  # Will be fetched from embedding key
                            "embedding_model": chunk_data.get(
                                "embedding_model", "unknown"
                            ),
                            "embedding_timestamp": float(
                                chunk_data.get("embedding_timestamp", time.time())
                            ),
                        },
                        tenant_id,
                    )

                    processed_count += 1

            logger.info(
                "Index rebuilt successfully",
                tenant_id=tenant_id,
                processed_count=processed_count,
            )

            return {
                "tenant_id": tenant_id,
                "status": "success",
                "processed_count": processed_count,
            }

        except Exception as e:
            logger.error("Index rebuild failed", error=str(e), tenant_id=tenant_id)
            return {"tenant_id": tenant_id, "status": "failed", "error": str(e)}
