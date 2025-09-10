"""Integration tests for workflow execution."""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch
from hypothesis import given, strategies as st

from apps.orchestrator.core.workflow_executor import WorkflowExecutor
from apps.orchestrator.core.saga_orchestrator import SagaOrchestrator
from services.tools.email_adapter import EmailAdapter
from services.tools.payment_adapter import PaymentAdapter
from services.tools.crm_adapter import CRMAdapter


class TestWorkflowExecution:
    """Test workflow execution integration."""

    @pytest.mark.asyncio
    async def test_plan_route_work_verify_repair_commit_happy_path(self):
        """Test complete workflow happy path."""
        executor = WorkflowExecutor()
        
        # Mock workflow execution
        with patch.object(executor, '_execute_workflow') as mock_execute:
            mock_execute.return_value = {
                "success": True,
                "result": "Order processed successfully",
                "steps": ["plan", "route", "work", "verify", "commit"]
            }
            
            result = await executor.execute_workflow(
                workflow_name="order_processing",
                tenant_id="tenant_001",
                user_id="user_001",
                input_data={"order_id": "12345"}
            )
            
            assert result["success"] is True
            assert "Order processed successfully" in result["result"]
            assert "plan" in result["steps"]
            assert "commit" in result["steps"]

    @pytest.mark.asyncio
    async def test_workflow_repair_path(self):
        """Test workflow repair path."""
        executor = WorkflowExecutor()
        
        # Mock workflow with repair
        with patch.object(executor, '_execute_workflow') as mock_execute:
            mock_execute.return_value = {
                "success": False,
                "error": "Validation failed",
                "repair_required": True,
                "repair_steps": ["validate_input", "retry_processing"]
            }
            
            result = await executor.execute_workflow(
                workflow_name="order_processing",
                tenant_id="tenant_001",
                user_id="user_001",
                input_data={"order_id": "invalid"}
            )
            
            assert result["success"] is False
            assert result["repair_required"] is True
            assert "validate_input" in result["repair_steps"]

    @pytest.mark.asyncio
    async def test_workflow_dlq_path(self):
        """Test workflow DLQ path."""
        executor = WorkflowExecutor()
        
        # Mock workflow failure
        with patch.object(executor, '_execute_workflow') as mock_execute:
            mock_execute.side_effect = Exception("Critical failure")
            
            with patch.object(executor, '_send_to_dlq') as mock_dlq:
                mock_dlq.return_value = True
                
                result = await executor.execute_workflow(
                    workflow_name="order_processing",
                    tenant_id="tenant_001",
                    user_id="user_001",
                    input_data={"order_id": "12345"}
                )
                
                assert result["success"] is False
                assert result["dlq_sent"] is True
                mock_dlq.assert_called_once()

    @pytest.mark.asyncio
    async def test_workflow_retry_mechanism(self):
        """Test workflow retry mechanism."""
        executor = WorkflowExecutor(max_retries=3, retry_delay=0.1)
        
        call_count = 0
        
        async def failing_workflow():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise Exception("Temporary failure")
            return {"success": True, "result": "Success after retries"}
        
        with patch.object(executor, '_execute_workflow', side_effect=failing_workflow):
            result = await executor.execute_workflow(
                workflow_name="test_workflow",
                tenant_id="tenant_001",
                user_id="user_001",
                input_data={}
            )
            
            assert result["success"] is True
            assert call_count == 3

    @pytest.mark.asyncio
    async def test_workflow_timeout(self):
        """Test workflow timeout handling."""
        executor = WorkflowExecutor(timeout=0.1)
        
        async def slow_workflow():
            await asyncio.sleep(0.2)
            return {"success": True, "result": "Too slow"}
        
        with patch.object(executor, '_execute_workflow', side_effect=slow_workflow):
            result = await executor.execute_workflow(
                workflow_name="slow_workflow",
                tenant_id="tenant_001",
                user_id="user_001",
                input_data={}
            )
            
            assert result["success"] is False
            assert "timeout" in result["error"].lower()


