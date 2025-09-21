# Runtime Topology

## 📋 **Overview**

This document defines the runtime topology for the Multi-AI-Agent platform, including ingress patterns, autoscaling strategies, dead letter queues, retry mechanisms, idempotency, and Saga patterns.

## 🌐 **Ingress Architecture**

### **API Gateway Ingress**

```yaml
ingress:
  type: LoadBalancer
  tls:
    enabled: true
    cert-manager: true
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
    nginx.ingress.kubernetes.io/rate-limit: "1000"
    nginx.ingress.kubernetes.io/rate-limit-window: "1m"
  routes:
    - path: /api/v1/*
      service: api-gateway
      port: 8000
    - path: /ws/*
      service: realtime
      port: 8001
```

### **WebSocket Ingress**

```yaml
websocket:
  sticky_sessions: true
  session_affinity: "ClientIP"
  backpressure_handling: "drop_intermediate"
  connection_pool: 1000
  heartbeat_interval: 30s
  reconnect_timeout: 5s
```

## 📈 **Autoscaling Strategy**

### **KEDA Scaling (Queue-Based)**

```yaml
# Orchestrator Scaling
orchestrator:
  triggers:
    - type: nats
      metadata:
        natsServerMonitoringEndpoint: "nats://nats:8222"
        queueGroup: "orchestrator"
        queueLength: "10"
  minReplicaCount: 2
  maxReplicaCount: 20
  scaleUp:
    stabilizationWindowSeconds: 60
    policies:
      - type: Pods
        value: 2
        periodSeconds: 60

# Ingestion Scaling
ingestion:
  triggers:
    - type: nats
      metadata:
        natsServerMonitoringEndpoint: "nats://nats:8222"
        queueGroup: "ingestion"
        queueLength: "5"
  minReplicaCount: 1
  maxReplicaCount: 10
```

### **HPA Scaling (Resource-Based)**

```yaml
# API Gateway HPA
api_gateway:
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Resource
      resource:
        name: memory
        target:
          type: Utilization
          averageUtilization: 80
  minReplicas: 3
  maxReplicas: 15

# Router Service HPA
router-service:
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 60
    - type: Pods
      pods:
        metric:
          name: router_decision_latency_ms
        target:
          type: AverageValue
          averageValue: "50"
  minReplicas: 2
  maxReplicas: 10

# Realtime Service HPA
realtime:
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
    - type: Pods
      pods:
        metric:
          name: ws_active_connections
        target:
          type: AverageValue
          averageValue: "100"
  minReplicas: 3
  maxReplicas: 12
```

## 📬 **Dead Letter Queues (DLQ)**

### **NATS JetStream DLQ Configuration**

```yaml
dlq_config:
  streams:
    - name: "agent.run.dlq"
      subjects: ["agent.run.failed"]
      retention: "limits"
      max_age: "7d"
      storage: "file"

    - name: "tool.call.dlq"
      subjects: ["tool.call.failed"]
      retention: "limits"
      max_age: "3d"
      storage: "file"

    - name: "workflow.compensation.dlq"
      subjects: ["workflow.compensation.failed"]
      retention: "limits"
      max_age: "30d"
      storage: "file"

  consumers:
    - stream: "agent.run.dlq"
      name: "dlq-processor"
      ack_policy: "explicit"
      max_deliver: 3
      ack_wait: "30s"

    - stream: "tool.call.dlq"
      name: "tool-dlq-processor"
      ack_policy: "explicit"
      max_deliver: 5
      ack_wait: "60s"
```

### **DLQ Processing Strategy**

