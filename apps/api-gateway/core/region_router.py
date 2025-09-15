"""Region Router for tenant data residency and regional provider selection."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import json
import os

logger = structlog.get_logger(__name__)


class ProviderType(Enum):
    """Supported provider types."""
    LLM = "llm"
    VECTOR = "vector"
    STORAGE = "storage"
    DATABASE = "database"
    CACHE = "cache"


@dataclass
class ProviderConfig:
    """Regional provider configuration."""
    region: str
    provider_type: ProviderType
    provider_name: str
    endpoint_url: str
    credentials: Dict[str, Any]
    priority: int = 1
    is_active: bool = True


@dataclass
class TenantRegionConfig:
    """Tenant regional configuration."""
    tenant_id: str
    data_region: str
    allowed_regions: List[str]
    regional_config: Dict[str, Any]


class RegionRouter:
    """Router for selecting region-specific providers based on tenant policy."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.regional_providers: Dict[str, Dict[ProviderType, List[ProviderConfig]]] = {}
        self.tenant_configs: Dict[str, TenantRegionConfig] = {}
        self._load_regional_providers()
    
    def _load_regional_providers(self) -> None:
        """Load regional providers from environment variables."""
        # Load default providers from environment
        default_providers = {
            "us-east-1": {
                ProviderType.LLM: [
                    ProviderConfig(
                        region="us-east-1",
                        provider_type=ProviderType.LLM,
                        provider_name="openai",
                        endpoint_url="https://api.openai.com/v1",
                        credentials={"api_key": os.getenv("OPENAI_API_KEY")},
                        priority=1
                    ),
                    ProviderConfig(
                        region="us-east-1",
                        provider_type=ProviderType.LLM,
                        provider_name="anthropic",
                        endpoint_url="https://api.anthropic.com/v1",
                        credentials={"api_key": os.getenv("ANTHROPIC_API_KEY")},
                        priority=2
                    )
                ],
                ProviderType.VECTOR: [
                    ProviderConfig(
                        region="us-east-1",
                        provider_type=ProviderType.VECTOR,
                        provider_name="pinecone",
                        endpoint_url="https://api.pinecone.io",
                        credentials={"api_key": os.getenv("PINECONE_API_KEY")},
                        priority=1
                    )
                ],
                ProviderType.STORAGE: [
                    ProviderConfig(
                        region="us-east-1",
                        provider_type=ProviderType.STORAGE,
                        provider_name="s3",
                        endpoint_url="https://s3.amazonaws.com",
                        credentials={
                            "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
                            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY")
                        },
                        priority=1
                    )
                ]
            },
            "eu-west-1": {
                ProviderType.LLM: [
                    ProviderConfig(
                        region="eu-west-1",
                        provider_type=ProviderType.LLM,
                        provider_name="openai",
                        endpoint_url="https://api.openai.com/v1",
                        credentials={"api_key": os.getenv("OPENAI_API_KEY")},
                        priority=1
                    ),
                    ProviderConfig(
                        region="eu-west-1",
                        provider_type=ProviderType.LLM,
                        provider_name="anthropic",
                        endpoint_url="https://api.anthropic.com/v1",
                        credentials={"api_key": os.getenv("ANTHROPIC_API_KEY")},
                        priority=2
                    )
                ],
                ProviderType.VECTOR: [
                    ProviderConfig(
                        region="eu-west-1",
                        provider_type=ProviderType.VECTOR,
                        provider_name="pinecone",
                        endpoint_url="https://api.pinecone.io",
                        credentials={"api_key": os.getenv("PINECONE_API_KEY")},
                        priority=1
                    )
                ],
                ProviderType.STORAGE: [
                    ProviderConfig(
                        region="eu-west-1",
                        provider_type=ProviderType.STORAGE,
                        provider_name="s3",
                        endpoint_url="https://s3.eu-west-1.amazonaws.com",
                        credentials={
                            "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
                            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY")
                        },
                        priority=1
                    )
                ]
            },
            "ap-southeast-1": {
                ProviderType.LLM: [
                    ProviderConfig(
                        region="ap-southeast-1",
                        provider_type=ProviderType.LLM,
                        provider_name="openai",
                        endpoint_url="https://api.openai.com/v1",
                        credentials={"api_key": os.getenv("OPENAI_API_KEY")},
                        priority=1
                    ),
                    ProviderConfig(
                        region="ap-southeast-1",
                        provider_type=ProviderType.LLM,
                        provider_name="anthropic",
                        endpoint_url="https://api.anthropic.com/v1",
                        credentials={"api_key": os.getenv("ANTHROPIC_API_KEY")},
                        priority=2
                    )
                ],
                ProviderType.VECTOR: [
                    ProviderConfig(
                        region="ap-southeast-1",
                        provider_type=ProviderType.VECTOR,
                        provider_name="pinecone",
                        endpoint_url="https://api.pinecone.io",
                        credentials={"api_key": os.getenv("PINECONE_API_KEY")},
                        priority=1
                    )
                ],
                ProviderType.STORAGE: [
                    ProviderConfig(
                        region="ap-southeast-1",
                        provider_type=ProviderType.STORAGE,
                        provider_name="s3",
                        endpoint_url="https://s3.ap-southeast-1.amazonaws.com",
                        credentials={
                            "access_key": os.getenv("AWS_ACCESS_KEY_ID"),
                            "secret_key": os.getenv("AWS_SECRET_ACCESS_KEY")
                        },
                        priority=1
                    )
                ]
            }
        }
        
        self.regional_providers = default_providers
        logger.info("Regional providers loaded", regions=list(default_providers.keys()))
    
    async def get_tenant_region(self, tenant_id: str) -> str:
        """Get tenant's data region from database."""
        # Check cache first
        if tenant_id in self.tenant_configs:
            return self.tenant_configs[tenant_id].data_region
        
        try:
            result = await self.db.execute(text("""
                SELECT data_region, allowed_regions, regional_config
                FROM tenants
                WHERE id = :tenant_id
            """), {"tenant_id": tenant_id})
            
            row = result.fetchone()
            if not row:
                logger.warning("Tenant not found, using default region", tenant_id=tenant_id)
                return "us-east-1"
            
            # Cache tenant config
            self.tenant_configs[tenant_id] = TenantRegionConfig(
                tenant_id=tenant_id,
                data_region=row[0],
                allowed_regions=row[1] or ["us-east-1"],
                regional_config=row[2] or {}
            )
            
            logger.info("Tenant region retrieved", 
                       tenant_id=tenant_id, 
                       data_region=row[0])
            
            return row[0]
            
        except Exception as e:
            logger.error("Failed to get tenant region", 
                        tenant_id=tenant_id, 
                        error=str(e))
            return "us-east-1"
    
    async def select_provider(self, tenant_id: str, provider_type: ProviderType) -> Optional[ProviderConfig]:
        """Select region-specific provider based on tenant policy."""
        try:
            # Get tenant region
            tenant_region = await self.get_tenant_region(tenant_id)
            
            # Get tenant config
            tenant_config = self.tenant_configs.get(tenant_id)
            if not tenant_config:
                await self.get_tenant_region(tenant_id)  # Load config
                tenant_config = self.tenant_configs.get(tenant_id)
            
            # Check if provider type is available in tenant's region
            if tenant_region not in self.regional_providers:
                logger.warning("Region not supported", 
                              tenant_id=tenant_id, 
                              region=tenant_region)
                return None
            
            region_providers = self.regional_providers[tenant_region]
            if provider_type not in region_providers:
                logger.warning("Provider type not available in region", 
                              tenant_id=tenant_id, 
                              region=tenant_region, 
                              provider_type=provider_type.value)
                return None
            
            # Get available providers for this type
            available_providers = [
                p for p in region_providers[provider_type] 
                if p.is_active
            ]
            
            if not available_providers:
                logger.warning("No active providers available", 
                              tenant_id=tenant_id, 
                              region=tenant_region, 
                              provider_type=provider_type.value)
                return None
            
            # Select provider based on priority (lower number = higher priority)
            selected_provider = min(available_providers, key=lambda p: p.priority)
            
            # Check tenant's regional config for provider preferences
            if tenant_config and tenant_config.regional_config:
                preferred_provider = tenant_config.regional_config.get(
                    f"{provider_type.value}_provider"
                )
                if preferred_provider:
                    preferred = next(
                        (p for p in available_providers if p.provider_name == preferred_provider),
                        None
                    )
                    if preferred:
                        selected_provider = preferred
            
            logger.info("Provider selected", 
                       tenant_id=tenant_id, 
                       region=tenant_region, 
                       provider_type=provider_type.value, 
                       provider_name=selected_provider.provider_name)
            
            return selected_provider
            
        except Exception as e:
            logger.error("Failed to select provider", 
                        tenant_id=tenant_id, 
                        provider_type=provider_type.value, 
                        error=str(e))
            return None
    
    async def enforce_regional_access(self, tenant_id: str, resource_region: str) -> bool:
        """Enforce cross-region access policies."""
        try:
            # Get tenant region
            tenant_region = await self.get_tenant_region(tenant_id)
            
            # Get tenant config
            tenant_config = self.tenant_configs.get(tenant_id)
            if not tenant_config:
                await self.get_tenant_region(tenant_id)  # Load config
                tenant_config = self.tenant_configs.get(tenant_id)
            
            # Check if resource region is in allowed regions
            if tenant_config and resource_region not in tenant_config.allowed_regions:
                logger.warning("Cross-region access denied", 
                              tenant_id=tenant_id, 
                              tenant_region=tenant_region, 
                              resource_region=resource_region)
                return False
            
            # Allow access if resource region matches tenant region
            if resource_region == tenant_region:
                return True
            
            # Check tenant's regional config for cross-region policies
            if tenant_config and tenant_config.regional_config:
                cross_region_allowed = tenant_config.regional_config.get(
                    "allow_cross_region_access", False
                )
                if not cross_region_allowed:
                    logger.warning("Cross-region access disabled by tenant policy", 
                                  tenant_id=tenant_id, 
                                  tenant_region=tenant_region, 
                                  resource_region=resource_region)
                    return False
            
            logger.info("Cross-region access allowed", 
                       tenant_id=tenant_id, 
                       tenant_region=tenant_region, 
                       resource_region=resource_region)
            
            return True
            
        except Exception as e:
            logger.error("Failed to enforce regional access", 
                        tenant_id=tenant_id, 
                        resource_region=resource_region, 
                        error=str(e))
            return False
    
    async def get_tenant_allowed_regions(self, tenant_id: str) -> List[str]:
        """Get list of regions allowed for tenant."""
        try:
            tenant_config = self.tenant_configs.get(tenant_id)
            if not tenant_config:
                await self.get_tenant_region(tenant_id)  # Load config
                tenant_config = self.tenant_configs.get(tenant_id)
            
            return tenant_config.allowed_regions if tenant_config else ["us-east-1"]
            
        except Exception as e:
            logger.error("Failed to get tenant allowed regions", 
                        tenant_id=tenant_id, 
                        error=str(e))
            return ["us-east-1"]
    
    async def update_tenant_region(self, tenant_id: str, new_region: str) -> bool:
        """Update tenant's data region."""
        try:
            await self.db.execute(text("""
                UPDATE tenants 
                SET data_region = :new_region, updated_at = NOW()
                WHERE id = :tenant_id
            """), {"tenant_id": tenant_id, "new_region": new_region})
            
            await self.db.commit()
            
            # Update cache
            if tenant_id in self.tenant_configs:
                self.tenant_configs[tenant_id].data_region = new_region
            
            logger.info("Tenant region updated", 
                       tenant_id=tenant_id, 
                       new_region=new_region)
            
            return True
            
        except Exception as e:
            logger.error("Failed to update tenant region", 
                        tenant_id=tenant_id, 
                        new_region=new_region, 
                        error=str(e))
            return False
    
    async def get_available_regions(self) -> List[str]:
        """Get list of available regions."""
        return list(self.regional_providers.keys())
    
    async def get_region_providers(self, region: str) -> Dict[ProviderType, List[ProviderConfig]]:
        """Get all providers for a specific region."""
        return self.regional_providers.get(region, {})
