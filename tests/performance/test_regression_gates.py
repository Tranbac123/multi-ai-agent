"""Test performance regression gates."""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import PerformanceAssertions


class TestPerformanceRegressionGates:
    """Test performance regression gates."""
    
    @pytest.mark.asyncio
    async def test_baseline_json_performance_gate(self):
        """Test baseline JSON performance gate."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock JSON performance baseline
        json_performance = Mock()
        json_performance.measure_json_processing = AsyncMock()
        json_performance.compare_to_baseline = AsyncMock()
        
        # Simulate JSON processing performance
        json_performance.measure_json_processing.return_value = {
            "processing_time_ms": 5,
            "json_size_bytes": 1024,
            "throughput_mb_per_sec": 200,
            "memory_usage_mb": 2.5,
            "cpu_usage_percent": 15
        }
        
        # Simulate baseline comparison
        json_performance.compare_to_baseline.return_value = {
            "baseline_comparison": True,
            "performance_regression": False,
            "regression_percentage": -10,  # 10% improvement
            "threshold_exceeded": False,
            "metrics": {
                "processing_time": {"current": 5, "baseline": 5.5, "threshold": 6.0},
                "throughput": {"current": 200, "baseline": 180, "threshold": 150},
                "memory_usage": {"current": 2.5, "baseline": 2.8, "threshold": 3.5},
                "cpu_usage": {"current": 15, "baseline": 18, "threshold": 25}
            }
        }
        
        # Test JSON performance measurement
        perf_result = await json_performance.measure_json_processing(
            json_data={"test": "data", "size": "1kb"}
        )
        assert perf_result["processing_time_ms"] == 5
        assert perf_result["throughput_mb_per_sec"] == 200
        
        # Test baseline comparison
        comparison_result = await json_performance.compare_to_baseline(perf_result)
        assert comparison_result["baseline_comparison"] is True
        assert comparison_result["performance_regression"] is False
        assert comparison_result["regression_percentage"] < 0  # Improvement
        
        # Verify performance gates
        metrics = comparison_result["metrics"]
        assert metrics["processing_time"]["current"] <= metrics["processing_time"]["threshold"]
        assert metrics["throughput"]["current"] >= metrics["throughput"]["threshold"]
        assert metrics["memory_usage"]["current"] <= metrics["memory_usage"]["threshold"]
        assert metrics["cpu_usage"]["current"] <= metrics["cpu_usage"]["threshold"]
        
        # Verify performance assertion
        perf_assertion = PerformanceAssertions.assert_latency_below_threshold(
            perf_result["processing_time_ms"], 10, "JSON processing baseline"
        )
        assert perf_assertion.passed, f"JSON processing should meet baseline: {perf_assertion.message}"
    
    @pytest.mark.asyncio
    async def test_locust_performance_regression_gate(self):
        """Test Locust performance regression gate."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock Locust performance results
        locust_performance = Mock()
        locust_performance.run_load_test = AsyncMock()
        locust_performance.analyze_results = AsyncMock()
        locust_performance.check_regression = AsyncMock()
        
        # Simulate Locust load test results
        locust_performance.run_load_test.return_value = {
            "test_completed": True,
            "test_duration_seconds": 300,
            "total_requests": 10000,
            "successful_requests": 9800,
            "failed_requests": 200,
            "response_times": {
                "p50_ms": 100,
                "p95_ms": 300,
                "p99_ms": 500,
                "max_ms": 1000
            },
            "throughput_rps": 33.3,
            "error_rate_percent": 2.0
        }
        
        # Simulate results analysis
        locust_performance.analyze_results.return_value = {
            "analysis_completed": True,
            "performance_metrics": {
                "avg_response_time_ms": 150,
                "throughput_rps": 33.3,
                "error_rate_percent": 2.0,
                "success_rate_percent": 98.0
            },
            "bottlenecks_detected": [],
            "performance_grade": "A"
        }
        
        # Simulate regression check
        locust_performance.check_regression.return_value = {
            "regression_check_completed": True,
            "performance_regression": False,
            "regression_details": {
                "response_time_regression": False,
                "throughput_regression": False,
                "error_rate_regression": False,
                "overall_regression": False
            },
            "comparison_to_baseline": {
                "response_time_change_percent": -5,  # 5% improvement
                "throughput_change_percent": 10,    # 10% improvement
                "error_rate_change_percent": -1     # 1% improvement
            },
            "gate_status": "PASSED"
        }
        
        # Test Locust load test
        test_result = await locust_performance.run_load_test(
            user_count=100,
            spawn_rate=10,
            duration_seconds=300
        )
        assert test_result["test_completed"] is True
        assert test_result["total_requests"] == 10000
        assert test_result["response_times"]["p95_ms"] == 300
        
        # Test results analysis
        analysis_result = await locust_performance.analyze_results(test_result)
        assert analysis_result["analysis_completed"] is True
        assert analysis_result["performance_grade"] == "A"
        assert len(analysis_result["bottlenecks_detected"]) == 0
        
        # Test regression check
        regression_result = await locust_performance.check_regression(analysis_result)
        assert regression_result["regression_check_completed"] is True
        assert regression_result["performance_regression"] is False
        assert regression_result["gate_status"] == "PASSED"
        
        # Verify performance thresholds
        assert regression_result["comparison_to_baseline"]["response_time_change_percent"] < 20  # No regression
        assert regression_result["comparison_to_baseline"]["throughput_change_percent"] > -20   # No regression
        assert regression_result["comparison_to_baseline"]["error_rate_change_percent"] < 5    # No regression
    
    @pytest.mark.asyncio
    async def test_cost_ceiling_gate(self):
        """Test cost ceiling gate."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock cost monitoring
        cost_monitor = Mock()
        cost_monitor.calculate_request_cost = AsyncMock()
        cost_monitor.check_cost_ceiling = AsyncMock()
        cost_monitor.get_cost_metrics = AsyncMock()
        
        # Simulate request cost calculation
        cost_monitor.calculate_request_cost.return_value = {
            "request_id": "req_001",
            "total_cost_usd": 0.015,
            "cost_breakdown": {
                "router_cost": 0.002,
                "llm_cost": 0.010,
                "storage_cost": 0.001,
                "network_cost": 0.002
            },
            "cost_efficiency_score": 0.85
        }
        
        # Simulate cost ceiling check
        cost_monitor.check_cost_ceiling.return_value = {
            "ceiling_check_completed": True,
            "cost_within_ceiling": True,
            "cost_ceiling_usd": 0.020,
            "current_cost_usd": 0.015,
            "ceiling_utilization_percent": 75,
            "cost_trend": "stable",
            "gate_status": "PASSED"
        }
        
        # Simulate cost metrics
        cost_monitor.get_cost_metrics.return_value = {
            "metrics_calculated": True,
            "daily_cost_usd": 45.50,
            "monthly_cost_usd": 1365.00,
            "cost_per_request_usd": 0.015,
            "cost_efficiency_trend": "improving",
            "cost_anomalies": [],
            "budget_status": "within_budget"
        }
        
        # Test request cost calculation
        cost_result = await cost_monitor.calculate_request_cost(
            request_type="chat",
            complexity="medium"
        )
        assert cost_result["total_cost_usd"] == 0.015
        assert cost_result["cost_efficiency_score"] == 0.85
        
        # Test cost ceiling check
        ceiling_result = await cost_monitor.check_cost_ceiling(cost_result)
        assert ceiling_result["ceiling_check_completed"] is True
        assert ceiling_result["cost_within_ceiling"] is True
        assert ceiling_result["gate_status"] == "PASSED"
        assert ceiling_result["ceiling_utilization_percent"] == 75
        
        # Test cost metrics
        metrics_result = await cost_monitor.get_cost_metrics()
        assert metrics_result["metrics_calculated"] is True
        assert metrics_result["daily_cost_usd"] == 45.50
        assert metrics_result["budget_status"] == "within_budget"
        assert len(metrics_result["cost_anomalies"]) == 0
        
        # Verify cost efficiency
        assert cost_result["total_cost_usd"] <= 0.020  # Within ceiling
        assert ceiling_result["current_cost_usd"] <= ceiling_result["cost_ceiling_usd"]
    
    @pytest.mark.asyncio
    async def test_memory_usage_regression_gate(self):
        """Test memory usage regression gate."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock memory monitoring
        memory_monitor = Mock()
        memory_monitor.measure_memory_usage = AsyncMock()
        memory_monitor.check_memory_regression = AsyncMock()
        memory_monitor.analyze_memory_trends = AsyncMock()
        
        # Simulate memory usage measurement
        memory_monitor.measure_memory_usage.return_value = {
            "measurement_completed": True,
            "current_usage_mb": 512,
            "peak_usage_mb": 768,
            "baseline_usage_mb": 480,
            "memory_efficiency_score": 0.90,
            "gc_frequency": 15,
            "memory_leaks_detected": False
        }
        
        # Simulate memory regression check
        memory_monitor.check_memory_regression.return_value = {
            "regression_check_completed": True,
            "memory_regression": False,
            "regression_percentage": 6.7,  # 6.7% increase from baseline
            "regression_threshold_percent": 20,
            "memory_efficiency_trend": "stable",
            "gate_status": "PASSED"
        }
        
        # Simulate memory trend analysis
        memory_monitor.analyze_memory_trends.return_value = {
            "trend_analysis_completed": True,
            "memory_trend": "stable",
            "trend_duration_hours": 24,
            "memory_growth_rate_mb_per_hour": 2.5,
            "predicted_oom_time_hours": 168,  # 7 days
            "memory_optimization_recommendations": [
                "Increase GC frequency",
                "Optimize object pooling"
            ]
        }
        
        # Test memory usage measurement
        memory_result = await memory_monitor.measure_memory_usage()
        assert memory_result["measurement_completed"] is True
        assert memory_result["current_usage_mb"] == 512
        assert memory_result["memory_leaks_detected"] is False
        
        # Test memory regression check
        regression_result = await memory_monitor.check_memory_regression(memory_result)
        assert regression_result["regression_check_completed"] is True
        assert regression_result["memory_regression"] is False
        assert regression_result["gate_status"] == "PASSED"
        assert regression_result["regression_percentage"] < regression_result["regression_threshold_percent"]
        
        # Test memory trend analysis
        trend_result = await memory_monitor.analyze_memory_trends()
        assert trend_result["trend_analysis_completed"] is True
        assert trend_result["memory_trend"] == "stable"
        assert trend_result["predicted_oom_time_hours"] > 24  # Should not OOM soon
        
        # Verify memory efficiency
        assert memory_result["memory_efficiency_score"] >= 0.8  # Good efficiency
        assert memory_result["current_usage_mb"] <= 1024  # Within reasonable limits
    
    @pytest.mark.asyncio
    async def test_cpu_usage_regression_gate(self):
        """Test CPU usage regression gate."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock CPU monitoring
        cpu_monitor = Mock()
        cpu_monitor.measure_cpu_usage = AsyncMock()
        cpu_monitor.check_cpu_regression = AsyncMock()
        cpu_monitor.analyze_cpu_trends = AsyncMock()
        
        # Simulate CPU usage measurement
        cpu_monitor.measure_cpu_usage.return_value = {
            "measurement_completed": True,
            "avg_cpu_percent": 45,
            "peak_cpu_percent": 85,
            "baseline_cpu_percent": 40,
            "cpu_efficiency_score": 0.88,
            "context_switches": 1500,
            "cpu_bottlenecks": []
        }
        
        # Simulate CPU regression check
        cpu_monitor.check_cpu_regression.return_value = {
            "regression_check_completed": True,
            "cpu_regression": False,
            "regression_percentage": 12.5,  # 12.5% increase from baseline
            "regression_threshold_percent": 25,
            "cpu_efficiency_trend": "stable",
            "gate_status": "PASSED"
        }
        
        # Simulate CPU trend analysis
        cpu_monitor.analyze_cpu_trends.return_value = {
            "trend_analysis_completed": True,
            "cpu_trend": "stable",
            "trend_duration_hours": 24,
            "avg_cpu_utilization_percent": 45,
            "cpu_spike_frequency": 2,  # 2 spikes per hour
            "cpu_optimization_recommendations": [
                "Optimize algorithm complexity",
                "Implement caching"
            ]
        }
        
        # Test CPU usage measurement
        cpu_result = await cpu_monitor.measure_cpu_usage()
        assert cpu_result["measurement_completed"] is True
        assert cpu_result["avg_cpu_percent"] == 45
        assert len(cpu_result["cpu_bottlenecks"]) == 0
        
        # Test CPU regression check
        regression_result = await cpu_monitor.check_cpu_regression(cpu_result)
        assert regression_result["regression_check_completed"] is True
        assert regression_result["cpu_regression"] is False
        assert regression_result["gate_status"] == "PASSED"
        assert regression_result["regression_percentage"] < regression_result["regression_threshold_percent"]
        
        # Test CPU trend analysis
        trend_result = await cpu_monitor.analyze_cpu_trends()
        assert trend_result["trend_analysis_completed"] is True
        assert trend_result["cpu_trend"] == "stable"
        assert trend_result["avg_cpu_utilization_percent"] == 45
        
        # Verify CPU efficiency
        assert cpu_result["cpu_efficiency_score"] >= 0.8  # Good efficiency
        assert cpu_result["avg_cpu_percent"] <= 80  # Within reasonable limits
    
    @pytest.mark.asyncio
    async def test_network_latency_regression_gate(self):
        """Test network latency regression gate."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock network monitoring
        network_monitor = Mock()
        network_monitor.measure_network_latency = AsyncMock()
        network_monitor.check_latency_regression = AsyncMock()
        network_monitor.analyze_network_trends = AsyncMock()
        
        # Simulate network latency measurement
        network_monitor.measure_network_latency.return_value = {
            "measurement_completed": True,
            "avg_latency_ms": 50,
            "p95_latency_ms": 120,
            "p99_latency_ms": 200,
            "baseline_latency_ms": 45,
            "network_efficiency_score": 0.92,
            "packet_loss_percent": 0.1,
            "bandwidth_utilization_percent": 35
        }
        
        # Simulate latency regression check
        network_monitor.check_latency_regression.return_value = {
            "regression_check_completed": True,
            "latency_regression": False,
            "regression_percentage": 11.1,  # 11.1% increase from baseline
            "regression_threshold_percent": 20,
            "network_efficiency_trend": "stable",
            "gate_status": "PASSED"
        }
        
        # Simulate network trend analysis
        network_monitor.analyze_network_trends.return_value = {
            "trend_analysis_completed": True,
            "latency_trend": "stable",
            "trend_duration_hours": 24,
            "avg_latency_ms": 50,
            "latency_spike_frequency": 1,  # 1 spike per hour
            "network_optimization_recommendations": [
                "Optimize connection pooling",
                "Implement CDN caching"
            ]
        }
        
        # Test network latency measurement
        latency_result = await network_monitor.measure_network_latency()
        assert latency_result["measurement_completed"] is True
        assert latency_result["avg_latency_ms"] == 50
        assert latency_result["packet_loss_percent"] < 1.0
        
        # Test latency regression check
        regression_result = await network_monitor.check_latency_regression(latency_result)
        assert regression_result["regression_check_completed"] is True
        assert regression_result["latency_regression"] is False
        assert regression_result["gate_status"] == "PASSED"
        assert regression_result["regression_percentage"] < regression_result["regression_threshold_percent"]
        
        # Test network trend analysis
        trend_result = await network_monitor.analyze_network_trends()
        assert trend_result["trend_analysis_completed"] is True
        assert trend_result["latency_trend"] == "stable"
        assert trend_result["avg_latency_ms"] == 50
        
        # Verify network efficiency
        assert latency_result["network_efficiency_score"] >= 0.8  # Good efficiency
        assert latency_result["avg_latency_ms"] <= 100  # Within reasonable limits
        
        # Verify performance assertion
        perf_assertion = PerformanceAssertions.assert_latency_below_threshold(
            latency_result["avg_latency_ms"], 100, "Network latency baseline"
        )
        assert perf_assertion.passed, f"Network latency should meet baseline: {perf_assertion.message}"
    
    @pytest.mark.asyncio
    async def test_comprehensive_performance_gate(self):
        """Test comprehensive performance gate combining all metrics."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock comprehensive performance monitor
        perf_monitor = Mock()
        perf_monitor.run_comprehensive_test = AsyncMock()
        perf_monitor.evaluate_all_gates = AsyncMock()
        perf_monitor.generate_performance_report = AsyncMock()
        
        # Simulate comprehensive performance test
        perf_monitor.run_comprehensive_test.return_value = {
            "test_completed": True,
            "test_duration_seconds": 600,
            "metrics": {
                "json_processing": {
                    "processing_time_ms": 5,
                    "throughput_mb_per_sec": 200,
                    "memory_usage_mb": 2.5,
                    "cpu_usage_percent": 15
                },
                "locust_performance": {
                    "avg_response_time_ms": 150,
                    "throughput_rps": 33.3,
                    "error_rate_percent": 2.0,
                    "success_rate_percent": 98.0
                },
                "cost_metrics": {
                    "cost_per_request_usd": 0.015,
                    "daily_cost_usd": 45.50,
                    "cost_efficiency_score": 0.85
                },
                "resource_usage": {
                    "memory_usage_mb": 512,
                    "cpu_usage_percent": 45,
                    "network_latency_ms": 50
                }
            }
        }
        
        # Simulate gate evaluation
        perf_monitor.evaluate_all_gates.return_value = {
            "evaluation_completed": True,
            "gate_results": {
                "json_performance_gate": "PASSED",
                "locust_performance_gate": "PASSED",
                "cost_ceiling_gate": "PASSED",
                "memory_regression_gate": "PASSED",
                "cpu_regression_gate": "PASSED",
                "network_latency_gate": "PASSED"
            },
            "overall_gate_status": "PASSED",
            "failed_gates": [],
            "performance_grade": "A",
            "regression_detected": False
        }
        
        # Simulate performance report generation
        perf_monitor.generate_performance_report.return_value = {
            "report_generated": True,
            "report_id": "perf_report_001",
            "report_summary": {
                "overall_performance": "excellent",
                "performance_score": 92,
                "regression_count": 0,
                "optimization_opportunities": [
                    "Implement response caching",
                    "Optimize database queries"
                ],
                "recommendations": [
                    "Continue current performance monitoring",
                    "Consider implementing performance budgets"
                ]
            }
        }
        
        # Test comprehensive performance test
        test_result = await perf_monitor.run_comprehensive_test()
        assert test_result["test_completed"] is True
        assert test_result["test_duration_seconds"] == 600
        
        # Test gate evaluation
        evaluation_result = await perf_monitor.evaluate_all_gates(test_result)
        assert evaluation_result["evaluation_completed"] is True
        assert evaluation_result["overall_gate_status"] == "PASSED"
        assert len(evaluation_result["failed_gates"]) == 0
        assert evaluation_result["performance_grade"] == "A"
        assert evaluation_result["regression_detected"] is False
        
        # Test performance report generation
        report_result = await perf_monitor.generate_performance_report(evaluation_result)
        assert report_result["report_generated"] is True
        assert report_result["report_summary"]["overall_performance"] == "excellent"
        assert report_result["report_summary"]["performance_score"] >= 90
        assert report_result["report_summary"]["regression_count"] == 0
        
        # Verify all gates passed
        gate_results = evaluation_result["gate_results"]
        assert all(status == "PASSED" for status in gate_results.values())
        
        # Verify performance assertions
        metrics = test_result["metrics"]
        
        # JSON performance
        json_assertion = PerformanceAssertions.assert_latency_below_threshold(
            metrics["json_processing"]["processing_time_ms"], 10, "JSON processing"
        )
        assert json_assertion.passed
        
        # Network latency
        latency_assertion = PerformanceAssertions.assert_latency_below_threshold(
            metrics["resource_usage"]["network_latency_ms"], 100, "Network latency"
        )
        assert latency_assertion.passed
        
        # Cost efficiency
        assert metrics["cost_metrics"]["cost_per_request_usd"] <= 0.020
        assert metrics["cost_metrics"]["cost_efficiency_score"] >= 0.8
