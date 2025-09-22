"""Regional management API endpoints."""

from typing import List, Optional
import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from libs.clients.database import get_db_session
from libs.clients.auth import get_current_tenant
from apps.api_gateway.core.region_router import RegionRouter, ProviderType
from libs.middleware.regional_middleware import RegionalAccessValidator

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/regional", tags=["Regional Management"])


class TenantRegionUpdate(BaseModel):
    """Request model for updating tenant region."""
    data_region: str
    allowed_regions: Optional[List[str]] = None
    regional_config: Optional[dict] = None


class ProviderSelectionRequest(BaseModel):
    """Request model for provider selection."""
    provider_type: str
    preferred_provider: Optional[str] = None


class RegionalQueryRequest(BaseModel):
    """Request model for regional analytics query."""
    query: str
    regions: Optional[List[str]] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


@router.get("/tenant/region")
async def get_tenant_region(
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session)
):
    """Get tenant's current region configuration."""
    try:
        region_router = RegionRouter(db)
        
        # Get tenant region
        data_region = await region_router.get_tenant_region(tenant_id)
        allowed_regions = await region_router.get_tenant_allowed_regions(tenant_id)
        
        return {
            "tenant_id": tenant_id,
            "data_region": data_region,
            "allowed_regions": allowed_regions
        }
        
    except Exception as e:
        logger.error("Failed to get tenant region", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve tenant region"
        )


@router.put("/tenant/region")
async def update_tenant_region(
    update_data: TenantRegionUpdate,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session)
):
    """Update tenant's region configuration."""
    try:
        region_router = RegionRouter(db)
        
        # Validate region is available
        available_regions = await region_router.get_available_regions()
        if update_data.data_region not in available_regions:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Region '{update_data.data_region}' not available"
            )
        
        # Update tenant region
        success = await region_router.update_tenant_region(tenant_id, update_data.data_region)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update tenant region"
            )
        
        logger.info("Tenant region updated", 
                   tenant_id=tenant_id, 
                   new_region=update_data.data_region)
        
        return {
            "tenant_id": tenant_id,
            "data_region": update_data.data_region,
            "status": "updated"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to update tenant region", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update tenant region"
        )


@router.get("/providers")
async def get_available_providers(
    region: Optional[str] = None,
    provider_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """Get available providers for region and type."""
    try:
        region_router = RegionRouter(db)
        
        if region:
            # Get providers for specific region
            providers = await region_router.get_region_providers(region)
            
            if provider_type:
                # Filter by provider type
                try:
                    provider_type_enum = ProviderType(provider_type)
                    providers = {provider_type_enum: providers.get(provider_type_enum, [])}
                except ValueError:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Invalid provider type: {provider_type}"
                    )
        else:
            # Get all regions and providers
            regions = await region_router.get_available_regions()
            providers = {}
            for r in regions:
                providers[r] = await region_router.get_region_providers(r)
        
        # Convert to serializable format
        result = {}
        for region_name, region_providers in providers.items():
            result[region_name] = {}
            for ptype, provider_list in region_providers.items():
                result[region_name][ptype.value] = [
                    {
                        "provider_name": p.provider_name,
                        "endpoint_url": p.endpoint_url,
                        "priority": p.priority,
                        "is_active": p.is_active
                    }
                    for p in provider_list
                ]
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to get available providers", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve providers"
        )


@router.post("/providers/select")
async def select_provider(
    request: ProviderSelectionRequest,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session)
):
    """Select provider for tenant based on regional policy."""
    try:
        region_router = RegionRouter(db)
        
        # Validate provider type
        try:
            provider_type = ProviderType(request.provider_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid provider type: {request.provider_type}"
            )
        
        # Select provider
        provider = await region_router.select_provider(tenant_id, provider_type)
        
        if not provider:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No provider available for type {request.provider_type}"
            )
        
        return {
            "tenant_id": tenant_id,
            "provider_type": request.provider_type,
            "selected_provider": {
                "region": provider.region,
                "provider_name": provider.provider_name,
                "endpoint_url": provider.endpoint_url,
                "priority": provider.priority
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to select provider", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to select provider"
        )


@router.post("/access/validate")
async def validate_regional_access(
    resource_region: str,
    resource_type: str,
    tenant_id: str = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db_session)
):
    """Validate if tenant can access resource in specified region."""
    try:
        access_validator = RegionalAccessValidator(RegionRouter(db))
        
        # Validate access
        allowed = await access_validator.validate_resource_access(
            tenant_id, resource_region, resource_type
        )
        
        return {
            "tenant_id": tenant_id,
            "resource_region": resource_region,
            "resource_type": resource_type,
            "access_allowed": allowed
        }
        
    except Exception as e:
        logger.error("Failed to validate regional access", tenant_id=tenant_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to validate regional access"
        )


@router.get("/regions")
async def get_available_regions(
    db: AsyncSession = Depends(get_db_session)
):
    """Get list of available regions."""
    try:
        region_router = RegionRouter(db)
        regions = await region_router.get_available_regions()
        
        return {
            "available_regions": regions,
            "count": len(regions)
        }
        
    except Exception as e:
        logger.error("Failed to get available regions", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve available regions"
        )


@router.get("/health")
async def get_regional_health(
    db: AsyncSession = Depends(get_db_session)
):
    """Get health status of regional components."""
    try:
        # This would typically check health of regional replicas
        # For now, return basic status
        return {
            "status": "healthy",
            "components": {
                "region_router": "healthy",
                "regional_middleware": "healthy",
                "regional_analytics": "healthy"
            },
            "timestamp": "2024-01-01T00:00:00Z"
        }
        
    except Exception as e:
        logger.error("Failed to get regional health", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve regional health"
        )
