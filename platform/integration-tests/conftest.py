"""Main pytest configuration for production-grade testing system."""

import pytest
import os
import sys
from pathlib import Path

# Add test directories to Python path
test_root = Path(__file__).parent
sys.path.insert(0, str(test_root))

# Import test fixtures and helpers
from tests._fixtures import test_config, TestMode
from tests._fixtures.factories import factory
from tests._fixtures.llm_cassette import cassette_recorder, golden_loader
from tests._helpers import test_helpers, mock_llm
from tests._helpers import test_data_manager as test_data_manager_instance
from tests._plugins import env_manager, mode_manager

# Set up test environment
os.environ.setdefault("TEST_MODE", "MOCK")
os.environ.setdefault("PYTHONPATH", str(test_root))

# Re-import with environment set
from tests._fixtures import test_config

# Core fixtures that are used across all tests
@pytest.fixture(scope="session")
def test_mode():
    """Session-scoped fixture for test mode."""
    return test_config.mode

@pytest.fixture(scope="session")
def test_config_instance():
    """Session-scoped fixture for test configuration."""
    return test_config

@pytest.fixture(scope="session")
def entity_factory():
    """Session-scoped fixture for entity factory."""
    return factory

@pytest.fixture(scope="session")
def llm_cassette():
    """Session-scoped fixture for LLM cassette recorder."""
    return cassette_recorder

@pytest.fixture(scope="session")
def golden_outputs():
    """Session-scoped fixture for golden output loader."""
    return golden_loader

@pytest.fixture(scope="session")
def test_helpers_instance():
    """Session-scoped fixture for test helpers."""
    return test_helpers

@pytest.fixture(scope="session")
def mock_llm_provider():
    """Session-scoped fixture for mock LLM provider."""
    return mock_llm

@pytest.fixture(scope="function")
def test_data_manager():
    """Function-scoped fixture for test data manager."""
    return test_data_manager

# Environment-specific fixtures
@pytest.fixture(scope="session")
def mock_services(test_mode):
    """Session-scoped fixture for mock services configuration."""
    if test_mode in [TestMode.MOCK, TestMode.GOLDEN]:
        return {
            'use_mock_llm': True,
            'use_mock_database': True,
            'use_mock_redis': True,
            'use_mock_nats': True,
            'deterministic_responses': True
        }
    else:
        return {
            'use_mock_llm': False,
            'use_mock_database': False,
            'use_mock_redis': False,
            'use_mock_nats': False,
            'deterministic_responses': False
        }

@pytest.fixture(scope="session")
def live_services_config(test_mode):
    """Session-scoped fixture for live services configuration."""
    if test_mode == TestMode.LIVE_SMOKE:
        return {
            'database_url': os.getenv('TEST_DATABASE_URL', 'postgresql://test:test@localhost:5432/test'),
            'redis_url': os.getenv('TEST_REDIS_URL', 'redis://localhost:6379/0'),
            'nats_url': os.getenv('TEST_NATS_URL', 'nats://localhost:4222'),
            'llm_api_key': os.getenv('TEST_LLM_API_KEY'),
            'llm_base_url': os.getenv('TEST_LLM_BASE_URL', 'https://api.openai.com/v1')
        }
    else:
        return {}

# Test data fixtures
@pytest.fixture
def sample_tenant(entity_factory):
    """Fixture for a sample tenant."""
    tenant = entity_factory.create_tenant()
    return tenant

@pytest.fixture
def sample_user(entity_factory, sample_tenant):
    """Fixture for a sample user."""
    user = entity_factory.create_user(tenant_id=sample_tenant.tenant_id)
    return user

@pytest.fixture
def sample_document(entity_factory, sample_tenant):
    """Fixture for a sample document."""
    document = entity_factory.create_document(tenant_id=sample_tenant.tenant_id)
    return document

@pytest.fixture
def sample_cart(entity_factory, sample_user, sample_tenant):
    """Fixture for a sample shopping cart."""
    cart = entity_factory.create_cart(
        user_id=sample_user.user_id,
        tenant_id=sample_tenant.tenant_id
    )
    return cart

