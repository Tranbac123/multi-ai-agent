"""Integration tests for data residency and regional features."""

import pytest
import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api_gateway.core.region_router import RegionRouter, ProviderType
from apps.analytics_service.core.regional_analytics import RegionalAnalyticsEngine
from libs.middleware.regional_middleware import RegionalMiddleware, RegionalAccessValidator


class TestRegionRouter:
    """Test RegionRouter functionality."""
    
    @pytest.fixture
    async def region_router(self):
        """Create RegionRouter instance for testing."""
        db_session = AsyncMock(spec=AsyncSession)
        return RegionRouter(db_session)
    
    @pytest.mark.asyncio
    async def test_get_tenant_region(self, region_router):
        """Test getting tenant region from database."""
        # Mock database response
        mock_result = MagicMock()
        mock_row = MagicMock()
        mock_row.__getitem__ = lambda self, key: {
            0: "us-east-1",  # data_region
            1: ["us-east-1", "eu-west-1"],  # allowed_regions
            2: {"llm_provider": "openai"}  # regional_config
        }[key]
        mock_result.fetchone.return_value = mock_row
        
        region_router.db.execute.return_value = mock_result
        
        # Test getting tenant region
        region = await region_router.get_tenant_region("test-tenant-1")
        
        assert region == "us-east-1"
        assert "test-tenant-1" in region_router.tenant_configs
        
        # Test caching - should not call database again
        cached_region = await region_router.get_tenant_region("test-tenant-1")
        assert cached_region == "us-east-1"
        assert region_router.db.execute.call_count == 1
    
    @pytest.mark.asyncio
    async def test_select_provider(self, region_router):
        """Test provider selection based on tenant region."""
        # Mock tenant config
        region_router.tenant_configs["test-tenant-1"] = MagicMock()
        region_router.tenant_configs["test-tenant-1"].data_region = "us-east-1"
        region_router.tenant_configs["test-tenant-1"].regional_config = {}
        
        # Test provider selection
        provider = await region_router.select_provider("test-tenant-1", ProviderType.LLM)
        
        assert provider is not None
        assert provider.region == "us-east-1"
        assert provider.provider_type == ProviderType.LLM
        assert provider.provider_name in ["openai", "anthropic"]
    
    @pytest.mark.asyncio
    async def test_enforce_regional_access_allowed(self, region_router):
        """Test regional access enforcement when allowed."""
        # Mock tenant config
        region_router.tenant_configs["test-tenant-1"] = MagicMock()
        region_router.tenant_configs["test-tenant-1"].data_region = "us-east-1"
        region_router.tenant_configs["test-tenant-1"].allowed_regions = ["us-east-1", "eu-west-1"]
        
        # Test allowed access
        allowed = await region_router.enforce_regional_access("test-tenant-1", "eu-west-1")
        assert allowed is True
    
    @pytest.mark.asyncio
    async def test_enforce_regional_access_denied(self, region_router):
        """Test regional access enforcement when denied."""
        # Mock tenant config
        region_router.tenant_configs["test-tenant-1"] = MagicMock()
        region_router.tenant_configs["test-tenant-1"].data_region = "us-east-1"
        region_router.tenant_configs["test-tenant-1"].allowed_regions = ["us-east-1"]
        
        # Test denied access
        allowed = await region_router.enforce_regional_access("test-tenant-1", "ap-southeast-1")
        assert allowed is False
    
    @pytest.mark.asyncio
    async def test_update_tenant_region(self, region_router):
        """Test updating tenant region."""
        # Mock database update
        mock_result = MagicMock()
        region_router.db.execute.return_value = mock_result
        region_router.db.commit.return_value = None
        
        # Test region update
        success = await region_router.update_tenant_region("test-tenant-1", "eu-west-1")
        
        assert success is True
        region_router.db.execute.assert_called_once()
        region_router.db.commit.assert_called_once()


class TestRegionalAnalytics:
    """Test RegionalAnalyticsEngine functionality."""
    
    @pytest.fixture
    async def analytics_engine(self):
        """Create RegionalAnalyticsEngine instance for testing."""
        db_session = AsyncMock(spec=AsyncSession)
        return RegionalAnalyticsEngine(db_session)
    
    @pytest.mark.asyncio
    async def test_route_analytics_query(self, analytics_engine):
        """Test routing analytics queries to regional replicas."""
        # Mock tenant allowed regions
        with patch.object(analytics_engine, '_get_tenant_allowed_regions', return_value=["us-east-1"]):
            with patch.object(analytics_engine, '_execute_regional_query') as mock_execute:
                # Mock regional query result
                mock_result = MagicMock()
                mock_result.region = "us-east-1"
                mock_result.data = [{"event_id": "123", "value": 100}]
                mock_result.processing_time = 0.5
                mock_result.record_count = 1
                mock_execute.return_value = mock_result
                
                # Test analytics query
                result = await analytics_engine.route_analytics_query(
                    "test-tenant-1", 
                    "SELECT * FROM events",
                    ["us-east-1"]
                )
                
                assert "data" in result
                assert "metadata" in result
                assert result["metadata"]["regions_queried"] == ["us-east-1"]
                assert result["metadata"]["total_records"] == 1
    
    @pytest.mark.asyncio
    async def test_regional_access_validation(self, analytics_engine):
        """Test validation of regional access for analytics queries."""
        # Mock tenant allowed regions
        with patch.object(analytics_engine, '_get_tenant_allowed_regions', return_value=["us-east-1"]):
            # Test allowed region
            allowed = await analytics_engine._validate_regional_access("test-tenant-1", ["us-east-1"])
            assert allowed is True
            
            # Test denied region
            allowed = await analytics_engine._validate_regional_access("test-tenant-1", ["eu-west-1"])
            assert allowed is False


class TestRegionalMiddleware:
    """Test RegionalMiddleware functionality."""
    
    @pytest.fixture
    async def regional_middleware(self):
        """Create RegionalMiddleware instance for testing."""
        region_router = AsyncMock(spec=RegionRouter)
        return RegionalMiddleware(region_router)
    
    @pytest.mark.asyncio
    async def test_regional_access_validator(self):
        """Test RegionalAccessValidator."""
        region_router = AsyncMock(spec=RegionRouter)
        validator = RegionalAccessValidator(region_router)
        
        # Mock regional access check
        region_router.enforce_regional_access.return_value = True
        
        # Test resource access validation
        allowed = await validator.validate_resource_access("test-tenant-1", "us-east-1", "analytics")
        assert allowed is True
        
        region_router.enforce_regional_access.assert_called_once_with("test-tenant-1", "us-east-1")
    
    @pytest.mark.asyncio
    async def test_regional_metrics_collector(self):
        """Test RegionalMetricsCollector."""
        from libs.middleware.regional_middleware import RegionalMetricsCollector
        
        collector = RegionalMetricsCollector()
        
        # Record some metrics
        collector.record_request("test-tenant-1", "us-east-1", "/api/test", "GET", 0.5)
        collector.record_cross_region_denial("test-tenant-1", "us-east-1", "eu-west-1")
        
        # Get stats
        stats = collector.get_regional_stats()
        
        assert "request_counts" in stats
        assert "cross_region_denials" in stats
        assert stats["request_counts"]["us-east-1"] == 1
        assert "us-east-1->eu-west-1" in stats["cross_region_denials"]


class TestDataResidencyEnforcement:
    """Test data residency enforcement across services."""
    
    @pytest.mark.asyncio
    async def test_tenant_cannot_read_cross_region_artifacts(self):
        """Test that tenant in ap-southeast-1 cannot read eu-west-1 artifacts."""
        region_router = AsyncMock(spec=RegionRouter)
        
        # Mock tenant config for ap-southeast-1
        region_router.tenant_configs["test-tenant-1"] = MagicMock()
        region_router.tenant_configs["test-tenant-1"].data_region = "ap-southeast-1"
        region_router.tenant_configs["test-tenant-1"].allowed_regions = ["ap-southeast-1"]
        
        # Test cross-region access denial
        access_validator = RegionalAccessValidator(region_router)
        allowed = await access_validator.validate_resource_access(
            "test-tenant-1", "eu-west-1", "analytics"
        )
        
        assert allowed is False
    
    @pytest.mark.asyncio
    async def test_traces_include_tenant_and_region(self):
        """Test that traces include tenant_id and region information."""
        # This would test OpenTelemetry trace attributes
        # For now, we'll test the middleware adds the correct headers
        
        region_router = AsyncMock(spec=RegionRouter)
        region_router.get_tenant_region.return_value = "us-east-1"
        region_router.get_tenant_allowed_regions.return_value = ["us-east-1"]
        
        middleware = RegionalMiddleware(region_router)
        
        # Mock request and response
        request = AsyncMock()
        request.headers = {}
        request.state = MagicMock()
        
        response = MagicMock()
        response.headers = {}
        
        # Test header addition
        result_response = middleware._add_regional_headers(response, "test-tenant-1", "us-east-1")
        
        assert result_response.headers["X-Data-Region"] == "us-east-1"
        assert result_response.headers["X-Tenant-ID"] == "test-tenant-1"
    
    @pytest.mark.asyncio
    async def test_dashboards_show_request_counts_by_region(self):
        """Test that dashboards can show request counts by region."""
        from libs.middleware.regional_middleware import RegionalMetricsCollector
        
        collector = RegionalMetricsCollector()
        
        # Record requests from different regions
        collector.record_request("tenant-1", "us-east-1", "/api/chat", "POST", 0.3)
        collector.record_request("tenant-2", "eu-west-1", "/api/chat", "POST", 0.4)
        collector.record_request("tenant-3", "ap-southeast-1", "/api/chat", "POST", 0.5)
        
        # Get stats
        stats = collector.get_regional_stats()
        
        assert stats["request_counts"]["us-east-1"] == 1
        assert stats["request_counts"]["eu-west-1"] == 1
        assert stats["request_counts"]["ap-southeast-1"] == 1


@pytest.mark.integration
class TestRegionalIntegration:
    """Integration tests for regional features."""
    
    @pytest.mark.asyncio
    async def test_full_regional_workflow(self):
        """Test complete regional workflow from request to analytics."""
        # This would test the full integration
        # 1. Request comes in with tenant
        # 2. Regional middleware determines region
        # 3. RegionRouter selects appropriate provider
        # 4. Analytics queries are routed to regional replicas
        # 5. Results are aggregated and returned
        
        pass  # Implementation would depend on full integration setup
