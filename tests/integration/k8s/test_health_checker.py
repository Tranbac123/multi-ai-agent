"""Test health checker functionality."""

import pytest
import asyncio
import json
from unittest.mock import Mock, AsyncMock, patch
from aiohttp import ClientTimeout, ClientResponse

from infra.k8s.health.enhanced_health_checker import (
    EnhancedHealthChecker,
    HealthCheck,
    HealthResult,
    HealthStatus,
)


class TestHealthCheck:
    """Test HealthCheck dataclass."""

    def test_health_check_creation(self):
        """Test creating a health check."""
        health_check = HealthCheck(
            name="test-service",
            url="http://test-service:8000/health",
            timeout=5.0,
            expected_status=200,
            expected_response={"status": "ok"},
            critical=True,
            retries=3,
            retry_delay=1.0
        )
        
        assert health_check.name == "test-service"
        assert health_check.url == "http://test-service:8000/health"
        assert health_check.timeout == 5.0
        assert health_check.expected_status == 200
        assert health_check.expected_response == {"status": "ok"}
        assert health_check.critical is True
        assert health_check.retries == 3
        assert health_check.retry_delay == 1.0

    def test_health_check_defaults(self):
        """Test health check with default values."""
        health_check = HealthCheck(
            name="test-service",
            url="http://test-service:8000/health"
        )
        
        assert health_check.timeout == 5.0
        assert health_check.expected_status == 200
        assert health_check.expected_response is None
        assert health_check.critical is True
        assert health_check.retries == 3
        assert health_check.retry_delay == 1.0


class TestHealthResult:
    """Test HealthResult dataclass."""

    def test_health_result_creation(self):
        """Test creating a health result."""
        result = HealthResult(
            name="test-service",
            status=HealthStatus.HEALTHY,
            response_time=0.5,
            details={"status": "ok"}
        )
        
        assert result.name == "test-service"
        assert result.status == HealthStatus.HEALTHY
        assert result.response_time == 0.5
        assert result.error is None
        assert result.details == {"status": "ok"}

    def test_health_result_with_error(self):
        """Test creating a health result with error."""
        result = HealthResult(
            name="test-service",
            status=HealthStatus.UNHEALTHY,
            response_time=5.0,
            error="Connection timeout"
        )
        
        assert result.status == HealthStatus.UNHEALTHY
        assert result.error == "Connection timeout"


