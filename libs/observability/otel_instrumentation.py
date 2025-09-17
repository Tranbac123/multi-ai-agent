"""
OpenTelemetry Instrumentation

Comprehensive OpenTelemetry instrumentation with spans, metrics, and traces
for all platform services with proper attribute naming and correlation.
"""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime, timedelta
from contextvars import ContextVar

from opentelemetry import trace, metrics
from opentelemetry.trace import Status, StatusCode
# from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.sdk.resources import Resource

logger = structlog.get_logger(__name__)

# Context variables for tracing
current_span: ContextVar[Optional[trace.Span]] = ContextVar('current_span', default=None)
current_tenant: ContextVar[Optional[str]] = ContextVar('current_tenant', default=None)
current_run_id: ContextVar[Optional[str]] = ContextVar('current_run_id', default=None)
current_step_id: ContextVar[Optional[str]] = ContextVar('current_step_id', default=None)


class ServiceType(Enum):
    """Service types for instrumentation."""
    API_GATEWAY = "api_gateway"
    ORCHESTRATOR = "orchestrator"
    ROUTER = "router"
    TOOL_SERVICE = "tool_service"
    REALTIME = "realtime"
    INGESTION = "ingestion"
    ANALYTICS = "analytics"
    BILLING = "billing"


@dataclass
class TraceContext:
    """Trace context for request correlation."""
    
    run_id: str
    tenant_id: str
    step_id: Optional[str] = None
    tool_id: Optional[str] = None
    tier: Optional[str] = None
    workflow: Optional[str] = None
    user_id: Optional[str] = None
    request_id: Optional[str] = None


class OTELInstrumentor:
    """OpenTelemetry instrumentation manager."""
    
    def __init__(self, service_name: str, service_type: ServiceType):
        self.service_name = service_name
        self.service_type = service_type
        self.tracer = None
        self.meter = None
        self.resource = None
        
        # Initialize instrumentation
        self._setup_resource()
        self._setup_tracing()
        self._setup_metrics()
        
        logger.info("OTEL instrumentation initialized", 
                   service_name=service_name,
                   service_type=service_type.value)
    
    def _setup_resource(self):
        """Set up OpenTelemetry resource."""
        
        self.resource = Resource.create({
            "service.name": self.service_name,
            "service.type": self.service_type.value,
            "service.version": "1.0.0",
            "deployment.environment": "production",
            "host.name": "ai-agent-platform"
        })
    
    def _setup_tracing(self):
        """Set up OpenTelemetry tracing."""
        
        # Create tracer provider
        trace.set_tracer_provider(TracerProvider(resource=self.resource))
        
        # Add span processor
        span_processor = BatchSpanProcessor(
            OTLPSpanExporter(endpoint="http://jaeger:14250")
        )
        trace.get_tracer_provider().add_span_processor(span_processor)
        
        # Get tracer
        self.tracer = trace.get_tracer(__name__)
    
    def _setup_metrics(self):
        """Set up OpenTelemetry metrics."""
        
        # Create meter provider
        metric_reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint="http://prometheus:9090")
        )
        metrics.set_meter_provider(MeterProvider(resource=self.resource, metric_readers=[metric_reader]))
        
        # Get meter
        self.meter = metrics.get_meter(__name__)
    
    def create_span(
        self, 
        name: str, 
        context: Optional[TraceContext] = None,
        attributes: Optional[Dict[str, Any]] = None
    ) -> trace.Span:
        """Create a new span with proper attributes."""
        
        span = self.tracer.start_span(name)
        
        # Set standard attributes
        if context:
            span.set_attribute("run_id", context.run_id)
            span.set_attribute("tenant_id", context.tenant_id)
            if context.step_id:
                span.set_attribute("step_id", context.step_id)
            if context.tool_id:
                span.set_attribute("tool_id", context.tool_id)
            if context.tier:
                span.set_attribute("tier", context.tier)
            if context.workflow:
                span.set_attribute("workflow", context.workflow)
            if context.user_id:
                span.set_attribute("user_id", context.user_id)
            if context.request_id:
                span.set_attribute("request_id", context.request_id)
        
        # Add service attributes
        span.set_attribute("service.name", self.service_name)
        span.set_attribute("service.type", self.service_type.value)
        
        # Add custom attributes
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        
        return span
    
    def create_metric(
        self, 
        name: str, 
        metric_type: str = "counter",
        description: str = "",
        unit: str = ""
    ):
        """Create a new metric."""
        
        if metric_type == "counter":
            return self.meter.create_counter(
                name=name,
                description=description,
                unit=unit
            )
        elif metric_type == "histogram":
            return self.meter.create_histogram(
                name=name,
                description=description,
                unit=unit
            )
        elif metric_type == "gauge":
            return self.meter.create_up_down_counter(
                name=name,
                description=description,
                unit=unit
            )
        else:
            raise ValueError(f"Unsupported metric type: {metric_type}")


