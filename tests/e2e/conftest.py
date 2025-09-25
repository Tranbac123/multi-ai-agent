"""
E2E Test Configuration and Fixtures
"""
import pytest
import asyncio
import httpx
import time
from typing import AsyncGenerator, Dict, Any
import os
import json


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="function")
async def http_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """Create HTTP client for E2E tests."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        yield client


@pytest.fixture(scope="session")
def service_urls() -> Dict[str, str]:
    """Service URLs for E2E tests."""
    return {
        "api_gateway": "http://localhost:8000",
        "model_gateway": "http://localhost:8080",
        "config_service": "http://localhost:8090",
        "policy_adapter": "http://localhost:8091",
        "retrieval_service": "http://localhost:8081",
        "tools_service": "http://localhost:8082",
        "router_service": "http://localhost:8083",
        "admin_portal": "http://localhost:8099",
        "web_frontend": "http://localhost:3000",
        "ai_chatbot": "http://localhost:3001",
    }


@pytest.fixture(scope="session")
def test_user_data() -> Dict[str, Any]:
    """Test user data for E2E scenarios."""
    return {
        "user_id": "test_user_123",
        "username": "testuser",
        "email": "test@example.com",
        "session_id": f"session_{int(time.time())}",
        "tenant_id": "test_tenant",
    }


@pytest.fixture(scope="session")
def test_chat_data() -> Dict[str, Any]:
    """Test chat data for E2E scenarios."""
    return {
        "messages": [
            {"role": "user", "content": "Hello, how can you help me today?"},
            {"role": "user", "content": "What is the weather like?"},
            {"role": "user", "content": "Can you help me with a technical question?"},
        ],
        "model": "gpt-3.5-turbo",
        "temperature": 0.7,
        "max_tokens": 100,
    }


@pytest.fixture(scope="session")
def test_config_data() -> Dict[str, Any]:
    """Test configuration data for E2E scenarios."""
    return {
        "service_name": "test_service",
        "config_key": "test_config",
        "config_value": "test_value",
        "environment": "test",
    }


class E2ETestHelper:
    """Helper class for E2E test operations."""
    
    @staticmethod
    async def wait_for_service(client: httpx.AsyncClient, url: str, max_retries: int = 10) -> bool:
        """Wait for a service to be available."""
        for attempt in range(max_retries):
            try:
                response = await client.get(f"{url}/healthz")
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(2)
        return False
    
    @staticmethod
    async def create_test_session(client: httpx.AsyncClient, api_gateway_url: str) -> str:
        """Create a test session."""
        try:
            response = await client.post(
                f"{api_gateway_url}/v1/session/create",
                json={"user_id": "test_user_e2e"}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("session_id", "default_session")
        except Exception:
            pass
        return "default_session"
    
    @staticmethod
    async def cleanup_test_data(client: httpx.AsyncClient, api_gateway_url: str, session_id: str):
        """Clean up test data."""
        try:
            await client.delete(f"{api_gateway_url}/v1/session/{session_id}")
        except Exception:
            pass


@pytest.fixture(scope="session")
def e2e_helper() -> E2ETestHelper:
    """E2E test helper instance."""
    return E2ETestHelper()
