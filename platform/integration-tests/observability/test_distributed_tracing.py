"""Distributed tracing tests with OpenTelemetry integration."""

import pytest
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from unittest.mock import Mock, AsyncMock, patch

from tests.observability import (
    TraceAssertion, MockSpan, MockTracer, MetricsCollector
)


class TraceValidator:
    """Validates distributed traces against assertions."""
    
    def __init__(self, tracer: MockTracer):
        self.tracer = tracer
    
    def validate_trace_assertion(self, assertion: TraceAssertion) -> bool:
        """Validate a trace assertion."""
        spans = self.tracer.get_spans_by_name(assertion.operation_name)
        if not spans:
            return False
        
        # Check if all expected spans are present
        span_names = [span.name for span in spans]
        for expected_span in assertion.expected_spans:
            if expected_span not in span_names:
                return False
        
        # Check duration if specified
        if assertion.expected_duration_ms is not None:
            for span in spans:
                if span.duration_ms > assertion.expected_duration_ms:
                    return False
        
        # Check tags if specified
        if assertion.expected_tags:
            for span in spans:
                for tag_key, expected_value in assertion.expected_tags.items():
                    if tag_key not in span.attributes or span.attributes[tag_key] != expected_value:
                        return False
        
        # Check error status if specified
        if assertion.error_expected:
            for span in spans:
                if span.status_code != "ERROR":
                    return False
        else:
            for span in spans:
                if span.status_code == "ERROR":
                    return False
        
        return True
    
    def get_trace_by_id(self, trace_id: str) -> List[MockSpan]:
        """Get all spans for a trace ID."""
        return self.tracer.get_spans_by_trace_id(trace_id)
    
    def get_span_by_name(self, name: str) -> Optional[MockSpan]:
        """Get the first span with the given name."""
        spans = self.tracer.get_spans_by_name(name)
        return spans[0] if spans else None
    
    def validate_trace_completeness(self, trace_id: str, expected_operations: List[str]) -> bool:
        """Validate that a trace contains all expected operations."""
        spans = self.get_trace_by_id(trace_id)
        span_names = [span.name for span in spans]
        
        for operation in expected_operations:
            if operation not in span_names:
                return False
        
        return True
    
    def validate_span_hierarchy(self, trace_id: str) -> bool:
        """Validate span parent-child relationships."""
        spans = self.get_trace_by_id(trace_id)
        
        # Find root spans (no parent)
        root_spans = [span for span in spans if span.parent_span_id is None]
        
        # Should have exactly one root span
        if len(root_spans) != 1:
            return False
        
        # Validate parent-child relationships
        span_by_id = {span.span_id: span for span in spans}
        for span in spans:
            if span.parent_span_id and span.parent_span_id not in span_by_id:
                return False
        
        return True


