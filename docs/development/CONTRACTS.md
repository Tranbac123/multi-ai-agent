# API Contracts Documentation

## 📋 **Overview**

This document defines the complete API contracts for the Multi-AI-Agent platform, including request/response schemas, validation rules, and error handling specifications.

## 🔗 **API Gateway Contracts**

### **Authentication & Authorization**

#### **JWT Token Structure**

```json
{
  "header": {
    "alg": "RS256",
    "typ": "JWT",
    "kid": "key-id-123"
  },
  "payload": {
    "iss": "multi-ai-agent",
    "sub": "user_123456",
    "aud": "api-gateway",
    "exp": 1694684400,
    "iat": 1694680800,
    "tenant_id": "tenant_789",
    "user_id": "user_123456",
    "roles": ["user", "admin"],
    "scopes": ["read", "write", "admin"]
  }
}
```

#### **API Key Structure**

```json
{
  "api_key_id": "ak_1234567890abcdef",
  "tenant_id": "tenant_789",
  "name": "Production API Key",
  "scopes": ["chat", "workflows", "analytics"],
  "rate_limits": {
    "requests_per_minute": 1000,
    "requests_per_hour": 10000,
    "requests_per_day": 100000
  },
  "expires_at": "2024-12-31T23:59:59Z",
  "created_at": "2024-09-14T10:30:00Z",
  "last_used": "2024-09-14T15:45:30Z"
}
```

### **Request Headers**

#### **Standard Headers**

```http
Authorization: Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...
X-Tenant-ID: tenant_789
X-User-ID: user_123456
X-Request-ID: req_1234567890abcdef
Content-Type: application/json
Accept: application/json
User-Agent: MultiAI-Agent-Client/1.0.0
```

#### **Rate Limiting Headers**

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1694684400
X-RateLimit-Window: 60
```

## 💬 **Chat API Contracts**

### **Send Message**

#### **Request Schema**

```json
{
  "message": {
    "type": "text",
    "content": "How do I reset my password?",
    "metadata": {
      "source": "web",
      "session_id": "sess_abc123",
      "user_agent": "Mozilla/5.0...",
      "ip_address": "192.168.1.100"
    }
  },
  "context": {
    "conversation_id": "conv_123456",
    "previous_messages": [
      {
        "role": "user",
        "content": "Hello",
        "timestamp": "2024-09-14T10:30:00Z"
      },
      {
        "role": "assistant",
        "content": "Hi! How can I help you today?",
        "timestamp": "2024-09-14T10:30:05Z"
      }
    ],
    "user_preferences": {
      "language": "en",
      "timezone": "UTC",
      "response_format": "detailed"
    }
  },
  "options": {
    "workflow": "faq_workflow",
    "tier_preference": "balanced",
    "max_tokens": 1000,
    "temperature": 0.7,
    "stream": false
  }
}
```

#### **Response Schema**

```json
{
  "response": {
    "message_id": "msg_1234567890",
    "conversation_id": "conv_123456",
    "content": {
      "type": "text",
      "text": "To reset your password, please follow these steps:\n\n1. Go to the login page\n2. Click 'Forgot Password'\n3. Enter your email address\n4. Check your email for reset instructions\n\nIf you need further assistance, please contact support.",
      "formatted": true
    },
    "metadata": {
      "tier_used": "SLM_A",
      "confidence": 0.95,
      "processing_time_ms": 1250,
      "tokens_used": 150,
      "cost_usd": 0.0015,
      "model_version": "gpt-4-0613"
    }
  },
  "workflow": {
    "workflow_id": "faq_workflow_v1.2",
    "steps_executed": [
      {
        "step_id": "step_1",
        "step_type": "router_decision",
        "status": "completed",
        "duration_ms": 100,
        "tier": "SLM_A"
      },
      {
        "step_id": "step_2",
        "step_type": "knowledge_search",
        "status": "completed",
        "duration_ms": 800,
        "results_count": 3
      },
      {
        "step_id": "step_3",
        "step_type": "response_generation",
        "status": "completed",
        "duration_ms": 350,
        "tokens_generated": 150
      }
    ],
    "total_duration_ms": 1250,
    "status": "completed"
  },
  "suggestions": [
    {
      "type": "quick_reply",
      "text": "Still need help?",
      "action": "contact_support"
    },
    {
      "type": "quick_reply",
      "text": "Try a different question",
      "action": "new_query"
    }
  ],
  "usage": {
    "request_id": "req_1234567890abcdef",
    "tenant_id": "tenant_789",
    "user_id": "user_123456",
    "timestamp": "2024-09-14T10:30:15Z",
    "cost_breakdown": {
      "router_cost": 0.0001,
      "knowledge_cost": 0.0005,
      "generation_cost": 0.0009,
      "total_cost": 0.0015
    }
  }
}
```

### **Streaming Response**

#### **Server-Sent Events Format**

```http
Content-Type: text/event-stream
Cache-Control: no-cache
Connection: keep-alive

event: message_start
data: {"message_id": "msg_1234567890", "status": "started"}

event: message_chunk
data: {"content": "To reset your password, please follow these steps:"}

event: message_chunk
data: {"content": "\n\n1. Go to the login page"}

event: message_chunk
data: {"content": "\n2. Click 'Forgot Password'"}

event: message_complete
data: {"message_id": "msg_1234567890", "status": "completed", "total_tokens": 150}
```

## 🔄 **Workflow API Contracts**

### **Execute Workflow**

#### **Request Schema**

```json
{
  "workflow": {
    "workflow_id": "order_processing_v2.1",
    "version": "2.1",
    "parameters": {
      "order_id": "order_123456",
      "customer_id": "customer_789",
      "items": [
        {
          "product_id": "prod_abc123",
          "quantity": 2,
          "price": 29.99
        }
      ],
      "payment_method": "credit_card",
      "shipping_address": {
        "street": "123 Main St",
        "city": "New York",
        "state": "NY",
        "zip": "10001",
        "country": "US"
      }
    }
  },
  "context": {
    "tenant_id": "tenant_789",
    "user_id": "user_123456",
    "session_id": "sess_abc123",
    "execution_options": {
      "async": true,
      "timeout_ms": 30000,
      "retry_policy": "exponential_backoff",
      "compensation_enabled": true
    }
  }
}
```

#### **Response Schema**

```json
{
  "execution": {
    "execution_id": "exec_1234567890abcdef",
    "workflow_id": "order_processing_v2.1",
    "status": "running",
    "started_at": "2024-09-14T10:30:00Z",
    "estimated_completion": "2024-09-14T10:30:30Z"
  },
  "steps": [
    {
      "step_id": "step_1",
      "step_type": "validate_order",
      "status": "completed",
      "started_at": "2024-09-14T10:30:00Z",
      "completed_at": "2024-09-14T10:30:02Z",
      "duration_ms": 2000,
      "result": {
        "valid": true,
        "validation_errors": []
      }
    },
    {
      "step_id": "step_2",
      "step_type": "process_payment",
      "status": "running",
      "started_at": "2024-09-14T10:30:02Z",
      "estimated_completion": "2024-09-14T10:30:15Z"
    },
    {
      "step_id": "step_3",
      "step_type": "update_inventory",
      "status": "pending"
    },
    {
      "step_id": "step_4",
      "step_type": "send_confirmation",
      "status": "pending"
    }
  ],
  "compensation_actions": [
    {
      "step_id": "step_2",
      "action": "refund_payment",
      "status": "ready"
    },
    {
      "step_id": "step_3",
      "action": "restore_inventory",
      "status": "ready"
    }
  ]
}
```

## 📊 **Analytics API Contracts**

### **Get Metrics**

#### **Request Schema**

```json
{
  "query": {
    "metrics": [
      "request_count",
      "response_time_p95",
      "error_rate",
      "cost_per_request"
    ],
    "filters": {
      "tenant_id": "tenant_789",
      "date_range": {
        "start": "2024-09-01T00:00:00Z",
        "end": "2024-09-14T23:59:59Z"
      },
      "workflow": "faq_workflow",
      "tier": "SLM_A"
    },
    "group_by": ["date", "workflow", "tier"],
    "aggregation": "daily"
  },
  "options": {
    "timezone": "UTC",
    "format": "json",
    "include_raw_data": false
  }
}
```

#### **Response Schema**

```json
{
  "metrics": {
    "request_count": {
      "total": 15420,
      "daily_average": 1101,
      "trend": "+12.5%",
      "breakdown": {
        "2024-09-01": 1050,
        "2024-09-02": 1080,
        "2024-09-03": 1120
      }
    },
    "response_time_p95": {
      "value": 450,
      "unit": "ms",
      "trend": "-5.2%",
      "breakdown": {
        "faq_workflow": 420,
        "order_workflow": 580,
        "support_workflow": 390
      }
    },
    "error_rate": {
      "value": 0.8,
      "unit": "%",
      "trend": "-0.3%",
      "breakdown": {
        "4xx_errors": 0.5,
        "5xx_errors": 0.3
      }
    },
    "cost_per_request": {
      "value": 0.0012,
      "unit": "USD",
      "trend": "+2.1%",
      "breakdown": {
        "router_cost": 0.0001,
        "generation_cost": 0.0011
      }
    }
  },
  "metadata": {
    "query_id": "query_1234567890",
    "generated_at": "2024-09-14T10:30:00Z",
    "cache_hit": false,
    "execution_time_ms": 150
  }
}
```

## 🔌 **WebSocket API Contracts**

### **Connection Establishment**

#### **Handshake Request**

```json
{
  "type": "handshake",
  "token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
  "tenant_id": "tenant_789",
  "user_id": "user_123456",
  "session_config": {
    "heartbeat_interval": 30,
    "max_message_size": 1048576,
    "compression": true
  }
}
```

#### **Handshake Response**

```json
{
  "type": "handshake_ack",
  "session_id": "sess_abc123",
  "status": "connected",
  "server_config": {
    "heartbeat_interval": 30,
    "max_message_size": 1048576,
    "supported_features": ["compression", "binary_messages"]
  },
  "rate_limits": {
    "messages_per_minute": 100,
    "bytes_per_minute": 10485760
  }
}
```

### **Message Format**

#### **Client Message**

```json
{
  "type": "message",
  "message_id": "msg_1234567890",
  "content": {
    "type": "text",
    "text": "Hello, I need help with my order"
  },
  "context": {
    "conversation_id": "conv_123456",
    "metadata": {
      "source": "mobile_app",
      "version": "1.2.3"
    }
  },
  "timestamp": "2024-09-14T10:30:00Z"
}
```

#### **Server Message**

```json
{
  "type": "message",
  "message_id": "msg_1234567891",
  "content": {
    "type": "text",
    "text": "I'd be happy to help you with your order. Can you provide your order number?",
    "suggestions": [
      {
        "type": "quick_reply",
        "text": "Order #123456",
        "payload": "order_123456"
      },
      {
        "type": "quick_reply",
        "text": "I don't have my order number",
        "payload": "no_order_number"
      }
    ]
  },
  "context": {
    "conversation_id": "conv_123456",
    "workflow": {
      "workflow_id": "order_support_v1.0",
      "step": "collect_order_info"
    }
  },
  "timestamp": "2024-09-14T10:30:05Z"
}
```

## ❌ **Error Response Contracts**

### **Standard Error Response**

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Invalid request parameters",
    "details": [
      {
        "field": "message.content",
        "message": "Content is required",
        "code": "REQUIRED_FIELD"
      },
      {
        "field": "options.max_tokens",
        "message": "Must be between 1 and 4000",
        "code": "INVALID_RANGE"
      }
    ],
    "request_id": "req_1234567890abcdef",
    "timestamp": "2024-09-14T10:30:00Z",
    "documentation_url": "https://docs.multi-ai-agent.com/errors/VALIDATION_ERROR"
  }
}
```

### **Error Codes**

| Code                        | HTTP Status | Description                         |
| --------------------------- | ----------- | ----------------------------------- |
| `AUTHENTICATION_REQUIRED`   | 401         | Valid authentication token required |
| `AUTHORIZATION_FAILED`      | 403         | Insufficient permissions            |
| `VALIDATION_ERROR`          | 400         | Request validation failed           |
| `RATE_LIMIT_EXCEEDED`       | 429         | Rate limit exceeded                 |
| `WORKFLOW_NOT_FOUND`        | 404         | Specified workflow not found        |
| `WORKFLOW_EXECUTION_FAILED` | 500         | Workflow execution failed           |
| `TENANT_QUOTA_EXCEEDED`     | 429         | Tenant quota exceeded               |
| `SERVICE_UNAVAILABLE`       | 503         | Service temporarily unavailable     |
| `INTERNAL_ERROR`            | 500         | Internal server error               |

## 🔒 **Security Contracts**

### **Rate Limiting**

#### **Rate Limit Headers**

```http
X-RateLimit-Limit: 1000
X-RateLimit-Remaining: 999
X-RateLimit-Reset: 1694684400
X-RateLimit-Window: 60
X-RateLimit-Policy: sliding_window
```

#### **Rate Limit Exceeded Response**

```json
{
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "details": {
      "limit": 1000,
      "remaining": 0,
      "reset_time": "2024-09-14T10:31:00Z",
      "retry_after": 60
    },
    "request_id": "req_1234567890abcdef",
    "timestamp": "2024-09-14T10:30:00Z"
  }
}
```

### **Content Security**

#### **PII Redaction**

```json
{
  "content": "Your order #123456 has been shipped to [REDACTED] at [REDACTED].",
  "redaction_applied": true,
  "redacted_fields": [
    {
      "field": "email",
      "type": "email_address",
      "replacement": "[REDACTED]"
    },
    {
      "field": "phone",
      "type": "phone_number",
      "replacement": "[REDACTED]"
    }
  ]
}
```

## 📋 **Validation Rules**

### **Field Validation**

#### **Message Content**

- **Type**: String
- **Min Length**: 1 character
- **Max Length**: 4000 characters
- **Pattern**: No control characters except newlines
- **Required**: Yes

#### **Workflow Parameters**

- **Type**: Object
- **Max Depth**: 10 levels
- **Max Size**: 1MB
- **Schema Validation**: Required for known workflows

#### **Rate Limits**

- **Requests per minute**: 1-10000
- **Requests per hour**: 1-100000
- **Requests per day**: 1-1000000

### **Schema Validation**

#### **JSON Schema**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "properties": {
    "message": {
      "type": "object",
      "properties": {
        "content": {
          "type": "string",
          "minLength": 1,
          "maxLength": 4000
        },
        "type": {
          "type": "string",
          "enum": ["text", "image", "file"]
        }
      },
      "required": ["content", "type"]
    }
  },
  "required": ["message"]
}
```

---

**Status**: ✅ Production-Ready API Contracts Documentation  
**Last Updated**: September 2024  
**Version**: 1.0.0
