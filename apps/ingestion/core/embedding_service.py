"""Embedding service for document chunks."""

import asyncio
import time
from typing import List, Dict, Any, Optional
import structlog
import openai
import numpy as np
from sentence_transformers import SentenceTransformer

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Service for generating embeddings for document chunks."""

    def __init__(
        self,
        openai_api_key: str,
        model_name: str = "text-embedding-ada-002",
        batch_size: int = 100,
        max_retries: int = 3,
    ):
        self.openai_api_key = openai_api_key
        self.model_name = model_name
        self.batch_size = batch_size
        self.max_retries = max_retries

        # Initialize OpenAI client
        openai.api_key = openai_api_key

        # Initialize local embedding model as fallback
        self.local_model = None
        self._init_local_model()

    def _init_local_model(self):
        """Initialize local embedding model as fallback."""
        try:
            self.local_model = SentenceTransformer("all-MiniLM-L6-v2")
            logger.info("Local embedding model initialized")
        except Exception as e:
            logger.warning("Failed to initialize local embedding model", error=str(e))

    async def generate_embeddings(
        self, chunks: List[Dict[str, Any]], tenant_id: str
    ) -> List[Dict[str, Any]]:
        """Generate embeddings for document chunks."""
        try:
            # Extract text content from chunks
            texts = [chunk["content"] for chunk in chunks]

            # Generate embeddings in batches
            embeddings = await self._generate_embeddings_batch(texts, tenant_id)

            # Combine chunks with embeddings
            result = []
            for i, chunk in enumerate(chunks):
                chunk_with_embedding = chunk.copy()
                chunk_with_embedding["embedding"] = embeddings[i]
                chunk_with_embedding["embedding_model"] = self.model_name
                chunk_with_embedding["embedding_timestamp"] = time.time()
                result.append(chunk_with_embedding)

            logger.info(
                "Embeddings generated successfully",
                tenant_id=tenant_id,
                chunks_count=len(chunks),
                model=self.model_name,
            )

            return result

        except Exception as e:
            logger.error(
                "Embedding generation failed",
                error=str(e),
                tenant_id=tenant_id,
                chunks_count=len(chunks),
            )
            raise

    async def _generate_embeddings_batch(
        self, texts: List[str], tenant_id: str
    ) -> List[List[float]]:
        """Generate embeddings for a batch of texts."""
        try:
            # Try OpenAI first
            embeddings = await self._generate_openai_embeddings(texts, tenant_id)
            return embeddings

        except Exception as e:
            logger.warning(
                "OpenAI embedding failed, trying local model",
                error=str(e),
                tenant_id=tenant_id,
            )

            # Fallback to local model
            try:
                embeddings = await self._generate_local_embeddings(texts, tenant_id)
                return embeddings
            except Exception as e2:
                logger.error(
                    "Local embedding also failed", error=str(e2), tenant_id=tenant_id
                )
                raise

    async def _generate_openai_embeddings(
        self, texts: List[str], tenant_id: str
    ) -> List[List[float]]:
        """Generate embeddings using OpenAI API."""
        embeddings = []

        # Process in batches
        for i in range(0, len(texts), self.batch_size):
            batch_texts = texts[i : i + self.batch_size]

            for attempt in range(self.max_retries):
                try:
                    response = await openai.Embedding.acreate(
                        input=batch_texts, model=self.model_name
                    )

                    batch_embeddings = [item["embedding"] for item in response["data"]]
                    embeddings.extend(batch_embeddings)

                    # Rate limiting
                    await asyncio.sleep(0.1)
                    break

                except Exception as e:
                    if attempt == self.max_retries - 1:
                        raise

                    wait_time = 2**attempt  # Exponential backoff
                    logger.warning(
                        "OpenAI embedding attempt failed, retrying",
                        attempt=attempt + 1,
                        error=str(e),
                        wait_time=wait_time,
                    )
                    await asyncio.sleep(wait_time)

        return embeddings

    async def _generate_local_embeddings(
        self, texts: List[str], tenant_id: str
    ) -> List[List[float]]:
        """Generate embeddings using local model."""
        if not self.local_model:
            raise RuntimeError("Local embedding model not available")

        # Run in thread pool to avoid blocking
        loop = asyncio.get_event_loop()
        embeddings = await loop.run_in_executor(None, self.local_model.encode, texts)

        # Convert to list of lists
        return [embedding.tolist() for embedding in embeddings]

    async def generate_query_embedding(self, query: str, tenant_id: str) -> List[float]:
        """Generate embedding for a search query."""
        try:
            embeddings = await self._generate_embeddings_batch([query], tenant_id)
            return embeddings[0]

        except Exception as e:
            logger.error(
                "Query embedding generation failed",
                error=str(e),
                tenant_id=tenant_id,
                query=query,
            )
            raise

    async def compute_similarity(
        self, embedding1: List[float], embedding2: List[float]
    ) -> float:
        """Compute cosine similarity between two embeddings."""
        try:
            # Convert to numpy arrays
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            # Compute cosine similarity
            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            similarity = dot_product / (norm1 * norm2)
            return float(similarity)

        except Exception as e:
            logger.error("Similarity computation failed", error=str(e))
            return 0.0

    async def find_similar_chunks(
        self,
        query_embedding: List[float],
        chunk_embeddings: List[Dict[str, Any]],
        top_k: int = 10,
        threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Find most similar chunks to query embedding."""
        similarities = []

        for chunk in chunk_embeddings:
            similarity = await self.compute_similarity(
                query_embedding, chunk["embedding"]
            )

            if similarity >= threshold:
                similarities.append({"chunk": chunk, "similarity": similarity})

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x["similarity"], reverse=True)

        # Return top-k results
        return similarities[:top_k]

    async def get_embedding_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get embedding statistics for a tenant."""
        # This would typically query a database
        # For now, return mock stats
        return {
            "tenant_id": tenant_id,
            "total_embeddings": 0,
            "models_used": [self.model_name],
            "last_updated": time.time(),
        }
