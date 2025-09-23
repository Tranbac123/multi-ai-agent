import asyncio
import numpy as np
from typing import List, Optional
import httpx
from .settings import settings

class EmbeddingService:
    def __init__(self):
        self.model = settings.embedding_model
        self.dimensions = settings.embedding_dimensions
        
    async def get_embedding(self, text: str) -> List[float]:
        """Get embedding for text using the configured model"""
        # For demo purposes, using a simple hash-based embedding
        # In production, this should call your actual embedding service
        return await self._mock_embedding(text)
    
    async def _mock_embedding(self, text: str) -> List[float]:
        """Mock embedding generation for demo purposes"""
        # Create a deterministic but varied embedding based on text content
        np.random.seed(hash(text) % (2**32))
        embedding = np.random.normal(0, 1, self.dimensions).tolist()
        
        # Normalize to unit vector
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = (np.array(embedding) / norm).tolist()
        
        return embedding
    
    async def _openai_embedding(self, text: str) -> List[float]:
        """Get embedding from OpenAI API"""
        # This would be used in production
        api_key = "your-openai-key"  # Should come from env/secrets
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": self.model,
            "input": text[:settings.max_text_length]  # Truncate if too long
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/embeddings",
                headers=headers,
                json=payload,
                timeout=30
            )
            response.raise_for_status()
            data = response.json()
            
        return data["data"][0]["embedding"]
    
    def cosine_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """Calculate cosine similarity between two embeddings"""
        if len(embedding1) != len(embedding2):
            raise ValueError("Embeddings must have the same dimensions")
        
        vec1 = np.array(embedding1)
        vec2 = np.array(embedding2)
        
        # Calculate cosine similarity
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return float(dot_product / (norm1 * norm2))
    
    def find_most_similar(
        self, 
        query_embedding: List[float], 
        embeddings: List[List[float]], 
        threshold: float = 0.8
    ) -> List[tuple]:
        """Find most similar embeddings above threshold"""
        similarities = []
        
        for i, emb in enumerate(embeddings):
            similarity = self.cosine_similarity(query_embedding, emb)
            if similarity >= threshold:
                similarities.append((i, similarity))
        
        # Sort by similarity descending
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities

