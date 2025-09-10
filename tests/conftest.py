"""Production-grade test configuration and fixtures."""

import asyncio
import json
import time
import uuid
from typing import Any, Dict, List, Optional, Union
from unittest.mock import AsyncMock, MagicMock
from dataclasses import dataclass

import pytest
import pytest_asyncio
import httpx
import redis.asyncio as redis
import nats
from hypothesis import given, strategies as st

from apps.api-gateway.main import app as api_gateway_app
from apps.orchestrator.main import app as orchestrator_app
from apps.router_service.main import app as router_app
from apps.analytics_service.main import app as analytics_app
from apps.billing-service.main import app as billing_app
from apps.realtime.main import app as realtime_app
from apps.ingestion.main import app as ingestion_app


# Test modes
class TestMode:
    MOCK = "mock"
    LIVE_SMOKE = "live_smoke"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def test_mode():
    """Test mode configuration."""
    return TestMode.MOCK


# LLM Fixtures
@pytest.fixture
def llm_mock():
    """Mock LLM client for testing."""
    mock = AsyncMock()
    mock.generate.return_value = {
        "content": "Mocked response",
        "tokens_used": 100,
        "model": "gpt-4",
        "finish_reason": "stop"
    }
    mock.embed.return_value = [0.1] * 1536
    return mock


@pytest.fixture
def llm_golden():
    """Golden LLM responses for deterministic testing."""
    return {
        "faq_response": {
            "content": "Our business hours are 9 AM to 5 PM EST, Monday through Friday.",
            "tokens_used": 25,
            "model": "gpt-4",
            "finish_reason": "stop"
        },
        "order_response": {
            "content": "I can help you track your order. Please provide your order number.",
            "tokens_used": 20,
            "model": "gpt-4",
            "finish_reason": "stop"
        },
        "lead_response": {
            "content": "Thank you for your interest! I'll connect you with our sales team.",
            "tokens_used": 18,
            "model": "gpt-4",
            "finish_reason": "stop"
        }
    }


# Service Clients
@pytest.fixture
async def router_client():
    """Router service client."""
    async with httpx.AsyncClient(app=router_app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def orchestrator_client():
    """Orchestrator service client."""
    async with httpx.AsyncClient(app=orchestrator_app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def api_gateway_client():
    """API Gateway client."""
    async with httpx.AsyncClient(app=api_gateway_app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def analytics_client():
    """Analytics service client."""
    async with httpx.AsyncClient(app=analytics_app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def billing_client():
    """Billing service client."""
    async with httpx.AsyncClient(app=billing_app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def realtime_client():
    """Realtime service client."""
    async with httpx.AsyncClient(app=realtime_app, base_url="http://test") as client:
        yield client


@pytest.fixture
async def ingestion_client():
    """Ingestion service client."""
    async with httpx.AsyncClient(app=ingestion_app, base_url="http://test") as client:
        yield client


# Tool Client
@pytest.fixture
def tool_client():
    """Tool execution client."""
    mock = AsyncMock()
    mock.execute_tool.return_value = {
        "success": True,
        "result": {"status": "completed"},
        "execution_time": 0.5,
        "cost": 0.01
    }
    return mock


# WebSocket Client
@pytest.fixture
async def ws_client():
    """WebSocket client for realtime testing."""
    mock = AsyncMock()
    mock.connect.return_value = None
    mock.send.return_value = None
    mock.receive.return_value = {
        "type": "websocket.receive",
        "text": json.dumps({"message": "test"})
    }
    mock.close.return_value = None
    return mock


# Infrastructure Fixtures
@pytest.fixture
async def redis_fixture():
    """Redis test fixture."""
    redis_client = redis.Redis(host="localhost", port=6379, db=15)
    await redis_client.flushdb()
    yield redis_client
    await redis_client.flushdb()
    await redis_client.close()


@pytest.fixture
async def nats_fixture():
    """NATS test fixture."""
    nc = await nats.connect("nats://localhost:4222")
    yield nc
    await nc.close()


@pytest.fixture
async def postgres_fixture():
    """PostgreSQL test fixture."""
    # Mock database connection for testing
    mock_db = AsyncMock()
    mock_db.execute.return_value = None
    mock_db.fetch_one.return_value = {"id": 1, "tenant_id": "test_tenant"}
    mock_db.fetch_all.return_value = [{"id": 1, "tenant_id": "test_tenant"}]
    return mock_db


# Test Data Factories
@pytest.fixture
def tenant_factory():
    """Factory for creating test tenants."""
    def _create_tenant(tenant_id: str = None, **kwargs):
        return {
            "tenant_id": tenant_id or f"tenant_{uuid.uuid4().hex[:8]}",
            "name": kwargs.get("name", "Test Tenant"),
            "plan": kwargs.get("plan", "basic"),
            "created_at": time.time(),
            **kwargs
        }
    return _create_tenant


@pytest.fixture
def user_factory():
    """Factory for creating test users."""
    def _create_user(user_id: str = None, tenant_id: str = None, **kwargs):
        return {
            "user_id": user_id or f"user_{uuid.uuid4().hex[:8]}",
            "tenant_id": tenant_id or f"tenant_{uuid.uuid4().hex[:8]}",
            "email": kwargs.get("email", "test@example.com"),
            "role": kwargs.get("role", "user"),
            "created_at": time.time(),
            **kwargs
        }
    return _create_user


@pytest.fixture
def message_factory():
    """Factory for creating test messages."""
    def _create_message(content: str = None, **kwargs):
        return {
            "message_id": kwargs.get("message_id", str(uuid.uuid4())),
            "content": content or "Test message",
            "tenant_id": kwargs.get("tenant_id", "test_tenant"),
            "user_id": kwargs.get("user_id", "test_user"),
            "session_id": kwargs.get("session_id", str(uuid.uuid4())),
            "timestamp": kwargs.get("timestamp", time.time()),
            "metadata": kwargs.get("metadata", {}),
            **kwargs
        }
    return _create_message


@pytest.fixture
def workflow_factory():
    """Factory for creating test workflows."""
    def _create_workflow(name: str = None, **kwargs):
        return {
            "name": name or "test_workflow",
            "version": kwargs.get("version", "1.0.0"),
            "description": kwargs.get("description", "Test workflow"),
            "nodes": kwargs.get("nodes", []),
            "edges": kwargs.get("edges", []),
            "created_at": time.time(),
            **kwargs
        }
    return _create_workflow


# Test Helpers
def assert_json_strict(data: Any, schema: Dict[str, Any]) -> None:
    """Assert JSON data matches schema strictly."""
    if not isinstance(data, dict):
        raise AssertionError(f"Expected dict, got {type(data)}")
    
    for key, expected_type in schema.items():
        if key not in data:
            raise AssertionError(f"Missing required key: {key}")
        
        actual_type = type(data[key])
        if not isinstance(data[key], expected_type):
            raise AssertionError(f"Key '{key}' expected {expected_type}, got {actual_type}")


def assert_cost_within(actual_cost: float, expected_cost: float, tolerance: float = 0.1) -> None:
    """Assert cost is within tolerance of expected."""
    if abs(actual_cost - expected_cost) > tolerance:
        raise AssertionError(f"Cost {actual_cost} not within tolerance {tolerance} of expected {expected_cost}")


def assert_trace_attrs(span: Dict[str, Any], required_attrs: List[str]) -> None:
    """Assert trace span contains required attributes."""
    for attr in required_attrs:
        if attr not in span.get("attributes", {}):
            raise AssertionError(f"Missing required trace attribute: {attr}")


# Hypothesis Strategies
@pytest.fixture
def tenant_id_strategy():
    """Hypothesis strategy for tenant IDs."""
    return st.text(min_size=8, max_size=32, alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd")))


@pytest.fixture
def message_content_strategy():
    """Hypothesis strategy for message content."""
    return st.text(min_size=1, max_size=1000)


@pytest.fixture
def json_payload_strategy():
    """Hypothesis strategy for JSON payloads."""
    return st.recursive(
        st.one_of(
            st.text(),
            st.integers(),
            st.floats(),
            st.booleans(),
            st.none()
        ),
        lambda children: st.lists(children) | st.dictionaries(st.text(), children)
    )


# Test Configuration
@pytest.fixture(autouse=True)
def test_config():
    """Test configuration."""
    return {
        "test_mode": TestMode.MOCK,
        "timeout": 30.0,
        "retry_attempts": 3,
        "cost_tolerance": 0.1,
        "latency_tolerance": 0.2
    }


# Cleanup
@pytest.fixture(autouse=True)
async def cleanup_test_data(redis_fixture):
    """Cleanup test data after each test."""
    yield
    await redis_fixture.flushdb()


# Test Markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "contract: Contract tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "chaos: Chaos engineering tests")
    config.addinivalue_line("markers", "eval: Evaluation tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "live: Live API tests")
    config.addinivalue_line("markers", "mock: Mock tests")