class SpanManager:
    """Manages span lifecycle and context."""
    
    def __init__(self, instrumentor: OTELInstrumentor):
        self.instrumentor = instrumentor
        self.active_spans: Dict[str, trace.Span] = {}
        
    def start_span(
        self, 
        name: str, 
        context: Optional[TraceContext] = None,
        attributes: Optional[Dict[str, Any]] = None,
        parent_span: Optional[trace.Span] = None
    ) -> trace.Span:
        """Start a new span."""
        
        # Create span with proper context
        span = self.instrumentor.create_span(name, context, attributes)
        
        # Set parent if provided
        if parent_span:
            span.set_parent(parent_span.get_span_context())
        
        # Store active span
        span_id = span.get_span_context().span_id
        self.active_spans[str(span_id)] = span
        
        # Set context variables
        current_span.set(span)
        if context:
            current_tenant.set(context.tenant_id)
            current_run_id.set(context.run_id)
            if context.step_id:
                current_step_id.set(context.step_id)
        
        return span
    
    def end_span(self, span: trace.Span, status: StatusCode = StatusCode.OK, message: str = ""):
        """End a span with status."""
        
        span.set_status(Status(status, message))
        span.end()
        
        # Remove from active spans
        span_id = span.get_span_context().span_id
        self.active_spans.pop(str(span_id), None)
    
    def get_current_span(self) -> Optional[trace.Span]:
        """Get current active span."""
        return current_span.get()
    
    def get_current_tenant(self) -> Optional[str]:
        """Get current tenant ID."""
        return current_tenant.get()
    
    def get_current_run_id(self) -> Optional[str]:
        """Get current run ID."""
        return current_run_id.get()


