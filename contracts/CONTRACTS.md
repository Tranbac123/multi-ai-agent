# Event Contracts & Schemas

This document describes the event contracts and schemas used for inter-service communication in the Multi-AI-Agent Platform.

## Overview

The platform uses NATS JetStream for event-driven communication between services. All events are defined using JSON Schema for validation and documentation.

## Event Topics

### Core Topics

| Topic               | Description               | Producers         | Consumers                          |
| ------------------- | ------------------------- | ----------------- | ---------------------------------- |
| `ingest.*`          | Document ingestion events | ingestion-service | analytics-service, billing-service |
| `orchestrator.step` | Workflow execution events | orchestrator      | usage-metering, audit-log          |
| `usage.metered`     | Usage tracking events     | All services      | billing-service, analytics-service |
| `realtime.push`     | Real-time message events  | realtime-gateway  | Chat clients, notification-service |
| `alerts.*`          | System alert events       | All services      | notification-service, audit-log    |

### Topic Patterns

- `ingest.document.processed` - Document successfully processed
- `ingest.document.failed` - Document processing failed
- `orchestrator.step.started` - Workflow step started
- `orchestrator.step.completed` - Workflow step completed
- `orchestrator.step.failed` - Workflow step failed
- `usage.metered.api_call` - API call usage tracked
- `usage.metered.model_inference` - Model inference usage tracked
- `realtime.push.chat_message` - Chat message sent
- `realtime.push.notification` - Notification sent
- `alerts.service_down` - Service health alert
- `alerts.high_latency` - High latency alert
- `alerts.quota_exceeded` - Quota exceeded alert

## Event Schemas

### UsageEvent

**Purpose**: Track service usage for billing and analytics

**Schema**: [UsageEvent.json](schemas/UsageEvent.json)

**Key Fields**:

- `event_id`: Unique identifier
- `timestamp`: When the event occurred
- `service_name`: Which service generated the event
- `user_id`: User who triggered the usage
- `tenant_id`: Tenant organization
- `event_type`: Type of usage (api_call, model_inference, etc.)
- `resource_type`: Type of resource consumed
- `quantity`: Amount consumed
- `cost`: Cost information

**Example**:

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "timestamp": "2024-01-15T10:30:00Z",
  "service_name": "model-gateway",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "tenant_id": "789e0123-e89b-12d3-a456-426614174000",
  "event_type": "model_inference",
  "resource_type": "tokens",
  "quantity": 150,
  "unit": "tokens",
  "metadata": {
    "model_name": "gpt-4",
    "response_time_ms": 1250
  },
  "cost": {
    "amount": 0.0003,
    "currency": "USD",
    "rate": 0.000002
  }
}
```

### OrchestratorStep

**Purpose**: Track workflow execution steps

**Schema**: [OrchestratorStep.json](schemas/OrchestratorStep.json)

**Key Fields**:

- `step_id`: Unique step identifier
- `workflow_id`: Parent workflow identifier
- `timestamp`: When the step occurred
- `step_name`: Human-readable step name
- `status`: Current step status
- `service_name`: Service executing the step
- `execution_time_ms`: Time taken to execute
- `error`: Error information if failed

**Example**:

```json
{
  "step_id": "660e8400-e29b-41d4-a716-446655440001",
  "workflow_id": "770e8400-e29b-41d4-a716-446655440002",
  "timestamp": "2024-01-15T10:30:00Z",
  "step_name": "Process Document",
  "status": "completed",
  "service_name": "ingestion-service",
  "step_type": "data_processing",
  "execution_time_ms": 2500,
  "metadata": {
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "tenant_id": "789e0123-e89b-12d3-a456-426614174000",
    "request_id": "req-123456"
  }
}
```

### RealtimeMessage

**Purpose**: Real-time messaging between services and clients

**Schema**: [RealtimeMessage.json](schemas/RealtimeMessage.json)

**Key Fields**:

- `message_id`: Unique message identifier
- `timestamp`: When the message was created
- `channel`: Channel or topic
- `message_type`: Type of message
- `payload`: Message data
- `sender`: Information about the sender
- `recipients`: List of recipients

**Example**:

```json
{
  "message_id": "880e8400-e29b-41d4-a716-446655440003",
  "timestamp": "2024-01-15T10:30:00Z",
  "channel": "user:123e4567-e89b-12d3-a456-426614174000",
  "message_type": "chat_message",
  "payload": {
    "content": "Hello, how can I help you?",
    "role": "assistant"
  },
  "sender": {
    "service_name": "model-gateway",
    "user_id": "123e4567-e89b-12d3-a456-426614174000"
  },
  "recipients": [
    {
      "user_id": "123e4567-e89b-12d3-a456-426614174000",
      "connection_id": "conn-abc123"
    }
  ]
}
```

## Event Flow Patterns

### Request-Response Pattern

1. Service A publishes request event
2. Service B consumes and processes
3. Service B publishes response event
4. Service A consumes response

### Pub-Sub Pattern

1. Service publishes event to topic
2. Multiple services subscribe and consume
3. Each service processes independently

### Workflow Pattern

1. Orchestrator publishes step events
2. Services execute steps based on events
3. Services publish completion events
4. Orchestrator coordinates next steps

## Schema Evolution

### Versioning Strategy

- Use semantic versioning for schemas
- Maintain backward compatibility
- Use `$schema` field for version identification

### Breaking Changes

- Changing required fields
- Removing fields
- Changing field types
- Changing enum values

### Non-Breaking Changes

- Adding optional fields
- Adding enum values
- Relaxing constraints
- Adding metadata

## Validation

### Schema Validation

- All events must validate against their schemas
- Use JSON Schema validators in each service
- Fail fast on invalid events

### Contract Testing

- Test event schemas in CI/CD
- Validate producer/consumer contracts
- Ensure backward compatibility

## Monitoring

### Event Metrics

- Event publish rate per service
- Event consumption rate per service
- Event processing latency
- Event failure rate

### Alerting

- High event failure rate
- Schema validation failures
- Event backlog size
- Service connectivity issues

## Best Practices

### Event Design

- Keep events focused and atomic
- Include correlation IDs for tracing
- Use consistent timestamp formats
- Include metadata for debugging

### Publishing

- Use idempotency keys for critical events
- Implement retry logic with backoff
- Monitor publish success rates
- Use appropriate message TTL

### Consumption

- Handle duplicate events gracefully
- Implement proper error handling
- Use dead letter queues for failures
- Monitor consumption lag

### Schema Management

- Version all schemas
- Document breaking changes
- Test schema evolution
- Maintain backward compatibility
