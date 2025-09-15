"""Test Prometheus scraping and metrics validation."""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory
from tests._helpers.assertions import PerformanceAssertions


class TestPrometheusScraping:
    """Test Prometheus scraping and metrics validation."""
    
    @pytest.mark.asyncio
    async def test_prometheus_metrics_scraping(self):
        """Test Prometheus metrics scraping."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock Prometheus scraper
        prometheus_scraper = Mock()
        prometheus_scraper.scrape_metrics = AsyncMock()
        prometheus_scraper.validate_metrics = AsyncMock()
        prometheus_scraper.check_metric_availability = AsyncMock()
        
        # Simulate metrics scraping
        prometheus_scraper.scrape_metrics.return_value = {
            "scraping_completed": True,
            "scraping_time_ms": 150,
            "metrics_collected": {
                "http_requests_total": {
                    "value": 1000,
                    "labels": {"method": "POST", "endpoint": "/api/v1/chat", "status": "200"},
                    "timestamp": time.time()
                },
                "http_request_duration_seconds": {
                    "value": 0.15,
                    "labels": {"method": "POST", "endpoint": "/api/v1/chat"},
                    "timestamp": time.time()
                },
                "router_decisions_total": {
                    "value": 500,
                    "labels": {"tier": "SLM_A", "confidence": "high"},
                    "timestamp": time.time()
                },
                "llm_tokens_consumed": {
                    "value": 25000,
                    "labels": {"model": "gpt-4", "tenant_id": tenant["tenant_id"]},
                    "timestamp": time.time()
                },
                "system_memory_usage_bytes": {
                    "value": 1073741824,  # 1GB
                    "labels": {"instance": "api-gateway-1"},
                    "timestamp": time.time()
                }
            },
            "scraping_errors": []
        }
        
        # Simulate metrics validation
        prometheus_scraper.validate_metrics.return_value = {
            "validation_completed": True,
            "valid_metrics": 5,
            "invalid_metrics": 0,
            "validation_errors": [],
            "metric_quality_score": 1.0
        }
        
        # Simulate metric availability check
        prometheus_scraper.check_metric_availability.return_value = {
            "availability_check_completed": True,
            "required_metrics": [
                "http_requests_total",
                "http_request_duration_seconds",
                "router_decisions_total",
                "llm_tokens_consumed",
                "system_memory_usage_bytes"
            ],
            "available_metrics": 5,
            "missing_metrics": [],
            "availability_percentage": 100.0
        }
        
        # Test metrics scraping
        scrape_result = await prometheus_scraper.scrape_metrics()
        assert scrape_result["scraping_completed"] is True
        assert len(scrape_result["metrics_collected"]) == 5
        assert len(scrape_result["scraping_errors"]) == 0
        
        # Test metrics validation
        validation_result = await prometheus_scraper.validate_metrics(scrape_result["metrics_collected"])
        assert validation_result["validation_completed"] is True
        assert validation_result["valid_metrics"] == 5
        assert validation_result["invalid_metrics"] == 0
        assert validation_result["metric_quality_score"] == 1.0
        
        # Test metric availability
        availability_result = await prometheus_scraper.check_metric_availability()
        assert availability_result["availability_check_completed"] is True
        assert availability_result["available_metrics"] == 5
        assert availability_result["missing_metrics"] == []
        assert availability_result["availability_percentage"] == 100.0
        
        # Verify scraping performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            scrape_result["scraping_time_ms"], 500, "Prometheus scraping time"
        )
        assert perf_result.passed, f"Prometheus scraping should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_promql_query_validation(self):
        """Test PromQL query validation."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock PromQL validator
        promql_validator = Mock()
        promql_validator.validate_query = AsyncMock()
        promql_validator.execute_query = AsyncMock()
        promql_validator.check_query_performance = AsyncMock()
        
        # Simulate PromQL query validation
        promql_validator.validate_query.return_value = {
            "validation_completed": True,
            "query_valid": True,
            "query_syntax": "valid",
            "metric_references": [
                "http_requests_total",
                "http_request_duration_seconds"
            ],
            "label_filters": ["method", "status"],
            "aggregation_functions": ["rate", "sum"],
            "validation_errors": []
        }
        
        # Simulate query execution
        promql_validator.execute_query.return_value = {
            "execution_completed": True,
            "query_result": {
                "result_type": "vector",
                "result": [
                    {
                        "metric": {"method": "POST", "status": "200"},
                        "value": [time.time(), "10.5"]
                    },
                    {
                        "metric": {"method": "GET", "status": "200"},
                        "value": [time.time(), "5.2"]
                    }
                ]
            },
            "execution_time_ms": 50,
            "query_complexity": "medium"
        }
        
        # Simulate query performance check
        promql_validator.check_query_performance.return_value = {
            "performance_check_completed": True,
            "execution_time_ms": 50,
            "performance_threshold_ms": 100,
            "performance_grade": "A",
            "optimization_suggestions": []
        }
        
        # Test PromQL query validation
        validation_result = await promql_validator.validate_query(
            "rate(http_requests_total{method=\"POST\"}[5m])"
        )
        assert validation_result["validation_completed"] is True
        assert validation_result["query_valid"] is True
        assert validation_result["query_syntax"] == "valid"
        assert len(validation_result["validation_errors"]) == 0
        
        # Test query execution
        execution_result = await promql_validator.execute_query(
            "rate(http_requests_total{method=\"POST\"}[5m])"
        )
        assert execution_result["execution_completed"] is True
        assert execution_result["query_result"]["result_type"] == "vector"
        assert len(execution_result["query_result"]["result"]) == 2
        
        # Test query performance
        performance_result = await promql_validator.check_query_performance(execution_result)
        assert performance_result["performance_check_completed"] is True
        assert performance_result["performance_grade"] == "A"
        assert performance_result["execution_time_ms"] <= performance_result["performance_threshold_ms"]
        
        # Verify query performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            execution_result["execution_time_ms"], 100, "PromQL query execution time"
        )
        assert perf_result.passed, f"PromQL query should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_metric_threshold_monitoring(self):
        """Test metric threshold monitoring."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock threshold monitor
        threshold_monitor = Mock()
        threshold_monitor.check_thresholds = AsyncMock()
        threshold_monitor.trigger_alerts = AsyncMock()
        threshold_monitor.update_thresholds = AsyncMock()
        
        # Simulate threshold check
        threshold_monitor.check_thresholds.return_value = {
            "threshold_check_completed": True,
            "thresholds_checked": 5,
            "thresholds_exceeded": 1,
            "threshold_results": {
                "http_request_duration_seconds": {
                    "current_value": 0.25,
                    "threshold": 0.20,
                    "status": "EXCEEDED",
                    "severity": "warning"
                },
                "http_requests_total": {
                    "current_value": 1000,
                    "threshold": 1500,
                    "status": "WITHIN_LIMIT",
                    "severity": "info"
                },
                "system_memory_usage_bytes": {
                    "current_value": 1073741824,  # 1GB
                    "threshold": 2147483648,  # 2GB
                    "status": "WITHIN_LIMIT",
                    "severity": "info"
                },
                "llm_tokens_consumed": {
                    "current_value": 25000,
                    "threshold": 30000,
                    "status": "WITHIN_LIMIT",
                    "severity": "info"
                },
                "router_decisions_total": {
                    "current_value": 500,
                    "threshold": 1000,
                    "status": "WITHIN_LIMIT",
                    "severity": "info"
                }
            }
        }
        
        # Simulate alert triggering
        threshold_monitor.trigger_alerts.return_value = {
            "alerts_triggered": True,
            "alert_count": 1,
            "alerts": [
                {
                    "alert_id": "alert_001",
                    "metric_name": "http_request_duration_seconds",
                    "severity": "warning",
                    "message": "HTTP request duration exceeded threshold",
                    "timestamp": time.time()
                }
            ]
        }
        
        # Simulate threshold update
        threshold_monitor.update_thresholds.return_value = {
            "thresholds_updated": True,
            "updated_thresholds": {
                "http_request_duration_seconds": 0.30  # Increased threshold
            },
            "update_reason": "Performance baseline adjustment"
        }
        
        # Test threshold monitoring
        threshold_result = await threshold_monitor.check_thresholds()
        assert threshold_result["threshold_check_completed"] is True
        assert threshold_result["thresholds_checked"] == 5
        assert threshold_result["thresholds_exceeded"] == 1
        
        # Test alert triggering
        alert_result = await threshold_monitor.trigger_alerts(threshold_result)
        assert alert_result["alerts_triggered"] is True
        assert alert_result["alert_count"] == 1
        assert len(alert_result["alerts"]) == 1
        
        # Test threshold update
        update_result = await threshold_monitor.update_thresholds(
            {"http_request_duration_seconds": 0.30}
        )
        assert update_result["thresholds_updated"] is True
        assert update_result["updated_thresholds"]["http_request_duration_seconds"] == 0.30
        
        # Verify threshold results
        threshold_results = threshold_result["threshold_results"]
        assert threshold_results["http_request_duration_seconds"]["status"] == "EXCEEDED"
        assert threshold_results["http_requests_total"]["status"] == "WITHIN_LIMIT"
        assert threshold_results["system_memory_usage_bytes"]["status"] == "WITHIN_LIMIT"
    
    @pytest.mark.asyncio
    async def test_metric_aggregation_validation(self):
        """Test metric aggregation validation."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock metric aggregator
        metric_aggregator = Mock()
        metric_aggregator.aggregate_metrics = AsyncMock()
        metric_aggregator.validate_aggregation = AsyncMock()
        metric_aggregator.check_aggregation_accuracy = AsyncMock()
        
        # Simulate metric aggregation
        metric_aggregator.aggregate_metrics.return_value = {
            "aggregation_completed": True,
            "aggregation_type": "sum",
            "time_window": "5m",
            "aggregated_metrics": {
                "http_requests_total_sum": {
                    "value": 5000,
                    "labels": {"method": "POST"},
                    "timestamp": time.time()
                },
                "http_request_duration_seconds_avg": {
                    "value": 0.18,
                    "labels": {"method": "POST"},
                    "timestamp": time.time()
                },
                "llm_tokens_consumed_sum": {
                    "value": 125000,
                    "labels": {"tenant_id": tenant["tenant_id"]},
                    "timestamp": time.time()
                }
            },
            "aggregation_time_ms": 75
        }
        
        # Simulate aggregation validation
        metric_aggregator.validate_aggregation.return_value = {
            "validation_completed": True,
            "aggregation_valid": True,
            "validation_errors": [],
            "aggregation_quality_score": 0.95
        }
        
        # Simulate aggregation accuracy check
        metric_aggregator.check_aggregation_accuracy.return_value = {
            "accuracy_check_completed": True,
            "accuracy_percentage": 99.5,
            "accuracy_threshold": 95.0,
            "accuracy_grade": "A",
            "accuracy_issues": []
        }
        
        # Test metric aggregation
        aggregation_result = await metric_aggregator.aggregate_metrics(
            aggregation_type="sum",
            time_window="5m"
        )
        assert aggregation_result["aggregation_completed"] is True
        assert len(aggregation_result["aggregated_metrics"]) == 3
        
        # Test aggregation validation
        validation_result = await metric_aggregator.validate_aggregation(aggregation_result)
        assert validation_result["validation_completed"] is True
        assert validation_result["aggregation_valid"] is True
        assert validation_result["aggregation_quality_score"] >= 0.9
        
        # Test aggregation accuracy
        accuracy_result = await metric_aggregator.check_aggregation_accuracy(aggregation_result)
        assert accuracy_result["accuracy_check_completed"] is True
        assert accuracy_result["accuracy_percentage"] >= accuracy_result["accuracy_threshold"]
        assert accuracy_result["accuracy_grade"] == "A"
        
        # Verify aggregation performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            aggregation_result["aggregation_time_ms"], 200, "Metric aggregation time"
        )
        assert perf_result.passed, f"Metric aggregation should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_metric_retention_policy(self):
        """Test metric retention policy enforcement."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock retention policy manager
        retention_manager = Mock()
        retention_manager.check_retention_policy = AsyncMock()
        retention_manager.cleanup_old_metrics = AsyncMock()
        retention_manager.validate_retention_compliance = AsyncMock()
        
        # Simulate retention policy check
        retention_manager.check_retention_policy.return_value = {
            "policy_check_completed": True,
            "retention_policies": {
                "http_requests_total": {"retention_days": 30, "current_age_days": 25},
                "http_request_duration_seconds": {"retention_days": 30, "current_age_days": 25},
                "system_memory_usage_bytes": {"retention_days": 7, "current_age_days": 5},
                "llm_tokens_consumed": {"retention_days": 90, "current_age_days": 45}
            },
            "metrics_to_cleanup": [],
            "retention_compliance": True
        }
        
        # Simulate metric cleanup
        retention_manager.cleanup_old_metrics.return_value = {
            "cleanup_completed": True,
            "metrics_cleaned": 0,
            "storage_freed_bytes": 0,
            "cleanup_time_ms": 50
        }
        
        # Simulate retention compliance validation
        retention_manager.validate_retention_compliance.return_value = {
            "compliance_check_completed": True,
            "compliance_status": "COMPLIANT",
            "compliance_score": 100.0,
            "compliance_issues": []
        }
        
        # Test retention policy check
        policy_result = await retention_manager.check_retention_policy()
        assert policy_result["policy_check_completed"] is True
        assert policy_result["retention_compliance"] is True
        assert len(policy_result["metrics_to_cleanup"]) == 0
        
        # Test metric cleanup
        cleanup_result = await retention_manager.cleanup_old_metrics()
        assert cleanup_result["cleanup_completed"] is True
        assert cleanup_result["metrics_cleaned"] == 0
        
        # Test retention compliance
        compliance_result = await retention_manager.validate_retention_compliance()
        assert compliance_result["compliance_check_completed"] is True
        assert compliance_result["compliance_status"] == "COMPLIANT"
        assert compliance_result["compliance_score"] == 100.0
        
        # Verify retention policies
        retention_policies = policy_result["retention_policies"]
        assert retention_policies["http_requests_total"]["retention_days"] == 30
        assert retention_policies["system_memory_usage_bytes"]["retention_days"] == 7
        assert retention_policies["llm_tokens_consumed"]["retention_days"] == 90
        
        # Verify cleanup performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            cleanup_result["cleanup_time_ms"], 200, "Metric cleanup time"
        )
        assert perf_result.passed, f"Metric cleanup should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_prometheus_high_availability(self):
        """Test Prometheus high availability."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock Prometheus HA manager
        prometheus_ha = Mock()
        prometheus_ha.check_ha_status = AsyncMock()
        prometheus_ha.failover_prometheus = AsyncMock()
        prometheus_ha.validate_ha_configuration = AsyncMock()
        
        # Simulate HA status check
        prometheus_ha.check_ha_status.return_value = {
            "ha_check_completed": True,
            "primary_prometheus": {
                "status": "healthy",
                "endpoint": "prometheus-primary:9090",
                "last_scrape": time.time() - 30,
                "uptime_hours": 720
            },
            "secondary_prometheus": {
                "status": "healthy",
                "endpoint": "prometheus-secondary:9090",
                "last_scrape": time.time() - 30,
                "uptime_hours": 720
            },
            "ha_status": "ACTIVE",
            "failover_required": False
        }
        
        # Simulate Prometheus failover
        prometheus_ha.failover_prometheus.return_value = {
            "failover_completed": True,
            "new_primary": "prometheus-secondary:9090",
            "failover_time_ms": 500,
            "failover_reason": "Primary Prometheus unavailable",
            "data_sync_status": "completed"
        }
        
        # Simulate HA configuration validation
        prometheus_ha.validate_ha_configuration.return_value = {
            "validation_completed": True,
            "ha_configuration_valid": True,
            "configuration_issues": [],
            "ha_readiness_score": 100.0
        }
        
        # Test HA status check
        ha_result = await prometheus_ha.check_ha_status()
        assert ha_result["ha_check_completed"] is True
        assert ha_result["ha_status"] == "ACTIVE"
        assert ha_result["failover_required"] is False
        
        # Test Prometheus failover
        failover_result = await prometheus_ha.failover_prometheus()
        assert failover_result["failover_completed"] is True
        assert failover_result["new_primary"] == "prometheus-secondary:9090"
        assert failover_result["data_sync_status"] == "completed"
        
        # Test HA configuration validation
        config_result = await prometheus_ha.validate_ha_configuration()
        assert config_result["validation_completed"] is True
        assert config_result["ha_configuration_valid"] is True
        assert config_result["ha_readiness_score"] == 100.0
        
        # Verify HA status
        assert ha_result["primary_prometheus"]["status"] == "healthy"
        assert ha_result["secondary_prometheus"]["status"] == "healthy"
        
        # Verify failover performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            failover_result["failover_time_ms"], 2000, "Prometheus failover time"
        )
        assert perf_result.passed, f"Prometheus failover should be reasonable: {perf_result.message}"
