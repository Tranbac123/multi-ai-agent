"""Test resilient tools functionality."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4

from apps.orchestrator.core.resilient_tools import (
    ResilientCRMTool,
    ResilientOrderTool,
    ResilientPaymentTool,
    ResilientLLMTool,
    ResilientToolManager,
)


class TestResilientCRMTool:
    """Test ResilientCRMTool functionality."""

    @pytest.fixture
    def crm_tool(self):
        """Create ResilientCRMTool instance."""
        return ResilientCRMTool()

    @pytest.mark.asyncio
    async def test_create_customer_success(self, crm_tool):
        """Test successful customer creation."""
        customer_data = {
            "name": "John Doe",
            "email": "john@example.com",
            "phone": "123-456-7890",
        }
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"id": "123", "status": "created"}
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await crm_tool.create_customer(customer_data, tenant_id)

            assert result["id"] == "123"
            assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_create_customer_failure(self, crm_tool):
        """Test customer creation failure."""
        customer_data = {"name": "John Doe"}
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("API Error")
            )

            with pytest.raises(Exception, match="API Error"):
                await crm_tool.create_customer(customer_data, tenant_id)

    @pytest.mark.asyncio
    async def test_search_customers_success(self, crm_tool):
        """Test successful customer search."""
        query = "John"
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {
                "customers": [
                    {"id": "1", "name": "John Doe"},
                    {"id": "2", "name": "John Smith"},
                ]
            }
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await crm_tool.search_customers(query, tenant_id)

            assert len(result) == 2
            assert result[0]["name"] == "John Doe"
            assert result[1]["name"] == "John Smith"

    @pytest.mark.asyncio
    async def test_search_customers_empty(self, crm_tool):
        """Test customer search with no results."""
        query = "Nonexistent"
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"customers": []}
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await crm_tool.search_customers(query, tenant_id)

            assert len(result) == 0


class TestResilientOrderTool:
    """Test ResilientOrderTool functionality."""

    @pytest.fixture
    def order_tool(self):
        """Create ResilientOrderTool instance."""
        return ResilientOrderTool()

    @pytest.mark.asyncio
    async def test_create_order_success(self, order_tool):
        """Test successful order creation."""
        order_data = {
            "customer_id": "123",
            "items": [{"product_id": "456", "quantity": 2}],
            "total": 100.0,
        }
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"order_id": "789", "status": "created"}
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await order_tool.create_order(order_data, tenant_id)

            assert result["order_id"] == "789"
            assert result["status"] == "created"

    @pytest.mark.asyncio
    async def test_get_order_status_success(self, order_tool):
        """Test successful order status retrieval."""
        order_id = "789"
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {
                "order_id": order_id,
                "status": "processing",
                "updated_at": "2024-01-15T10:00:00Z",
            }
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_response
            )

            result = await order_tool.get_order_status(order_id, tenant_id)

            assert result["order_id"] == order_id
            assert result["status"] == "processing"

    @pytest.mark.asyncio
    async def test_create_order_failure(self, order_tool):
        """Test order creation failure."""
        order_data = {"invalid": "data"}
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("Order creation failed")
            )

            with pytest.raises(Exception, match="Order creation failed"):
                await order_tool.create_order(order_data, tenant_id)


class TestResilientPaymentTool:
    """Test ResilientPaymentTool functionality."""

    @pytest.fixture
    def payment_tool(self):
        """Create ResilientPaymentTool instance."""
        return ResilientPaymentTool()

    @pytest.mark.asyncio
    async def test_process_payment_success(self, payment_tool):
        """Test successful payment processing."""
        payment_data = {
            "amount": 100.0,
            "currency": "USD",
            "card_token": "tok_123",
        }
        tenant_id = uuid4()

        with patch.object(payment_tool, "_authorize_payment") as mock_auth, \
             patch.object(payment_tool, "_capture_payment") as mock_capture:
            
            mock_auth.return_value = {"auth_id": "auth_123", "status": "authorized"}
            mock_capture.return_value = {"capture_id": "cap_123", "status": "captured"}

            result = await payment_tool.process_payment(payment_data, tenant_id)

            assert result["status"] == "success"
            assert "saga_id" in result

    @pytest.mark.asyncio
    async def test_process_payment_failure(self, payment_tool):
        """Test payment processing failure."""
        payment_data = {
            "amount": 100.0,
            "currency": "USD",
            "card_token": "invalid_token",
        }
        tenant_id = uuid4()

        with patch.object(payment_tool, "_authorize_payment") as mock_auth:
            mock_auth.side_effect = Exception("Authorization failed")

            result = await payment_tool.process_payment(payment_data, tenant_id)

            assert result["status"] == "failed"
            assert "error" in result

    @pytest.mark.asyncio
    async def test_authorize_payment_success(self, payment_tool):
        """Test successful payment authorization."""
        payment_data = {"amount": 100.0, "currency": "USD"}
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"auth_id": "auth_123", "status": "authorized"}
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await payment_tool._authorize_payment(payment_data, tenant_id)

            assert result["auth_id"] == "auth_123"
            assert result["status"] == "authorized"

    @pytest.mark.asyncio
    async def test_capture_payment_success(self, payment_tool):
        """Test successful payment capture."""
        payment_data = {"amount": 100.0, "currency": "USD"}
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"capture_id": "cap_123", "status": "captured"}
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await payment_tool._capture_payment(payment_data, tenant_id)

            assert result["capture_id"] == "cap_123"
            assert result["status"] == "captured"

    @pytest.mark.asyncio
    async def test_void_payment_success(self, payment_tool):
        """Test successful payment void."""
        payment_data = {"auth_id": "auth_123"}
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"void_id": "void_123", "status": "voided"}
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await payment_tool._void_payment(payment_data, tenant_id)

            assert result["void_id"] == "void_123"
            assert result["status"] == "voided"

    @pytest.mark.asyncio
    async def test_refund_payment_success(self, payment_tool):
        """Test successful payment refund."""
        payment_data = {"capture_id": "cap_123", "amount": 100.0}
        tenant_id = uuid4()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {"refund_id": "ref_123", "status": "refunded"}
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await payment_tool._refund_payment(payment_data, tenant_id)

            assert result["refund_id"] == "ref_123"
            assert result["status"] == "refunded"


class TestResilientLLMTool:
    """Test ResilientLLMTool functionality."""

    @pytest.fixture
    def llm_tool(self):
        """Create ResilientLLMTool instance."""
        return ResilientLLMTool("test-api-key")

    @pytest.mark.asyncio
    async def test_generate_completion_success(self, llm_tool):
        """Test successful completion generation."""
        prompt = "What is the capital of France?"
        model = "gpt-4"
        max_tokens = 100
        temperature = 0.7

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {
                "choices": [
                    {
                        "message": {
                            "content": "The capital of France is Paris."
                        }
                    }
                ],
                "usage": {"total_tokens": 25},
            }
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await llm_tool.generate_completion(
                prompt, model, max_tokens, temperature
            )

            assert "choices" in result
            assert len(result["choices"]) == 1
            assert "Paris" in result["choices"][0]["message"]["content"]

    @pytest.mark.asyncio
    async def test_generate_completion_failure(self, llm_tool):
        """Test completion generation failure."""
        prompt = "Test prompt"

        with patch("httpx.AsyncClient") as mock_client:
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                side_effect=Exception("API Error")
            )

            with pytest.raises(Exception, match="API Error"):
                await llm_tool.generate_completion(prompt)

    @pytest.mark.asyncio
    async def test_generate_completion_with_defaults(self, llm_tool):
        """Test completion generation with default parameters."""
        prompt = "Test prompt"

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {
                "choices": [{"message": {"content": "Test response"}}],
                "usage": {"total_tokens": 10},
            }
            mock_response.raise_for_status.return_value = None
            
            mock_client.return_value.__aenter__.return_value.post = AsyncMock(
                return_value=mock_response
            )

            result = await llm_tool.generate_completion(prompt)

            assert "choices" in result
            assert result["choices"][0]["message"]["content"] == "Test response"


class TestResilientToolManager:
    """Test ResilientToolManager functionality."""

    @pytest.fixture
    def tool_manager(self):
        """Create ResilientToolManager instance."""
        return ResilientToolManager()

    def test_initialization(self, tool_manager):
        """Test tool manager initialization."""
        assert tool_manager.crm_tool is not None
        assert tool_manager.order_tool is not None
        assert tool_manager.payment_tool is not None
        assert tool_manager.llm_tool is None  # Not initialized yet

    def test_initialize_llm_tool(self, tool_manager):
        """Test LLM tool initialization."""
        api_key = "test-api-key"
        tool_manager.initialize_llm_tool(api_key)

        assert tool_manager.llm_tool is not None
        assert tool_manager.llm_tool.api_key == api_key

    def test_get_all_stats(self, tool_manager):
        """Test getting statistics for all tools."""
        # Mock adapter stats
        tool_manager.crm_tool.adapter.get_stats = Mock(return_value={"requests": 10})
        tool_manager.order_tool.adapter.get_stats = Mock(return_value={"requests": 5})
        tool_manager.payment_tool.adapter.get_stats = Mock(return_value={"requests": 3})

        stats = tool_manager.get_all_stats()

        assert "crm_tool" in stats
        assert "order_tool" in stats
        assert "payment_tool" in stats
        assert "llm_tool" not in stats  # Not initialized

        assert stats["crm_tool"]["requests"] == 10
        assert stats["order_tool"]["requests"] == 5
        assert stats["payment_tool"]["requests"] == 3

    def test_get_all_stats_with_llm(self, tool_manager):
        """Test getting statistics including LLM tool."""
        # Initialize LLM tool
        tool_manager.initialize_llm_tool("test-key")
        tool_manager.llm_tool.adapter.get_stats = Mock(return_value={"requests": 15})

        # Mock other adapter stats
        tool_manager.crm_tool.adapter.get_stats = Mock(return_value={"requests": 10})
        tool_manager.order_tool.adapter.get_stats = Mock(return_value={"requests": 5})
        tool_manager.payment_tool.adapter.get_stats = Mock(return_value={"requests": 3})

        stats = tool_manager.get_all_stats()

        assert "llm_tool" in stats
        assert stats["llm_tool"]["requests"] == 15

    def test_reset_all_stats(self, tool_manager):
        """Test resetting statistics for all tools."""
        # Mock reset methods
        tool_manager.crm_tool.adapter.reset_stats = Mock()
        tool_manager.order_tool.adapter.reset_stats = Mock()
        tool_manager.payment_tool.adapter.reset_stats = Mock()

        tool_manager.reset_all_stats()

        tool_manager.crm_tool.adapter.reset_stats.assert_called_once()
        tool_manager.order_tool.adapter.reset_stats.assert_called_once()
        tool_manager.payment_tool.adapter.reset_stats.assert_called_once()

    def test_reset_all_stats_with_llm(self, tool_manager):
        """Test resetting statistics including LLM tool."""
        # Initialize LLM tool
        tool_manager.initialize_llm_tool("test-key")
        tool_manager.llm_tool.adapter.reset_stats = Mock()

        # Mock other reset methods
        tool_manager.crm_tool.adapter.reset_stats = Mock()
        tool_manager.order_tool.adapter.reset_stats = Mock()
        tool_manager.payment_tool.adapter.reset_stats = Mock()

        tool_manager.reset_all_stats()

        tool_manager.llm_tool.adapter.reset_stats.assert_called_once()

    @pytest.mark.asyncio
    async def test_end_to_end_workflow(self, tool_manager):
        """Test end-to-end workflow with multiple tools."""
        # Initialize LLM tool
        tool_manager.initialize_llm_tool("test-key")

        tenant_id = uuid4()

        # Mock successful operations
        with patch.object(tool_manager.crm_tool, "create_customer") as mock_create_customer, \
             patch.object(tool_manager.order_tool, "create_order") as mock_create_order, \
             patch.object(tool_manager.payment_tool, "process_payment") as mock_process_payment, \
             patch.object(tool_manager.llm_tool, "generate_completion") as mock_generate:

            mock_create_customer.return_value = {"id": "123", "status": "created"}
            mock_create_order.return_value = {"order_id": "789", "status": "created"}
            mock_process_payment.return_value = {"status": "success", "saga_id": "saga_123"}
            mock_generate.return_value = {"choices": [{"message": {"content": "Generated content"}}]}

            # Execute workflow
            customer_result = await tool_manager.crm_tool.create_customer(
                {"name": "John Doe", "email": "john@example.com"}, tenant_id
            )
            order_result = await tool_manager.order_tool.create_order(
                {"customer_id": customer_result["id"], "items": []}, tenant_id
            )
            payment_result = await tool_manager.payment_tool.process_payment(
                {"amount": 100.0, "currency": "USD"}, tenant_id
            )
            llm_result = await tool_manager.llm_tool.generate_completion(
                "Generate order confirmation"
            )

            # Verify results
            assert customer_result["id"] == "123"
            assert order_result["order_id"] == "789"
            assert payment_result["status"] == "success"
            assert "Generated content" in llm_result["choices"][0]["message"]["content"]

            # Verify all methods were called
            mock_create_customer.assert_called_once()
            mock_create_order.assert_called_once()
            mock_process_payment.assert_called_once()
            mock_generate.assert_called_once()
