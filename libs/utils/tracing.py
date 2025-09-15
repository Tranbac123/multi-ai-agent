"""OpenTelemetry tracing utilities."""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.instrumentation.redis import RedisInstrumentor
import structlog

logger = structlog.get_logger(__name__)


def setup_tracing(
    service_name: str = "aiaas-platform",
    endpoint: str = "http://jaeger:14268/api/traces",
):
    """Setup OpenTelemetry tracing."""
    try:
        # Create resource
        resource = Resource.create(
            {"service.name": service_name, "service.version": "2.0.0"}
        )

        # Create tracer provider
        tracer_provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(tracer_provider)

        # Create OTLP exporter
        otlp_exporter = OTLPSpanExporter(endpoint=endpoint)

        # Create span processor
        span_processor = BatchSpanProcessor(otlp_exporter)
        tracer_provider.add_span_processor(span_processor)

        # Instrument libraries
        FastAPIInstrumentor().instrument()
        SQLAlchemyInstrumentor().instrument()
        HTTPXClientInstrumentor().instrument()
        RedisInstrumentor().instrument()

        logger.info(
            "Tracing setup completed", service_name=service_name, endpoint=endpoint
        )

    except Exception as e:
        logger.error("Failed to setup tracing", error=str(e))


def get_tracer(name: str) -> trace.Tracer:
    """Get tracer instance."""
    return trace.get_tracer(name)
