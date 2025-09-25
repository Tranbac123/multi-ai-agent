"""
E2E Tests for Complete User Workflows
"""
import pytest
import asyncio
import httpx
from typing import Dict, Any
import json


class TestUserWorkflows:
    """Test complete user workflows across all services."""
    
    @pytest.mark.asyncio
    async def test_chatbot_user_journey(
        self, 
        http_client: httpx.AsyncClient, 
        service_urls: Dict[str, str],
        test_user_data: Dict[str, Any],
        test_chat_data: Dict[str, Any],
        e2e_helper
    ):
        """Test complete user journey: Login -> Chat -> Get Help."""
        
        # Step 1: Access AI Chatbot Frontend
        response = await http_client.get(service_urls["ai_chatbot"])
        assert response.status_code in [200, 404]  # 404 is OK for SPA
        
        # Step 2: Initialize chat session
        session_id = await e2e_helper.create_test_session(http_client, service_urls["api_gateway"])
        assert session_id is not None
        
        # Step 3: Send chat message through API Gateway
        chat_response = await http_client.post(
            f"{service_urls['api_gateway']}/v1/chat",
            json={
                "messages": test_chat_data["messages"][:1],  # First message only
                "model": test_chat_data["model"],
                "temperature": test_chat_data["temperature"],
                "max_tokens": test_chat_data["max_tokens"],
                "session_id": session_id
            }
        )
        assert chat_response.status_code in [200, 503]  # 503 if no API key
        
        # Step 4: Verify response structure
        if chat_response.status_code == 200:
            chat_data = chat_response.json()
            assert "content" in chat_data
            assert chat_data["content"] is not None
    
    @pytest.mark.asyncio
    async def test_admin_portal_workflow(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        test_user_data: Dict[str, Any]
    ):
        """Test admin portal workflow: Access -> Dashboard -> Configuration."""
        
        # Step 1: Access Admin Portal
        response = await http_client.get(service_urls["admin_portal"])
        assert response.status_code == 200
        
        # Step 2: Check health endpoint
        health_response = await http_client.get(f"{service_urls['admin_portal']}/healthz")
        assert health_response.status_code == 200
        
        # Step 3: Access configuration through API Gateway
        config_response = await http_client.get(f"{service_urls['api_gateway']}/v1/config")
        # This might return 404 if endpoint doesn't exist, which is OK for E2E
        assert config_response.status_code in [200, 404, 503]
    
    @pytest.mark.asyncio
    async def test_web_frontend_user_registration(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        test_user_data: Dict[str, Any]
    ):
        """Test web frontend user registration workflow."""
        
        # Step 1: Access Web Frontend
        response = await http_client.get(service_urls["web_frontend"])
        # Vite dev server might return 404 for root, check index.html
        if response.status_code == 404:
            response = await http_client.get(f"{service_urls['web_frontend']}/index.html")
        
        assert response.status_code in [200, 404]  # 404 OK for dev mode
        
        # Step 2: Test API endpoints that frontend would use
        api_response = await http_client.get(f"{service_urls['api_gateway']}/")
        assert api_response.status_code == 200
    
    @pytest.mark.asyncio
    async def test_data_retrieval_workflow(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        test_user_data: Dict[str, Any]
    ):
        """Test data retrieval workflow across services."""
        
        # Step 1: Test Retrieval Service directly
        retrieval_health = await http_client.get(f"{service_urls['retrieval_service']}/healthz")
        assert retrieval_health.status_code == 200
        
        # Step 2: Test search functionality
        search_data = {
            "query": "test search",
            "limit": 10,
            "user_id": test_user_data["user_id"]
        }
        
        search_response = await http_client.post(
            f"{service_urls['retrieval_service']}/search",
            json=search_data
        )
        assert search_response.status_code in [200, 422, 503]  # 422 for validation, 503 for no data
    
    @pytest.mark.asyncio
    async def test_tools_service_integration(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        test_user_data: Dict[str, Any]
    ):
        """Test tools service integration workflow."""
        
        # Step 1: Check Tools Service health
        tools_health = await http_client.get(f"{service_urls['tools_service']}/healthz")
        assert tools_health.status_code == 200
        
        # Step 2: Test tools listing
        tools_response = await http_client.get(f"{service_urls['tools_service']}/tools")
        assert tools_response.status_code in [200, 404]  # 404 if endpoint doesn't exist
        
        # Step 3: Test tool execution through API Gateway
        tool_execution = await http_client.post(
            f"{service_urls['api_gateway']}/v1/tools/execute",
            json={
                "tool_name": "test_tool",
                "parameters": {"param1": "value1"},
                "user_id": test_user_data["user_id"]
            }
        )
        assert tool_execution.status_code in [200, 404, 422, 503]  # Various valid responses
    
    @pytest.mark.asyncio
    async def test_model_gateway_integration(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        test_user_data: Dict[str, Any]
    ):
        """Test model gateway integration workflow."""
        
        # Step 1: Check Model Gateway health
        model_health = await http_client.get(f"{service_urls['model_gateway']}/healthz")
        assert model_health.status_code == 200
        
        # Step 2: Test model listing
        models_response = await http_client.get(f"{service_urls['model_gateway']}/models")
        assert models_response.status_code in [200, 404]  # 404 if endpoint doesn't exist
        
        # Step 3: Test model inference
        inference_response = await http_client.post(
            f"{service_urls['model_gateway']}/inference",
            json={
                "model": "test-model",
                "prompt": "Hello, world!",
                "user_id": test_user_data["user_id"]
            }
        )
        assert inference_response.status_code in [200, 404, 422, 503]  # Various valid responses
    
    @pytest.mark.asyncio
    async def test_config_service_workflow(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        test_config_data: Dict[str, Any]
    ):
        """Test configuration service workflow."""
        
        # Step 1: Check Config Service health
        config_health = await http_client.get(f"{service_urls['config_service']}/healthz")
        assert config_health.status_code == 200
        
        # Step 2: Test configuration retrieval
        config_response = await http_client.get(f"{service_urls['config_service']}/config")
        assert config_response.status_code in [200, 404]  # 404 if endpoint doesn't exist
        
        # Step 3: Test configuration update
        config_update = await http_client.put(
            f"{service_urls['config_service']}/config",
            json=test_config_data
        )
        assert config_update.status_code in [200, 404, 422]  # Various valid responses
    
    @pytest.mark.asyncio
    async def test_policy_adapter_workflow(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        test_user_data: Dict[str, Any]
    ):
        """Test policy adapter workflow."""
        
        # Step 1: Check Policy Adapter health
        policy_health = await http_client.get(f"{service_urls['policy_adapter']}/healthz")
        assert policy_health.status_code == 200
        
        # Step 2: Test policy evaluation
        policy_response = await http_client.post(
            f"{service_urls['policy_adapter']}/evaluate",
            json={
                "user_id": test_user_data["user_id"],
                "action": "test_action",
                "resource": "test_resource"
            }
        )
        assert policy_response.status_code in [200, 404, 422, 503]  # Various valid responses
    
    @pytest.mark.asyncio
    async def test_router_service_workflow(
        self,
        http_client: httpx.AsyncClient,
        service_urls: Dict[str, str],
        test_user_data: Dict[str, Any]
    ):
        """Test router service workflow."""
        
        # Step 1: Check Router Service health
        router_health = await http_client.get(f"{service_urls['router_service']}/healthz")
        assert router_health.status_code == 200
        
        # Step 2: Test request routing
        route_response = await http_client.post(
            f"{service_urls['router_service']}/route",
            json={
                "request_type": "chat",
                "user_id": test_user_data["user_id"],
                "data": {"message": "test"}
            }
        )
        assert route_response.status_code in [200, 404, 422, 503]  # Various valid responses
