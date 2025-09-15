"""API performance regression tests with baseline comparison."""

import pytest
import asyncio
import time
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from tests.performance import (
    PerformanceTestType, LoadProfile, PerformanceBaseline, 
    PerformanceRegressionThreshold, PerformanceTestResult
)
from tests._fixtures.factories import factory, TenantTier


class MockAPIClient:
    """Mock API client for performance testing."""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.session_stats: Dict[str, List[float]] = {}
        self.error_counts: Dict[str, int] = {}
        self.response_times: Dict[str, List[float]] = {}
    
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Mock GET request with performance tracking."""
        start_time = time.time()
        
        # Simulate API response time
        await asyncio.sleep(0.1 + (hash(endpoint) % 100) / 1000)  # 100-200ms
        
        response_time = (time.time() - start_time) * 1000  # Convert to ms
        
        # Track response time
        if endpoint not in self.response_times:
            self.response_times[endpoint] = []
        self.response_times[endpoint].append(response_time)
        
        # Simulate occasional errors
        import random
        if random.random() < 0.02:  # 2% error rate
            if endpoint not in self.error_counts:
                self.error_counts[endpoint] = 0
            self.error_counts[endpoint] += 1
            raise Exception(f"API error for {endpoint}")
        
        return {
            "status": "success",
            "data": {"message": f"Response from {endpoint}"},
            "response_time_ms": response_time
        }
    
    async def post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Mock POST request with performance tracking."""
        start_time = time.time()
        
        # Simulate API response time (POST is typically slower)
        await asyncio.sleep(0.15 + (hash(endpoint) % 150) / 1000)  # 150-300ms
        
        response_time = (time.time() - start_time) * 1000
        
        # Track response time
        if endpoint not in self.response_times:
            self.response_times[endpoint] = []
        self.response_times[endpoint].append(response_time)
        
        # Simulate occasional errors
        import random
        if random.random() < 0.03:  # 3% error rate for POST
            if endpoint not in self.error_counts:
                self.error_counts[endpoint] = 0
            self.error_counts[endpoint] += 1
            raise Exception(f"API error for {endpoint}")
        
        return {
            "status": "success",
            "data": data,
            "response_time_ms": response_time
        }
    
    def get_metrics(self, endpoint: str) -> Dict[str, float]:
        """Get performance metrics for an endpoint."""
        if endpoint not in self.response_times:
            return {}
        
        times = self.response_times[endpoint]
        error_count = self.error_counts.get(endpoint, 0)
        total_requests = len(times)
        
        if not times:
            return {}
        
        # Calculate percentiles
        sorted_times = sorted(times)
        p50 = sorted_times[int(len(sorted_times) * 0.5)]
        p95 = sorted_times[int(len(sorted_times) * 0.95)]
        p99 = sorted_times[int(len(sorted_times) * 0.99)]
        
        return {
            "p50_latency_ms": p50,
            "p95_latency_ms": p95,
            "p99_latency_ms": p99,
            "avg_latency_ms": sum(times) / len(times),
            "error_rate_percent": (error_count / total_requests) * 100,
            "total_requests": total_requests,
            "throughput_rps": total_requests / (time.time() - min(times) / 1000) if times else 0
        }


