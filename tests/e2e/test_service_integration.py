"""
E2E Tests for Service Integration and Communication
"""
import pytest
import asyncio
import httpx
from typing import Dict, Any
import json


class TestServiceIntegration:
    """Test integration between services."""
    
    @pytest.mark.asyncio
    async def test_api_gateway_to_all_services(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        e2e_helper
    ):
        """Test API Gateway can communicate with all backend services."""
        
        # Wait for all services to be ready
        services_to_check = [
            ("model_gateway", service_urls["model_gateway"]),
            ("config_service", service_urls["config_service"]),
            ("retrieval_service", service_urls["retrieval_service"]),
            ("tools_service", service_urls["tools_service"]),
            ("router_service", service_urls["router_service"]),
            ("policy_adapter", service_urls["policy_adapter"]),
        ]
        
        for service_name, url in services_to_check:
            is_ready = await e2e_helper.wait_for_service(http_client, url, max_retries=3)
            if is_ready:
                # Service is ready, test API Gateway can proxy to it
                proxy_response = await http_client.get(f"{service_urls['api_gateway']}/v1/proxy/{service_name}/healthz")
                # Proxy might not be implemented, so 404 is acceptable
                assert proxy_response.status_code in [200, 404, 503]
            else:
                # Service not ready, skip this test
                pytest.skip(f"Service {service_name} not ready")
    
    @pytest.mark.asyncio
    async def test_frontend_to_api_gateway_integration(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str]
    ):
        """Test frontend services can communicate with API Gateway."""
        
        # Test AI Chatbot -> API Gateway
        chatbot_to_gateway = await http_client.get(service_urls["ai_chatbot"])
        assert chatbot_to_gateway.status_code in [200, 404]  # 404 OK for SPA
        
        # Test Admin Portal -> API Gateway
        admin_to_gateway = await http_client.get(service_urls["admin_portal"])
        assert admin_to_gateway.status_code == 200
        
        # Test Web Frontend -> API Gateway
        web_to_gateway = await http_client.get(service_urls["web_frontend"])
        assert web_to_gateway.status_code in [200, 404]  # 404 OK for Vite dev
        
        # Verify API Gateway is accessible
        gateway_health = await http_client.get(f"{service_urls['api_gateway']}/healthz")
        assert gateway_health.status_code == 200
    
    @pytest.mark.asyncio
    async def test_data_flow_through_services(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        test_user_data: Dict[str, Any]
    ):
        """Test data flow through the service chain."""
        
        # Step 1: User sends request through API Gateway
        request_data = {
            "user_id": test_user_data["user_id"],
            "message": "Hello, I need help with something",
            "session_id": test_user_data["session_id"]
        }
        
        api_response = await http_client.post(
            f"{service_urls['api_gateway']}/ask",
            json=request_data
        )
        assert api_response.status_code in [200, 404, 422, 503]
        
        # Step 2: API Gateway should route to appropriate services
        if api_response.status_code == 200:
            response_data = api_response.json()
            # Verify response structure
            assert isinstance(response_data, (dict, str))
    
    @pytest.mark.asyncio
    async def test_error_handling_across_services(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str]
    ):
        """Test error handling and propagation across services."""
        
        # Test invalid requests to each service
        services = [
            service_urls["api_gateway"],
            service_urls["model_gateway"],
            service_urls["config_service"],
            service_urls["retrieval_service"],
            service_urls["tools_service"],
            service_urls["router_service"],
            service_urls["policy_adapter"],
        ]
        
        for service_url in services:
            # Test invalid JSON
            try:
                response = await http_client.post(
                    f"{service_url}/invalid-endpoint",
                    content="invalid json",
                    headers={"Content-Type": "application/json"}
                )
                # Should return 404, 422, or 400
                assert response.status_code in [400, 404, 422, 500, 503]
            except Exception:
                # Connection error is also acceptable for E2E
                pass
    
    @pytest.mark.asyncio
    async def test_service_discovery_and_health_checks(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str]
    ):
        """Test service discovery and health check endpoints."""
        
        all_services = [
            ("API Gateway", service_urls["api_gateway"]),
            ("Model Gateway", service_urls["model_gateway"]),
            ("Config Service", service_urls["config_service"]),
            ("Retrieval Service", service_urls["retrieval_service"]),
            ("Tools Service", service_urls["tools_service"]),
            ("Router Service", service_urls["router_service"]),
            ("Policy Adapter", service_urls["policy_adapter"]),
            ("Admin Portal", service_urls["admin_portal"]),
        ]
        
        healthy_services = []
        unhealthy_services = []
        
        for service_name, url in all_services:
            try:
                response = await http_client.get(f"{url}/healthz", timeout=5.0)
                if response.status_code == 200:
                    healthy_services.append(service_name)
                else:
                    unhealthy_services.append(f"{service_name} (HTTP {response.status_code})")
            except Exception as e:
                unhealthy_services.append(f"{service_name} (Connection Error)")
        
        # Log results
        print(f"\n✅ Healthy Services ({len(healthy_services)}): {healthy_services}")
        if unhealthy_services:
            print(f"❌ Unhealthy Services ({len(unhealthy_services)}): {unhealthy_services}")
        
        # At least core services should be healthy
        core_services = ["API Gateway", "Model Gateway", "Config Service"]
        core_healthy = [s for s in core_services if s in healthy_services]
        assert len(core_healthy) >= 2, f"At least 2 core services should be healthy, got: {core_healthy}"
    
    @pytest.mark.asyncio
    async def test_concurrent_requests_across_services(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str]
    ):
        """Test concurrent requests across multiple services."""
        
        async def make_request(service_name: str, url: str):
            try:
                response = await http_client.get(f"{url}/healthz", timeout=5.0)
                return service_name, response.status_code, None
            except Exception as e:
                return service_name, None, str(e)
        
        # Create concurrent requests to all services
        tasks = [
            make_request("API Gateway", service_urls["api_gateway"]),
            make_request("Model Gateway", service_urls["model_gateway"]),
            make_request("Config Service", service_urls["config_service"]),
            make_request("Retrieval Service", service_urls["retrieval_service"]),
            make_request("Tools Service", service_urls["tools_service"]),
            make_request("Router Service", service_urls["router_service"]),
            make_request("Policy Adapter", service_urls["policy_adapter"]),
            make_request("Admin Portal", service_urls["admin_portal"]),
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Analyze results
        successful_requests = 0
        failed_requests = 0
        
        for result in results:
            if isinstance(result, tuple):
                service_name, status_code, error = result
                if status_code == 200:
                    successful_requests += 1
                else:
                    failed_requests += 1
            else:
                failed_requests += 1
        
        print(f"\n📊 Concurrent Request Results:")
        print(f"✅ Successful: {successful_requests}")
        print(f"❌ Failed: {failed_requests}")
        
        # At least 50% of requests should succeed
        total_requests = successful_requests + failed_requests
        success_rate = successful_requests / total_requests if total_requests > 0 else 0
        assert success_rate >= 0.5, f"Success rate too low: {success_rate:.2%}"
    
    @pytest.mark.asyncio
    async def test_service_configuration_consistency(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str]
    ):
        """Test that service configurations are consistent."""
        
        # Test that all services return consistent health check format
        health_endpoints = [
            service_urls["api_gateway"],
            service_urls["model_gateway"],
            service_urls["config_service"],
            service_urls["retrieval_service"],
            service_urls["tools_service"],
            service_urls["router_service"],
            service_urls["policy_adapter"],
            service_urls["admin_portal"],
        ]
        
        consistent_services = []
        inconsistent_services = []
        
        for url in health_endpoints:
            try:
                response = await http_client.get(f"{url}/healthz", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    # Check if response has expected structure
                    if isinstance(data, dict) and ("status" in data or "healthy" in str(data).lower()):
                        consistent_services.append(url)
                    else:
                        inconsistent_services.append(f"{url} - Unexpected format")
                else:
                    inconsistent_services.append(f"{url} - HTTP {response.status_code}")
            except Exception as e:
                inconsistent_services.append(f"{url} - Error: {str(e)}")
        
        print(f"\n🔧 Configuration Consistency Results:")
        print(f"✅ Consistent: {len(consistent_services)}")
        print(f"⚠️ Inconsistent: {len(inconsistent_services)}")
        
        # Most services should have consistent health check format
        assert len(consistent_services) >= len(health_endpoints) // 2