class TestEnhancedHealthChecker:
    """Test EnhancedHealthChecker functionality."""

    @pytest.fixture
    def health_checker(self):
        """Create EnhancedHealthChecker instance."""
        return EnhancedHealthChecker()

    @pytest.fixture
    def mock_health_check(self):
        """Create mock health check."""
        return HealthCheck(
            name="test-service",
            url="http://test-service:8000/health",
            expected_status=200,
            expected_response={"status": "ok"}
        )

    def test_health_checker_initialization(self, health_checker):
        """Test health checker initialization."""
        assert health_checker.session is None
        assert health_checker.health_checks == []
        assert health_checker.results == []

    def test_add_health_check(self, health_checker, mock_health_check):
        """Test adding health checks."""
        health_checker.add_health_check(mock_health_check)
        
        assert len(health_checker.health_checks) == 1
        assert health_checker.health_checks[0] == mock_health_check

    @pytest.mark.asyncio
    async def test_context_manager(self, health_checker):
        """Test async context manager functionality."""
        async with health_checker as checker:
            assert checker.session is not None
            assert isinstance(checker.session, AsyncMock)
        
        # Session should be closed after context exit
        assert health_checker.session is None

    @pytest.mark.asyncio
    async def test_check_service_health_success(self, health_checker, mock_health_check):
        """Test successful health check."""
        # Mock successful response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                result = await health_checker.check_service_health(mock_health_check)
            
            assert result.name == "test-service"
            assert result.status == HealthStatus.HEALTHY
            assert result.response_time > 0
            assert result.error is None
            assert result.details == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_check_service_health_wrong_status(self, health_checker, mock_health_check):
        """Test health check with wrong status code."""
        # Mock response with wrong status
        mock_response = Mock()
        mock_response.status = 500
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                result = await health_checker.check_service_health(mock_health_check)
            
            assert result.status == HealthStatus.UNHEALTHY
            assert "Expected status 200, got 500" in result.error

    @pytest.mark.asyncio
    async def test_check_service_health_wrong_response(self, health_checker, mock_health_check):
        """Test health check with wrong response content."""
        # Mock response with wrong content
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "error"})
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                result = await health_checker.check_service_health(mock_health_check)
            
            assert result.status == HealthStatus.UNHEALTHY
            assert "Expected 'status' to be 'ok'" in result.error

    @pytest.mark.asyncio
    async def test_check_service_health_timeout(self, health_checker, mock_health_check):
        """Test health check timeout."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = asyncio.TimeoutError()
            
            async with health_checker:
                result = await health_checker.check_service_health(mock_health_check)
            
            assert result.status == HealthStatus.UNHEALTHY
            assert "Timeout after 5.0s" in result.error

    @pytest.mark.asyncio
    async def test_check_service_health_connection_error(self, health_checker, mock_health_check):
        """Test health check connection error."""
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = Exception("Connection refused")
            
            async with health_checker:
                result = await health_checker.check_service_health(mock_health_check)
            
            assert result.status == HealthStatus.UNHEALTHY
            assert "Unexpected error: Connection refused" in result.error

    @pytest.mark.asyncio
    async def test_check_service_health_slow_response(self, health_checker, mock_health_check):
        """Test health check with slow response."""
        # Mock slow response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        
        with patch('aiohttp.ClientSession.get') as mock_get, \
             patch('time.time', side_effect=[0, 6]):  # 6 second response time
            
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                result = await health_checker.check_service_health(mock_health_check)
            
            assert result.status == HealthStatus.DEGRADED
            assert result.response_time == 6.0

    @pytest.mark.asyncio
    async def test_check_service_health_with_retries(self, health_checker):
        """Test health check with retries."""
        # Create health check with retries
        health_check = HealthCheck(
            name="test-service",
            url="http://test-service:8000/health",
            retries=2,
            retry_delay=0.1
        )
        
        # Mock responses: first two fail, third succeeds
        mock_responses = [
            Mock(status=500),
            Mock(status=500),
            Mock(status=200, json=AsyncMock(return_value={"status": "ok"}))
        ]
        
        with patch('aiohttp.ClientSession.get') as mock_get, \
             patch('asyncio.sleep') as mock_sleep:
            
            mock_get.return_value.__aenter__.side_effect = mock_responses
            
            async with health_checker:
                result = await health_checker.check_service_health(health_check)
            
            assert result.status == HealthStatus.HEALTHY
            assert mock_get.call_count == 3  # Initial + 2 retries
            assert mock_sleep.call_count == 2  # 2 retry delays

    @pytest.mark.asyncio
    async def test_check_service_health_retries_exhausted(self, health_checker):
        """Test health check with all retries exhausted."""
        health_check = HealthCheck(
            name="test-service",
            url="http://test-service:8000/health",
            retries=2,
            retry_delay=0.1
        )
        
        # Mock all responses to fail
        mock_response = Mock(status=500)
        
        with patch('aiohttp.ClientSession.get') as mock_get, \
             patch('asyncio.sleep') as mock_sleep:
            
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                result = await health_checker.check_service_health(health_check)
            
            assert result.status == HealthStatus.UNHEALTHY
            assert mock_get.call_count == 3  # Initial + 2 retries
            assert mock_sleep.call_count == 2  # 2 retry delays

    @pytest.mark.asyncio
    async def test_run_all_health_checks(self, health_checker):
        """Test running all health checks concurrently."""
        # Add multiple health checks
        health_checks = [
            HealthCheck(name="service1", url="http://service1:8000/health"),
            HealthCheck(name="service2", url="http://service2:8000/health"),
            HealthCheck(name="service3", url="http://service3:8000/health")
        ]
        
        for check in health_checks:
            health_checker.add_health_check(check)
        
        # Mock successful responses
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                results = await health_checker.run_all_health_checks()
            
            assert len(results) == 3
            assert all(result.status == HealthStatus.HEALTHY for result in results)

    @pytest.mark.asyncio
    async def test_run_all_health_checks_with_exceptions(self, health_checker):
        """Test running health checks with exceptions."""
        health_check = HealthCheck(name="test-service", url="http://test-service:8000/health")
        health_checker.add_health_check(health_check)
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.side_effect = Exception("Network error")
            
            async with health_checker:
                results = await health_checker.run_all_health_checks()
            
            assert len(results) == 1
            assert results[0].status == HealthStatus.UNHEALTHY
            assert "Network error" in results[0].error

    def test_get_overall_status_healthy(self, health_checker):
        """Test getting overall status when all services are healthy."""
        results = [
            HealthResult("service1", HealthStatus.HEALTHY, 0.5),
            HealthResult("service2", HealthStatus.HEALTHY, 0.3),
            HealthResult("service3", HealthStatus.HEALTHY, 0.4)
        ]
        health_checker.results = results
        
        status = health_checker.get_overall_status()
        assert status == HealthStatus.HEALTHY

    def test_get_overall_status_degraded(self, health_checker):
        """Test getting overall status when some services are degraded."""
        results = [
            HealthResult("service1", HealthStatus.HEALTHY, 0.5),
            HealthResult("service2", HealthStatus.DEGRADED, 6.0),
            HealthResult("service3", HealthStatus.HEALTHY, 0.4)
        ]
        health_checker.results = results
        
        status = health_checker.get_overall_status()
        assert status == HealthStatus.DEGRADED

    def test_get_overall_status_unhealthy_critical(self, health_checker):
        """Test getting overall status when critical services are unhealthy."""
        # Add health checks with critical flag
        critical_check = HealthCheck(name="critical-service", url="http://critical:8000/health", critical=True)
        non_critical_check = HealthCheck(name="non-critical-service", url="http://non-critical:8000/health", critical=False)
        
        health_checker.health_checks = [critical_check, non_critical_check]
        
        results = [
            HealthResult("critical-service", HealthStatus.UNHEALTHY, 0.0),
            HealthResult("non-critical-service", HealthStatus.UNHEALTHY, 0.0)
        ]
        health_checker.results = results
        
        status = health_checker.get_overall_status()
        assert status == HealthStatus.UNHEALTHY

    def test_get_overall_status_unhealthy_non_critical(self, health_checker):
        """Test getting overall status when only non-critical services are unhealthy."""
        # Add health checks
        critical_check = HealthCheck(name="critical-service", url="http://critical:8000/health", critical=True)
        non_critical_check = HealthCheck(name="non-critical-service", url="http://non-critical:8000/health", critical=False)
        
        health_checker.health_checks = [critical_check, non_critical_check]
        
        results = [
            HealthResult("critical-service", HealthStatus.HEALTHY, 0.5),
            HealthResult("non-critical-service", HealthStatus.UNHEALTHY, 0.0)
        ]
        health_checker.results = results
        
        status = health_checker.get_overall_status()
        assert status == HealthStatus.HEALTHY  # Should still be healthy

    def test_get_overall_status_no_results(self, health_checker):
        """Test getting overall status with no results."""
        status = health_checker.get_overall_status()
        assert status == HealthStatus.UNKNOWN

    def test_generate_report(self, health_checker):
        """Test generating health report."""
        results = [
            HealthResult("service1", HealthStatus.HEALTHY, 0.5, details={"status": "ok"}),
            HealthResult("service2", HealthStatus.DEGRADED, 6.0, details={"status": "slow"}),
            HealthResult("service3", HealthStatus.UNHEALTHY, 0.0, error="Connection failed")
        ]
        health_checker.results = results
        
        report = health_checker.generate_report()
        
        assert "timestamp" in report
        assert "overall_status" in report
        assert "total_checks" in report
        assert "healthy_checks" in report
        assert "degraded_checks" in report
        assert "unhealthy_checks" in report
        assert "unknown_checks" in report
        assert "checks" in report
        
        assert report["total_checks"] == 3
        assert report["healthy_checks"] == 1
        assert report["degraded_checks"] == 1
        assert report["unhealthy_checks"] == 1
        assert report["unknown_checks"] == 0
        
        assert len(report["checks"]) == 3
        
        # Check individual check details
        check_details = report["checks"]
        assert check_details[0]["name"] == "service1"
        assert check_details[0]["status"] == "healthy"
        assert check_details[0]["response_time"] == 0.5
        assert check_details[0]["error"] is None
        assert check_details[0]["details"] == {"status": "ok"}
        
        assert check_details[1]["name"] == "service2"
        assert check_details[1]["status"] == "degraded"
        assert check_details[1]["response_time"] == 6.0
        
        assert check_details[2]["name"] == "service3"
        assert check_details[2]["status"] == "unhealthy"
        assert check_details[2]["error"] == "Connection failed"

    @pytest.mark.asyncio
    async def test_invalid_json_response(self, health_checker, mock_health_check):
        """Test health check with invalid JSON response."""
        # Mock response with invalid JSON
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                result = await health_checker.check_service_health(mock_health_check)
            
            assert result.status == HealthStatus.UNHEALTHY
            assert "Invalid JSON response" in result.error

    @pytest.mark.asyncio
    async def test_missing_expected_key(self, health_checker, mock_health_check):
        """Test health check with missing expected key in response."""
        # Mock response missing expected key
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"other_field": "value"})
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                result = await health_checker.check_service_health(mock_health_check)
            
            assert result.status == HealthStatus.UNHEALTHY
            assert "Missing expected key 'status'" in result.error

    @pytest.mark.asyncio
    async def test_basic_health_check_no_expected_response(self, health_checker):
        """Test basic health check without expected response validation."""
        health_check = HealthCheck(
            name="basic-service",
            url="http://basic-service:8000/health",
            expected_status=200
            # No expected_response
        )
        
        # Mock successful response
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"status": "ok"})
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                result = await health_checker.check_service_health(health_check)
            
            assert result.status == HealthStatus.HEALTHY
            assert result.details == {"status": "ok"}

    @pytest.mark.asyncio
    async def test_basic_health_check_non_json_response(self, health_checker):
        """Test basic health check with non-JSON response."""
        health_check = HealthCheck(
            name="basic-service",
            url="http://basic-service:8000/health",
            expected_status=200
        )
        
        # Mock response with non-JSON content
        mock_response = Mock()
        mock_response.status = 200
        mock_response.json = AsyncMock(side_effect=json.JSONDecodeError("Invalid JSON", "", 0))
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_get.return_value.__aenter__.return_value = mock_response
            
            async with health_checker:
                result = await health_checker.check_service_health(health_check)
            
            assert result.status == HealthStatus.HEALTHY
            assert result.details == {"status": "ok"}  # Default fallback

    def test_health_status_enum_values(self):
        """Test HealthStatus enum values."""
        assert HealthStatus.HEALTHY.value == "healthy"
        assert HealthStatus.UNHEALTHY.value == "unhealthy"
        assert HealthStatus.DEGRADED.value == "degraded"
        assert HealthStatus.UNKNOWN.value == "unknown"
