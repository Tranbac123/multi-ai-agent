"""Integration tests for resilient tool adapters."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
import structlog

from libs.adapters import (
    BaseToolAdapter, CircuitBreaker, CircuitBreakerConfig,
    RetryPolicy, RetryConfig, TimeoutHandler, TimeoutConfig,
    Bulkhead, BulkheadConfig, RateLimiter, RateLimitConfig,
    HealthChecker, HealthCheckConfig, AdapterConfig
)
from libs.adapters.http_adapter import HTTPAdapter, HTTPAdapterConfig
from libs.adapters.database_adapter import DatabaseAdapter, DatabaseAdapterConfig

logger = structlog.get_logger(__name__)


class MockToolAdapter(BaseToolAdapter):
    """Mock tool adapter for testing."""
    
    def __init__(self, name: str, config: AdapterConfig = None, should_fail: bool = False):
        super().__init__(name, config)
        self.should_fail = should_fail
        self.call_count = 0
    
    async def _execute_tool(self, *args, **kwargs):
        """Mock tool execution."""
        self.call_count += 1
        await asyncio.sleep(0.1)  # Simulate work
        
        if self.should_fail:
            raise Exception("Mock tool failure")
        
        return {"result": "success", "args": args, "kwargs": kwargs}


@pytest.mark.asyncio
class TestResilientAdapters:
    """Test resilient tool adapters."""
    
    async def test_circuit_breaker(self):
        """Test circuit breaker functionality."""
        config = CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=1.0,
            success_threshold=2
        )
        cb = CircuitBreaker("test_cb", config)
        
        # Test successful calls
        async def success_func():
            return "success"
        
        result = await cb.call(success_func)
        assert result == "success"
        assert cb.state.value == "closed"
        
        # Test failure threshold
        async def fail_func():
            raise Exception("test failure")
        
        # Should fail after threshold
        for i in range(3):
            with pytest.raises(Exception):
                await cb.call(fail_func)
        
        assert cb.state.value == "open"
        
        # Test open circuit rejects calls
        with pytest.raises(Exception):
            await cb.call(success_func)
    
    async def test_retry_policy(self):
        """Test retry policy functionality."""
        config = RetryConfig(
            max_attempts=3,
            base_delay=0.1,
            strategy="exponential"
        )
        retry = RetryPolicy(config)
        
        call_count = 0
        
        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("temporary failure")
            return "success"
        
        result = await retry.execute(flaky_func)
        assert result == "success"
        assert call_count == 3
        
        # Test retry exhaustion
        call_count = 0
        config.max_attempts = 2
        
        with pytest.raises(Exception):
            await retry.execute(flaky_func)
    
    async def test_timeout_handler(self):
        """Test timeout handler functionality."""
        config = TimeoutConfig(default_timeout=0.5)
        handler = TimeoutHandler(config)
        
        # Test successful call
        async def fast_func():
            await asyncio.sleep(0.1)
            return "success"
        
        result = await handler.execute_with_timeout(fast_func)
        assert result == "success"
        
        # Test timeout
        async def slow_func():
            await asyncio.sleep(1.0)
            return "success"
        
        with pytest.raises(Exception):
            await handler.execute_with_timeout(slow_func, timeout=0.2)
    
    async def test_bulkhead(self):
        """Test bulkhead functionality."""
        config = BulkheadConfig(max_concurrent=2)
        bulkhead = Bulkhead("test_bh", config)
        
        # Test concurrent execution
        async def work_func(delay: float):
            await asyncio.sleep(delay)
            return "done"
        
        # Start 3 tasks, only 2 should run concurrently
        tasks = [
            bulkhead.execute(work_func, 0.1),
            bulkhead.execute(work_func, 0.1),
            bulkhead.execute(work_func, 0.1)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All should complete successfully
        assert all(r == "done" for r in results)
        
        # Check stats
        stats = bulkhead.get_stats()
        assert stats["completed_count"] == 3
    
    async def test_rate_limiter(self):
        """Test rate limiter functionality."""
        config = RateLimitConfig(requests_per_second=10.0)
        limiter = RateLimiter("test_rl", config)
        
        # Test rate limiting
        async def request_func():
            return "success"
        
        # Make many requests quickly
        tasks = [limiter.execute(request_func) for _ in range(20)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Some should succeed, some might be rate limited
        success_count = sum(1 for r in results if r == "success")
        assert success_count > 0
        
        # Check stats
        stats = limiter.get_stats()
        assert stats["total_requests"] == 20
    
    async def test_health_checker(self):
        """Test health checker functionality."""
        config = HealthCheckConfig(
            check_interval=0.1,
            failure_threshold=2,
            success_threshold=1
        )
        checker = HealthChecker("test_hc", config)
        
        # Set up health check function
        check_count = 0
        
        async def health_check():
            nonlocal check_count
            check_count += 1
            return check_count > 2  # Fail first 2 times, then succeed
        
        checker.set_check_function(health_check)
        
        # Start checker
        await checker.start()
        
        # Wait for checks to complete
        await asyncio.sleep(0.5)
        
        # Stop checker
        await checker.stop()
        
        # Check that health check was called
        assert check_count > 0
        
        # Check final status
        status = checker.get_status()
        assert status["consecutive_successes"] > 0
    
    async def test_mock_tool_adapter(self):
        """Test mock tool adapter with all resilience patterns."""
        config = AdapterConfig()
        adapter = MockToolAdapter("test_adapter", config)
        
        # Start adapter
        await adapter.start()
        
        # Test successful execution
        result = await adapter.execute("arg1", "arg2", key="value")
        assert result["result"] == "success"
        assert adapter.call_count == 1
        
        # Test with failing adapter
        failing_adapter = MockToolAdapter("failing_adapter", config, should_fail=True)
        await failing_adapter.start()
        
        # Should fail with retry
        with pytest.raises(Exception):
            await failing_adapter.execute("test")
        
        # Stop adapters
        await adapter.stop()
        await failing_adapter.stop()
    
    async def test_http_adapter(self):
        """Test HTTP adapter."""
        config = HTTPAdapterConfig(
            base_url="https://httpbin.org",
            timeout=10.0
        )
        adapter = HTTPAdapter("test_http", config)
        
        # Start adapter
        await adapter.start()
        
        try:
            # Test GET request
            response = await adapter.get("/get")
            assert response.status_code == 200
            
            # Test POST request
            response = await adapter.post("/post", json={"test": "data"})
            assert response.status_code == 200
            
        finally:
            # Clean up
            await adapter.stop()
    
    async def test_database_adapter(self):
        """Test database adapter."""
        config = DatabaseAdapterConfig(
            connection_string="sqlite:///test.db"
        )
        adapter = DatabaseAdapter("test_db", config)
        
        # Start adapter
        await adapter.start()
        
        try:
            # Test query execution (this will fail without actual DB)
            with pytest.raises(Exception):
                await adapter.execute_query("SELECT 1")
            
        finally:
            # Clean up
            await adapter.stop()
    
    async def test_adapter_manager(self):
        """Test adapter manager."""
        from libs.adapters.base_adapter import ToolAdapterManager
        
        manager = ToolAdapterManager()
        
        # Add adapters
        adapter1 = MockToolAdapter("adapter1")
        adapter2 = MockToolAdapter("adapter2")
        
        manager.add_adapter("adapter1", adapter1)
        manager.add_adapter("adapter2", adapter2)
        
        # Start all adapters
        await manager.start_all()
        
        # Test execution
        result1 = await adapter1.execute("test1")
        result2 = await adapter2.execute("test2")
        
        assert result1["result"] == "success"
        assert result2["result"] == "success"
        
        # Test manager stats
        stats = manager.get_all_stats()
        assert len(stats) == 2
        assert "adapter1" in stats
        assert "adapter2" in stats
        
        # Stop all adapters
        await manager.stop_all()
    
    async def test_integration_scenario(self):
        """Test integration scenario with multiple resilience patterns."""
        # Create adapter with all resilience patterns
        config = AdapterConfig()
        config.circuit_breaker.failure_threshold = 2
        config.retry_policy.max_attempts = 3
        config.timeout.default_timeout = 1.0
        config.bulkhead.max_concurrent = 5
        config.rate_limiter.requests_per_second = 10.0
        
        adapter = MockToolAdapter("integration_test", config)
        await adapter.start()
        
        try:
            # Test normal operation
            result = await adapter.execute("test")
            assert result["result"] == "success"
            
            # Test concurrent execution
            tasks = [adapter.execute(f"test_{i}") for i in range(10)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Most should succeed
            success_count = sum(1 for r in results if isinstance(r, dict) and r.get("result") == "success")
            assert success_count > 0
            
            # Test stats
            stats = adapter.get_stats()
            assert "circuit_breaker" in stats
            assert "bulkhead" in stats
            assert "rate_limiter" in stats
            assert "health_checker" in stats
            
        finally:
            await adapter.stop()


if __name__ == "__main__":
    pytest.main([__file__])
