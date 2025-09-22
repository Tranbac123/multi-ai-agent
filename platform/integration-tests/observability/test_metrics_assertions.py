"""Metrics assertions with Prometheus integration and custom metric validation."""

import pytest
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch

from tests.observability import (
    MetricAssertion, MockSpan, MockTracer, MetricsCollector
)


class MetricsValidator:
    """Validates metrics against assertions."""
    
    def __init__(self, metrics_collector: MetricsCollector):
        self.metrics_collector = metrics_collector
    
    def validate_assertion(self, assertion: MetricAssertion) -> bool:
        """Validate a single metric assertion."""
        if assertion.metric_type == "counter":
            return self._validate_counter(assertion)
        elif assertion.metric_type == "gauge":
            return self._validate_gauge(assertion)
        elif assertion.metric_type == "histogram":
            return self._validate_histogram(assertion)
        elif assertion.metric_type == "summary":
            return self._validate_summary(assertion)
        else:
            return False
    
    def _validate_counter(self, assertion: MetricAssertion) -> bool:
        """Validate counter metric assertion."""
        value = self.metrics_collector.get_counter_value(assertion.name, assertion.labels)
        
        if assertion.operator == "eq":
            return abs(value - (assertion.expected_value or 0)) <= (assertion.tolerance_percent / 100 * (assertion.expected_value or 0))
        elif assertion.operator == "gt":
            return value > (assertion.expected_value or 0)
        elif assertion.operator == "lt":
            return value < (assertion.expected_value or 0)
        elif assertion.operator == "gte":
            return value >= (assertion.expected_value or 0)
        elif assertion.operator == "lte":
            return value <= (assertion.expected_value or 0)
        elif assertion.operator == "in_range":
            if assertion.expected_range:
                return assertion.expected_range[0] <= value <= assertion.expected_range[1]
            return False
        
        return False
    
    def _validate_gauge(self, assertion: MetricAssertion) -> bool:
        """Validate gauge metric assertion."""
        value = self.metrics_collector.get_gauge_value(assertion.name, assertion.labels)
        
        if assertion.operator == "eq":
            return abs(value - (assertion.expected_value or 0)) <= (assertion.tolerance_percent / 100 * (assertion.expected_value or 0))
        elif assertion.operator == "gt":
            return value > (assertion.expected_value or 0)
        elif assertion.operator == "lt":
            return value < (assertion.expected_value or 0)
        elif assertion.operator == "gte":
            return value >= (assertion.expected_value or 0)
        elif assertion.operator == "lte":
            return value <= (assertion.expected_value or 0)
        elif assertion.operator == "in_range":
            if assertion.expected_range:
                return assertion.expected_range[0] <= value <= assertion.expected_range[1]
            return False
        
        return False
    
    def _validate_histogram(self, assertion: MetricAssertion) -> bool:
        """Validate histogram metric assertion."""
        stats = self.metrics_collector.get_histogram_stats(assertion.name)
        
        if assertion.operator == "eq":
            if assertion.expected_value is not None:
                # Use average for comparison
                return abs(stats.get("avg", 0) - assertion.expected_value) <= (assertion.tolerance_percent / 100 * assertion.expected_value)
            return False
        elif assertion.operator == "gt":
            return stats.get("avg", 0) > (assertion.expected_value or 0)
        elif assertion.operator == "lt":
            return stats.get("avg", 0) < (assertion.expected_value or 0)
        elif assertion.operator == "gte":
            return stats.get("avg", 0) >= (assertion.expected_value or 0)
        elif assertion.operator == "lte":
            return stats.get("avg", 0) <= (assertion.expected_value or 0)
        elif assertion.operator == "in_range":
            if assertion.expected_range:
                avg = stats.get("avg", 0)
                return assertion.expected_range[0] <= avg <= assertion.expected_range[1]
            return False
        
        return False
    
    def _validate_summary(self, assertion: MetricAssertion) -> bool:
        """Validate summary metric assertion."""
        stats = self.metrics_collector.get_summary_stats(assertion.name, assertion.labels)
        
        if assertion.operator == "eq":
            if assertion.expected_value is not None:
                return abs(stats.get("avg", 0) - assertion.expected_value) <= (assertion.tolerance_percent / 100 * assertion.expected_value)
            return False
        elif assertion.operator == "gt":
            return stats.get("avg", 0) > (assertion.expected_value or 0)
        elif assertion.operator == "lt":
            return stats.get("avg", 0) < (assertion.expected_value or 0)
        elif assertion.operator == "gte":
            return stats.get("avg", 0) >= (assertion.expected_value or 0)
        elif assertion.operator == "lte":
            return stats.get("avg", 0) <= (assertion.expected_value or 0)
        elif assertion.operator == "in_range":
            if assertion.expected_range:
                avg = stats.get("avg", 0)
                return assertion.expected_range[0] <= avg <= assertion.expected_range[1]
            return False
        
        return False


