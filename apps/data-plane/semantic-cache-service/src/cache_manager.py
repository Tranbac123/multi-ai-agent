import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
import redis.asyncio as redis
from .models import CacheEntry, CacheRequest, CacheResponse, CacheStats
from .embedding_service import EmbeddingService
from .settings import settings

class SemanticCacheManager:
    def __init__(self):
        self.redis_client = None
        self.embedding_service = EmbeddingService()
        
    async def connect(self):
        """Initialize Redis connection"""
        self.redis_client = redis.from_url(
            settings.redis_url,
            db=settings.redis_db,
            password=settings.redis_password,
            decode_responses=True
        )
    
    async def disconnect(self):
        """Close Redis connection"""
        if self.redis_client:
            await self.redis_client.close()
    
    def _cache_key(self, tenant_id: str, key: str) -> str:
        """Generate Redis key for cache entry"""
        return f"semantic_cache:{tenant_id}:{key}"
    
    def _embedding_key(self, tenant_id: str, key: str) -> str:
        """Generate Redis key for embedding storage"""
        return f"semantic_embeddings:{tenant_id}:{key}"
    
    def _tenant_keys_key(self, tenant_id: str) -> str:
        """Generate Redis key for tenant's cache keys list"""
        return f"tenant_keys:{tenant_id}"
    
    async def store(self, request: CacheRequest) -> bool:
        """Store content in semantic cache"""
        try:
            # Generate embedding for the content
            embedding = await self.embedding_service.get_embedding(request.content)
            
            # Calculate expiration
            ttl = request.ttl_seconds or settings.default_ttl_seconds
            ttl = min(ttl, settings.max_ttl_seconds)  # Cap at max TTL
            
            now = datetime.utcnow()
            expires_at = now + timedelta(seconds=ttl)
            
            # Create cache entry
            entry = CacheEntry(
                cache_key=request.cache_key,
                tenant_id=request.tenant_id,
                content=request.content,
                embedding=embedding,
                cached_at=now,
                expires_at=expires_at,
                metadata=request.metadata,
                hit_count=0
            )
            
            # Store in Redis
            cache_key = self._cache_key(request.tenant_id, request.cache_key)
            embedding_key = self._embedding_key(request.tenant_id, request.cache_key)
            tenant_keys_key = self._tenant_keys_key(request.tenant_id)
            
            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            
            # Store cache entry
            pipe.setex(cache_key, ttl, entry.model_dump_json())
            
            # Store embedding separately for efficient similarity search
            pipe.setex(embedding_key, ttl, json.dumps(embedding))
            
            # Add to tenant's keys set
            pipe.sadd(tenant_keys_key, request.cache_key)
            pipe.expire(tenant_keys_key, ttl)
            
            await pipe.execute()
            
            return True
            
        except Exception as e:
            print(f"Error storing cache entry: {e}")
            return False
    
    async def retrieve(self, tenant_id: str, query: str, similarity_threshold: Optional[float] = None) -> CacheResponse:
        """Retrieve content from semantic cache using similarity search"""
        threshold = similarity_threshold or settings.similarity_threshold
        
        try:
            # Generate embedding for query
            query_embedding = await self.embedding_service.get_embedding(query)
            
            # Get all cached embeddings for this tenant
            tenant_keys_key = self._tenant_keys_key(tenant_id)
            cache_keys = await self.redis_client.smembers(tenant_keys_key)
            
            if not cache_keys:
                return CacheResponse(found=False)
            
            # Find most similar cached content
            best_match = None
            best_similarity = 0.0
            
            for cache_key in cache_keys:
                embedding_key = self._embedding_key(tenant_id, cache_key)
                embedding_data = await self.redis_client.get(embedding_key)
                
                if not embedding_data:
                    continue
                
                try:
                    cached_embedding = json.loads(embedding_data)
                    similarity = self.embedding_service.cosine_similarity(
                        query_embedding, cached_embedding
                    )
                    
                    if similarity > best_similarity and similarity >= threshold:
                        best_similarity = similarity
                        best_match = cache_key
                        
                except (json.JSONDecodeError, ValueError):
                    continue
            
            if not best_match:
                return CacheResponse(found=False)
            
            # Retrieve the best matching cache entry
            cache_key = self._cache_key(tenant_id, best_match)
            entry_data = await self.redis_client.get(cache_key)
            
            if not entry_data:
                return CacheResponse(found=False)
            
            try:
                entry = CacheEntry.model_validate_json(entry_data)
                
                # Update hit count
                entry.hit_count += 1
                ttl = await self.redis_client.ttl(cache_key)
                if ttl > 0:
                    await self.redis_client.setex(cache_key, ttl, entry.model_dump_json())
                
                return CacheResponse(
                    found=True,
                    content=entry.content,
                    similarity_score=best_similarity,
                    cache_key=entry.cache_key,
                    cached_at=entry.cached_at.isoformat(),
                    expires_at=entry.expires_at.isoformat(),
                    metadata=entry.metadata
                )
                
            except Exception as e:
                print(f"Error parsing cache entry: {e}")
                return CacheResponse(found=False)
            
        except Exception as e:
            print(f"Error retrieving from cache: {e}")
            return CacheResponse(found=False)
    
    async def delete(self, tenant_id: str, cache_key: str) -> bool:
        """Delete a specific cache entry"""
        try:
            cache_redis_key = self._cache_key(tenant_id, cache_key)
            embedding_redis_key = self._embedding_key(tenant_id, cache_key)
            tenant_keys_key = self._tenant_keys_key(tenant_id)
            
            # Use pipeline for atomic operations
            pipe = self.redis_client.pipeline()
            pipe.delete(cache_redis_key)
            pipe.delete(embedding_redis_key)
            pipe.srem(tenant_keys_key, cache_key)
            
            results = await pipe.execute()
            return any(results)
            
        except Exception as e:
            print(f"Error deleting cache entry: {e}")
            return False
    
    async def get_stats(self, tenant_id: str) -> CacheStats:
        """Get cache statistics for a tenant"""
        try:
            tenant_keys_key = self._tenant_keys_key(tenant_id)
            cache_keys = await self.redis_client.smembers(tenant_keys_key)
            
            if not cache_keys:
                return CacheStats(
                    tenant_id=tenant_id,
                    total_entries=0,
                    hit_rate=0.0,
                    avg_similarity=0.0,
                    cache_size_mb=0.0
                )
            
            # Collect statistics
            total_hits = 0
            total_entries = len(cache_keys)
            oldest_entry = None
            newest_entry = None
            total_size = 0
            
            for cache_key in cache_keys:
                redis_key = self._cache_key(tenant_id, cache_key)
                entry_data = await self.redis_client.get(redis_key)
                
                if entry_data:
                    try:
                        entry = CacheEntry.model_validate_json(entry_data)
                        total_hits += entry.hit_count
                        total_size += len(entry_data)
                        
                        if not oldest_entry or entry.cached_at < oldest_entry:
                            oldest_entry = entry.cached_at
                        if not newest_entry or entry.cached_at > newest_entry:
                            newest_entry = entry.cached_at
                            
                    except Exception:
                        continue
            
            hit_rate = total_hits / max(total_entries, 1)
            cache_size_mb = total_size / (1024 * 1024)
            
            return CacheStats(
                tenant_id=tenant_id,
                total_entries=total_entries,
                hit_rate=hit_rate,
                avg_similarity=0.85,  # This would need to be calculated properly
                cache_size_mb=cache_size_mb,
                oldest_entry=oldest_entry.isoformat() if oldest_entry else None,
                newest_entry=newest_entry.isoformat() if newest_entry else None
            )
            
        except Exception as e:
            print(f"Error getting cache stats: {e}")
            return CacheStats(
                tenant_id=tenant_id,
                total_entries=0,
                hit_rate=0.0,
                avg_similarity=0.0,
                cache_size_mb=0.0
            )

