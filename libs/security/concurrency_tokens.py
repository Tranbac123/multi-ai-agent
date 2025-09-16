"""
Concurrency Token Management

Implements per-tenant concurrency token management for resource isolation
and fair resource allocation across tenants.
"""

import asyncio
import time
from typing import Dict, Optional, Any, Set, List
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta
import uuid

logger = structlog.get_logger(__name__)


class ConcurrencyTokenStatus(Enum):
    """Concurrency token status."""
    AVAILABLE = "available"
    ACQUIRED = "acquired"
    RELEASED = "released"
    EXPIRED = "expired"


@dataclass
class ConcurrencyToken:
    """Concurrency token with metadata."""
    
    token_id: str
    tenant_id: str
    resource_type: str
    acquired_at: datetime
    expires_at: Optional[datetime] = None
    status: ConcurrencyTokenStatus = ConcurrencyTokenStatus.AVAILABLE
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def is_expired(self) -> bool:
        """Check if token is expired."""
        if self.expires_at is None:
            return False
        return datetime.now() > self.expires_at
    
    def time_until_expiry(self) -> Optional[timedelta]:
        """Get time until token expires."""
        if self.expires_at is None:
            return None
        remaining = self.expires_at - datetime.now()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)


@dataclass
class ConcurrencyLimits:
    """Concurrency limits for a tenant."""
    
    tenant_id: str
    max_concurrent_requests: int
    max_concurrent_agents: int
    max_concurrent_workflows: int
    max_concurrent_tools: int
    priority_weight: float = 1.0  # Higher weight = higher priority
    burst_limit: int = 0  # Additional tokens for burst capacity