class PerformanceBaselineManager:
    """Manages performance baselines and regression detection."""
    
    def __init__(self):
        self.baselines: Dict[str, PerformanceBaseline] = {}
        self.thresholds = PerformanceRegressionThreshold()
    
    def add_baseline(self, baseline: PerformanceBaseline):
        """Add a performance baseline."""
        key = f"{baseline.test_type.value}:{baseline.endpoint}"
        self.baselines[key] = baseline
    
    def get_baseline(self, test_type: PerformanceTestType, endpoint: str) -> Optional[PerformanceBaseline]:
        """Get baseline for a specific test type and endpoint."""
        key = f"{test_type.value}:{endpoint}"
        return self.baselines.get(key)
    
    def detect_regression(self, test_type: PerformanceTestType, endpoint: str, current_metrics: Dict[str, float]) -> PerformanceTestResult:
        """Detect performance regression against baseline."""
        baseline = self.get_baseline(test_type, endpoint)
        if not baseline:
            raise ValueError(f"No baseline found for {test_type.value}:{endpoint}")
        
        # Calculate regression percentages
        latency_regression_p50 = ((current_metrics.get("p50_latency_ms", 0) - baseline.p50_latency_ms) / baseline.p50_latency_ms) * 100
        latency_regression_p95 = ((current_metrics.get("p95_latency_ms", 0) - baseline.p95_latency_ms) / baseline.p95_latency_ms) * 100
        latency_regression_p99 = ((current_metrics.get("p99_latency_ms", 0) - baseline.p99_latency_ms) / baseline.p99_latency_ms) * 100
        
        throughput_regression = ((baseline.throughput_rps - current_metrics.get("throughput_rps", 0)) / baseline.throughput_rps) * 100
        error_rate_increase = current_metrics.get("error_rate_percent", 0) - baseline.error_rate_percent
        
        # Detect regressions
        regression_detected = False
        regression_details = {}
        
        if latency_regression_p95 > self.thresholds.latency_regression_percent:
            regression_detected = True
            regression_details["p95_latency_regression"] = latency_regression_p95
        
        if latency_regression_p99 > self.thresholds.latency_regression_percent:
            regression_detected = True
            regression_details["p99_latency_regression"] = latency_regression_p99
        
        if throughput_regression > self.thresholds.throughput_regression_percent:
            regression_detected = True
            regression_details["throughput_regression"] = throughput_regression
        
        if error_rate_increase > self.thresholds.error_rate_increase_percent:
            regression_detected = True
            regression_details["error_rate_increase"] = error_rate_increase
        
        # Check critical latency threshold
        if current_metrics.get("p99_latency_ms", 0) > self.thresholds.critical_latency_ms:
            regression_detected = True
            regression_details["critical_latency_exceeded"] = current_metrics.get("p99_latency_ms", 0)
        
        passed = not regression_detected
        
        return PerformanceTestResult(
            test_name=f"{test_type.value}_{endpoint}",
            baseline=baseline,
            current_metrics=current_metrics,
            regression_detected=regression_detected,
            regression_details=regression_details,
            passed=passed,
            timestamp=datetime.now()
        )


