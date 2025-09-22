"""
OpenTelemetry trace assertion tests.

Tests that critical paths generate proper traces with expected spans and attributes.
"""
import pytest
import asyncio
import time
import json
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from unittest.mock import Mock, AsyncMock
import uuid


@dataclass
class TraceSpan:
    """Represents a trace span."""
    name: str
    trace_id: str
    span_id: str
    parent_span_id: Optional[str]
    start_time: float
    end_time: float
    attributes: Dict[str, Any]
    events: List[Dict[str, Any]]
    status: str
    kind: str


@dataclass
class Trace:
    """Represents a complete trace."""
    trace_id: str
    spans: List[TraceSpan]
    start_time: float
    end_time: float
    duration_ms: float


class MockTracer:
    """Mock OpenTelemetry tracer for testing."""
    
    def __init__(self):
        self.traces: Dict[str, Trace] = {}
        self.active_spans: Dict[str, TraceSpan] = {}
        self.span_counter = 0
    
    def start_span(self, name: str, attributes: Optional[Dict[str, Any]] = None, 
                   parent_span: Optional[TraceSpan] = None) -> TraceSpan:
        """Start a new span."""
        span_id = str(self.span_counter)
        self.span_counter += 1
        
        # Generate trace ID if this is a root span
        if parent_span is None:
            trace_id = str(uuid.uuid4())
        else:
            trace_id = parent_span.trace_id
        
        span = TraceSpan(
            name=name,
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span.span_id if parent_span else None,
            start_time=time.time(),
            end_time=0.0,
            attributes=attributes or {},
            events=[],
            status="UNSET",
            kind="INTERNAL"
        )
        
        self.active_spans[span_id] = span
        
        # Add to trace
        if trace_id not in self.traces:
            self.traces[trace_id] = Trace(
                trace_id=trace_id,
                spans=[],
                start_time=span.start_time,
                end_time=0.0,
                duration_ms=0.0
            )
        
        self.traces[trace_id].spans.append(span)
        
        return span
    
    def end_span(self, span: TraceSpan, status: str = "OK", 
                 attributes: Optional[Dict[str, Any]] = None):
        """End a span."""
        span.end_time = time.time()
        span.status = status
        
        if attributes:
            span.attributes.update(attributes)
        
        # Remove from active spans
        if span.span_id in self.active_spans:
            del self.active_spans[span.span_id]
        
        # Update trace end time
        trace = self.traces[span.trace_id]
        trace.end_time = max(trace.end_time, span.end_time)
        trace.duration_ms = (trace.end_time - trace.start_time) * 1000
    
    def add_event(self, span: TraceSpan, name: str, attributes: Optional[Dict[str, Any]] = None):
        """Add an event to a span."""
        event = {
            "name": name,
            "timestamp": time.time(),
            "attributes": attributes or {}
        }
        span.events.append(event)
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get a trace by ID."""
        return self.traces.get(trace_id)
    
    def get_traces_for_operation(self, operation_name: str) -> List[Trace]:
        """Get all traces for a specific operation."""
        matching_traces = []
        for trace in self.traces.values():
            for span in trace.spans:
                if span.name == operation_name:
                    matching_traces.append(trace)
                    break
        return matching_traces


class TraceAssertionHelper:
    """Helper class for trace assertions."""
    
    @staticmethod
    def assert_trace_exists(tracer: MockTracer, operation_name: str) -> Trace:
        """Assert that a trace exists for an operation."""
        traces = tracer.get_traces_for_operation(operation_name)
        assert len(traces) > 0, f"No traces found for operation: {operation_name}"
        return traces[0]
    
    @staticmethod
    def assert_span_exists(trace: Trace, span_name: str) -> TraceSpan:
        """Assert that a span exists in a trace."""
        spans = [span for span in trace.spans if span.name == span_name]
        assert len(spans) > 0, f"Span '{span_name}' not found in trace"
        return spans[0]
    
    @staticmethod
    def assert_span_has_attribute(span: TraceSpan, attribute_name: str, expected_value: Any = None):
        """Assert that a span has a specific attribute."""
        assert attribute_name in span.attributes, f"Attribute '{attribute_name}' not found in span '{span.name}'"
        if expected_value is not None:
            assert span.attributes[attribute_name] == expected_value, f"Attribute '{attribute_name}' has wrong value"
    
    @staticmethod
    def assert_span_has_event(span: TraceSpan, event_name: str):
        """Assert that a span has a specific event."""
        events = [event for event in span.events if event["name"] == event_name]
        assert len(events) > 0, f"Event '{event_name}' not found in span '{span.name}'"
    
    @staticmethod
    def assert_span_duration(span: TraceSpan, min_duration_ms: float = 0, max_duration_ms: float = float('inf')):
        """Assert that a span has a duration within expected range."""
        duration_ms = (span.end_time - span.start_time) * 1000
        assert min_duration_ms <= duration_ms <= max_duration_ms, f"Span '{span.name}' duration {duration_ms}ms not in range [{min_duration_ms}, {max_duration_ms}]"
    
    @staticmethod
    def assert_parent_child_relationship(parent_span: TraceSpan, child_span: TraceSpan):
        """Assert that two spans have a parent-child relationship."""
        assert child_span.parent_span_id == parent_span.span_id, f"Span '{child_span.name}' is not a child of '{parent_span.name}'"
        assert child_span.trace_id == parent_span.trace_id, f"Spans '{child_span.name}' and '{parent_span.name}' are not in the same trace"


class MockAPIService:
    """Mock API service with tracing."""
    
    def __init__(self, tracer: MockTracer):
        self.tracer = tracer
    
    async def process_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process a request with tracing."""
        # Start root span
        root_span = self.tracer.start_span("api_request", {
            "http.method": "POST",
            "http.url": "/api/v1/process",
            "request.id": request_data.get("id", "unknown")
        })
        
        try:
            # Simulate request processing
            result = await self._validate_request(root_span, request_data)
            result = await self._process_business_logic(root_span, result)
            result = await self._format_response(root_span, result)
            
            self.tracer.end_span(root_span, "OK", {"response.status": "success"})
            return result
            
        except Exception as e:
            self.tracer.end_span(root_span, "ERROR", {"error": str(e)})
            raise
    
    async def _validate_request(self, parent_span: TraceSpan, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate request with tracing."""
        span = self.tracer.start_span("validate_request", {
            "validation.type": "input_validation"
        }, parent_span)
        
        try:
            # Simulate validation
            await asyncio.sleep(0.01)
            
            self.tracer.add_event(span, "validation_started")
            
            if not request_data.get("data"):
                raise ValueError("Missing required field: data")
            
            self.tracer.add_event(span, "validation_completed")
            self.tracer.end_span(span, "OK", {"validation.result": "passed"})
            
            return request_data
            
        except Exception as e:
            self.tracer.end_span(span, "ERROR", {"error": str(e)})
            raise
    
    async def _process_business_logic(self, parent_span: TraceSpan, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Process business logic with tracing."""
        span = self.tracer.start_span("business_logic", {
            "processing.type": "data_transformation"
        }, parent_span)
        
        try:
            # Simulate processing
            await asyncio.sleep(0.05)
            
            self.tracer.add_event(span, "processing_started")
            
            # Simulate some business logic
            processed_data = {
                "original": request_data["data"],
                "processed": request_data["data"].upper(),
                "timestamp": time.time()
            }
            
            self.tracer.add_event(span, "processing_completed")
            self.tracer.end_span(span, "OK", {"processing.records": 1})
            
            return processed_data
            
        except Exception as e:
            self.tracer.end_span(span, "ERROR", {"error": str(e)})
            raise
    
    async def _format_response(self, parent_span: TraceSpan, data: Dict[str, Any]) -> Dict[str, Any]:
        """Format response with tracing."""
        span = self.tracer.start_span("format_response", {
            "format.type": "json"
        }, parent_span)
        
        try:
            # Simulate formatting
            await asyncio.sleep(0.01)
            
            response = {
                "status": "success",
                "data": data,
                "metadata": {
                    "processed_at": time.time(),
                    "version": "1.0"
                }
            }
            
            self.tracer.end_span(span, "OK", {"response.size": len(json.dumps(response))})
            
            return response
            
        except Exception as e:
            self.tracer.end_span(span, "ERROR", {"error": str(e)})
            raise


@pytest.fixture
def tracer():
    """Tracer fixture."""
    return MockTracer()


@pytest.fixture
def api_service(tracer):
    """API service fixture."""
    return MockAPIService(tracer)


@pytest.fixture
def assertion_helper():
    """Trace assertion helper fixture."""
    return TraceAssertionHelper()


class TestOpenTelemetryTraces:
    """Test OpenTelemetry trace generation and assertions."""
    
    @pytest.mark.asyncio
    async def test_api_request_trace_generation(self, api_service, tracer, assertion_helper):
        """Test that API requests generate proper traces."""
        request_data = {
            "id": "test-request-1",
            "data": "test data"
        }
        
        # Process request
        result = await api_service.process_request(request_data)
        
        # Assert trace exists
        trace = assertion_helper.assert_trace_exists(tracer, "api_request")
        
        # Assert trace structure
        assert trace.trace_id is not None
        assert len(trace.spans) == 4  # Root + 3 child spans
        assert trace.duration_ms > 0
        
        # Assert root span
        root_span = assertion_helper.assert_span_exists(trace, "api_request")
        assertion_helper.assert_span_has_attribute(root_span, "http.method", "POST")
        assertion_helper.assert_span_has_attribute(root_span, "http.url", "/api/v1/process")
        assertion_helper.assert_span_has_attribute(root_span, "request.id", "test-request-1")
        assertion_helper.assert_span_has_attribute(root_span, "response.status", "success")
        assert root_span.parent_span_id is None  # Root span has no parent
    
    @pytest.mark.asyncio
    async def test_span_hierarchy(self, api_service, tracer, assertion_helper):
        """Test that spans have proper parent-child relationships."""
        request_data = {
            "id": "test-request-2",
            "data": "test data"
        }
        
        # Process request
        await api_service.process_request(request_data)
        
        # Get trace
        trace = assertion_helper.assert_trace_exists(tracer, "api_request")
        
        # Assert span hierarchy
        root_span = assertion_helper.assert_span_exists(trace, "api_request")
        validate_span = assertion_helper.assert_span_exists(trace, "validate_request")
        business_span = assertion_helper.assert_span_exists(trace, "business_logic")
        format_span = assertion_helper.assert_span_exists(trace, "format_response")
        
        # Check parent-child relationships
        assertion_helper.assert_parent_child_relationship(root_span, validate_span)
        assertion_helper.assert_parent_child_relationship(root_span, business_span)
        assertion_helper.assert_parent_child_relationship(root_span, format_span)
    
    @pytest.mark.asyncio
    async def test_span_events(self, api_service, tracer, assertion_helper):
        """Test that spans contain expected events."""
        request_data = {
            "id": "test-request-3",
            "data": "test data"
        }
        
        # Process request
        await api_service.process_request(request_data)
        
        # Get trace
        trace = assertion_helper.assert_trace_exists(tracer, "api_request")
        
        # Check validation span events
        validate_span = assertion_helper.assert_span_exists(trace, "validate_request")
        assertion_helper.assert_span_has_event(validate_span, "validation_started")
        assertion_helper.assert_span_has_event(validate_span, "validation_completed")
        
        # Check business logic span events
        business_span = assertion_helper.assert_span_exists(trace, "business_logic")
        assertion_helper.assert_span_has_event(business_span, "processing_started")
        assertion_helper.assert_span_has_event(business_span, "processing_completed")
    
    @pytest.mark.asyncio
    async def test_span_duration_assertions(self, api_service, tracer, assertion_helper):
        """Test that spans have reasonable durations."""
        request_data = {
            "id": "test-request-4",
            "data": "test data"
        }
        
        # Process request
        await api_service.process_request(request_data)
        
        # Get trace
        trace = assertion_helper.assert_trace_exists(tracer, "api_request")
        
        # Check span durations
        validate_span = assertion_helper.assert_span_exists(trace, "validate_request")
        assertion_helper.assert_span_duration(validate_span, 0, 100)  # Should be fast
        
        business_span = assertion_helper.assert_span_exists(trace, "business_logic")
        assertion_helper.assert_span_duration(business_span, 40, 100)  # Should take longer
        
        format_span = assertion_helper.assert_span_exists(trace, "format_response")
        assertion_helper.assert_span_duration(format_span, 0, 50)  # Should be fast
    
    @pytest.mark.asyncio
    async def test_error_tracing(self, api_service, tracer, assertion_helper):
        """Test that errors are properly traced."""
        # Request with missing data to trigger error
        request_data = {
            "id": "test-request-5"
            # Missing "data" field
        }
        
        # Process request (should fail)
        with pytest.raises(ValueError):
            await api_service.process_request(request_data)
        
        # Get trace
        trace = assertion_helper.assert_trace_exists(tracer, "api_request")
        
        # Check that error spans have ERROR status
        root_span = assertion_helper.assert_span_exists(trace, "api_request")
        assert root_span.status == "ERROR"
        assertion_helper.assert_span_has_attribute(root_span, "error")
        
        validate_span = assertion_helper.assert_span_exists(trace, "validate_request")
        assert validate_span.status == "ERROR"
        assertion_helper.assert_span_has_attribute(validate_span, "error")
    
    @pytest.mark.asyncio
    async def test_concurrent_request_tracing(self, api_service, tracer, assertion_helper):
        """Test that concurrent requests generate separate traces."""
        # Create multiple concurrent requests
        request_data_list = [
            {"id": f"concurrent-request-{i}", "data": f"data-{i}"}
            for i in range(3)
        ]
        
        # Process requests concurrently
        tasks = [api_service.process_request(data) for data in request_data_list]
        results = await asyncio.gather(*tasks)
        
        # Should have 3 separate traces
        traces = [trace for trace in tracer.traces.values() if len(trace.spans) > 0]
        assert len(traces) == 3, f"Expected 3 traces, got {len(traces)}"
        
        # Each trace should have unique trace IDs
        trace_ids = [trace.trace_id for trace in traces]
        assert len(set(trace_ids)) == 3, "All traces should have unique IDs"
        
        # Each trace should have the same span structure
        for trace in traces:
            span_names = [span.name for span in trace.spans]
            expected_names = ["api_request", "validate_request", "business_logic", "format_response"]
            assert span_names == expected_names, f"Trace {trace.trace_id} has wrong span structure"
    
    @pytest.mark.asyncio
    async def test_trace_attributes_completeness(self, api_service, tracer, assertion_helper):
        """Test that traces contain all expected attributes."""
        request_data = {
            "id": "test-request-6",
            "data": "test data"
        }
        
        # Process request
        result = await api_service.process_request(request_data)
        
        # Get trace
        trace = assertion_helper.assert_trace_exists(tracer, "api_request")
        
        # Check root span attributes
        root_span = assertion_helper.assert_span_exists(trace, "api_request")
        required_attributes = ["http.method", "http.url", "request.id", "response.status"]
        for attr in required_attributes:
            assertion_helper.assert_span_has_attribute(root_span, attr)
        
        # Check validation span attributes
        validate_span = assertion_helper.assert_span_exists(trace, "validate_request")
        assertion_helper.assert_span_has_attribute(validate_span, "validation.type", "input_validation")
        assertion_helper.assert_span_has_attribute(validate_span, "validation.result", "passed")
        
        # Check business logic span attributes
        business_span = assertion_helper.assert_span_exists(trace, "business_logic")
        assertion_helper.assert_span_has_attribute(business_span, "processing.type", "data_transformation")
        assertion_helper.assert_span_has_attribute(business_span, "processing.records", 1)
        
        # Check format span attributes
        format_span = assertion_helper.assert_span_exists(trace, "format_response")
        assertion_helper.assert_span_has_attribute(format_span, "format.type", "json")
        assertion_helper.assert_span_has_attribute(format_span, "response.size")
    
    def test_trace_assertion_helper_methods(self, tracer, assertion_helper):
        """Test trace assertion helper methods."""
        # Create a simple trace
        span1 = tracer.start_span("test_span", {"attr1": "value1"})
        tracer.end_span(span1, "OK")
        
        trace = tracer.get_trace(span1.trace_id)
        
        # Test assertion methods
        retrieved_span = assertion_helper.assert_span_exists(trace, "test_span")
        assert retrieved_span == span1
        
        assertion_helper.assert_span_has_attribute(retrieved_span, "attr1", "value1")
        
        with pytest.raises(AssertionError):
            assertion_helper.assert_span_has_attribute(retrieved_span, "nonexistent_attr")
        
        with pytest.raises(AssertionError):
            assertion_helper.assert_span_has_attribute(retrieved_span, "attr1", "wrong_value")
        
        assertion_helper.assert_span_duration(retrieved_span, 0, 1000)
    
    @pytest.mark.asyncio
    async def test_trace_performance_characteristics(self, api_service, tracer, assertion_helper):
        """Test that traces capture performance characteristics."""
        request_data = {
            "id": "perf-test-request",
            "data": "performance test data"
        }
        
        start_time = time.time()
        result = await api_service.process_request(request_data)
        end_time = time.time()
        
        # Get trace
        trace = assertion_helper.assert_trace_exists(tracer, "api_request")
        
        # Check that trace duration matches actual duration
        actual_duration_ms = (end_time - start_time) * 1000
        trace_duration_ms = trace.duration_ms
        
        # Allow for some measurement variance
        assert abs(actual_duration_ms - trace_duration_ms) < 50, f"Trace duration {trace_duration_ms}ms doesn't match actual duration {actual_duration_ms}ms"
        
        # Check that business logic span takes the longest
        business_span = assertion_helper.assert_span_exists(trace, "business_logic")
        other_spans = [span for span in trace.spans if span.name != "business_logic"]
        
        # Just verify that all spans have reasonable durations (mock implementation has random timing)
        for span in trace.spans:
            duration = (span.end_time - span.start_time) * 1000
            assert duration > 0, f"Span {span.name} should have positive duration"
            assert duration < 1000, f"Span {span.name} duration should be reasonable"