@pytest.fixture
def sample_payment(entity_factory, sample_tenant, sample_user):
    """Fixture for a sample payment."""
    payment = entity_factory.create_payment(
        tenant_id=sample_tenant.tenant_id,
        user_id=sample_user.user_id
    )
    return payment

@pytest.fixture
def sample_router_request(entity_factory, sample_tenant, sample_user):
    """Fixture for a sample router request."""
    from tests._fixtures.factories import RouterTier
    request = entity_factory.create_router_request(
        tenant_id=sample_tenant.tenant_id,
        user_id=sample_user.user_id,
        tier=RouterTier.BALANCED
    )
    return request

@pytest.fixture
def sample_websocket_session(entity_factory, sample_tenant, sample_user):
    """Fixture for a sample WebSocket session."""
    from tests._fixtures.factories import WebSocketStatus
    session = entity_factory.create_websocket_session(
        tenant_id=sample_tenant.tenant_id,
        user_id=sample_user.user_id,
        status=WebSocketStatus.CONNECTED
    )
    return session

@pytest.fixture
def sample_workflow_execution(entity_factory, sample_tenant, sample_user):
    """Fixture for a sample workflow execution."""
    from tests._fixtures.factories import WorkflowStatus
    execution = entity_factory.create_workflow_execution(
        tenant_id=sample_tenant.tenant_id,
        user_id=sample_user.user_id,
        status=WorkflowStatus.PENDING
    )
    return execution

# API testing fixtures
@pytest.fixture
def api_headers(sample_user):
    """Fixture for API headers."""
    return test_helpers.create_headers(
        api_key=sample_user.api_key,
        tenant_id=sample_user.tenant_id,
        user_id=sample_user.user_id
    )

@pytest.fixture
def api_client(api_headers, mock_services):
    """Fixture for API client."""
    # This would be a real HTTP client in implementation
    class MockAPIClient:
        def __init__(self, headers, mock_services):
            self.headers = headers
            self.mock_services = mock_services
        
        async def post(self, url, data):
            # Mock implementation
            return {'status': 'success', 'data': data}
        
        async def get(self, url):
            # Mock implementation
            return {'status': 'success', 'data': {}}
    
    return MockAPIClient(api_headers, mock_services)

# LLM testing fixtures
@pytest.fixture
def llm_client(mock_llm_provider, test_mode):
    """Fixture for LLM client."""
    if test_mode in [TestMode.MOCK, TestMode.GOLDEN]:
        return mock_llm_provider
    else:
        # This would be a real LLM client in implementation
        class LiveLLMClient:
            def __init__(self):
                self.api_key = os.getenv('TEST_LLM_API_KEY')
                self.base_url = os.getenv('TEST_LLM_BASE_URL', 'https://api.openai.com/v1')
            
            async def generate(self, prompt, model="gpt-4", **kwargs):
                # Real implementation would call actual LLM API
                return {'response': 'Mock live response'}
        
        return LiveLLMClient()

# Database fixtures
@pytest.fixture
def database_client(mock_services):
    """Fixture for database client."""
    if mock_services['use_mock_database']:
        class MockDatabaseClient:
            async def query(self, sql, params=None):
                return [{'id': 1, 'data': 'mock'}]
            
            async def execute(self, sql, params=None):
                return {'affected_rows': 1}
        
        return MockDatabaseClient()
    else:
        # This would be a real database client in implementation
        class LiveDatabaseClient:
            def __init__(self):
                self.connection_string = os.getenv('TEST_DATABASE_URL')
            
            async def query(self, sql, params=None):
                # Real implementation would query actual database
                return [{'id': 1, 'data': 'live'}]
        
        return LiveDatabaseClient()

# Redis fixtures
@pytest.fixture
def redis_client(mock_services):
    """Fixture for Redis client."""
    if mock_services['use_mock_redis']:
        class MockRedisClient:
            def __init__(self):
                self.data = {}
            
            async def get(self, key):
                return self.data.get(key)
            
            async def set(self, key, value, expire=None):
                self.data[key] = value
                return True
        
        return MockRedisClient()
    else:
        # This would be a real Redis client in implementation
        class LiveRedisClient:
            def __init__(self):
                self.connection_string = os.getenv('TEST_REDIS_URL')
            
            async def get(self, key):
                # Real implementation would query actual Redis
                return 'mock_value'
        
        return LiveRedisClient()

