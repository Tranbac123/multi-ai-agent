"""Standardized OpenTelemetry configuration for all services."""

from typing import Optional
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import ConsoleSpanExporter, SimpleSpanProcessor
from opentelemetry.semconv.resource import ResourceAttributes

from .logging_config import get_logger

logger = get_logger(__name__)


def configure_otel_tracing(service_name: str, enable_console_exporter: bool = False) -> None:
    """Configure OpenTelemetry tracing for a service."""
    
    # Create resource
    resource = Resource.create({ResourceAttributes.SERVICE_NAME: service_name})
    
    # Create tracer provider
    provider = TracerProvider(resource=resource)
    
    # Add console exporter if enabled (useful for development)
    if enable_console_exporter:
        processor = SimpleSpanProcessor(ConsoleSpanExporter())
        provider.add_span_processor(processor)
    
    # Set the tracer provider
    trace.set_tracer_provider(provider)
    
    logger.info(f"OpenTelemetry tracing configured for {service_name}")


def get_tracer(name: str) -> trace.Tracer:
    """Get a tracer instance for the given name."""
    return trace.get_tracer(name)


def create_span(name: str, attributes: Optional[dict] = None):
    """Create a span with the given name and attributes."""
    tracer = get_tracer(__name__)
    span = tracer.start_span(name)
    
    if attributes:
        for key, value in attributes.items():
            span.set_attribute(key, value)
    
    return span