class PrometheusQueryValidator:
    """Validates Prometheus queries and expressions."""
    
    def __init__(self):
        self.valid_functions = {
            "rate", "increase", "sum", "avg", "min", "max", "count", "histogram_quantile",
            "quantile", "stddev", "stdvar", "topk", "bottomk", "group", "group_left",
            "group_right", "ignoring", "on", "without", "by", "and", "or", "unless",
            "avg_over_time", "sum_over_time", "min_over_time", "max_over_time", "count_over_time"
        }
    
    def validate_query(self, query: str) -> bool:
        """Validate Prometheus query syntax."""
        if not query or not isinstance(query, str):
            return False
        
        # Basic syntax checks
        if query.count('{') != query.count('}'):
            return False
        
        if query.count('[') != query.count(']'):
            return False
        
        # Check for valid metric names
        if not self._has_valid_metric_name(query):
            return False
        
        # Check for valid functions
        if not self._has_valid_functions(query):
            return False
        
        return True
    
    def _has_valid_metric_name(self, query: str) -> bool:
        """Check if query has valid metric names."""
        import re
        # Remove quoted strings to avoid false positives
        cleaned_query = re.sub(r'"[^"]*"', '', query)
        
        # Check for invalid metric names (starting with number)
        invalid_metric_pattern = r'\b[0-9][a-zA-Z0-9_]*'
        if re.search(invalid_metric_pattern, cleaned_query):
            return False
        
        # Check for valid metric names
        metric_pattern = r'[a-zA-Z_][a-zA-Z0-9_]*'
        return bool(re.search(metric_pattern, cleaned_query))
    
    def _has_valid_functions(self, query: str) -> bool:
        """Check if query uses valid Prometheus functions."""
        import re
        function_pattern = r'([a-zA-Z_][a-zA-Z0-9_]*)\s*\('
        functions = re.findall(function_pattern, query)
        
        for func in functions:
            if func not in self.valid_functions:
                return False
        
        return True
    
    def _is_metric_name(self, name: str) -> bool:
        """Check if name is a valid metric name."""
        import re
        return bool(re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', name))


class TestMetricsAssertions:
    """Test metrics assertions and validation."""
    
    @pytest.fixture
    def metrics_collector(self):
        """Create metrics collector."""
        return MetricsCollector()
    
    @pytest.fixture
    def metrics_validator(self, metrics_collector):
        """Create metrics validator."""
        return MetricsValidator(metrics_collector)
    
    @pytest.fixture
    def prometheus_validator(self):
        """Create Prometheus query validator."""
        return PrometheusQueryValidator()
    
    def test_counter_metric_assertion(self, metrics_collector, metrics_validator):
        """Test counter metric assertion."""
        # Create counter assertion
        assertion = MetricAssertion(
            name="http_requests_total",
            metric_type="counter",
            labels={"method": "GET", "status": "200"},
            expected_value=100.0,
            operator="eq",
            tolerance_percent=5.0
        )
        
        # Set counter value
        metrics_collector.increment_counter("http_requests_total", 100.0, {"method": "GET", "status": "200"})
        
        # Validate assertion
        result = metrics_validator.validate_assertion(assertion)
        assert result is True
    
    def test_gauge_metric_assertion(self, metrics_collector, metrics_validator):
        """Test gauge metric assertion."""
        # Create gauge assertion
        assertion = MetricAssertion(
            name="active_connections",
            metric_type="gauge",
            labels={"service": "api"},
            expected_value=50.0,
            operator="lte"
        )
        
        # Set gauge value
        metrics_collector.set_gauge("active_connections", 45.0, {"service": "api"})
        
        # Validate assertion
        result = metrics_validator.validate_assertion(assertion)
        assert result is True
    
    def test_histogram_metric_assertion(self, metrics_collector, metrics_validator):
        """Test histogram metric assertion."""
        # Create histogram assertion
        assertion = MetricAssertion(
            name="http_request_duration_seconds",
            metric_type="histogram",
            expected_value=0.1,  # 100ms average
            operator="lte",
            tolerance_percent=10.0
        )
        
        # Record histogram values
        for i in range(100):
            metrics_collector.record_histogram("http_request_duration_seconds", 0.1)
        
        # Validate assertion
        result = metrics_validator.validate_assertion(assertion)
        assert result is True
    
    def test_summary_metric_assertion(self, metrics_collector, metrics_validator):
        """Test summary metric assertion."""
        # Create summary assertion
        assertion = MetricAssertion(
            name="response_size_bytes",
            metric_type="summary",
            labels={"endpoint": "/api/query"},
            expected_value=1024.0,
            operator="in_range",
            expected_range=(800.0, 1200.0)
        )
        
        # Record summary values
        for i in range(50):
            metrics_collector.record_summary("response_size_bytes", 1000.0, {"endpoint": "/api/query"})
        
        # Validate assertion
        result = metrics_validator.validate_assertion(assertion)
        assert result is True
    
    def test_metric_assertion_failure(self, metrics_collector, metrics_validator):
        """Test metric assertion failure."""
        # Create assertion that should fail
        assertion = MetricAssertion(
            name="http_requests_total",
            metric_type="counter",
            expected_value=100.0,
            operator="gt"
        )
        
        # Set counter value below threshold
        metrics_collector.increment_counter("http_requests_total", 50.0)
        
        # Validate assertion
        result = metrics_validator.validate_assertion(assertion)
        assert result is False
    
    def test_tolerance_based_assertion(self, metrics_collector, metrics_validator):
        """Test tolerance-based metric assertion."""
        # Create assertion with tolerance
        assertion = MetricAssertion(
            name="response_time_ms",
            metric_type="gauge",
            expected_value=100.0,
            operator="eq",
            tolerance_percent=10.0  # 10% tolerance
        )
        
        # Set value within tolerance (105ms, within 10% of 100ms)
        metrics_collector.set_gauge("response_time_ms", 105.0)
        
        # Validate assertion
        result = metrics_validator.validate_assertion(assertion)
        assert result is True
    
    def test_range_based_assertion(self, metrics_collector, metrics_validator):
        """Test range-based metric assertion."""
        # Create range assertion
        assertion = MetricAssertion(
            name="memory_usage_bytes",
            metric_type="gauge",
            operator="in_range",
            expected_range=(1000.0, 2000.0)
        )
        
        # Set value within range
        metrics_collector.set_gauge("memory_usage_bytes", 1500.0)
        
        # Validate assertion
        result = metrics_validator.validate_assertion(assertion)
        assert result is True
    
    def test_prometheus_query_validation(self, prometheus_validator):
        """Test Prometheus query validation."""
        # Valid queries
        valid_queries = [
            "http_requests_total",
            "rate(http_requests_total[5m])",
            "sum(rate(http_requests_total[5m])) by (service)",
            "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))",
            "avg(cpu_usage_percent) by (instance)"
        ]
        
        for query in valid_queries:
            result = prometheus_validator.validate_query(query)
            assert result is True, f"Query should be valid: {query}"
    
    def test_invalid_prometheus_query(self, prometheus_validator):
        """Test invalid Prometheus query detection."""
        # Invalid queries
        invalid_queries = [
            "",  # Empty query
            "invalid_function()",  # Invalid function
            "metric{label",  # Unclosed brace
            "metric[5m",  # Unclosed bracket
            "123invalid_metric",  # Invalid metric name
        ]
        
        for query in invalid_queries:
            result = prometheus_validator.validate_query(query)
            assert result is False, f"Query should be invalid: {query}"
    
    def test_multiple_metric_assertions(self, metrics_collector, metrics_validator):
        """Test multiple metric assertions."""
        # Create multiple assertions
        assertions = [
            MetricAssertion("request_count", "counter", expected_value=100.0, operator="eq"),
            MetricAssertion("response_time", "gauge", expected_value=50.0, operator="lte"),
            MetricAssertion("error_rate", "gauge", expected_value=5.0, operator="lte")
        ]
        
        # Set metric values
        metrics_collector.increment_counter("request_count", 100.0)
        metrics_collector.set_gauge("response_time", 45.0)
        metrics_collector.set_gauge("error_rate", 3.0)
        
        # Validate all assertions
        results = []
        for assertion in assertions:
            result = metrics_validator.validate_assertion(assertion)
            results.append(result)
        
        # All should pass
        assert all(results) is True
    
    def test_labeled_metric_assertions(self, metrics_collector, metrics_validator):
        """Test labeled metric assertions."""
        # Create labeled assertion
        assertion = MetricAssertion(
            name="http_requests_total",
            metric_type="counter",
            labels={"method": "POST", "status": "200"},
            expected_value=50.0,
            operator="eq"
        )
        
        # Set labeled metric value
        metrics_collector.increment_counter("http_requests_total", 50.0, {"method": "POST", "status": "200"})
        
        # Validate assertion
        result = metrics_validator.validate_assertion(assertion)
        assert result is True
        
        # Test with different labels (should not match)
        metrics_collector.increment_counter("http_requests_total", 100.0, {"method": "GET", "status": "200"})
        result = metrics_validator.validate_assertion(assertion)
        assert result is True  # Still true because labels match
    
    def test_histogram_statistics_assertion(self, metrics_collector, metrics_validator):
        """Test histogram statistics assertion."""
        # Record various histogram values
        values = [0.05, 0.1, 0.15, 0.2, 0.25, 0.3, 0.35, 0.4, 0.45, 0.5]
        for value in values:
            metrics_collector.record_histogram("latency_seconds", value)
        
        # Create assertion for average
        assertion = MetricAssertion(
            name="latency_seconds",
            metric_type="histogram",
            expected_value=0.275,  # Average of values
            operator="eq",
            tolerance_percent=5.0
        )
        
        # Validate assertion
        result = metrics_validator.validate_assertion(assertion)
        assert result is True
    
    def test_metric_assertion_with_missing_metric(self, metrics_validator):
        """Test metric assertion with missing metric."""
        # Create assertion for non-existent metric
        assertion = MetricAssertion(
            name="non_existent_metric",
            metric_type="counter",
            expected_value=100.0,
            operator="eq"
        )
        
        # Validate assertion (should fail)
        result = metrics_validator.validate_assertion(assertion)
        assert result is False
    
    def test_complex_prometheus_query_validation(self, prometheus_validator):
        """Test complex Prometheus query validation."""
        # Complex valid queries
        complex_queries = [
            "histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[5m])) by (le))",
            "topk(10, sum(rate(http_requests_total[5m])) by (service))",
            "avg_over_time(cpu_usage_percent[1h])",
            "increase(http_requests_total[1h])"
        ]
        
        for query in complex_queries:
            result = prometheus_validator.validate_query(query)
            assert result is True, f"Complex query should be valid: {query}"