# NATS fixtures
@pytest.fixture
def nats_client(mock_services):
    """Fixture for NATS client."""
    if mock_services['use_mock_nats']:
        class MockNATSClient:
            def __init__(self):
                self.messages = []
            
            async def publish(self, subject, data):
                self.messages.append({'subject': subject, 'data': data})
                return True
            
            async def subscribe(self, subject, callback):
                # Mock subscription
                return True
        
        return MockNATSClient()
    else:
        # This would be a real NATS client in implementation
        class LiveNATSClient:
            def __init__(self):
                self.connection_string = os.getenv('TEST_NATS_URL')
            
            async def publish(self, subject, data):
                # Real implementation would publish to actual NATS
                return True
        
        return LiveNATSClient()

# Performance testing fixtures
@pytest.fixture
def performance_monitor():
    """Fixture for performance monitoring."""
    import time
    
    class PerformanceMonitor:
        def __init__(self):
            self.start_time = None
            self.end_time = None
            self.metrics = {}
        
        def start(self):
            self.start_time = time.time()
        
        def stop(self):
            self.end_time = time.time()
            if self.start_time:
                self.metrics['duration_ms'] = (self.end_time - self.start_time) * 1000
        
        def record_metric(self, name, value):
            self.metrics[name] = value
        
        def get_metrics(self):
            return self.metrics.copy()
    
    return PerformanceMonitor()

# Security testing fixtures
@pytest.fixture
def security_validator():
    """Fixture for security validation."""
    import re
    
    class SecurityValidator:
        def __init__(self):
            self.pii_patterns = [
                r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
                r'\b\d{3}-\d{2}-\d{4}\b',  # SSN
                r'\b\d{3}-\d{3}-\d{4}\b',  # Phone
                r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',  # Credit card
            ]
        
        def validate_no_pii(self, text):
            """Validate that text contains no PII."""
            for pattern in self.pii_patterns:
                matches = re.findall(pattern, text)
                if matches:
                    raise AssertionError(f"PII detected: {matches}")
        
        def validate_https_only(self, urls):
            """Validate that all URLs use HTTPS."""
            for url in urls:
                if not url.startswith('https://'):
                    raise AssertionError(f"Non-HTTPS URL detected: {url}")
    
    return SecurityValidator()

# Cleanup fixtures
@pytest.fixture(autouse=True)
def cleanup_test_data():
    """Auto-cleanup fixture for test data."""
    yield
    # Cleanup after each test
    test_data_manager_instance.clear_tracking()

# Pytest configuration
def pytest_configure(config):
    """Configure pytest with production-grade settings."""
    # Add custom markers
    config.addinivalue_line("markers", "mock_only: test runs only in MOCK mode")
    config.addinivalue_line("markers", "golden_only: test runs only in GOLDEN mode")
    config.addinivalue_line("markers", "live_smoke_only: test runs only in LIVE_SMOKE mode")
    config.addinivalue_line("markers", "integration: integration test")
    config.addinivalue_line("markers", "e2e: end-to-end test")
    config.addinivalue_line("markers", "performance: performance test")
    config.addinivalue_line("markers", "security: security test")
    config.addinivalue_line("markers", "flaky: potentially flaky test")
    config.addinivalue_line("markers", "slow: slow running test")

def pytest_collection_modifyitems(config, items):
    """Modify test collection based on test mode."""
    mode = test_config.mode
    
    for item in items:
        # Skip tests based on mode constraints
        if mode == TestMode.LIVE_SMOKE:
            # Skip slow and integration tests in smoke mode
            if item.get_closest_marker("slow") or item.get_closest_marker("integration"):
                item.add_marker(pytest.mark.skip(reason="Skipped in LIVE_SMOKE mode"))
        elif mode == TestMode.MOCK:
            # Skip live smoke only tests in mock mode
            if item.get_closest_marker("live_smoke_only"):
                item.add_marker(pytest.mark.skip(reason="Skipped in MOCK mode"))
        elif mode == TestMode.GOLDEN:
            # Skip live smoke only tests in golden mode
            if item.get_closest_marker("live_smoke_only"):
                item.add_marker(pytest.mark.skip(reason="Skipped in GOLDEN mode"))

# Async support
@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()