```python
class DLQProcessor:
    """Processes messages from dead letter queues."""

    async def process_agent_run_dlq(self, message):
        """Process failed agent runs from DLQ."""
        try:
            # Log failure for analysis
            await self.log_failure(message)

            # Attempt compensation if applicable
            if message.data.get("workflow_id"):
                await self.compensate_workflow(message.data["workflow_id"])

            # Send alert for manual review
            await self.send_alert(message)

        except Exception as e:
            logger.error(f"DLQ processing failed: {e}")

    async def process_tool_call_dlq(self, message):
        """Process failed tool calls from DLQ."""
        try:
            # Attempt retry with exponential backoff
            await self.retry_tool_call(message)

        except Exception as e:
            logger.error(f"Tool DLQ processing failed: {e}")
```

## 🔄 **Retry & Backoff Strategy**

### **Retry Configuration**

```yaml
retry_config:
  default:
    max_attempts: 3
    base_delay: 1s
    max_delay: 60s
    exponential_base: 2
    jitter: true

  api_calls:
    max_attempts: 5
    base_delay: 500ms
    max_delay: 30s
    exponential_base: 2
    jitter: true

  tool_calls:
    max_attempts: 3
    base_delay: 2s
    max_delay: 120s
    exponential_base: 2
    jitter: true

  database_operations:
    max_attempts: 3
    base_delay: 100ms
    max_delay: 5s
    exponential_base: 1.5
    jitter: true
```

### **Retry Implementation**

```python
class RetryHandler:
    """Handles retry logic with exponential backoff and jitter."""

    def __init__(self, max_attempts: int = 3, base_delay: float = 1.0):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.exponential_base = 2.0
        self.max_delay = 60.0
        self.jitter = True

    async def retry_async(self, func, *args, **kwargs):
        """Retry async function with exponential backoff."""
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                last_exception = e

                if attempt == self.max_attempts - 1:
                    break

                delay = self._calculate_delay(attempt)
                await asyncio.sleep(delay)

        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """Calculate delay with exponential backoff and jitter."""
        delay = self.base_delay * (self.exponential_base ** attempt)
        delay = min(delay, self.max_delay)

        if self.jitter:
            # Add ±10% jitter
            jitter = delay * 0.1 * (random.random() - 0.5)
            delay += jitter

        return max(0, delay)
```

## 🔑 **Idempotency**

### **Idempotency Key Format**

```python
class IdempotencyKey:
    """Generates and validates idempotency keys."""

    @staticmethod
    def generate(tenant_id: str, user_id: str, operation: str,
                request_hash: str) -> str:
        """Generate idempotency key."""
        timestamp = int(time.time())
        return f"idempotency:{tenant_id}:{user_id}:{operation}:{request_hash}:{timestamp}"

    @staticmethod
    def parse(key: str) -> dict:
        """Parse idempotency key."""
        parts = key.split(":")
        if len(parts) != 6 or parts[0] != "idempotency":
            raise ValueError("Invalid idempotency key format")

        return {
            "tenant_id": parts[1],
            "user_id": parts[2],
            "operation": parts[3],
            "request_hash": parts[4],
            "timestamp": int(parts[5])
        }
```

### **Idempotency Storage**

```yaml
idempotency:
  storage: "redis"
  ttl: 3600s # 1 hour
  key_prefix: "idempotency:"

  validation:
    request_hash: true
    response_hash: true
    timestamp_tolerance: 300s # 5 minutes
```

## 🔄 **Saga Pattern**

### **Saga Orchestration**

```python
class SagaOrchestrator:
    """Orchestrates Saga transactions with compensation."""

    def __init__(self):
        self.compensation_actions = {}
        self.step_results = {}

    async def execute_saga(self, saga_id: str, steps: List[SagaStep]):
        """Execute Saga with compensation on failure."""
        completed_steps = []

        try:
            for step in steps:
                result = await self._execute_step(step)
                self.step_results[step.step_id] = result
                completed_steps.append(step)

                # Register compensation action
                if step.compensation_action:
                    self.compensation_actions[step.step_id] = step.compensation_action

        except Exception as e:
            # Execute compensation in reverse order
            await self._compensate(completed_steps)
            raise e

    async def _compensate(self, completed_steps: List[SagaStep]):
        """Execute compensation actions in reverse order."""
        for step in reversed(completed_steps):
            if step.step_id in self.compensation_actions:
                compensation = self.compensation_actions[step.step_id]
                try:
                    await compensation.execute(self.step_results[step.step_id])
                except Exception as e:
                    logger.error(f"Compensation failed for step {step.step_id}: {e}")
```