class TestSagaOrchestration:
    """Test saga orchestration integration."""

    @pytest.mark.asyncio
    async def test_saga_success_path(self):
        """Test saga success path."""
        saga = SagaOrchestrator()
        
        # Mock successful operations
        email_adapter = EmailAdapter()
        payment_adapter = PaymentAdapter()
        crm_adapter = CRMAdapter()
        
        with patch.object(email_adapter, 'send_email') as mock_email:
            with patch.object(payment_adapter, 'process_payment') as mock_payment:
                with patch.object(crm_adapter, 'create_lead') as mock_crm:
                    
                    mock_email.return_value = {"success": True, "message_id": "email_001"}
                    mock_payment.return_value = {"success": True, "transaction_id": "txn_001"}
                    mock_crm.return_value = {"success": True, "lead_id": "lead_001"}
                    
                    # Execute saga
                    result = await saga.execute_saga([
                        (email_adapter.send_email, email_adapter.compensate),
                        (payment_adapter.process_payment, payment_adapter.compensate),
                        (crm_adapter.create_lead, crm_adapter.compensate)
                    ])
                    
                    assert result["success"] is True
                    assert len(result["results"]) == 3
                    assert result["results"][0]["message_id"] == "email_001"
                    assert result["results"][1]["transaction_id"] == "txn_001"
                    assert result["results"][2]["lead_id"] == "lead_001"

    @pytest.mark.asyncio
    async def test_saga_compensation_path(self):
        """Test saga compensation path."""
        saga = SagaOrchestrator()
        
        # Mock operations with failure
        email_adapter = EmailAdapter()
        payment_adapter = PaymentAdapter()
        crm_adapter = CRMAdapter()
        
        with patch.object(email_adapter, 'send_email') as mock_email:
            with patch.object(payment_adapter, 'process_payment') as mock_payment:
                with patch.object(crm_adapter, 'create_lead') as mock_crm:
                    with patch.object(payment_adapter, 'compensate') as mock_payment_comp:
                        with patch.object(email_adapter, 'compensate') as mock_email_comp:
                            
                            mock_email.return_value = {"success": True, "message_id": "email_001"}
                            mock_payment.return_value = {"success": True, "transaction_id": "txn_001"}
                            mock_crm.side_effect = Exception("CRM failure")
                            
                            mock_payment_comp.return_value = {"success": True, "refund_id": "refund_001"}
                            mock_email_comp.return_value = {"success": True, "cancelled": True}
                            
                            # Execute saga
                            result = await saga.execute_saga([
                                (email_adapter.send_email, email_adapter.compensate),
                                (payment_adapter.process_payment, payment_adapter.compensate),
                                (crm_adapter.create_lead, crm_adapter.compensate)
                            ])
                            
                            assert result["success"] is False
                            assert result["compensation_executed"] is True
                            
                            # Verify compensation was called in reverse order
                            mock_payment_comp.assert_called_once()
                            mock_email_comp.assert_called_once()

    @pytest.mark.asyncio
    async def test_saga_partial_compensation(self):
        """Test saga with partial compensation."""
        saga = SagaOrchestrator()
        
        # Mock operations with some having no compensation
        email_adapter = EmailAdapter()
        payment_adapter = PaymentAdapter()
        crm_adapter = CRMAdapter()
        
        with patch.object(email_adapter, 'send_email') as mock_email:
            with patch.object(payment_adapter, 'process_payment') as mock_payment:
                with patch.object(crm_adapter, 'create_lead') as mock_crm:
                    with patch.object(payment_adapter, 'compensate') as mock_payment_comp:
                        
                        mock_email.return_value = {"success": True, "message_id": "email_001"}
                        mock_payment.return_value = {"success": True, "transaction_id": "txn_001"}
                        mock_crm.side_effect = Exception("CRM failure")
                        
                        mock_payment_comp.return_value = {"success": True, "refund_id": "refund_001"}
                        
                        # Execute saga with partial compensation
                        result = await saga.execute_saga([
                            (email_adapter.send_email, None),  # No compensation
                            (payment_adapter.process_payment, payment_adapter.compensate),
                            (crm_adapter.create_lead, None)  # No compensation
                        ])
                        
                        assert result["success"] is False
                        assert result["compensation_executed"] is True
                        
                        # Only payment should be compensated
                        mock_payment_comp.assert_called_once()

    @pytest.mark.asyncio
    async def test_saga_timeout_handling(self):
        """Test saga timeout handling."""
        saga = SagaOrchestrator(timeout=0.1)
        
        async def slow_operation():
            await asyncio.sleep(0.2)
            return {"success": True}
        
        async def compensation():
            return {"success": True}
        
        result = await saga.execute_saga([
            (slow_operation, compensation)
        ])
        
        assert result["success"] is False
        assert "timeout" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_saga_compensation_failure(self):
        """Test saga when compensation fails."""
        saga = SagaOrchestrator()
        
        # Mock operations with compensation failure
        email_adapter = EmailAdapter()
        payment_adapter = PaymentAdapter()
        
        with patch.object(email_adapter, 'send_email') as mock_email:
            with patch.object(payment_adapter, 'process_payment') as mock_payment:
                with patch.object(payment_adapter, 'compensate') as mock_payment_comp:
                    with patch.object(email_adapter, 'compensate') as mock_email_comp:
                        
                        mock_email.return_value = {"success": True, "message_id": "email_001"}
                        mock_payment.side_effect = Exception("Payment failure")
                        
                        mock_payment_comp.side_effect = Exception("Compensation failed")
                        mock_email_comp.return_value = {"success": True, "cancelled": True}
                        
                        # Execute saga
                        result = await saga.execute_saga([
                            (email_adapter.send_email, email_adapter.compensate),
                            (payment_adapter.process_payment, payment_adapter.compensate)
                        ])
                        
                        assert result["success"] is False
                        assert result["compensation_executed"] is True
                        assert result["compensation_failures"] == 1


