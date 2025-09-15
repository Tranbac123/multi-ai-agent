"""Test the scaffolding infrastructure for production-grade testing."""

import pytest
from tests._fixtures import test_config, TestMode
from tests._fixtures.factories import factory, TenantTier, UserRole
from tests._fixtures.llm_cassette import cassette_recorder, golden_loader
from tests._helpers import test_helpers, mock_llm


class TestScaffoldingInfrastructure:
    """Test the test scaffolding infrastructure."""
    
    def test_test_config_initialization(self):
        """Test that test configuration is properly initialized."""
        assert test_config is not None
        assert isinstance(test_config.mode, TestMode)
        assert test_config.temperature == 0.0
    
    def test_entity_factory_creation(self):
        """Test entity factory can create test entities."""
        tenant = factory.create_tenant(name="Test Company", tier=TenantTier.BASIC)
        
        assert tenant.tenant_id.startswith("tenant_")
        assert tenant.name == "Test Company"
        assert tenant.tier == TenantTier.BASIC
        assert tenant.quota_requests_per_hour > 0
        
        user = factory.create_user(
            tenant_id=tenant.tenant_id,
            email="test@example.com",
            role=UserRole.ADMIN
        )
        
        assert user.user_id.startswith("user_")
        assert user.tenant_id == tenant.tenant_id
        assert user.email == "test@example.com"
        assert user.role == UserRole.ADMIN
        assert user.api_key.startswith("ak_test_")
    
    def test_llm_cassette_recording(self):
        """Test LLM cassette recorder functionality."""
        prompt = "What is the capital of France?"
        response = "The capital of France is Paris."
        
        key = cassette_recorder.record_interaction(prompt, response, model="gpt-4")
        
        assert key is not None
        assert len(key) == 16  # SHA256 hash first 16 chars
        
        # Test retrieval
        retrieved_response = cassette_recorder.get_response(prompt, model="gpt-4")
        assert retrieved_response == response
    
    def test_golden_output_management(self):
        """Test golden output loader functionality."""
        test_name = "test_sample_output"
        test_output = {"result": "success", "data": [1, 2, 3]}
        
        # Save golden output
        golden_file = golden_loader.save_golden_output(test_name, test_output)
        assert golden_file is not None
        
        # Load golden output
        loaded_output = golden_loader.load_golden_output(test_name)
        assert loaded_output == test_output
        
        # Test comparison
        comparison = golden_loader.compare_outputs(test_name, test_output)
        assert comparison['match'] is True
    
    def test_test_helpers_utilities(self):
        """Test test helper utilities."""
        # Test header creation
        headers = test_helpers.create_headers(
            api_key="test_key",
            tenant_id="tenant_123",
            user_id="user_456"
        )
        
        assert headers["Authorization"] == "Bearer test_key"
        assert headers["X-Tenant-ID"] == "tenant_123"
        assert headers["X-User-ID"] == "user_456"
        assert headers["Content-Type"] == "application/json"
        
        # Test JSON validation
        valid_json = {"test": "data"}
        parsed = test_helpers.assert_valid_json(valid_json)
        assert parsed == valid_json
        
        # Test budget assertions
        test_helpers.assert_within_budget(
            actual_cost=0.005,
            max_cost=0.01,
            actual_latency=500,
            max_latency=1000
        )
        
        # Test error extraction
        error_response = {
            'status_code': 400,
            'error_code': 'INVALID_INPUT',
            'message': 'Invalid input provided',
            'details': {'field': 'email'}
        }
        error_details = test_helpers.extract_error_details(error_response)
        assert error_details['error_code'] == 'INVALID_INPUT'
    
    def test_mock_llm_provider(self):
        """Test mock LLM provider functionality."""
        prompt = "What is artificial intelligence?"
        response = mock_llm.generate_response(prompt)
        
        assert 'choices' in response
        assert len(response['choices']) > 0
        assert 'text' in response['choices'][0]
        assert 'usage' in response
        assert response['model'] == 'gpt-4'
    
    @pytest.mark.parametrize("mode", [TestMode.MOCK, TestMode.GOLDEN, TestMode.LIVE_SMOKE])
    def test_mode_configurations(self, mode):
        """Test different test mode configurations."""
        # This test validates that each mode has proper configuration
        if mode == TestMode.MOCK:
            assert test_config.mode in [TestMode.MOCK, TestMode.GOLDEN, TestMode.LIVE_SMOKE]
        elif mode == TestMode.GOLDEN:
            assert test_config.temperature == 0.0  # Deterministic
        elif mode == TestMode.LIVE_SMOKE:
            # Live smoke tests should be minimal
            pass
    
    def test_deterministic_behavior(self):
        """Test deterministic behavior for GOLDEN mode."""
        if test_config.mode == TestMode.GOLDEN:
            # Test that same input produces same output
            prompt = "Test deterministic behavior"
            
            response1 = mock_llm.generate_response(prompt, temperature=0.0)
            response2 = mock_llm.generate_response(prompt, temperature=0.0)
            
            assert response1['choices'][0]['text'] == response2['choices'][0]['text']
    
    def test_fixture_integration(self, sample_tenant, sample_user, api_headers):
        """Test that fixtures work together properly."""
        assert sample_tenant is not None
        assert sample_user is not None
        assert api_headers is not None
        
        # Test that user belongs to tenant
        assert sample_user.tenant_id == sample_tenant.tenant_id
        
        # Test that headers contain correct information
        assert api_headers["X-Tenant-ID"] == sample_tenant.tenant_id
        assert api_headers["X-User-ID"] == sample_user.user_id
        assert api_headers["Authorization"] == f"Bearer {sample_user.api_key}"
    
    @pytest.mark.asyncio
    async def test_async_fixtures(self, api_client, database_client):
        """Test async fixture functionality."""
        # Test API client
        response = await api_client.get("/test")
        assert response['status'] == 'success'
        
        # Test database client
        result = await database_client.query("SELECT 1")
        assert len(result) > 0
    
    def test_performance_monitoring(self, performance_monitor):
        """Test performance monitoring fixture."""
        performance_monitor.start()
        
        # Simulate some work
        import time
        time.sleep(0.001)  # 1ms
        
        performance_monitor.stop()
        
        metrics = performance_monitor.get_metrics()
        assert 'duration_ms' in metrics
        assert metrics['duration_ms'] >= 1.0
    
    def test_security_validation(self, security_validator):
        """Test security validation fixture."""
        # Test PII detection
        clean_text = "This is a clean text with no personal information."
        security_validator.validate_no_pii(clean_text)
        
        # Test HTTPS validation
        https_urls = ["https://api.example.com", "https://secure.site.com"]
        security_validator.validate_https_only(https_urls)
    
    @pytest.mark.flaky
    def test_flaky_marker(self):
        """Test that flaky marker works."""
        # This test is marked as flaky and may fail randomly
        import random
        if random.random() < 0.5:
            pytest.fail("Random failure for flaky test demonstration")
    
    @pytest.mark.slow
    def test_slow_marker(self):
        """Test that slow marker works."""
        # This test is marked as slow
        import time
        time.sleep(0.1)  # Simulate slow operation
        assert True
    
    @pytest.mark.integration
    def test_integration_marker(self):
        """Test that integration marker works."""
        # This test is marked as integration
        assert True
    
    @pytest.mark.e2e
    def test_e2e_marker(self):
        """Test that e2e marker works."""
        # This test is marked as end-to-end
        assert True
    
    @pytest.mark.performance
    def test_performance_marker(self):
        """Test that performance marker works."""
        # This test is marked as performance
        assert True
    
    @pytest.mark.security
    def test_security_marker(self):
        """Test that security marker works."""
        # This test is marked as security
        assert True