### **Saga Compensation Table**

```yaml
saga_compensations:
  order_processing:
    steps:
      - step_id: "payment_authorization"
        compensation_action:
          type: "refund_transaction"
          timeout: 30s
          retry_count: 3

      - step_id: "inventory_reservation"
        compensation_action:
          type: "restore_inventory"
          timeout: 15s
          retry_count: 3

      - step_id: "email_notification"
        compensation_action:
          type: "send_cancellation_email"
          timeout: 10s
          retry_count: 2

      - step_id: "crm_update"
        compensation_action:
          type: "revert_crm_status"
          timeout: 20s
          retry_count: 3
```

## 🔍 **Health Checks**

### **Readiness Probes**

```yaml
readiness_probes:
  api_gateway:
    http_get:
      path: /health/ready
      port: 8000
    initial_delay_seconds: 10
    period_seconds: 5
    timeout_seconds: 3
    success_threshold: 1
    failure_threshold: 3

  orchestrator:
    http_get:
      path: /health/ready
      port: 8000
    initial_delay_seconds: 15
    period_seconds: 10
    timeout_seconds: 5
    success_threshold: 1
    failure_threshold: 3

  router-service:
    http_get:
      path: /health/ready
      port: 8000
    initial_delay_seconds: 5
    period_seconds: 5
    timeout_seconds: 3
    success_threshold: 1
    failure_threshold: 3
```

### **Liveness Probes**

```yaml
liveness_probes:
  api_gateway:
    http_get:
      path: /health/live
      port: 8000
    initial_delay_seconds: 30
    period_seconds: 10
    timeout_seconds: 5
    success_threshold: 1
    failure_threshold: 3

  orchestrator:
    http_get:
      path: /health/live
      port: 8000
    initial_delay_seconds: 60
    period_seconds: 30
    timeout_seconds: 10
    success_threshold: 1
    failure_threshold: 3
```

## 🌐 **Network Policies**

### **Namespace Isolation**

```yaml
network_policies:
  api_gateway:
    ingress:
      - from:
          - namespaceSelector:
              matchLabels:
                name: ingress-nginx
        ports:
          - protocol: TCP
            port: 8000

    egress:
      - to:
          - namespaceSelector:
              matchLabels:
                name: orchestrator
        ports:
          - protocol: TCP
            port: 8000

  orchestrator:
    ingress:
      - from:
          - namespaceSelector:
              matchLabels:
                name: api-gateway
        ports:
          - protocol: TCP
            port: 8000

    egress:
      - to:
          - namespaceSelector:
              matchLabels:
                name: router-service
        ports:
          - protocol: TCP
            port: 8000
```

## 📊 **Monitoring & Observability**

### **Key Metrics**

```yaml
metrics:
  autoscaling:
    - name: "queue_depth"
      type: "gauge"
      help: "Current queue depth for autoscaling"

    - name: "active_connections"
      type: "gauge"
      help: "Active WebSocket connections"

    - name: "cpu_utilization"
      type: "gauge"
      help: "CPU utilization percentage"

    - name: "memory_utilization"
      type: "gauge"
      help: "Memory utilization percentage"

  reliability:
    - name: "retry_total"
      type: "counter"
      help: "Total number of retries"

    - name: "dlq_messages_total"
      type: "counter"
      help: "Total messages sent to DLQ"

    - name: "saga_compensations_total"
      type: "counter"
      help: "Total Saga compensations executed"

    - name: "idempotency_hits_total"
      type: "counter"
      help: "Total idempotency cache hits"
```

---

**Status**: ✅ Production-Ready Runtime Topology  
**Last Updated**: September 2024  
**Version**: 1.0.0