class MetricsCollector:
    """Collects and exposes Prometheus metrics."""
    
    def __init__(self, instrumentor: OTELInstrumentor):
        self.instrumentor = instrumentor
        self.metrics = self._initialize_metrics()
        
        logger.info("Metrics collector initialized")
    
    def _initialize_metrics(self) -> Dict[str, Any]:
        """Initialize all platform metrics."""
        
        metrics = {}
        
        # Agent metrics
        metrics["agent_run_latency_ms"] = self.instrumentor.create_metric(
            "agent_run_latency_ms",
            "histogram",
            "Agent run latency in milliseconds",
            "ms"
        )
        
        metrics["agent_steps_total"] = self.instrumentor.create_metric(
            "agent_steps_total",
            "counter",
            "Total number of agent steps executed"
        )
        
        metrics["agent_loop_cut_total"] = self.instrumentor.create_metric(
            "agent_loop_cut_total",
            "counter",
            "Total number of agent loops cut due to safety mechanisms"
        )
        
        # Router metrics
        metrics["router_decision_latency_ms"] = self.instrumentor.create_metric(
            "router_decision_latency_ms",
            "histogram",
            "Router decision latency in milliseconds",
            "ms"
        )
        
        metrics["router_misroute_rate"] = self.instrumentor.create_metric(
            "router_misroute_rate",
            "counter",
            "Router misroute rate"
        )
        
        metrics["tier_distribution"] = self.instrumentor.create_metric(
            "tier_distribution",
            "counter",
            "Distribution of requests across tiers"
        )
        
        metrics["expected_vs_actual_cost"] = self.instrumentor.create_metric(
            "expected_vs_actual_cost",
            "histogram",
            "Expected vs actual cost difference"
        )
        
        metrics["expected_vs_actual_latency"] = self.instrumentor.create_metric(
            "expected_vs_actual_latency",
            "histogram",
            "Expected vs actual latency difference",
            "ms"
        )
        
        # Tool metrics
        metrics["tool_error_rate"] = self.instrumentor.create_metric(
            "tool_error_rate",
            "counter",
            "Tool error rate"
        )
        
        metrics["retry_total"] = self.instrumentor.create_metric(
            "retry_total",
            "counter",
            "Total number of retries"
        )
        
        metrics["circuit_open_total"] = self.instrumentor.create_metric(
            "circuit_open_total",
            "counter",
            "Total number of circuit breaker openings"
        )
        
        # WebSocket metrics
        metrics["ws_active_connections"] = self.instrumentor.create_metric(
            "ws_active_connections",
            "gauge",
            "Number of active WebSocket connections"
        )
        
        metrics["ws_backpressure_drops"] = self.instrumentor.create_metric(
            "ws_backpressure_drops",
            "counter",
            "Number of messages dropped due to backpressure"
        )
        
        metrics["ws_send_errors"] = self.instrumentor.create_metric(
            "ws_send_errors",
            "counter",
            "Number of WebSocket send errors"
        )
        
        # Cost and token metrics
        metrics["cost_usd_total"] = self.instrumentor.create_metric(
            "cost_usd_total",
            "counter",
            "Total cost in USD"
        )
        
        metrics["tokens_total"] = self.instrumentor.create_metric(
            "tokens_total",
            "counter",
            "Total number of tokens processed"
        )
        
        return metrics
    
    def record_agent_run_latency(self, latency_ms: float, tenant_id: str, run_id: str):
        """Record agent run latency."""
        
        self.metrics["agent_run_latency_ms"].add(
            latency_ms,
            attributes={
                "tenant_id": tenant_id,
                "run_id": run_id
            }
        )
    
    def record_router_decision_latency(self, latency_ms: float, tenant_id: str, tier: str):
        """Record router decision latency."""
        
        self.metrics["router_decision_latency_ms"].add(
            latency_ms,
            attributes={
                "tenant_id": tenant_id,
                "tier": tier
            }
        )
    
    def record_tier_distribution(self, tier: str, tenant_id: str, count: int = 1):
        """Record tier distribution."""
        
        self.metrics["tier_distribution"].add(
            count,
            attributes={
                "tier": tier,
                "tenant_id": tenant_id
            }
        )
    
    def record_expected_vs_actual_cost(self, expected: float, actual: float, tenant_id: str):
        """Record expected vs actual cost."""
        
        difference = abs(expected - actual)
        self.metrics["expected_vs_actual_cost"].add(
            difference,
            attributes={
                "tenant_id": tenant_id,
                "expected": expected,
                "actual": actual
            }
        )
    
    def record_expected_vs_actual_latency(self, expected_ms: float, actual_ms: float, tenant_id: str):
        """Record expected vs actual latency."""
        
        difference = abs(expected_ms - actual_ms)
        self.metrics["expected_vs_actual_latency"].add(
            difference,
            attributes={
                "tenant_id": tenant_id,
                "expected": expected_ms,
                "actual": actual_ms
            }
        )
    
    def record_ws_connections(self, count: int, tenant_id: str):
        """Record WebSocket connections."""
        
        self.metrics["ws_active_connections"].add(
            count,
            attributes={
                "tenant_id": tenant_id
            }
        )
    
    def record_ws_backpressure_drops(self, count: int, tenant_id: str):
        """Record WebSocket backpressure drops."""
        
        self.metrics["ws_backpressure_drops"].add(
            count,
            attributes={
                "tenant_id": tenant_id
            }
        )
    
    def record_cost(self, cost_usd: float, tenant_id: str, service: str):
        """Record cost."""
        
        self.metrics["cost_usd_total"].add(
            cost_usd,
            attributes={
                "tenant_id": tenant_id,
                "service": service
            }
        )
    
    def record_tokens(self, token_count: int, tenant_id: str, service: str):
        """Record token usage."""
        
        self.metrics["tokens_total"].add(
            token_count,
            attributes={
                "tenant_id": tenant_id,
                "service": service
            }
        )