class TestDistributedTracing:
    """Test distributed tracing functionality."""
    
    @pytest.fixture
    def mock_tracer(self):
        """Create mock tracer."""
        return MockTracer()
    
    @pytest.fixture
    def trace_validator(self, mock_tracer):
        """Create trace validator."""
        return TraceValidator(mock_tracer)
    
    def test_basic_span_creation(self, mock_tracer):
        """Test basic span creation."""
        # Create a span
        span = mock_tracer.start_span("test_operation")
        
        # Verify span properties
        assert span.name == "test_operation"
        assert span.status_code == "OK"
        assert span.start_time is not None
        assert span.span_id is not None
        assert span.trace_id is not None
        
        # Finish the span
        span.finish()
        assert span.end_time is not None
        assert span.duration_ms > 0
    
    def test_span_with_attributes(self, mock_tracer):
        """Test span with attributes."""
        # Create span with attributes
        span = mock_tracer.start_span("api_request", attributes={
            "http.method": "GET",
            "http.url": "/api/query",
            "user.id": "12345"
        })
        
        # Verify attributes
        assert span.attributes["http.method"] == "GET"
        assert span.attributes["http.url"] == "/api/query"
        assert span.attributes["user.id"] == "12345"
        
        span.finish()
    
    def test_span_with_events(self, mock_tracer):
        """Test span with events."""
        # Create span
        span = mock_tracer.start_span("database_query")
        
        # Add events
        span.add_event("query_started", {"query": "SELECT * FROM users"})
        span.add_event("query_completed", {"rows_returned": 100})
        
        # Verify events
        assert len(span.events) == 2
        assert span.events[0]["name"] == "query_started"
        assert span.events[1]["name"] == "query_completed"
        
        span.finish()
    
    def test_span_with_status(self, mock_tracer):
        """Test span with error status."""
        # Create span
        span = mock_tracer.start_span("failed_operation")
        
        # Set error status
        span.set_status("ERROR", "Database connection failed")
        
        # Verify status
        assert span.status_code == "ERROR"
        assert span.status_message == "Database connection failed"
        
        span.finish()
    
    def test_parent_child_spans(self, mock_tracer):
        """Test parent-child span relationships."""
        # Create parent span
        parent_span = mock_tracer.start_span("parent_operation")
        
        # Create child span
        child_span = mock_tracer.start_span("child_operation", parent=parent_span)
        
        # Verify relationship
        assert child_span.parent_span_id == parent_span.span_id
        assert child_span.trace_id == parent_span.trace_id
        
        # Finish spans
        child_span.finish()
        parent_span.finish()
    
    def test_trace_assertion_validation(self, mock_tracer, trace_validator):
        """Test trace assertion validation."""
        # Create spans
        api_span = mock_tracer.start_span("api_request", attributes={
            "http.method": "POST",
            "http.url": "/api/workflow"
        })
        
        db_span = mock_tracer.start_span("database_query", parent=api_span)
        cache_span = mock_tracer.start_span("cache_lookup", parent=api_span)
        
        # Finish spans
        db_span.finish()
        cache_span.finish()
        api_span.finish()
        
        # Create trace assertion
        assertion = TraceAssertion(
            operation_name="api_request",
            expected_spans=["api_request", "database_query", "cache_lookup"],
            expected_duration_ms=1000.0,
            expected_tags={"http.method": "POST"},
            error_expected=False
        )
        
        # Validate assertion
        result = trace_validator.validate_trace_assertion(assertion)
        assert result is True
    
    def test_trace_assertion_failure(self, mock_tracer, trace_validator):
        """Test trace assertion failure."""
        # Create spans
        api_span = mock_tracer.start_span("api_request")
        db_span = mock_tracer.start_span("database_query", parent=api_span)
        
        # Finish spans
        db_span.finish()
        api_span.finish()
        
        # Create assertion that should fail (missing expected span)
        assertion = TraceAssertion(
            operation_name="api_request",
            expected_spans=["api_request", "cache_lookup"],  # cache_lookup is missing
            error_expected=False
        )
        
        # Validate assertion
        result = trace_validator.validate_trace_assertion(assertion)
        assert result is False
    
    def test_duration_assertion(self, mock_tracer, trace_validator):
        """Test duration-based trace assertion."""
        # Create span with long duration
        span = mock_tracer.start_span("slow_operation")
        time.sleep(0.1)  # 100ms
        span.finish()
        
        # Create assertion with short duration limit
        assertion = TraceAssertion(
            operation_name="slow_operation",
            expected_spans=["slow_operation"],
            expected_duration_ms=50.0,  # 50ms limit
            error_expected=False
        )
        
        # Validate assertion (should fail due to duration)
        result = trace_validator.validate_trace_assertion(assertion)
        assert result is False
    
    def test_error_status_assertion(self, mock_tracer, trace_validator):
        """Test error status trace assertion."""
        # Create span with error status
        span = mock_tracer.start_span("error_operation")
        span.set_status("ERROR", "Something went wrong")
        span.finish()
        
        # Create assertion expecting error
        assertion = TraceAssertion(
            operation_name="error_operation",
            expected_spans=["error_operation"],
            error_expected=True
        )
        
        # Validate assertion
        result = trace_validator.validate_trace_assertion(assertion)
        assert result is True
    
    def test_trace_completeness_validation(self, mock_tracer, trace_validator):
        """Test trace completeness validation."""
        # Create trace with multiple operations
        root_span = mock_tracer.start_span("user_request")
        
        auth_span = mock_tracer.start_span("authentication", parent=root_span)
        auth_span.finish()
        
        api_span = mock_tracer.start_span("api_call", parent=root_span)
        db_span = mock_tracer.start_span("database_query", parent=api_span)
        db_span.finish()
        api_span.finish()
        
        root_span.finish()
        
        # Validate completeness
        expected_operations = ["user_request", "authentication", "api_call", "database_query"]
        result = trace_validator.validate_trace_completeness(root_span.trace_id, expected_operations)
        assert result is True
    
    def test_span_hierarchy_validation(self, mock_tracer, trace_validator):
        """Test span hierarchy validation."""
        # Create proper hierarchy
        root_span = mock_tracer.start_span("root")
        
        child1_span = mock_tracer.start_span("child1", parent=root_span)
        child2_span = mock_tracer.start_span("child2", parent=root_span)
        
        grandchild_span = mock_tracer.start_span("grandchild", parent=child1_span)
        
        # Finish spans
        grandchild_span.finish()
        child1_span.finish()
        child2_span.finish()
        root_span.finish()
        
        # Validate hierarchy
        result = trace_validator.validate_span_hierarchy(root_span.trace_id)
        assert result is True
    
    def test_invalid_span_hierarchy(self, mock_tracer, trace_validator):
        """Test invalid span hierarchy detection."""
        # Create invalid hierarchy (orphaned span)
        root_span = mock_tracer.start_span("root")
        orphaned_span = mock_tracer.start_span("orphaned")
        
        # Finish spans
        root_span.finish()
        orphaned_span.finish()
        
        # Validate hierarchy (should fail due to orphaned span)
        result = trace_validator.validate_span_hierarchy(root_span.trace_id)
        assert result is False
    
    def test_span_retrieval_by_name(self, mock_tracer, trace_validator):
        """Test span retrieval by name."""
        # Create spans with different names
        span1 = mock_tracer.start_span("operation_a")
        span2 = mock_tracer.start_span("operation_b")
        span3 = mock_tracer.start_span("operation_a")  # Same name as span1
        
        span1.finish()
        span2.finish()
        span3.finish()
        
        # Get spans by name
        retrieved_span = trace_validator.get_span_by_name("operation_a")
        assert retrieved_span is not None
        assert retrieved_span.name == "operation_a"
        
        # Get non-existent span
        non_existent = trace_validator.get_span_by_name("non_existent")
        assert non_existent is None
    
    def test_trace_retrieval_by_id(self, mock_tracer, trace_validator):
        """Test trace retrieval by ID."""
        # Create trace
        root_span = mock_tracer.start_span("root")
        child_span = mock_tracer.start_span("child", parent=root_span)
        
        child_span.finish()
        root_span.finish()
        
        # Get trace by ID
        trace_spans = trace_validator.get_trace_by_id(root_span.trace_id)
        assert len(trace_spans) == 2
        assert any(span.name == "root" for span in trace_spans)
        assert any(span.name == "child" for span in trace_spans)
    
    def test_complex_trace_assertion(self, mock_tracer, trace_validator):
        """Test complex trace assertion with multiple criteria."""
        # Create complex trace
        api_span = mock_tracer.start_span("api_request", attributes={
            "http.method": "POST",
            "http.url": "/api/complex",
            "user.id": "12345"
        })
        
        # Add events
        api_span.add_event("request_received", {"timestamp": datetime.now().isoformat()})
        
        # Create child spans
        auth_span = mock_tracer.start_span("authentication", parent=api_span)
        auth_span.finish()
        
        db_span = mock_tracer.start_span("database_query", parent=api_span)
        db_span.finish()
        
        cache_span = mock_tracer.start_span("cache_operation", parent=api_span)
        cache_span.finish()
        
        api_span.finish()
        
        # Create complex assertion
        assertion = TraceAssertion(
            operation_name="api_request",
            expected_spans=["api_request", "authentication", "database_query", "cache_operation"],
            expected_duration_ms=2000.0,
            expected_tags={
                "http.method": "POST",
                "user.id": "12345"
            },
            error_expected=False
        )
        
        # Validate assertion
        result = trace_validator.validate_trace_assertion(assertion)
        assert result is True
    
    def test_trace_clear_functionality(self, mock_tracer):
        """Test trace clearing functionality."""
        # Create some spans
        span1 = mock_tracer.start_span("operation1")
        span2 = mock_tracer.start_span("operation2")
        
        span1.finish()
        span2.finish()
        
        # Verify spans exist
        assert len(mock_tracer.spans) == 2
        
        # Clear spans
        mock_tracer.clear()
        
        # Verify spans are cleared
        assert len(mock_tracer.spans) == 0
        assert len(mock_tracer.active_spans) == 0
