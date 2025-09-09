"""Prometheus metrics for multi-tenant AIaaS platform."""

import time
from typing import Dict, Any, Optional
from uuid import UUID
import structlog
from prometheus_client import (
    Counter, Histogram, Gauge, Summary, 
    CollectorRegistry, generate_latest, CONTENT_TYPE_LATEST
)
from prometheus_client.core import GaugeMetricFamily, CounterMetricFamily, HistogramMetricFamily

logger = structlog.get_logger(__name__)


class AIaaSMetrics:
    """Comprehensive metrics for AIaaS platform."""
    
    def __init__(self):
        self.registry = CollectorRegistry()
        self._init_metrics()
    
    def _init_metrics(self):
        """Initialize all metrics."""
        
        # Agent run metrics
        self.agent_run_total = Counter(
            'agent_run_total',
            'Total number of agent runs',
            ['tenant_id', 'workflow', 'status'],
            registry=self.registry
        )
        
        self.agent_run_duration = Histogram(
            'agent_run_duration_seconds',
            'Duration of agent runs',
            ['tenant_id', 'workflow'],
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0],
            registry=self.registry
        )
        
        self.agent_run_tokens = Counter(
            'agent_run_tokens_total',
            'Total tokens processed',
            ['tenant_id', 'workflow', 'type'],
            registry=self.registry
        )
        
        self.agent_run_cost = Counter(
            'agent_run_cost_usd_total',
            'Total cost in USD',
            ['tenant_id', 'workflow'],
            registry=self.registry
        )
        
        # Router metrics
        self.router_decisions = Counter(
            'router_decisions_total',
            'Total router decisions',
            ['tenant_id', 'tier', 'confidence_level'],
            registry=self.registry
        )
        
        self.router_decision_duration = Histogram(
            'router_decision_duration_seconds',
            'Duration of router decisions',
            ['tenant_id'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0],
            registry=self.registry
        )
        
        self.router_misroute_rate = Gauge(
            'router_misroute_rate',
            'Router misroute rate',
            ['tenant_id'],
            registry=self.registry
        )
        
        # Tool metrics
        self.tool_calls = Counter(
            'tool_calls_total',
            'Total tool calls',
            ['tenant_id', 'tool_name', 'status'],
            registry=self.registry
        )
        
        self.tool_call_duration = Histogram(
            'tool_call_duration_seconds',
            'Duration of tool calls',
            ['tenant_id', 'tool_name'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        self.tool_error_rate = Gauge(
            'tool_error_rate',
            'Tool error rate',
            ['tenant_id', 'tool_name'],
            registry=self.registry
        )
        
        # Circuit breaker metrics
        self.circuit_breaker_state = Gauge(
            'circuit_breaker_state',
            'Circuit breaker state (0=closed, 1=open, 2=half_open)',
            ['tenant_id', 'service'],
            registry=self.registry
        )
        
        self.circuit_breaker_failures = Counter(
            'circuit_breaker_failures_total',
            'Circuit breaker failures',
            ['tenant_id', 'service'],
            registry=self.registry
        )
        
        # WebSocket metrics
        self.websocket_connections = Gauge(
            'websocket_connections_active',
            'Active WebSocket connections',
            ['tenant_id'],
            registry=self.registry
        )
        
        self.websocket_messages = Counter(
            'websocket_messages_total',
            'Total WebSocket messages',
            ['tenant_id', 'message_type'],
            registry=self.registry
        )
        
        self.websocket_backpressure_drops = Counter(
            'websocket_backpressure_drops_total',
            'WebSocket backpressure drops',
            ['tenant_id'],
            registry=self.registry
        )
        
        # Usage metrics
        self.usage_tokens = Counter(
            'usage_tokens_total',
            'Total tokens used',
            ['tenant_id', 'type'],
            registry=self.registry
        )
        
        self.usage_cost = Counter(
            'usage_cost_usd_total',
            'Total cost in USD',
            ['tenant_id'],
            registry=self.registry
        )
        
        self.usage_quota_remaining = Gauge(
            'usage_quota_remaining',
            'Remaining quota',
            ['tenant_id', 'quota_type'],
            registry=self.registry
        )
        
        # System metrics
        self.request_duration = Histogram(
            'request_duration_seconds',
            'Request duration',
            ['service', 'endpoint', 'method', 'status_code'],
            buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0],
            registry=self.registry
        )
        
        self.request_total = Counter(
            'request_total',
            'Total requests',
            ['service', 'endpoint', 'method', 'status_code'],
            registry=self.registry
        )
        
        self.active_connections = Gauge(
            'active_connections',
            'Active connections',
            ['service'],
            registry=self.registry
        )
        
        # Error metrics
        self.errors_total = Counter(
            'errors_total',
            'Total errors',
            ['service', 'error_type', 'severity'],
            registry=self.registry
        )
        
        # Feature flag metrics
        self.feature_flag_evaluations = Counter(
            'feature_flag_evaluations_total',
            'Feature flag evaluations',
            ['tenant_id', 'flag_name', 'result'],
            registry=self.registry
        )
        
        # Database metrics
        self.database_connections = Gauge(
            'database_connections_active',
            'Active database connections',
            ['tenant_id'],
            registry=self.registry
        )
        
        self.database_query_duration = Histogram(
            'database_query_duration_seconds',
            'Database query duration',
            ['tenant_id', 'query_type'],
            buckets=[0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5],
            registry=self.registry
        )
    
    def record_agent_run(
        self, 
        tenant_id: UUID, 
        workflow: str, 
        status: str, 
        duration: float,
        tokens_in: int = 0,
        tokens_out: int = 0,
        cost: float = 0.0
    ):
        """Record agent run metrics."""
        self.agent_run_total.labels(
            tenant_id=str(tenant_id),
            workflow=workflow,
            status=status
        ).inc()
        
        self.agent_run_duration.labels(
            tenant_id=str(tenant_id),
            workflow=workflow
        ).observe(duration)
        
        if tokens_in > 0:
            self.agent_run_tokens.labels(
                tenant_id=str(tenant_id),
                workflow=workflow,
                type='in'
            ).inc(tokens_in)
        
        if tokens_out > 0:
            self.agent_run_tokens.labels(
                tenant_id=str(tenant_id),
                workflow=workflow,
                type='out'
            ).inc(tokens_out)
        
        if cost > 0:
            self.agent_run_cost.labels(
                tenant_id=str(tenant_id),
                workflow=workflow
            ).inc(cost)
    
    def record_router_decision(
        self,
        tenant_id: UUID,
        tier: str,
        confidence: float,
        duration: float
    ):
        """Record router decision metrics."""
        confidence_level = "high" if confidence > 0.8 else "medium" if confidence > 0.5 else "low"
        
        self.router_decisions.labels(
            tenant_id=str(tenant_id),
            tier=tier,
            confidence_level=confidence_level
        ).inc()
        
        self.router_decision_duration.labels(
            tenant_id=str(tenant_id)
        ).observe(duration)
    
    def record_tool_call(
        self,
        tenant_id: UUID,
        tool_name: str,
        status: str,
        duration: float
    ):
        """Record tool call metrics."""
        self.tool_calls.labels(
            tenant_id=str(tenant_id),
            tool_name=tool_name,
            status=status
        ).inc()
        
        self.tool_call_duration.labels(
            tenant_id=str(tenant_id),
            tool_name=tool_name
        ).observe(duration)
    
    def record_circuit_breaker_state(
        self,
        tenant_id: UUID,
        service: str,
        state: str
    ):
        """Record circuit breaker state."""
        state_value = {"closed": 0, "open": 1, "half_open": 2}.get(state, 0)
        
        self.circuit_breaker_state.labels(
            tenant_id=str(tenant_id),
            service=service
        ).set(state_value)
    
    def record_websocket_connection(
        self,
        tenant_id: UUID,
        active_count: int
    ):
        """Record WebSocket connection count."""
        self.websocket_connections.labels(
            tenant_id=str(tenant_id)
        ).set(active_count)
    
    def record_websocket_message(
        self,
        tenant_id: UUID,
        message_type: str
    ):
        """Record WebSocket message."""
        self.websocket_messages.labels(
            tenant_id=str(tenant_id),
            message_type=message_type
        ).inc()
    
    def record_usage(
        self,
        tenant_id: UUID,
        tokens: int,
        token_type: str,
        cost: float
    ):
        """Record usage metrics."""
        self.usage_tokens.labels(
            tenant_id=str(tenant_id),
            type=token_type
        ).inc(tokens)
        
        self.usage_cost.labels(
            tenant_id=str(tenant_id)
        ).inc(cost)
    
    def record_request(
        self,
        service: str,
        endpoint: str,
        method: str,
        status_code: int,
        duration: float
    ):
        """Record request metrics."""
        self.request_total.labels(
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=str(status_code)
        ).inc()
        
        self.request_duration.labels(
            service=service,
            endpoint=endpoint,
            method=method,
            status_code=str(status_code)
        ).observe(duration)
    
    def record_error(
        self,
        service: str,
        error_type: str,
        severity: str
    ):
        """Record error metrics."""
        self.errors_total.labels(
            service=service,
            error_type=error_type,
            severity=severity
        ).inc()
    
    def record_feature_flag(
        self,
        tenant_id: UUID,
        flag_name: str,
        result: bool
    ):
        """Record feature flag evaluation."""
        self.feature_flag_evaluations.labels(
            tenant_id=str(tenant_id),
            flag_name=flag_name,
            result=str(result)
        ).inc()
    
    def get_metrics(self) -> str:
        """Get metrics in Prometheus format."""
        return generate_latest(self.registry)
    
    def get_metrics_dict(self) -> Dict[str, Any]:
        """Get metrics as dictionary."""
        metrics = {}
        
        # Collect all metrics
        for metric in self.registry.collect():
            if hasattr(metric, 'samples'):
                for sample in metric.samples:
                    key = f"{sample.name}"
                    if sample.labels:
                        key += f"{{{','.join(f'{k}={v}' for k, v in sample.labels.items())}}}"
                    
                    metrics[key] = sample.value
        
        return metrics


# Global metrics instance
metrics = AIaaSMetrics()