class ConcurrencyTokenPool:
    """Pool of concurrency tokens for a specific resource type."""
    
    def __init__(self, resource_type: str, total_tokens: int):
        self.resource_type = resource_type
        self.total_tokens = total_tokens
        self.available_tokens: Set[str] = set()
        self.acquired_tokens: Dict[str, ConcurrencyToken] = {}
        self.waiting_requests: List[asyncio.Future] = []
        
        # Initialize available tokens
        for i in range(total_tokens):
            token_id = f"{resource_type}_token_{i}"
            self.available_tokens.add(token_id)
        
        logger.info("Concurrency token pool created", 
                   resource_type=resource_type,
                   total_tokens=total_tokens)
    
    async def acquire_token(
        self, 
        tenant_id: str, 
        timeout_seconds: Optional[float] = None,
        expires_in_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ConcurrencyToken]:
        """Acquire a concurrency token."""
        
        # Check if token is available immediately
        if self.available_tokens:
            token_id = self.available_tokens.pop()
            
            token = ConcurrencyToken(
                token_id=token_id,
                tenant_id=tenant_id,
                resource_type=self.resource_type,
                acquired_at=datetime.now(),
                expires_at=(
                    datetime.now() + timedelta(seconds=expires_in_seconds)
                    if expires_in_seconds else None
                ),
                status=ConcurrencyTokenStatus.ACQUIRED,
                metadata=metadata or {}
            )
            
            self.acquired_tokens[token_id] = token
            
            logger.debug("Concurrency token acquired", 
                        token_id=token_id,
                        tenant_id=tenant_id,
                        resource_type=self.resource_type)
            
            return token
        
        # No tokens available, wait or timeout
        if timeout_seconds is None or timeout_seconds <= 0:
            logger.debug("No tokens available and no timeout", 
                        tenant_id=tenant_id,
                        resource_type=self.resource_type)
            return None
        
        # Wait for token to become available
        try:
            future = asyncio.Future()
            self.waiting_requests.append(future)
            
            token = await asyncio.wait_for(future, timeout=timeout_seconds)
            
            logger.debug("Concurrency token acquired after waiting", 
                        token_id=token.token_id,
                        tenant_id=tenant_id,
                        resource_type=self.resource_type)
            
            return token
            
        except asyncio.TimeoutError:
            logger.debug("Timeout waiting for concurrency token", 
                        tenant_id=tenant_id,
                        resource_type=self.resource_type,
                        timeout_seconds=timeout_seconds)
            return None
        finally:
            # Remove from waiting list
            if future in self.waiting_requests:
                self.waiting_requests.remove(future)
    
    async def release_token(self, token_id: str) -> bool:
        """Release a concurrency token."""
        
        if token_id not in self.acquired_tokens:
            logger.warning("Attempted to release non-existent token", token_id=token_id)
            return False
        
        token = self.acquired_tokens[token_id]
        token.status = ConcurrencyTokenStatus.RELEASED
        
        # Remove from acquired tokens
        del self.acquired_tokens[token_id]
        
        # Add back to available tokens
        self.available_tokens.add(token_id)
        
        # Notify waiting requests
        if self.waiting_requests:
            future = self.waiting_requests.pop(0)
            if not future.done():
                # Create new token for waiting request
                new_token = ConcurrencyToken(
                    token_id=token_id,
                    tenant_id=token.tenant_id,  # Will be updated by caller
                    resource_type=self.resource_type,
                    acquired_at=datetime.now(),
                    expires_at=token.expires_at,
                    status=ConcurrencyTokenStatus.ACQUIRED,
                    metadata=token.metadata
                )
                future.set_result(new_token)
        
        logger.debug("Concurrency token released", 
                    token_id=token_id,
                    resource_type=self.resource_type)
        
        return True
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get token pool metrics."""
        
        return {
            "resource_type": self.resource_type,
            "total_tokens": self.total_tokens,
            "available_tokens": len(self.available_tokens),
            "acquired_tokens": len(self.acquired_tokens),
            "waiting_requests": len(self.waiting_requests),
            "utilization": len(self.acquired_tokens) / self.total_tokens,
            "acquired_token_details": [
                {
                    "token_id": token.token_id,
                    "tenant_id": token.tenant_id,
                    "acquired_at": token.acquired_at.isoformat(),
                    "expires_at": token.expires_at.isoformat() if token.expires_at else None,
                    "is_expired": token.is_expired()
                }
                for token in self.acquired_tokens.values()
            ]
        }


class ConcurrencyManager:
    """Manages concurrency tokens across all resource types and tenants."""
    
    def __init__(self, redis_client=None):
        self.redis_client = redis_client
        self.token_pools: Dict[str, ConcurrencyTokenPool] = {}
        self.tenant_limits: Dict[str, ConcurrencyLimits] = {}
        self.tenant_tokens: Dict[str, Dict[str, Set[str]]] = {}  # tenant_id -> resource_type -> token_ids
        
        # Initialize default token pools
        self._initialize_default_pools()
        
        # Background task for token cleanup
        self._cleanup_task = None
        
        logger.info("Concurrency manager initialized")
    
    def _initialize_default_pools(self):
        """Initialize default concurrency token pools."""
        
        default_pools = {
            "requests": 1000,  # 1000 concurrent requests
            "agents": 100,     # 100 concurrent agents
            "workflows": 200,  # 200 concurrent workflows
            "tools": 500       # 500 concurrent tools
        }
        
        for resource_type, total_tokens in default_pools.items():
            self.token_pools[resource_type] = ConcurrencyTokenPool(resource_type, total_tokens)
    
    async def start(self):
        """Start the concurrency manager."""
        
        # Start background cleanup task
        self._cleanup_task = asyncio.create_task(self._cleanup_expired_tokens())
        
        logger.info("Concurrency manager started")
    
    async def stop(self):
        """Stop the concurrency manager."""
        
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        
        logger.info("Concurrency manager stopped")
    
    async def set_tenant_limits(self, limits: ConcurrencyLimits):
        """Set concurrency limits for a tenant."""
        
        self.tenant_limits[limits.tenant_id] = limits
        
        # Initialize tenant token tracking
        if limits.tenant_id not in self.tenant_tokens:
            self.tenant_tokens[limits.tenant_id] = {}
        
        for resource_type in self.token_pools.keys():
            if resource_type not in self.tenant_tokens[limits.tenant_id]:
                self.tenant_tokens[limits.tenant_id][resource_type] = set()
        
        logger.info("Tenant concurrency limits set", 
                   tenant_id=limits.tenant_id,
                   max_concurrent_requests=limits.max_concurrent_requests,
                   max_concurrent_agents=limits.max_concurrent_agents,
                   priority_weight=limits.priority_weight)
    
    async def acquire_token(
        self, 
        tenant_id: str, 
        resource_type: str,
        timeout_seconds: Optional[float] = None,
        expires_in_seconds: Optional[float] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[ConcurrencyToken]:
        """Acquire a concurrency token for a tenant."""
        
        # Check if resource type exists
        if resource_type not in self.token_pools:
            logger.error("Unknown resource type", resource_type=resource_type)
            return None
        
        # Check tenant limits
        if not await self._check_tenant_limits(tenant_id, resource_type):
            logger.warning("Tenant limit exceeded", 
                          tenant_id=tenant_id,
                          resource_type=resource_type)
            return None
        
        # Acquire token from pool
        token_pool = self.token_pools[resource_type]
        token = await token_pool.acquire_token(
            tenant_id=tenant_id,
            timeout_seconds=timeout_seconds,
            expires_in_seconds=expires_in_seconds,
            metadata=metadata
        )
        
        if token:
            # Track token for tenant
            if tenant_id not in self.tenant_tokens:
                self.tenant_tokens[tenant_id] = {}
            if resource_type not in self.tenant_tokens[tenant_id]:
                self.tenant_tokens[tenant_id][resource_type] = set()
            
            self.tenant_tokens[tenant_id][resource_type].add(token.token_id)
            
            logger.debug("Concurrency token acquired", 
                        token_id=token.token_id,
                        tenant_id=tenant_id,
                        resource_type=resource_type)
        
        return token
    
    async def release_token(self, token: ConcurrencyToken) -> bool:
        """Release a concurrency token."""
        
        # Check if resource type exists
        if token.resource_type not in self.token_pools:
            logger.error("Unknown resource type", resource_type=token.resource_type)
            return False
        
        # Release token from pool
        token_pool = self.token_pools[token.resource_type]
        success = await token_pool.release_token(token.token_id)
        
        if success:
            # Remove token tracking for tenant
            if (token.tenant_id in self.tenant_tokens and 
                token.resource_type in self.tenant_tokens[token.tenant_id]):
                self.tenant_tokens[token.tenant_id][token.resource_type].discard(token.token_id)
            
            logger.debug("Concurrency token released", 
                        token_id=token.token_id,
                        tenant_id=token.tenant_id,
                        resource_type=token.resource_type)
        
        return success
    
    async def _check_tenant_limits(self, tenant_id: str, resource_type: str) -> bool:
        """Check if tenant has reached concurrency limits."""
        
        if tenant_id not in self.tenant_limits:
            # Use default limits for unknown tenants
            return True
        
        limits = self.tenant_limits[tenant_id]
        current_count = len(self.tenant_tokens.get(tenant_id, {}).get(resource_type, set()))
        
        # Check specific limits based on resource type
        if resource_type == "requests":
            return current_count < limits.max_concurrent_requests
        elif resource_type == "agents":
            return current_count < limits.max_concurrent_agents
        elif resource_type == "workflows":
            return current_count < limits.max_concurrent_workflows
        elif resource_type == "tools":
            return current_count < limits.max_concurrent_tools
        
        return True
    
    async def _cleanup_expired_tokens(self):
        """Background task to cleanup expired tokens."""
        
        while True:
            try:
                await asyncio.sleep(30)  # Run every 30 seconds
                
                for resource_type, token_pool in self.token_pools.items():
                    expired_tokens = []
                    
                    for token_id, token in token_pool.acquired_tokens.items():
                        if token.is_expired():
                            expired_tokens.append(token_id)
                    
                    # Release expired tokens
                    for token_id in expired_tokens:
                        await token_pool.release_token(token_id)
                        logger.info("Expired concurrency token released", 
                                  token_id=token_id,
                                  resource_type=resource_type)
                
            except Exception as e:
                logger.error("Error in token cleanup task", error=str(e))
                await asyncio.sleep(60)  # Wait longer on error
    
    async def get_tenant_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """Get concurrency metrics for a tenant."""
        
        metrics = {
            "tenant_id": tenant_id,
            "resource_usage": {},
            "limits": {},
            "total_tokens_acquired": 0
        }
        
        # Get tenant limits
        if tenant_id in self.tenant_limits:
            limits = self.tenant_limits[tenant_id]
            metrics["limits"] = {
                "max_concurrent_requests": limits.max_concurrent_requests,
                "max_concurrent_agents": limits.max_concurrent_agents,
                "max_concurrent_workflows": limits.max_concurrent_workflows,
                "max_concurrent_tools": limits.max_concurrent_tools,
                "priority_weight": limits.priority_weight
            }
        
        # Get current usage
        if tenant_id in self.tenant_tokens:
            for resource_type, token_ids in self.tenant_tokens[tenant_id].items():
                metrics["resource_usage"][resource_type] = {
                    "current_usage": len(token_ids),
                    "token_ids": list(token_ids)
                }
                metrics["total_tokens_acquired"] += len(token_ids)
        
        return metrics
    
    async def get_global_metrics(self) -> Dict[str, Any]:
        """Get global concurrency metrics."""
        
        metrics = {
            "total_tenants": len(self.tenant_limits),
            "token_pools": {},
            "total_tokens_acquired": 0
        }
        
        # Get metrics for each token pool
        for resource_type, token_pool in self.token_pools.items():
            pool_metrics = token_pool.get_metrics()
            metrics["token_pools"][resource_type] = pool_metrics
            metrics["total_tokens_acquired"] += pool_metrics["acquired_tokens"]
        
        return metrics
    
    async def force_release_tenant_tokens(self, tenant_id: str) -> int:
        """Force release all tokens for a tenant."""
        
        released_count = 0
        
        if tenant_id in self.tenant_tokens:
            for resource_type, token_ids in list(self.tenant_tokens[tenant_id].items()):
                for token_id in list(token_ids):
                    token_pool = self.token_pools.get(resource_type)
                    if token_pool:
                        success = await token_pool.release_token(token_id)
                        if success:
                            released_count += 1
                            token_ids.discard(token_id)
        
        logger.info("Forced release of tenant tokens", 
                   tenant_id=tenant_id,
                   released_count=released_count)
        
        return released_count