class TestAPIPerformanceRegression:
    """Test API performance regression detection."""
    
    @pytest.fixture
    def mock_api_client(self):
        """Create mock API client."""
        return MockAPIClient()
    
    @pytest.fixture
    def baseline_manager(self):
        """Create baseline manager."""
        return PerformanceBaselineManager()
    
    @pytest.fixture
    def sample_baseline(self):
        """Create sample performance baseline."""
        return PerformanceBaseline(
            test_type=PerformanceTestType.API_ENDPOINT,
            endpoint="/api/query",
            p50_latency_ms=150.0,
            p95_latency_ms=300.0,
            p99_latency_ms=500.0,
            throughput_rps=100.0,
            error_rate_percent=1.0,
            timestamp=datetime.now() - timedelta(days=1),
            version="v1.0.0"
        )
    
    @pytest.mark.asyncio
    async def test_api_endpoint_performance(self, mock_api_client):
        """Test API endpoint performance measurement."""
        endpoint = "/api/query"
        
        # Make multiple requests
        requests_count = 50
        for i in range(requests_count):
            try:
                await mock_api_client.get(endpoint, {"query": f"test_query_{i}"})
            except Exception:
                pass  # Handle errors gracefully
        
        # Get metrics
        metrics = mock_api_client.get_metrics(endpoint)
        
        # Validate metrics
        assert "p50_latency_ms" in metrics
        assert "p95_latency_ms" in metrics
        assert "p99_latency_ms" in metrics
        assert "error_rate_percent" in metrics
        assert "total_requests" in metrics
        
        # Check reasonable values
        assert metrics["p50_latency_ms"] > 0
        assert metrics["p95_latency_ms"] >= metrics["p50_latency_ms"]
        assert metrics["p99_latency_ms"] >= metrics["p95_latency_ms"]
        assert metrics["total_requests"] == requests_count
    
    @pytest.mark.asyncio
    async def test_performance_baseline_comparison(self, mock_api_client, baseline_manager, sample_baseline):
        """Test performance baseline comparison."""
        # Add baseline
        baseline_manager.add_baseline(sample_baseline)
        
        # Run performance test
        endpoint = "/api/query"
        requests_count = 30
        
        for i in range(requests_count):
            try:
                await mock_api_client.get(endpoint, {"query": f"baseline_test_{i}"})
            except Exception:
                pass
        
        # Get current metrics
        current_metrics = mock_api_client.get_metrics(endpoint)
        
        # Detect regression
        result = baseline_manager.detect_regression(
            PerformanceTestType.API_ENDPOINT,
            endpoint,
            current_metrics
        )
        
        # Validate result
        assert result.baseline == sample_baseline
        assert result.current_metrics == current_metrics
        assert isinstance(result.regression_detected, bool)
        assert isinstance(result.passed, bool)
        assert result.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_latency_regression_detection(self, mock_api_client, baseline_manager):
        """Test latency regression detection."""
        # Create baseline with good performance
        baseline = PerformanceBaseline(
            test_type=PerformanceTestType.API_ENDPOINT,
            endpoint="/api/slow",
            p50_latency_ms=100.0,
            p95_latency_ms=200.0,
            p99_latency_ms=300.0,
            throughput_rps=150.0,
            error_rate_percent=0.5,
            timestamp=datetime.now() - timedelta(days=1),
            version="v1.0.0"
        )
        
        baseline_manager.add_baseline(baseline)
        
        # Simulate degraded performance
        current_metrics = {
            "p50_latency_ms": 120.0,  # 20% increase
            "p95_latency_ms": 250.0,  # 25% increase (should trigger regression)
            "p99_latency_ms": 400.0,  # 33% increase (should trigger regression)
            "throughput_rps": 140.0,  # Slight decrease
            "error_rate_percent": 1.0,  # Slight increase
            "total_requests": 50
        }
        
        # Detect regression
        result = baseline_manager.detect_regression(
            PerformanceTestType.API_ENDPOINT,
            "/api/slow",
            current_metrics
        )
        
        # Should detect regression
        assert result.regression_detected is True
        assert result.passed is False
        assert "p95_latency_regression" in result.regression_details
        assert "p99_latency_regression" in result.regression_details
    
    @pytest.mark.asyncio
    async def test_throughput_regression_detection(self, mock_api_client, baseline_manager):
        """Test throughput regression detection."""
        # Create baseline
        baseline = PerformanceBaseline(
            test_type=PerformanceTestType.API_ENDPOINT,
            endpoint="/api/throughput",
            p50_latency_ms=100.0,
            p95_latency_ms=200.0,
            p99_latency_ms=300.0,
            throughput_rps=200.0,
            error_rate_percent=0.5,
            timestamp=datetime.now() - timedelta(days=1),
            version="v1.0.0"
        )
        
        baseline_manager.add_baseline(baseline)
        
        # Simulate throughput regression
        current_metrics = {
            "p50_latency_ms": 110.0,  # Slight increase
            "p95_latency_ms": 220.0,  # Slight increase
            "p99_latency_ms": 330.0,  # Slight increase
            "throughput_rps": 150.0,  # 25% decrease (should trigger regression)
            "error_rate_percent": 0.8,  # Slight increase
            "total_requests": 50
        }
        
        # Detect regression
        result = baseline_manager.detect_regression(
            PerformanceTestType.API_ENDPOINT,
            "/api/throughput",
            current_metrics
        )
        
        # Should detect throughput regression
        assert result.regression_detected is True
        assert result.passed is False
        assert "throughput_regression" in result.regression_details
    
    @pytest.mark.asyncio
    async def test_error_rate_regression_detection(self, mock_api_client, baseline_manager):
        """Test error rate regression detection."""
        # Create baseline
        baseline = PerformanceBaseline(
            test_type=PerformanceTestType.API_ENDPOINT,
            endpoint="/api/error",
            p50_latency_ms=100.0,
            p95_latency_ms=200.0,
            p99_latency_ms=300.0,
            throughput_rps=150.0,
            error_rate_percent=1.0,
            timestamp=datetime.now() - timedelta(days=1),
            version="v1.0.0"
        )
        
        baseline_manager.add_baseline(baseline)
        
        # Simulate error rate increase
        current_metrics = {
            "p50_latency_ms": 105.0,  # Slight increase
            "p95_latency_ms": 210.0,  # Slight increase
            "p99_latency_ms": 320.0,  # Slight increase
            "throughput_rps": 145.0,  # Slight decrease
            "error_rate_percent": 8.0,  # 7% increase (should trigger regression)
            "total_requests": 50
        }
        
        # Detect regression
        result = baseline_manager.detect_regression(
            PerformanceTestType.API_ENDPOINT,
            "/api/error",
            current_metrics
        )
        
        # Should detect error rate regression
        assert result.regression_detected is True
        assert result.passed is False
        assert "error_rate_increase" in result.regression_details
    
    @pytest.mark.asyncio
    async def test_critical_latency_threshold(self, mock_api_client, baseline_manager):
        """Test critical latency threshold detection."""
        # Create baseline
        baseline = PerformanceBaseline(
            test_type=PerformanceTestType.API_ENDPOINT,
            endpoint="/api/critical",
            p50_latency_ms=100.0,
            p95_latency_ms=200.0,
            p99_latency_ms=300.0,
            throughput_rps=150.0,
            error_rate_percent=1.0,
            timestamp=datetime.now() - timedelta(days=1),
            version="v1.0.0"
        )
        
        baseline_manager.add_baseline(baseline)
        
        # Simulate critical latency
        current_metrics = {
            "p50_latency_ms": 200.0,  # Increased
            "p95_latency_ms": 400.0,  # Increased
            "p99_latency_ms": 1200.0,  # Above critical threshold
            "throughput_rps": 100.0,  # Decreased
            "error_rate_percent": 2.0,  # Increased
            "total_requests": 50
        }
        
        # Detect regression
        result = baseline_manager.detect_regression(
            PerformanceTestType.API_ENDPOINT,
            "/api/critical",
            current_metrics
        )
        
        # Should detect critical latency
        assert result.regression_detected is True
        assert result.passed is False
        assert "critical_latency_exceeded" in result.regression_details
    
    @pytest.mark.asyncio
    async def test_no_regression_scenario(self, mock_api_client, baseline_manager):
        """Test scenario with no performance regression."""
        # Create baseline
        baseline = PerformanceBaseline(
            test_type=PerformanceTestType.API_ENDPOINT,
            endpoint="/api/good",
            p50_latency_ms=100.0,
            p95_latency_ms=200.0,
            p99_latency_ms=300.0,
            throughput_rps=150.0,
            error_rate_percent=1.0,
            timestamp=datetime.now() - timedelta(days=1),
            version="v1.0.0"
        )
        
        baseline_manager.add_baseline(baseline)
        
        # Simulate good performance
        current_metrics = {
            "p50_latency_ms": 95.0,  # Slight improvement
            "p95_latency_ms": 190.0,  # Slight improvement
            "p99_latency_ms": 280.0,  # Slight improvement
            "throughput_rps": 155.0,  # Slight improvement
            "error_rate_percent": 0.8,  # Slight improvement
            "total_requests": 50
        }
        
        # Detect regression
        result = baseline_manager.detect_regression(
            PerformanceTestType.API_ENDPOINT,
            "/api/good",
            current_metrics
        )
        
        # Should not detect regression
        assert result.regression_detected is False
        assert result.passed is True
        assert len(result.regression_details) == 0
    
    @pytest.mark.asyncio
    async def test_multiple_endpoints_performance(self, mock_api_client, baseline_manager):
        """Test performance regression for multiple endpoints."""
        endpoints = ["/api/query", "/api/workflow", "/api/ingest"]
        
        # Create baselines for each endpoint
        for i, endpoint in enumerate(endpoints):
            baseline = PerformanceBaseline(
                test_type=PerformanceTestType.API_ENDPOINT,
                endpoint=endpoint,
                p50_latency_ms=100.0 + i * 20,
                p95_latency_ms=200.0 + i * 30,
                p99_latency_ms=300.0 + i * 40,
                throughput_rps=150.0 - i * 10,
                error_rate_percent=1.0 + i * 0.5,
                timestamp=datetime.now() - timedelta(days=1),
                version="v1.0.0"
            )
            baseline_manager.add_baseline(baseline)
        
        # Test each endpoint
        results = []
        for endpoint in endpoints:
            # Make requests
            for i in range(20):
                try:
                    await mock_api_client.get(endpoint, {"test": f"multi_endpoint_{i}"})
                except Exception:
                    pass
            
            # Get metrics and detect regression
            current_metrics = mock_api_client.get_metrics(endpoint)
            result = baseline_manager.detect_regression(
                PerformanceTestType.API_ENDPOINT,
                endpoint,
                current_metrics
            )
            results.append(result)
        
        # Validate results
        assert len(results) == len(endpoints)
        for result in results:
            assert result.baseline is not None
            assert result.current_metrics is not None
            assert isinstance(result.passed, bool)
    
    @pytest.mark.asyncio
    async def test_performance_metrics_calculation(self, mock_api_client):
        """Test performance metrics calculation accuracy."""
        endpoint = "/api/metrics"
        
        # Make controlled requests
        for i in range(10):
            try:
                await mock_api_client.get(endpoint, {"iteration": i})
            except Exception:
                pass
        
        # Get metrics
        metrics = mock_api_client.get_metrics(endpoint)
        
        # Validate metric calculations
        assert "total_requests" in metrics
        assert metrics["total_requests"] >= 0
        
        if metrics["total_requests"] > 0:
            assert "avg_latency_ms" in metrics
            assert metrics["avg_latency_ms"] > 0
            assert "error_rate_percent" in metrics
            assert 0 <= metrics["error_rate_percent"] <= 100