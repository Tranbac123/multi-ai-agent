"""Embedding service for document vectorization."""

import asyncio
from typing import List, Dict, Any, Optional
from uuid import UUID
import structlog
import openai
from openai import AsyncOpenAI

logger = structlog.get_logger(__name__)


class EmbeddingService:
    """Service for generating document embeddings."""
    
    def __init__(self, api_key: str, model: str = "text-embedding-ada-002"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.batch_size = 100  # Process embeddings in batches
        self.max_tokens = 8191  # OpenAI embedding limit
    
    async def generate_embeddings(
        self, 
        texts: List[str], 
        tenant_id: UUID
    ) -> List[List[float]]:
        """Generate embeddings for list of texts."""
        try:
            # Split texts into batches
            batches = self._split_into_batches(texts)
            all_embeddings = []
            
            for batch in batches:
                embeddings = await self._process_batch(batch, tenant_id)
                all_embeddings.extend(embeddings)
            
            logger.info("Embeddings generated", 
                       text_count=len(texts), 
                       embedding_count=len(all_embeddings),
                       tenant_id=tenant_id)
            
            return all_embeddings
            
        except Exception as e:
            logger.error("Failed to generate embeddings", 
                        text_count=len(texts), 
                        error=str(e))
            raise
    
    async def generate_embedding(
        self, 
        text: str, 
        tenant_id: UUID
    ) -> List[float]:
        """Generate embedding for single text."""
        try:
            # Truncate text if too long
            if len(text) > self.max_tokens:
                text = text[:self.max_tokens]
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=text
            )
            
            embedding = response.data[0].embedding
            
            logger.debug("Embedding generated", 
                        text_length=len(text), 
                        embedding_dim=len(embedding),
                        tenant_id=tenant_id)
            
            return embedding
            
        except Exception as e:
            logger.error("Failed to generate embedding", 
                        text_length=len(text), 
                        error=str(e))
            raise
    
    async def chunk_document(
        self, 
        content: str, 
        chunk_size: int = 1000, 
        overlap: int = 200
    ) -> List[Dict[str, Any]]:
        """Chunk document into smaller pieces for embedding."""
        try:
            chunks = []
            start = 0
            
            while start < len(content):
                end = start + chunk_size
                chunk_text = content[start:end]
                
                # Try to break at sentence boundary
                if end < len(content):
                    last_period = chunk_text.rfind('.')
                    last_newline = chunk_text.rfind('\n')
                    break_point = max(last_period, last_newline)
                    
                    if break_point > start + chunk_size // 2:
                        end = start + break_point + 1
                        chunk_text = content[start:end]
                
                chunks.append({
                    "text": chunk_text.strip(),
                    "start": start,
                    "end": end,
                    "length": len(chunk_text)
                })
                
                start = end - overlap
            
            logger.info("Document chunked", 
                       original_length=len(content), 
                       chunk_count=len(chunks))
            
            return chunks
            
        except Exception as e:
            logger.error("Failed to chunk document", 
                        content_length=len(content), 
                        error=str(e))
            raise
    
    def _split_into_batches(self, texts: List[str]) -> List[List[str]]:
        """Split texts into batches for processing."""
        batches = []
        current_batch = []
        current_length = 0
        
        for text in texts:
            text_length = len(text)
            
            # If adding this text would exceed batch size, start new batch
            if current_length + text_length > self.batch_size and current_batch:
                batches.append(current_batch)
                current_batch = [text]
                current_length = text_length
            else:
                current_batch.append(text)
                current_length += text_length
        
        if current_batch:
            batches.append(current_batch)
        
        return batches
    
    async def _process_batch(
        self, 
        batch: List[str], 
        tenant_id: UUID
    ) -> List[List[float]]:
        """Process a batch of texts for embedding."""
        try:
            # Truncate texts if necessary
            truncated_batch = [text[:self.max_tokens] for text in batch]
            
            response = await self.client.embeddings.create(
                model=self.model,
                input=truncated_batch
            )
            
            embeddings = [data.embedding for data in response.data]
            
            logger.debug("Batch processed", 
                        batch_size=len(batch), 
                        tenant_id=tenant_id)
            
            return embeddings
            
        except Exception as e:
            logger.error("Batch processing failed", 
                        batch_size=len(batch), 
                        error=str(e))
            raise
    
    async def get_embedding_dimension(self) -> int:
        """Get the dimension of embeddings."""
        try:
            # Generate a test embedding to get dimension
            test_embedding = await self.generate_embedding("test", UUID("00000000-0000-0000-0000-000000000000"))
            return len(test_embedding)
        except Exception as e:
            logger.error("Failed to get embedding dimension", error=str(e))
            return 1536  # Default for text-embedding-ada-002