class TestWorkflowIntegration:
    """Test workflow integration scenarios."""

    @pytest.mark.asyncio
    async def test_multi_tenant_workflow_isolation(self):
        """Test multi-tenant workflow isolation."""
        executor = WorkflowExecutor()
        
        # Execute workflow for different tenants
        tenant1_result = await executor.execute_workflow(
            workflow_name="test_workflow",
            tenant_id="tenant_001",
            user_id="user_001",
            input_data={"data": "tenant1_data"}
        )
        
        tenant2_result = await executor.execute_workflow(
            workflow_name="test_workflow",
            tenant_id="tenant_002",
            user_id="user_001",
            input_data={"data": "tenant2_data"}
        )
        
        # Results should be isolated
        assert tenant1_result["tenant_id"] == "tenant_001"
        assert tenant2_result["tenant_id"] == "tenant_002"
        assert tenant1_result["input_data"]["data"] == "tenant1_data"
        assert tenant2_result["input_data"]["data"] == "tenant2_data"

    @pytest.mark.asyncio
    async def test_workflow_metrics_collection(self):
        """Test workflow metrics collection."""
        executor = WorkflowExecutor()
        
        with patch.object(executor, '_collect_metrics') as mock_metrics:
            mock_metrics.return_value = {
                "execution_time": 1.5,
                "cost": 0.05,
                "tokens_used": 100,
                "steps_executed": 5
            }
            
            result = await executor.execute_workflow(
                workflow_name="test_workflow",
                tenant_id="tenant_001",
                user_id="user_001",
                input_data={}
            )
            
            assert "metrics" in result
            assert result["metrics"]["execution_time"] == 1.5
            assert result["metrics"]["cost"] == 0.05

    @pytest.mark.asyncio
    async def test_workflow_audit_logging(self):
        """Test workflow audit logging."""
        executor = WorkflowExecutor()
        
        with patch.object(executor, '_log_audit_event') as mock_audit:
            mock_audit.return_value = True
            
            result = await executor.execute_workflow(
                workflow_name="test_workflow",
                tenant_id="tenant_001",
                user_id="user_001",
                input_data={}
            )
            
            # Verify audit logging was called
            assert mock_audit.called
            audit_call = mock_audit.call_args[0]
            assert audit_call[0]["workflow_name"] == "test_workflow"
            assert audit_call[0]["tenant_id"] == "tenant_001"
            assert audit_call[0]["user_id"] == "user_001"
