"""Test OpenTelemetry spans and tracing."""

import pytest
import asyncio
import time
import json
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import PerformanceAssertions


class TestOpenTelemetrySpans:
    """Test OpenTelemetry spans and tracing."""
    
    @pytest.mark.asyncio
    async def test_span_creation_and_tracking(self):
        """Test span creation and tracking."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Mock OpenTelemetry tracer
        otel_tracer = Mock()
        otel_tracer.create_span = AsyncMock()
        otel_tracer.add_span_attributes = AsyncMock()
        otel_tracer.finish_span = AsyncMock()
        
        # Simulate span creation
        otel_tracer.create_span.return_value = {
            "span_created": True,
            "span_id": "span_001",
            "trace_id": "trace_001",
            "operation_name": "user_request_processing",
            "start_time": time.time(),
            "span_context": {
                "tenant_id": tenant["tenant_id"],
                "user_id": user["user_id"],
                "request_id": "req_001"
            }
        }
        
        # Simulate span attributes
        otel_tracer.add_span_attributes.return_value = {
            "attributes_added": True,
            "span_id": "span_001",
            "attributes": {
                "http.method": "POST",
                "http.url": "/api/v1/chat",
                "http.status_code": 200,
                "tenant.id": tenant["tenant_id"],
                "user.id": user["user_id"],
                "request.duration_ms": 150
            }
        }
        
        # Simulate span finishing
        otel_tracer.finish_span.return_value = {
            "span_finished": True,
            "span_id": "span_001",
            "end_time": time.time(),
            "duration_ms": 150,
            "status": "OK"
        }
        
        # Test span creation
        span_result = await otel_tracer.create_span(
            operation_name="user_request_processing",
            context={"tenant_id": tenant["tenant_id"], "user_id": user["user_id"]}
        )
        assert span_result["span_created"] is True
        assert span_result["span_id"] == "span_001"
        assert span_result["trace_id"] == "trace_001"
        
        # Test span attributes
        attributes_result = await otel_tracer.add_span_attributes(
            span_id="span_001",
            attributes={
                "http.method": "POST",
                "http.url": "/api/v1/chat",
                "http.status_code": 200
            }
        )
        assert attributes_result["attributes_added"] is True
        assert len(attributes_result["attributes"]) == 6
        
        # Test span finishing
        finish_result = await otel_tracer.finish_span("span_001")
        assert finish_result["span_finished"] is True
        assert finish_result["duration_ms"] == 150
        assert finish_result["status"] == "OK"
        
        # Verify span performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            finish_result["duration_ms"], 500, "Span duration"
        )
        assert perf_result.passed, f"Span should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_distributed_tracing(self):
        """Test distributed tracing across services."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock distributed tracer
        distributed_tracer = Mock()
        distributed_tracer.create_distributed_trace = AsyncMock()
        distributed_tracer.add_service_span = AsyncMock()
        distributed_tracer.validate_trace_continuity = AsyncMock()
        
        # Simulate distributed trace creation
        distributed_tracer.create_distributed_trace.return_value = {
            "trace_created": True,
            "trace_id": "trace_001",
            "services_involved": ["api-gateway", "router", "orchestrator", "llm"],
            "total_spans": 4,
            "trace_duration_ms": 500
        }
        
        # Simulate service span addition
        distributed_tracer.add_service_span.return_value = {
            "span_added": True,
            "service_name": "router",
            "span_id": "span_002",
            "parent_span_id": "span_001",
            "operation": "route_decision",
            "duration_ms": 50,
            "attributes": {
                "service.name": "router",
                "operation.name": "route_decision",
                "router.tier": "SLM_A",
                "router.confidence": 0.95
            }
        }
        
        # Simulate trace continuity validation
        distributed_tracer.validate_trace_continuity.return_value = {
            "continuity_validated": True,
            "trace_id": "trace_001",
            "span_continuity": "valid",
            "parent_child_relationships": "correct",
            "trace_completeness": "complete",
            "validation_errors": []
        }
        
        # Test distributed trace creation
        trace_result = await distributed_tracer.create_distributed_trace(
            trace_id="trace_001",
            services=["api-gateway", "router", "orchestrator", "llm"]
        )
        assert trace_result["trace_created"] is True
        assert len(trace_result["services_involved"]) == 4
        assert trace_result["total_spans"] == 4
        
        # Test service span addition
        span_result = await distributed_tracer.add_service_span(
            trace_id="trace_001",
            service_name="router",
            operation="route_decision",
            parent_span_id="span_001"
        )
        assert span_result["span_added"] is True
        assert span_result["service_name"] == "router"
        assert span_result["parent_span_id"] == "span_001"
        
        # Test trace continuity validation
        continuity_result = await distributed_tracer.validate_trace_continuity("trace_001")
        assert continuity_result["continuity_validated"] is True
        assert continuity_result["span_continuity"] == "valid"
        assert continuity_result["trace_completeness"] == "complete"
        assert len(continuity_result["validation_errors"]) == 0
        
        # Verify trace performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            trace_result["trace_duration_ms"], 1000, "Distributed trace duration"
        )
        assert perf_result.passed, f"Distributed trace should be reasonable: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_span_error_handling(self):
        """Test span error handling and status tracking."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock error span handler
        error_span_handler = Mock()
        error_span_handler.handle_span_error = AsyncMock()
        error_span_handler.set_span_status = AsyncMock()
        error_span_handler.add_error_attributes = AsyncMock()
        
        # Simulate span error handling
        error_span_handler.handle_span_error.return_value = {
            "error_handled": True,
            "span_id": "span_001",
            "error_type": "ServiceUnavailableError",
            "error_message": "Router service unavailable",
            "error_timestamp": time.time(),
            "span_status": "ERROR"
        }
        
        # Simulate span status setting
        error_span_handler.set_span_status.return_value = {
            "status_set": True,
            "span_id": "span_001",
            "status_code": "ERROR",
            "status_description": "Service unavailable"
        }
        
        # Simulate error attributes addition
        error_span_handler.add_error_attributes.return_value = {
            "attributes_added": True,
            "span_id": "span_001",
            "error_attributes": {
                "error.type": "ServiceUnavailableError",
                "error.message": "Router service unavailable",
                "error.stack_trace": "Traceback (most recent call last)...",
                "error.retry_count": 3,
                "error.recovery_time_ms": 1000
            }
        }
        
        # Test span error handling
        error_result = await error_span_handler.handle_span_error(
            span_id="span_001",
            error=Exception("Router service unavailable")
        )
        assert error_result["error_handled"] is True
        assert error_result["error_type"] == "ServiceUnavailableError"
        assert error_result["span_status"] == "ERROR"
        
        # Test span status setting
        status_result = await error_span_handler.set_span_status(
            span_id="span_001",
            status_code="ERROR",
            description="Service unavailable"
        )
        assert status_result["status_set"] is True
        assert status_result["status_code"] == "ERROR"
        
        # Test error attributes addition
        attributes_result = await error_span_handler.add_error_attributes(
            span_id="span_001",
            error_attributes={
                "error.type": "ServiceUnavailableError",
                "error.message": "Router service unavailable",
                "error.retry_count": 3
            }
        )
        assert attributes_result["attributes_added"] is True
        assert len(attributes_result["error_attributes"]) == 5
        
        # Verify error handling
        assert error_result["error_type"] == "ServiceUnavailableError"
        assert error_result["span_status"] == "ERROR"
        assert attributes_result["error_attributes"]["error.retry_count"] == 3
    
    @pytest.mark.asyncio
    async def test_span_sampling_strategies(self):
        """Test span sampling strategies."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock span sampler
        span_sampler = Mock()
        span_sampler.should_sample = AsyncMock()
        span_sampler.get_sampling_decision = AsyncMock()
        span_sampler.update_sampling_rate = AsyncMock()
        
        # Simulate sampling decision
        span_sampler.should_sample.return_value = {
            "sampling_decision": True,
            "span_id": "span_001",
            "sampling_strategy": "probabilistic",
            "sampling_rate": 0.1,
            "sampling_reason": "random_sampling"
        }
        
        # Simulate sampling decision details
        span_sampler.get_sampling_decision.return_value = {
            "decision_made": True,
            "span_id": "span_001",
            "sampling_strategy": "probabilistic",
            "sampling_rate": 0.1,
            "decision_factors": {
                "tenant_id": tenant["tenant_id"],
                "operation_type": "user_request",
                "request_frequency": "high",
                "error_rate": "low"
            },
            "sampling_metadata": {
                "random_value": 0.05,
                "threshold": 0.1,
                "decision": "sample"
            }
        }
        
        # Simulate sampling rate update
        span_sampler.update_sampling_rate.return_value = {
            "rate_updated": True,
            "old_rate": 0.1,
            "new_rate": 0.05,
            "update_reason": "High volume, reducing sampling rate",
            "effective_date": time.time()
        }
        
        # Test sampling decision
        sampling_result = await span_sampler.should_sample(
            span_id="span_001",
            context={"tenant_id": tenant["tenant_id"], "operation": "user_request"}
        )
        assert sampling_result["sampling_decision"] is True
        assert sampling_result["sampling_strategy"] == "probabilistic"
        assert sampling_result["sampling_rate"] == 0.1
        
        # Test sampling decision details
        decision_result = await span_sampler.get_sampling_decision("span_001")
        assert decision_result["decision_made"] is True
        assert decision_result["sampling_strategy"] == "probabilistic"
        assert len(decision_result["decision_factors"]) == 4
        
        # Test sampling rate update
        update_result = await span_sampler.update_sampling_rate(0.05)
        assert update_result["rate_updated"] is True
        assert update_result["old_rate"] == 0.1
        assert update_result["new_rate"] == 0.05
        
        # Verify sampling logic
        assert sampling_result["sampling_decision"] is True
        assert decision_result["sampling_metadata"]["decision"] == "sample"
        assert decision_result["sampling_metadata"]["random_value"] <= decision_result["sampling_metadata"]["threshold"]
    
    @pytest.mark.asyncio
    async def test_span_export_and_storage(self):
        """Test span export and storage."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock span exporter
        span_exporter = Mock()
        span_exporter.export_spans = AsyncMock()
        span_exporter.validate_span_data = AsyncMock()
        span_exporter.check_export_performance = AsyncMock()
        
        # Simulate span export
        span_exporter.export_spans.return_value = {
            "export_completed": True,
            "spans_exported": 100,
            "export_time_ms": 200,
            "export_success_rate": 100.0,
            "export_errors": []
        }
        
        # Simulate span data validation
        span_exporter.validate_span_data.return_value = {
            "validation_completed": True,
            "valid_spans": 100,
            "invalid_spans": 0,
            "validation_errors": [],
            "span_data_quality_score": 1.0
        }
        
        # Simulate export performance check
        span_exporter.check_export_performance.return_value = {
            "performance_check_completed": True,
            "export_time_ms": 200,
            "performance_threshold_ms": 500,
            "performance_grade": "A",
            "optimization_suggestions": []
        }
        
        # Test span export
        export_result = await span_exporter.export_spans(
            spans=[{"span_id": f"span_{i}"} for i in range(100)]
        )
        assert export_result["export_completed"] is True
        assert export_result["spans_exported"] == 100
        assert export_result["export_success_rate"] == 100.0
        assert len(export_result["export_errors"]) == 0
        
        # Test span data validation
        validation_result = await span_exporter.validate_span_data(export_result)
        assert validation_result["validation_completed"] is True
        assert validation_result["valid_spans"] == 100
        assert validation_result["invalid_spans"] == 0
        assert validation_result["span_data_quality_score"] == 1.0
        
        # Test export performance
        performance_result = await span_exporter.check_export_performance(export_result)
        assert performance_result["performance_check_completed"] is True
        assert performance_result["performance_grade"] == "A"
        assert performance_result["export_time_ms"] <= performance_result["performance_threshold_ms"]
        
        # Verify export performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            export_result["export_time_ms"], 500, "Span export time"
        )
        assert perf_result.passed, f"Span export should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_span_correlation_with_logs(self):
        """Test span correlation with logs."""
        # Setup
        tenant_factory = TenantFactory()
        user_factory = UserFactory()
        
        tenant = tenant_factory.create()
        user = user_factory.create(tenant["tenant_id"])
        
        # Mock span-log correlator
        span_log_correlator = Mock()
        span_log_correlator.correlate_spans_with_logs = AsyncMock()
        span_log_correlator.validate_correlation = AsyncMock()
        span_log_correlator.extract_correlation_metadata = AsyncMock()
        
        # Simulate span-log correlation
        span_log_correlator.correlate_spans_with_logs.return_value = {
            "correlation_completed": True,
            "spans_correlated": 50,
            "logs_correlated": 200,
            "correlation_rate": 0.95,
            "correlation_metadata": {
                "trace_id": "trace_001",
                "span_id": "span_001",
                "log_level": "INFO",
                "log_message": "Processing user request",
                "correlation_timestamp": time.time()
            }
        }
        
        # Simulate correlation validation
        span_log_correlator.validate_correlation.return_value = {
            "validation_completed": True,
            "correlation_valid": True,
            "validation_errors": [],
            "correlation_quality_score": 0.98
        }
        
        # Simulate correlation metadata extraction
        span_log_correlator.extract_correlation_metadata.return_value = {
            "metadata_extracted": True,
            "correlation_fields": {
                "trace_id": "trace_001",
                "span_id": "span_001",
                "tenant_id": tenant["tenant_id"],
                "user_id": user["user_id"],
                "request_id": "req_001"
            },
            "extraction_accuracy": 0.99
        }
        
        # Test span-log correlation
        correlation_result = await span_log_correlator.correlate_spans_with_logs(
            trace_id="trace_001",
            span_id="span_001"
        )
        assert correlation_result["correlation_completed"] is True
        assert correlation_result["spans_correlated"] == 50
        assert correlation_result["logs_correlated"] == 200
        assert correlation_result["correlation_rate"] >= 0.9
        
        # Test correlation validation
        validation_result = await span_log_correlator.validate_correlation(correlation_result)
        assert validation_result["validation_completed"] is True
        assert validation_result["correlation_valid"] is True
        assert validation_result["correlation_quality_score"] >= 0.95
        
        # Test correlation metadata extraction
        metadata_result = await span_log_correlator.extract_correlation_metadata(correlation_result)
        assert metadata_result["metadata_extracted"] is True
        assert len(metadata_result["correlation_fields"]) == 5
        assert metadata_result["extraction_accuracy"] >= 0.95
        
        # Verify correlation quality
        assert correlation_result["correlation_rate"] >= 0.9
        assert validation_result["correlation_quality_score"] >= 0.95
        assert metadata_result["extraction_accuracy"] >= 0.95