class InstrumentationMiddleware:
    """Middleware for automatic instrumentation."""
    
    def __init__(self, instrumentor: OTELInstrumentor):
        self.instrumentor = instrumentor
        self.span_manager = SpanManager(instrumentor)
        self.metrics_collector = MetricsCollector(instrumentor)
        
        logger.info("Instrumentation middleware initialized")
    
    def instrument_fastapi_app(self, app):
        """Instrument FastAPI application."""
        
        FastAPIInstrumentor.instrument_app(app)
        
        @app.middleware("http")
        async def otel_middleware(request, call_next):
            """OpenTelemetry middleware for FastAPI."""
            
            start_time = time.time()
            
            # Extract trace context from headers
            context = self._extract_trace_context(request)
            
            # Start span
            span = self.span_manager.start_span(
                name=f"{request.method} {request.url.path}",
                context=context,
                attributes={
                    "http.method": request.method,
                    "http.url": str(request.url),
                    "http.route": request.url.path,
                    "http.user_agent": request.headers.get("user-agent", ""),
                    "http.request_id": request.headers.get("x-request-id", ""),
                }
            )
            
            try:
                # Process request
                response = await call_next(request)
                
                # Record response attributes
                span.set_attribute("http.status_code", response.status_code)
                span.set_attribute("http.response_size", response.headers.get("content-length", 0))
                
                # Record latency
                latency_ms = (time.time() - start_time) * 1000
                self.metrics_collector.record_agent_run_latency(
                    latency_ms, 
                    context.tenant_id if context else "unknown",
                    context.run_id if context else "unknown"
                )
                
                return response
                
            except Exception as e:
                # Record error
                span.set_attribute("error", True)
                span.set_attribute("error.message", str(e))
                self.span_manager.end_span(span, StatusCode.ERROR, str(e))
                raise
            
            finally:
                self.span_manager.end_span(span)
        
        return app
    
    def _extract_trace_context(self, request) -> Optional[TraceContext]:
        """Extract trace context from request headers."""
        
        # Extract from headers
        run_id = request.headers.get("x-run-id")
        tenant_id = request.headers.get("x-tenant-id")
        step_id = request.headers.get("x-step-id")
        tool_id = request.headers.get("x-tool-id")
        tier = request.headers.get("x-tier")
        workflow = request.headers.get("x-workflow")
        user_id = request.headers.get("x-user-id")
        request_id = request.headers.get("x-request-id")
        
        if not run_id or not tenant_id:
            return None
        
        return TraceContext(
            run_id=run_id,
            tenant_id=tenant_id,
            step_id=step_id,
            tool_id=tool_id,
            tier=tier,
            workflow=workflow,
            user_id=user_id,
            request_id=request_id
        )
    
    def instrument_database(self, engine):
        """Instrument SQLAlchemy database engine."""
        
        SQLAlchemyInstrumentor().instrument(engine=engine)
    
    def instrument_redis(self, redis_client):
        """Instrument Redis client."""
        
        RedisInstrumentor().instrument(redis_client)
    
    def instrument_httpx(self):
        """Instrument HTTPX client."""
        
        HTTPXClientInstrumentor().instrument()


def create_instrumentation(service_name: str, service_type: ServiceType) -> InstrumentationMiddleware:
    """Create instrumentation middleware for a service."""
    
    instrumentor = OTELInstrumentor(service_name, service_type)
    return InstrumentationMiddleware(instrumentor)


# Decorators for easy instrumentation
def trace_function(name: Optional[str] = None, attributes: Optional[Dict[str, Any]] = None):
    """Decorator to trace function execution."""
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            # Get current span manager (would be injected in real implementation)
            span_manager = None  # This would come from dependency injection
            
            if span_manager:
                span_name = name or f"{func.__module__}.{func.__name__}"
                span = span_manager.start_span(span_name, attributes=attributes)
                
                try:
                    if asyncio.iscoroutinefunction(func):
                        result = await func(*args, **kwargs)
                    else:
                        result = func(*args, **kwargs)
                    
                    span_manager.end_span(span)
                    return result
                    
                except Exception as e:
                    span_manager.end_span(span, StatusCode.ERROR, str(e))
                    raise
            
            # Fallback if no span manager
            if asyncio.iscoroutinefunction(func):
                return await func(*args, **kwargs)
            else:
                return func(*args, **kwargs)
        
        def sync_wrapper(*args, **kwargs):
            # Similar logic for sync functions
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator


def record_metric(metric_name: str, value: float, attributes: Optional[Dict[str, str]] = None):
    """Decorator to record metrics."""
    
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                # Record success metric
                # In real implementation, this would use the metrics collector
                return result
                
            except Exception as e:
                # Record error metric
                raise
            
            finally:
                # Record timing metric
                duration = time.time() - start_time
                # Record duration metric here
        
        def sync_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator
