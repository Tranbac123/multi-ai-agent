"""
Contract tests for event schemas
"""

import json
import pytest
import jsonschema
from pathlib import Path


def load_schema(schema_name: str) -> dict:
    """Load a JSON schema from the contracts directory"""
    schema_path = Path(__file__).parent.parent / "contracts" / "schemas" / f"{schema_name}.json"
    with open(schema_path, 'r') as f:
        return json.load(f)


def test_usage_event_schema():
    """Test UsageEvent schema validation"""
    schema = load_schema("UsageEvent")
    
    # Valid usage event
    valid_event = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2024-01-15T10:30:00Z",
        "service_name": "api-gateway",
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "tenant_id": "789e0123-e89b-12d3-a456-426614174000",
        "event_type": "api_call",
        "resource_type": "requests",
        "quantity": 1,
        "unit": "requests",
        "metadata": {
            "request_id": "req-123456",
            "response_time_ms": 150
        },
        "cost": {
            "amount": 0.01,
            "currency": "USD",
            "rate": 0.01
        }
    }
    
    # Should validate successfully
    jsonschema.validate(valid_event, schema)
    
    # Invalid event (missing required field)
    invalid_event = {
        "event_id": "550e8400-e29b-41d4-a716-446655440000",
        "timestamp": "2024-01-15T10:30:00Z",
        # Missing service_name
        "user_id": "123e4567-e89b-12d3-a456-426614174000",
        "tenant_id": "789e0123-e89b-12d3-a456-426614174000",
        "event_type": "api_call",
        "resource_type": "requests",
        "quantity": 1
    }
    
    # Should raise validation error
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_event, schema)


def test_orchestrator_step_schema():
    """Test OrchestratorStep schema validation"""
    schema = load_schema("OrchestratorStep")
    
    # Valid orchestrator step
    valid_step = {
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
    
    # Should validate successfully
    jsonschema.validate(valid_step, schema)
    
    # Invalid step (invalid status)
    invalid_step = {
        "step_id": "660e8400-e29b-41d4-a716-446655440001",
        "workflow_id": "770e8400-e29b-41d4-a716-446655440002",
        "timestamp": "2024-01-15T10:30:00Z",
        "step_name": "Process Document",
        "status": "invalid_status",  # Invalid status
        "service_name": "ingestion-service"
    }
    
    # Should raise validation error
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_step, schema)


def test_realtime_message_schema():
    """Test RealtimeMessage schema validation"""
    schema = load_schema("RealtimeMessage")
    
    # Valid realtime message
    valid_message = {
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
    
    # Should validate successfully
    jsonschema.validate(valid_message, schema)
    
    # Invalid message (invalid message_type)
    invalid_message = {
        "message_id": "880e8400-e29b-41d4-a716-446655440003",
        "timestamp": "2024-01-15T10:30:00Z",
        "channel": "user:123e4567-e89b-12d3-a456-426614174000",
        "message_type": "invalid_type",  # Invalid message type
        "payload": {
            "content": "Hello, how can I help you?",
            "role": "assistant"
        }
    }
    
    # Should raise validation error
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid_message, schema)


def test_schema_compatibility():
    """Test that schemas are compatible with JSON Schema Draft 7"""
    schemas = ["UsageEvent", "OrchestratorStep", "RealtimeMessage"]
    
    for schema_name in schemas:
        schema = load_schema(schema_name)
        
        # Check that schema uses Draft 7
        assert schema.get("$schema") == "http://json-schema.org/draft-07/schema#"
        
        # Check that schema has required fields
        assert "type" in schema
        assert "properties" in schema
        assert "required" in schema


def test_schema_evolution():
    """Test that schemas can handle optional fields gracefully"""
    schemas = ["UsageEvent", "OrchestratorStep", "RealtimeMessage"]
    
    for schema_name in schemas:
        schema = load_schema(schema_name)
        
        # Create a minimal valid event with only required fields
        minimal_event = {}
        for field in schema.get("required", []):
            field_def = schema["properties"].get(field, {})
            
            # Set default values based on field type
            if field_def.get("type") == "string":
                if "format" in field_def and field_def["format"] == "uuid":
                    minimal_event[field] = "550e8400-e29b-41d4-a716-446655440000"
                elif "format" in field_def and field_def["format"] == "date-time":
                    minimal_event[field] = "2024-01-15T10:30:00Z"
                else:
                    minimal_event[field] = "test_value"
            elif field_def.get("type") == "number":
                minimal_event[field] = 1
            elif field_def.get("type") == "integer":
                minimal_event[field] = 1
            elif field_def.get("type") == "boolean":
                minimal_event[field] = True
            elif field_def.get("type") == "array":
                minimal_event[field] = []
            elif field_def.get("type") == "object":
                minimal_event[field] = {}
        
        # Should validate successfully
        jsonschema.validate(minimal_event, schema)
