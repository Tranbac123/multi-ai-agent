"""Regional middleware for data residency and cross-region access control."""

from typing import Optional
import structlog
from fastapi import Request, Response, HTTPException, status
from fastapi.responses import JSONResponse
import time

from apps.api-gateway.core.region_router import RegionRouter
from libs.utils.auth import get_tenant_from_jwt

logger = structlog.get_logger(__name__)


class RegionalMiddleware:
    """Middleware for enforcing regional access policies and adding regional headers."""
    
    def __init__(self, region_router: RegionRouter):
        self.region_router = region_router
    
    async def __call__(self, request: Request, call_next) -> Response:
        """Process request with regional middleware."""
        start_time = time.time()
        
        try:
            # Extract tenant from JWT token
            tenant_id = await self._extract_tenant_id(request)
            if not tenant_id:
                # Allow requests without tenant (public endpoints)
                response = await call_next(request)
                return self._add_regional_headers(response, None, None)
            
            # Get tenant's data region
            tenant_region = await self.region_router.get_tenant_region(tenant_id)
            
            # Add regional context to request state
            request.state.tenant_id = tenant_id
            request.state.data_region = tenant_region
            request.state.allowed_regions = await self.region_router.get_tenant_allowed_regions(tenant_id)
            
            # Check for cross-region access attempts
            if await self._check_cross_region_access(request, tenant_id, tenant_region):
                response = await call_next(request)
            else:
                # Deny cross-region access
                return JSONResponse(
                    status_code=status.HTTP_403_FORBIDDEN,
                    content={
                        "error": "Cross-region access denied",
                        "detail": f"Access to region '{request.state.target_region}' not allowed for tenant region '{tenant_region}'"
                    }
                )
            
            # Add regional headers to response
            response = self._add_regional_headers(response, tenant_id, tenant_region)
            
            # Log request with regional context
            processing_time = time.time() - start_time
            logger.info("Request processed with regional context",
                       tenant_id=tenant_id,
                       region=tenant_region,
                       path=request.url.path,
                       method=request.method,
                       processing_time_ms=round(processing_time * 1000, 2))
            
            return response
            
        except Exception as e:
            logger.error("Regional middleware error",
                        error=str(e),
                        path=request.url.path,
                        method=request.method)
            
            # Continue with request even if regional middleware fails
            response = await call_next(request)
            return self._add_regional_headers(response, None, None)
    
    async def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request."""
        try:
            # Try to get tenant from JWT token
            tenant_id = await get_tenant_from_jwt(request)
            return tenant_id
        except Exception as e:
            logger.debug("Could not extract tenant from JWT", error=str(e))
            return None
    
    async def _check_cross_region_access(self, request: Request, tenant_id: str, tenant_region: str) -> bool:
        """Check if request involves cross-region access."""
        try:
            # Check if request specifies a target region
            target_region = request.headers.get("X-Target-Region")
            if not target_region:
                # No target region specified, allow request
                return True
            
            # Store target region in request state
            request.state.target_region = target_region
            
            # Check if cross-region access is allowed
            allowed = await self.region_router.enforce_regional_access(tenant_id, target_region)
            
            if not allowed:
                logger.warning("Cross-region access denied",
                              tenant_id=tenant_id,
                              tenant_region=tenant_region,
                              target_region=target_region,
                              path=request.url.path)
            
            return allowed
            
        except Exception as e:
            logger.error("Error checking cross-region access",
                        tenant_id=tenant_id,
                        error=str(e))
            # Default to allowing access if check fails
            return True
    
    def _add_regional_headers(self, response: Response, tenant_id: Optional[str], region: Optional[str]) -> Response:
        """Add regional headers to response."""
        try:
            if region:
                response.headers["X-Data-Region"] = region
            
            if tenant_id:
                response.headers["X-Tenant-ID"] = tenant_id
            
            # Add CORS headers for regional information
            response.headers["Access-Control-Expose-Headers"] = "X-Data-Region, X-Tenant-ID"
            
            return response
            
        except Exception as e:
            logger.error("Error adding regional headers", error=str(e))
            return response


class RegionalAccessValidator:
    """Validator for regional access policies."""
    
    def __init__(self, region_router: RegionRouter):
        self.region_router = region_router
    
    async def validate_resource_access(self, tenant_id: str, resource_region: str, resource_type: str) -> bool:
        """Validate if tenant can access resource in specified region."""
        try:
            # Check if resource region is allowed for tenant
            allowed = await self.region_router.enforce_regional_access(tenant_id, resource_region)
            
            if not allowed:
                logger.warning("Resource access denied due to regional policy",
                              tenant_id=tenant_id,
                              resource_region=resource_region,
                              resource_type=resource_type)
            
            return allowed
            
        except Exception as e:
            logger.error("Error validating resource access",
                        tenant_id=tenant_id,
                        resource_region=resource_region,
                        error=str(e))
            return False
    
    async def validate_analytics_query(self, tenant_id: str, query_regions: list) -> bool:
        """Validate if tenant can query analytics from specified regions."""
        try:
            # Get tenant's allowed regions
            allowed_regions = await self.region_router.get_tenant_allowed_regions(tenant_id)
            
            # Check if all query regions are allowed
            for region in query_regions:
                if region not in allowed_regions:
                    logger.warning("Analytics query denied due to regional policy",
                                  tenant_id=tenant_id,
                                  denied_region=region,
                                  allowed_regions=allowed_regions)
                    return False
            
            return True
            
        except Exception as e:
            logger.error("Error validating analytics query",
                        tenant_id=tenant_id,
                        query_regions=query_regions,
                        error=str(e))
            return False
    
    async def validate_ingestion_region(self, tenant_id: str, document_region: str) -> bool:
        """Validate if tenant can ingest documents to specified region."""
        try:
            # Get tenant's data region
            tenant_region = await self.region_router.get_tenant_region(tenant_id)
            
            # Documents should be ingested to tenant's data region
            if document_region != tenant_region:
                logger.warning("Document ingestion denied due to regional policy",
                              tenant_id=tenant_id,
                              tenant_region=tenant_region,
                              document_region=document_region)
                return False
            
            return True
            
        except Exception as e:
            logger.error("Error validating ingestion region",
                        tenant_id=tenant_id,
                        document_region=document_region,
                        error=str(e))
            return False


class RegionalMetricsCollector:
    """Collector for regional access metrics."""
    
    def __init__(self):
        self.request_counts = {}
        self.cross_region_denials = {}
        self.processing_times = {}
    
    def record_request(self, tenant_id: str, region: str, path: str, method: str, processing_time: float):
        """Record request metrics."""
        try:
            key = f"{tenant_id}:{region}:{method}:{path}"
            
            # Count requests by region
            if region not in self.request_counts:
                self.request_counts[region] = 0
            self.request_counts[region] += 1
            
            # Record processing time
            if region not in self.processing_times:
                self.processing_times[region] = []
            self.processing_times[region].append(processing_time)
            
        except Exception as e:
            logger.error("Error recording request metrics", error=str(e))
    
    def record_cross_region_denial(self, tenant_id: str, tenant_region: str, target_region: str):
        """Record cross-region access denial."""
        try:
            key = f"{tenant_region}->{target_region}"
            if key not in self.cross_region_denials:
                self.cross_region_denials[key] = 0
            self.cross_region_denials[key] += 1
            
        except Exception as e:
            logger.error("Error recording cross-region denial", error=str(e))
    
    def get_regional_stats(self) -> dict:
        """Get regional statistics."""
        try:
            stats = {
                "request_counts": self.request_counts.copy(),
                "cross_region_denials": self.cross_region_denials.copy(),
                "avg_processing_times": {}
            }
            
            # Calculate average processing times
            for region, times in self.processing_times.items():
                if times:
                    stats["avg_processing_times"][region] = sum(times) / len(times)
            
            return stats
            
        except Exception as e:
            logger.error("Error getting regional stats", error=str(e))
            return {}
