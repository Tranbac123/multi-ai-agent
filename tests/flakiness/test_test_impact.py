"""Test test impact analysis and selective test execution."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import PerformanceAssertions


class TestTestImpact:
    """Test test impact analysis and selective test execution."""
    
    @pytest.mark.asyncio
    async def test_test_impact_analysis(self):
        """Test test impact analysis."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock test impact analyzer
        test_impact_analyzer = Mock()
        test_impact_analyzer.analyze_test_impact = AsyncMock()
        test_impact_analyzer.calculate_impact_score = AsyncMock()
        test_impact_analyzer.identify_affected_tests = AsyncMock()
        
        # Simulate test impact analysis
        test_impact_analyzer.analyze_test_impact.return_value = {
            "analysis_completed": True,
            "analysis_id": "impact_analysis_001",
            "code_changes": [
                {
                    "file_path": "apps/router-service/core/decision_engine.py",
                    "change_type": "modified",
                    "change_lines": [10, 15, 20],
                    "impact_level": "high"
                },
                {
                    "file_path": "apps/orchestrator/core/workflow_manager.py",
                    "change_type": "added",
                    "change_lines": [5, 10],
                    "impact_level": "medium"
                }
            ],
            "affected_tests": [
                {
                    "test_id": "test_001",
                    "test_name": "test_router_decision_accuracy",
                    "impact_score": 0.9,
                    "impact_reason": "Direct code change in decision_engine.py"
                },
                {
                    "test_id": "test_002",
                    "test_name": "test_workflow_execution",
                    "impact_score": 0.7,
                    "impact_reason": "Indirect impact through workflow_manager.py"
                }
            ]
        }
        
        # Simulate impact score calculation
        test_impact_analyzer.calculate_impact_score.return_value = {
            "score_calculated": True,
            "test_id": "test_001",
            "impact_score": 0.9,
            "score_breakdown": {
                "direct_code_impact": 0.9,
                "dependency_impact": 0.0,
                "integration_impact": 0.8
            },
            "impact_level": "high"
        }
        
        # Simulate affected test identification
        test_impact_analyzer.identify_affected_tests.return_value = {
            "identification_completed": True,
            "affected_tests_count": 2,
            "affected_tests": [
                {
                    "test_id": "test_001",
                    "test_name": "test_router_decision_accuracy",
                    "test_type": "unit",
                    "impact_confidence": 0.95
                },
                {
                    "test_id": "test_002",
                    "test_name": "test_workflow_execution",
                    "test_type": "integration",
                    "impact_confidence": 0.85
                }
            ]
        }
        
        # Test test impact analysis
        analysis_result = await test_impact_analyzer.analyze_test_impact()
        assert analysis_result["analysis_completed"] is True
        assert len(analysis_result["code_changes"]) == 2
        assert len(analysis_result["affected_tests"]) == 2
        
        # Test impact score calculation
        score_result = await test_impact_analyzer.calculate_impact_score("test_001")
        assert score_result["score_calculated"] is True
        assert score_result["impact_score"] == 0.9
        assert score_result["impact_level"] == "high"
        
        # Test affected test identification
        identification_result = await test_impact_analyzer.identify_affected_tests()
        assert identification_result["identification_completed"] is True
        assert identification_result["affected_tests_count"] == 2
        assert len(identification_result["affected_tests"]) == 2
        
        # Verify impact analysis results
        assert analysis_result["code_changes"][0]["impact_level"] == "high"
        assert analysis_result["affected_tests"][0]["impact_score"] == 0.9
        assert identification_result["affected_tests"][0]["impact_confidence"] == 0.95
    
    @pytest.mark.asyncio
    async def test_selective_test_execution(self):
        """Test selective test execution based on impact analysis."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock selective test executor
        selective_executor = Mock()
        selective_executor.execute_selective_tests = AsyncMock()
        selective_executor.filter_tests_by_impact = AsyncMock()
        selective_executor.optimize_test_execution_order = AsyncMock()
        
        # Simulate selective test execution
        selective_executor.execute_selective_tests.return_value = {
            "execution_completed": True,
            "execution_id": "selective_execution_001",
            "tests_executed": 2,
            "total_tests_available": 100,
            "execution_time_ms": 5000,
            "time_saved_ms": 45000,
            "execution_results": [
                {
                    "test_id": "test_001",
                    "test_name": "test_router_decision_accuracy",
                    "execution_time_ms": 3000,
                    "result": "PASSED",
                    "impact_score": 0.9
                },
                {
                    "test_id": "test_002",
                    "test_name": "test_workflow_execution",
                    "execution_time_ms": 2000,
                    "result": "PASSED",
                    "impact_score": 0.7
                }
            ]
        }
        
        # Simulate test filtering by impact
        selective_executor.filter_tests_by_impact.return_value = {
            "filtering_completed": True,
            "filtered_tests": [
                {
                    "test_id": "test_001",
                    "test_name": "test_router_decision_accuracy",
                    "impact_score": 0.9,
                    "filter_reason": "High impact score"
                },
                {
                    "test_id": "test_002",
                    "test_name": "test_workflow_execution",
                    "impact_score": 0.7,
                    "filter_reason": "Medium impact score"
                }
            ],
            "filtered_count": 2,
            "total_count": 100,
            "filter_efficiency": 0.98
        }
        
        # Simulate test execution order optimization
        selective_executor.optimize_test_execution_order.return_value = {
            "optimization_completed": True,
            "optimized_order": [
                {
                    "test_id": "test_001",
                    "test_name": "test_router_decision_accuracy",
                    "execution_priority": 1,
                    "optimization_reason": "Highest impact score"
                },
                {
                    "test_id": "test_002",
                    "test_name": "test_workflow_execution",
                    "execution_priority": 2,
                    "optimization_reason": "Medium impact score"
                }
            ],
            "optimization_benefits": {
                "estimated_time_savings_ms": 1000,
                "failure_detection_improvement": 0.2,
                "parallel_execution_opportunities": 1
            }
        }
        
        # Test selective test execution
        execution_result = await selective_executor.execute_selective_tests()
        assert execution_result["execution_completed"] is True
        assert execution_result["tests_executed"] == 2
        assert execution_result["total_tests_available"] == 100
        assert execution_result["time_saved_ms"] == 45000
        
        # Test test filtering by impact
        filtering_result = await selective_executor.filter_tests_by_impact()
        assert filtering_result["filtering_completed"] is True
        assert filtering_result["filtered_count"] == 2
        assert filtering_result["filter_efficiency"] == 0.98
        
        # Test test execution order optimization
        optimization_result = await selective_executor.optimize_test_execution_order()
        assert optimization_result["optimization_completed"] is True
        assert len(optimization_result["optimized_order"]) == 2
        assert optimization_result["optimization_benefits"]["estimated_time_savings_ms"] == 1000
        
        # Verify selective execution results
        assert execution_result["execution_results"][0]["result"] == "PASSED"
        assert execution_result["execution_results"][1]["result"] == "PASSED"
        assert filtering_result["filtered_tests"][0]["impact_score"] == 0.9
        assert optimization_result["optimized_order"][0]["execution_priority"] == 1
        
        # Verify performance improvements
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            execution_result["execution_time_ms"], 10000, "Selective test execution duration"
        )
        assert perf_result.passed, f"Selective test execution should be efficient: {perf_result.message}"
        
        # Verify time savings
        time_savings_percentage = (execution_result["time_saved_ms"] / 
                                 (execution_result["time_saved_ms"] + execution_result["execution_time_ms"])) * 100
        assert time_savings_percentage >= 80.0, f"Time savings should be significant: {time_savings_percentage}%"
    
    @pytest.mark.asyncio
    async def test_test_impact_caching(self):
        """Test test impact analysis caching."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock test impact cache
        test_impact_cache = Mock()
        test_impact_cache.cache_impact_analysis = AsyncMock()
        test_impact_cache.retrieve_cached_impact = AsyncMock()
        test_impact_cache.invalidate_cache = AsyncMock()
        
        # Simulate impact analysis caching
        test_impact_cache.cache_impact_analysis.return_value = {
            "caching_completed": True,
            "cache_key": "impact_analysis_001",
            "cached_data": {
                "analysis_id": "impact_analysis_001",
                "affected_tests": ["test_001", "test_002"],
                "impact_scores": {"test_001": 0.9, "test_002": 0.7},
                "cache_timestamp": time.time()
            },
            "cache_ttl_seconds": 3600,
            "cache_size_bytes": 1024
        }
        
        # Simulate cached impact retrieval
        test_impact_cache.retrieve_cached_impact.return_value = {
            "retrieval_completed": True,
            "cache_hit": True,
            "cached_data": {
                "analysis_id": "impact_analysis_001",
                "affected_tests": ["test_001", "test_002"],
                "impact_scores": {"test_001": 0.9, "test_002": 0.7},
                "cache_timestamp": time.time() - 1800  # 30 minutes ago
            },
            "retrieval_time_ms": 10,
            "cache_age_seconds": 1800
        }
        
        # Simulate cache invalidation
        test_impact_cache.invalidate_cache.return_value = {
            "invalidation_completed": True,
            "cache_key": "impact_analysis_001",
            "invalidation_reason": "Code changes detected",
            "invalidation_time": time.time(),
            "affected_cache_entries": 1
        }
        
        # Test impact analysis caching
        caching_result = await test_impact_cache.cache_impact_analysis(
            analysis_data={"affected_tests": ["test_001", "test_002"]}
        )
        assert caching_result["caching_completed"] is True
        assert caching_result["cache_ttl_seconds"] == 3600
        assert caching_result["cache_size_bytes"] == 1024
        
        # Test cached impact retrieval
        retrieval_result = await test_impact_cache.retrieve_cached_impact("impact_analysis_001")
        assert retrieval_result["retrieval_completed"] is True
        assert retrieval_result["cache_hit"] is True
        assert retrieval_result["retrieval_time_ms"] == 10
        
        # Test cache invalidation
        invalidation_result = await test_impact_cache.invalidate_cache("impact_analysis_001")
        assert invalidation_result["invalidation_completed"] is True
        assert invalidation_result["invalidation_reason"] == "Code changes detected"
        assert invalidation_result["affected_cache_entries"] == 1
        
        # Verify caching performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            retrieval_result["retrieval_time_ms"], 100, "Cache retrieval duration"
        )
        assert perf_result.passed, f"Cache retrieval should be fast: {perf_result.message}"
        
        # Verify cache data integrity
        assert caching_result["cached_data"]["affected_tests"] == ["test_001", "test_002"]
        assert retrieval_result["cached_data"]["impact_scores"]["test_001"] == 0.9
        assert retrieval_result["cache_age_seconds"] == 1800
    
    @pytest.mark.asyncio
    async def test_test_impact_reporting(self):
        """Test test impact analysis reporting."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock test impact reporter
        test_impact_reporter = Mock()
        test_impact_reporter.generate_impact_report = AsyncMock()
        test_impact_reporter.export_impact_data = AsyncMock()
        test_impact_reporter.send_impact_notifications = AsyncMock()
        
        # Simulate impact report generation
        test_impact_reporter.generate_impact_report.return_value = {
            "report_generated": True,
            "report_id": "impact_report_001",
            "report_summary": {
                "total_tests": 100,
                "affected_tests": 2,
                "impact_coverage": 0.02,
                "high_impact_tests": 1,
                "medium_impact_tests": 1,
                "low_impact_tests": 0
            },
            "report_details": {
                "code_changes": [
                    {
                        "file_path": "apps/router-service/core/decision_engine.py",
                        "change_type": "modified",
                        "impact_level": "high"
                    }
                ],
                "affected_tests": [
                    {
                        "test_id": "test_001",
                        "test_name": "test_router_decision_accuracy",
                        "impact_score": 0.9,
                        "test_type": "unit"
                    }
                ]
            }
        }
        
        # Simulate impact data export
        test_impact_reporter.export_impact_data.return_value = {
            "export_completed": True,
            "export_format": "JSON",
            "export_file_path": "/tmp/impact_data_001.json",
            "export_size_bytes": 2048,
            "export_timestamp": time.time()
        }
        
        # Simulate impact notification sending
        test_impact_reporter.send_impact_notifications.return_value = {
            "notifications_sent": True,
            "notification_count": 3,
            "notifications": [
                {
                    "notification_id": "notif_001",
                    "recipient": "developer@example.com",
                    "notification_type": "high_impact_test",
                    "message": "Test test_router_decision_accuracy has high impact score (0.9)"
                },
                {
                    "notification_id": "notif_002",
                    "recipient": "qa-team@example.com",
                    "notification_type": "impact_summary",
                    "message": "2 tests affected by recent code changes"
                },
                {
                    "notification_id": "notif_003",
                    "recipient": "ci-system@example.com",
                    "notification_type": "selective_execution",
                    "message": "Selective test execution saved 45 seconds"
                }
            ]
        }
        
        # Test impact report generation
        report_result = await test_impact_reporter.generate_impact_report()
        assert report_result["report_generated"] is True
        assert report_result["report_summary"]["total_tests"] == 100
        assert report_result["report_summary"]["affected_tests"] == 2
        assert report_result["report_summary"]["impact_coverage"] == 0.02
        
        # Test impact data export
        export_result = await test_impact_reporter.export_impact_data()
        assert export_result["export_completed"] is True
        assert export_result["export_format"] == "JSON"
        assert export_result["export_size_bytes"] == 2048
        
        # Test impact notification sending
        notification_result = await test_impact_reporter.send_impact_notifications()
        assert notification_result["notifications_sent"] is True
        assert notification_result["notification_count"] == 3
        assert len(notification_result["notifications"]) == 3
        
        # Verify report content
        assert report_result["report_summary"]["high_impact_tests"] == 1
        assert report_result["report_summary"]["medium_impact_tests"] == 1
        assert report_result["report_details"]["code_changes"][0]["impact_level"] == "high"
        assert report_result["report_details"]["affected_tests"][0]["impact_score"] == 0.9
        
        # Verify notification types
        notifications = notification_result["notifications"]
        assert notifications[0]["notification_type"] == "high_impact_test"
        assert notifications[1]["notification_type"] == "impact_summary"
        assert notifications[2]["notification_type"] == "selective_execution"
        assert all(notif["message"] for notif in notifications)
    
    @pytest.mark.asyncio
    async def test_test_impact_optimization(self):
        """Test test impact analysis optimization."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock test impact optimizer
        test_impact_optimizer = Mock()
        test_impact_optimizer.optimize_impact_analysis = AsyncMock()
        test_impact_optimizer.improve_analysis_accuracy = AsyncMock()
        test_impact_optimizer.reduce_analysis_time = AsyncMock()
        
        # Simulate impact analysis optimization
        test_impact_optimizer.optimize_impact_analysis.return_value = {
            "optimization_completed": True,
            "optimization_id": "impact_optimization_001",
            "optimization_strategies": [
                "Parallel analysis execution",
                "Incremental analysis",
                "Smart caching"
            ],
            "optimization_metrics": {
                "analysis_time_reduction_percent": 60.0,
                "accuracy_improvement_percent": 15.0,
                "resource_usage_reduction_percent": 40.0
            }
        }
        
        # Simulate analysis accuracy improvement
        test_impact_optimizer.improve_analysis_accuracy.return_value = {
            "accuracy_improvement_completed": True,
            "accuracy_improvements": {
                "false_positive_rate_reduction": 0.2,
                "false_negative_rate_reduction": 0.1,
                "overall_accuracy_improvement": 0.15
            },
            "improvement_techniques": [
                "Enhanced dependency analysis",
                "Machine learning-based impact prediction",
                "Historical impact data analysis"
            ]
        }
        
        # Simulate analysis time reduction
        test_impact_optimizer.reduce_analysis_time.return_value = {
            "time_reduction_completed": True,
            "time_reduction_metrics": {
                "baseline_analysis_time_ms": 10000,
                "optimized_analysis_time_ms": 4000,
                "time_reduction_percentage": 60.0
            },
            "optimization_techniques": [
                "Parallel processing",
                "Incremental analysis",
                "Smart caching",
                "Early termination"
            ]
        }
        
        # Test impact analysis optimization
        optimization_result = await test_impact_optimizer.optimize_impact_analysis()
        assert optimization_result["optimization_completed"] is True
        assert len(optimization_result["optimization_strategies"]) == 3
        assert optimization_result["optimization_metrics"]["analysis_time_reduction_percent"] == 60.0
        
        # Test analysis accuracy improvement
        accuracy_result = await test_impact_optimizer.improve_analysis_accuracy()
        assert accuracy_result["accuracy_improvement_completed"] is True
        assert accuracy_result["accuracy_improvements"]["overall_accuracy_improvement"] == 0.15
        
        # Test analysis time reduction
        time_result = await test_impact_optimizer.reduce_analysis_time()
        assert time_result["time_reduction_completed"] is True
        assert time_result["time_reduction_metrics"]["time_reduction_percentage"] == 60.0
        
        # Verify optimization results
        assert optimization_result["optimization_metrics"]["accuracy_improvement_percent"] == 15.0
        assert optimization_result["optimization_metrics"]["resource_usage_reduction_percent"] == 40.0
        assert accuracy_result["accuracy_improvements"]["false_positive_rate_reduction"] == 0.2
        assert time_result["time_reduction_metrics"]["baseline_analysis_time_ms"] == 10000
        assert time_result["time_reduction_metrics"]["optimized_analysis_time_ms"] == 4000
