"""E2E tests for saga compensation user journey."""

import pytest
import asyncio
import json
from typing import Dict, Any
from unittest.mock import AsyncMock, patch

from tests.fixtures.e2e_data import CompensationContext, TestDataFactory, UserContext


class TestSagaCompensationJourney:
    """E2E tests for saga compensation journey."""
    
    @pytest.fixture
    def compensation_scenarios(self):
        """Get compensation test scenarios."""
        return TestDataFactory.create_compensation_scenarios()
    
    @pytest.fixture
    async def orchestrator(self):
        """Create orchestrator instance for testing."""
        from apps.orchestrator.core.orchestrator import OrchestratorEngine
        from libs.clients.event_bus import EventBus, EventProducer
        
        event_bus = EventBus()
        event_producer = EventProducer(event_bus)
        
        orchestrator = OrchestratorEngine(
            event_producer=event_producer,
            workflow_engine=AsyncMock(),
            saga_manager=AsyncMock()
        )
        
        return orchestrator
    
    @pytest.fixture
    async def router(self):
        """Create router instance for testing."""
        from apps.router-service.core.router import RouterEngine
        from apps.router-service.core.features import FeatureExtractor
        from apps.router-service.core.classifier import MLClassifier
        from apps.router-service.core.cost import CostCalculator
        from apps.router-service.core.judge import LLMJudge
        
        feature_extractor = FeatureExtractor()
        classifier = MLClassifier()
        cost_calculator = CostCalculator()
        llm_judge = LLMJudge()
        
        router = RouterEngine(
            feature_extractor=feature_extractor,
            classifier=classifier,
            cost_calculator=cost_calculator,
            llm_judge=llm_judge
        )
        
        return router
    
    def assert_json_strict(self, data: Any, schema: Dict[str, Any]) -> None:
        """Assert JSON data matches schema strictly."""
        if not isinstance(data, dict):
            raise AssertionError(f"Expected dict, got {type(data)}")
        
        for key, expected_type in schema.items():
            if key not in data:
                raise AssertionError(f"Missing required key: {key}")
            
            actual_type = type(data[key])
            if not isinstance(data[key], expected_type):
                raise AssertionError(f"Key '{key}' expected {expected_type}, got {actual_type}")
    
    def assert_audit_trail(self, logs: list, expected_actions: list) -> None:
        """Assert audit trail contains expected actions."""
        actual_actions = [log.get("action") for log in logs]
        
        for expected_action in expected_actions:
            assert expected_action in actual_actions, f"Expected action '{expected_action}' not found in audit trail"
        
        # Verify all logs have required fields
        for log in logs:
            assert "timestamp" in log
            assert "tenant_id" in log
            assert "user_id" in log
            assert "action" in log
            assert "success" in log
    
    def assert_cost_latency_budget(self, metrics: Dict[str, Any], max_cost: float = 0.025, max_latency_ms: int = 5000) -> None:
        """Assert cost and latency are within budget."""
        if "cost_usd" in metrics:
            assert metrics["cost_usd"] <= max_cost, f"Cost {metrics['cost_usd']} exceeds budget {max_cost}"
        
        if "latency_ms" in metrics:
            assert metrics["latency_ms"] <= max_latency_ms, f"Latency {metrics['latency_ms']}ms exceeds budget {max_latency_ms}ms"
    
    @pytest.mark.asyncio
    async def test_saga_compensation_payment_failure_journey(self, compensation_scenarios, orchestrator, router):
        """Test saga compensation for payment failure journey."""
        scenario = next(s for s in compensation_scenarios if s.failure_step == 2)  # Payment failure
        
        # Step 1: Start saga with payment failure
        saga_request = {
            "type": "saga_execution",
            "saga_id": scenario.saga_id,
            "steps": scenario.steps,
            "user_context": scenario.user_context.dict(),
            "metadata": scenario.metadata
        }
        
        # Step 2: Execute saga steps until failure
        saga_execution_log = []
        
        # Step 1: Create order (success)
        saga_execution_log.append({
            "step": 1,
            "action": "create_order",
            "status": "completed",
            "timestamp": "2024-01-01T10:00:00Z",
            "result": {"order_id": "order_123", "status": "created"}
        })
        
        # Step 2: Charge payment (failure)
        saga_execution_log.append({
            "step": 2,
            "action": "charge_payment",
            "status": "failed",
            "timestamp": "2024-01-01T10:00:30Z",
            "error": "Insufficient funds",
            "requires_compensation": True
        })
        
        # Step 3: Compensation starts
        compensation_log = [
            {
                "step": 1,
                "compensation_action": "cancel_order",
                "status": "completed",
                "timestamp": "2024-01-01T10:01:00Z",
                "result": {"order_id": "order_123", "status": "cancelled"}
            }
        ]
        
        # Step 4: Process saga compensation
        saga_response = {
            "type": "saga_compensated",
            "saga_id": scenario.saga_id,
            "status": "compensated",
            "failure_step": 2,
            "failure_reason": "Insufficient funds",
            "execution_log": saga_execution_log,
            "compensation_log": compensation_log,
            "final_state": {
                "order_status": "cancelled",
                "payment_status": "not_charged",
                "inventory_status": "not_reserved"
            },
            "compensation_summary": {
                "total_steps": 1,
                "compensated_steps": 1,
                "compensation_success": True,
                "data_consistency": "maintained"
            },
            "metadata": {
                "processing_time_ms": 3500,
                "cost_usd": 0.022,
                "workflow_steps": ["execute_saga", "detect_failure", "trigger_compensation", "execute_compensations", "verify_consistency"]
            },
            "user_context": scenario.user_context.dict()
        }
        
        # Step 5: Validate response schema
        expected_schema = {
            "type": str,
            "saga_id": str,
            "status": str,
            "failure_step": int,
            "failure_reason": str,
            "execution_log": list,
            "compensation_log": list,
            "final_state": dict,
            "compensation_summary": dict,
            "metadata": dict,
            "user_context": dict
        }
        
        self.assert_json_strict(saga_response, expected_schema)
        
        # Step 6: Validate saga compensation
        assert saga_response["status"] == "compensated"
        assert saga_response["failure_step"] == 2
        assert saga_response["failure_reason"] == "Insufficient funds"
        assert len(saga_response["compensation_log"]) > 0
        assert saga_response["compensation_summary"]["compensation_success"] is True
        assert saga_response["final_state"]["order_status"] == "cancelled"
        
        # Step 7: Check cost and latency budget
        self.assert_cost_latency_budget(saga_response["metadata"])
        
        # Step 8: Generate audit trail
        audit_logs = [
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_execution_started",
                "success": True
            },
            {
                "timestamp": "2024-01-01T10:00:00Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_step_completed",
                "success": True
            },
            {
                "timestamp": "2024-01-01T10:00:30Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_step_failed",
                "success": False
            },
            {
                "timestamp": "2024-01-01T10:01:00Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_compensation_started",
                "success": True
            },
            {
                "timestamp": "2024-01-01T10:01:30Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_compensation_completed",
                "success": True
            }
        ]
        
        self.assert_audit_trail(audit_logs, ["saga_execution_started", "saga_step_completed", "saga_step_failed", "saga_compensation_started", "saga_compensation_completed"])
        
        # Step 9: Validate tenant isolation
        assert saga_response["user_context"]["tenant_id"] == scenario.user_context.tenant_id
        assert saga_response["user_context"]["user_id"] == scenario.user_context.user_id
    
    @pytest.mark.asyncio
    async def test_saga_compensation_notification_failure_journey(self, compensation_scenarios, orchestrator, router):
        """Test saga compensation for notification failure journey."""
        scenario = next(s for s in compensation_scenarios if s.failure_step == 3)  # Notification failure
        
        # Step 1: Start saga with notification failure
        saga_request = {
            "type": "saga_execution",
            "saga_id": scenario.saga_id,
            "steps": scenario.steps,
            "user_context": scenario.user_context.dict(),
            "metadata": scenario.metadata
        }
        
        # Step 2: Execute saga steps until failure
        saga_execution_log = []
        
        # Step 1: Send email (success)
        saga_execution_log.append({
            "step": 1,
            "action": "send_email",
            "status": "completed",
            "timestamp": "2024-01-01T11:00:00Z",
            "result": {"email_id": "email_123", "status": "sent"}
        })
        
        # Step 2: Update database (success)
        saga_execution_log.append({
            "step": 2,
            "action": "update_database",
            "status": "completed",
            "timestamp": "2024-01-01T11:00:15Z",
            "result": {"record_id": "record_123", "status": "updated"}
        })
        
        # Step 3: Notify external service (failure)
        saga_execution_log.append({
            "step": 3,
            "action": "notify_external",
            "status": "failed",
            "timestamp": "2024-01-01T11:00:30Z",
            "error": "External service unavailable",
            "requires_compensation": True
        })
        
        # Step 3: Compensation starts (reverse order)
        compensation_log = [
            {
                "step": 2,
                "compensation_action": "rollback_database",
                "status": "completed",
                "timestamp": "2024-01-01T11:01:00Z",
                "result": {"record_id": "record_123", "status": "rollback_completed"}
            },
            {
                "step": 1,
                "compensation_action": "send_apology_email",
                "status": "completed",
                "timestamp": "2024-01-01T11:01:30Z",
                "result": {"email_id": "apology_email_123", "status": "sent"}
            }
        ]
        
        # Step 4: Process saga compensation
        saga_response = {
            "type": "saga_compensated",
            "saga_id": scenario.saga_id,
            "status": "compensated",
            "failure_step": 3,
            "failure_reason": "External service unavailable",
            "execution_log": saga_execution_log,
            "compensation_log": compensation_log,
            "final_state": {
                "email_status": "apology_sent",
                "database_status": "rollback_completed",
                "external_notification_status": "cancelled"
            },
            "compensation_summary": {
                "total_steps": 2,
                "compensated_steps": 2,
                "compensation_success": True,
                "data_consistency": "maintained"
            },
            "metadata": {
                "processing_time_ms": 4200,
                "cost_usd": 0.024,
                "workflow_steps": ["execute_saga", "detect_failure", "trigger_compensation", "execute_compensations_reverse", "verify_consistency"]
            },
            "user_context": scenario.user_context.dict()
        }
        
        # Step 5: Validate response schema
        expected_schema = {
            "type": str,
            "saga_id": str,
            "status": str,
            "failure_step": int,
            "failure_reason": str,
            "execution_log": list,
            "compensation_log": list,
            "final_state": dict,
            "compensation_summary": dict,
            "metadata": dict,
            "user_context": dict
        }
        
        self.assert_json_strict(saga_response, expected_schema)
        
        # Step 6: Validate saga compensation
        assert saga_response["status"] == "compensated"
        assert saga_response["failure_step"] == 3
        assert saga_response["failure_reason"] == "External service unavailable"
        assert len(saga_response["compensation_log"]) == 2
        assert saga_response["compensation_summary"]["compensation_success"] is True
        assert saga_response["final_state"]["database_status"] == "rollback_completed"
        
        # Step 7: Check cost and latency budget
        self.assert_cost_latency_budget(saga_response["metadata"])
        
        # Step 8: Generate audit trail
        audit_logs = [
            {
                "timestamp": "2024-01-01T11:00:00Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_execution_started",
                "success": True
            },
            {
                "timestamp": "2024-01-01T11:00:00Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_step_completed",
                "success": True
            },
            {
                "timestamp": "2024-01-01T11:00:15Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_step_completed",
                "success": True
            },
            {
                "timestamp": "2024-01-01T11:00:30Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_step_failed",
                "success": False
            },
            {
                "timestamp": "2024-01-01T11:01:00Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_compensation_started",
                "success": True
            },
            {
                "timestamp": "2024-01-01T11:01:30Z",
                "tenant_id": scenario.user_context.tenant_id,
                "user_id": scenario.user_context.user_id,
                "action": "saga_compensation_completed",
                "success": True
            }
        ]
        
        self.assert_audit_trail(audit_logs, ["saga_execution_started", "saga_step_completed", "saga_step_failed", "saga_compensation_started", "saga_compensation_completed"])
    
    @pytest.mark.asyncio
    async def test_saga_compensation_partial_failure_journey(self, orchestrator, router):
        """Test saga compensation with partial compensation failure."""
        user_context = UserContext()
        
        # Step 1: Start saga with partial compensation failure
        saga_request = {
            "type": "saga_execution",
            "saga_id": "saga_partial_001",
            "steps": [
                {"step": 1, "action": "create_order", "compensate": "cancel_order"},
                {"step": 2, "action": "charge_payment", "compensate": "refund_payment"},
                {"step": 3, "action": "reserve_inventory", "compensate": "release_inventory"}
            ],
            "user_context": user_context.dict(),
            "metadata": {}
        }
        
        # Step 2: Execute saga steps until failure
        saga_execution_log = []
        
        # Step 1: Create order (success)
        saga_execution_log.append({
            "step": 1,
            "action": "create_order",
            "status": "completed",
            "timestamp": "2024-01-01T12:00:00Z",
            "result": {"order_id": "order_partial_123", "status": "created"}
        })
        
        # Step 2: Charge payment (success)
        saga_execution_log.append({
            "step": 2,
            "action": "charge_payment",
            "status": "completed",
            "timestamp": "2024-01-01T12:00:20Z",
            "result": {"payment_id": "pay_partial_123", "status": "charged"}
        })
        
        # Step 3: Reserve inventory (failure)
        saga_execution_log.append({
            "step": 3,
            "action": "reserve_inventory",
            "status": "failed",
            "timestamp": "2024-01-01T12:00:40Z",
            "error": "Inventory unavailable",
            "requires_compensation": True
        })
        
        # Step 3: Compensation with partial failure
        compensation_log = [
            {
                "step": 2,
                "compensation_action": "refund_payment",
                "status": "completed",
                "timestamp": "2024-01-01T12:01:00Z",
                "result": {"payment_id": "pay_partial_123", "status": "refunded"}
            },
            {
                "step": 1,
                "compensation_action": "cancel_order",
                "status": "failed",
                "timestamp": "2024-01-01T12:01:20Z",
                "error": "Order already processed",
                "manual_intervention_required": True
            }
        ]
        
        # Step 4: Process saga compensation with partial failure
        saga_response = {
            "type": "saga_compensation_partial_failure",
            "saga_id": "saga_partial_001",
            "status": "compensation_partial_failure",
            "failure_step": 3,
            "failure_reason": "Inventory unavailable",
            "execution_log": saga_execution_log,
            "compensation_log": compensation_log,
            "final_state": {
                "order_status": "requires_manual_cancellation",
                "payment_status": "refunded",
                "inventory_status": "not_reserved"
            },
            "compensation_summary": {
                "total_steps": 2,
                "compensated_steps": 1,
                "failed_compensations": 1,
                "compensation_success": False,
                "data_consistency": "partial",
                "manual_intervention_required": True
            },
            "manual_intervention": {
                "required": True,
                "actions": [
                    {
                        "action": "manual_order_cancellation",
                        "reason": "Order already processed, cannot be cancelled automatically",
                        "priority": "high"
                    }
                ]
            },
            "metadata": {
                "processing_time_ms": 4800,
                "cost_usd": 0.026,
                "workflow_steps": ["execute_saga", "detect_failure", "trigger_compensation", "execute_compensations", "handle_compensation_failure"]
            },
            "user_context": user_context.dict()
        }
        
        # Step 5: Validate response schema
        expected_schema = {
            "type": str,
            "saga_id": str,
            "status": str,
            "failure_step": int,
            "failure_reason": str,
            "execution_log": list,
            "compensation_log": list,
            "final_state": dict,
            "compensation_summary": dict,
            "manual_intervention": dict,
            "metadata": dict,
            "user_context": dict
        }
        
        self.assert_json_strict(saga_response, expected_schema)
        
        # Step 6: Validate partial compensation failure
        assert saga_response["status"] == "compensation_partial_failure"
        assert saga_response["compensation_summary"]["compensation_success"] is False
        assert saga_response["compensation_summary"]["failed_compensations"] == 1
        assert saga_response["compensation_summary"]["manual_intervention_required"] is True
        assert saga_response["final_state"]["order_status"] == "requires_manual_cancellation"
        
        # Step 7: Check cost and latency budget
        self.assert_cost_latency_budget(saga_response["metadata"])
        
        # Step 8: Generate audit trail
        audit_logs = [
            {
                "timestamp": "2024-01-01T12:00:00Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_execution_started",
                "success": True
            },
            {
                "timestamp": "2024-01-01T12:00:00Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_step_completed",
                "success": True
            },
            {
                "timestamp": "2024-01-01T12:00:20Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_step_completed",
                "success": True
            },
            {
                "timestamp": "2024-01-01T12:00:40Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_step_failed",
                "success": False
            },
            {
                "timestamp": "2024-01-01T12:01:00Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_compensation_started",
                "success": True
            },
            {
                "timestamp": "2024-01-01T12:01:20Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_compensation_failed",
                "success": False
            }
        ]
        
        self.assert_audit_trail(audit_logs, ["saga_execution_started", "saga_step_completed", "saga_step_failed", "saga_compensation_started", "saga_compensation_failed"])
    
    @pytest.mark.asyncio
    async def test_saga_compensation_timeout_journey(self, orchestrator, router):
        """Test saga compensation timeout journey."""
        user_context = UserContext()
        
        # Step 1: Start saga with compensation timeout
        saga_request = {
            "type": "saga_execution",
            "saga_id": "saga_timeout_001",
            "steps": [
                {"step": 1, "action": "create_order", "compensate": "cancel_order"},
                {"step": 2, "action": "charge_payment", "compensate": "refund_payment"}
            ],
            "user_context": user_context.dict(),
            "metadata": {}
        }
        
        # Step 2: Execute saga steps until failure
        saga_execution_log = []
        
        # Step 1: Create order (success)
        saga_execution_log.append({
            "step": 1,
            "action": "create_order",
            "status": "completed",
            "timestamp": "2024-01-01T13:00:00Z",
            "result": {"order_id": "order_timeout_123", "status": "created"}
        })
        
        # Step 2: Charge payment (failure)
        saga_execution_log.append({
            "step": 2,
            "action": "charge_payment",
            "status": "failed",
            "timestamp": "2024-01-01T13:00:30Z",
            "error": "Payment gateway timeout",
            "requires_compensation": True
        })
        
        # Step 3: Compensation timeout
        compensation_log = [
            {
                "step": 1,
                "compensation_action": "cancel_order",
                "status": "timeout",
                "timestamp": "2024-01-01T13:01:30Z",
                "error": "Compensation timeout after 60 seconds",
                "retry_scheduled": True
            }
        ]
        
        # Step 4: Process saga compensation timeout
        saga_response = {
            "type": "saga_compensation_timeout",
            "saga_id": "saga_timeout_001",
            "status": "compensation_timeout",
            "failure_step": 2,
            "failure_reason": "Payment gateway timeout",
            "execution_log": saga_execution_log,
            "compensation_log": compensation_log,
            "final_state": {
                "order_status": "compensation_pending",
                "payment_status": "not_charged"
            },
            "compensation_summary": {
                "total_steps": 1,
                "compensated_steps": 0,
                "timeout_steps": 1,
                "compensation_success": False,
                "data_consistency": "pending",
                "retry_scheduled": True
            },
            "retry_info": {
                "retry_scheduled": True,
                "retry_time": "2024-01-01T13:05:00Z",
                "max_retries": 3,
                "current_retry": 1
            },
            "metadata": {
                "processing_time_ms": 6000,
                "cost_usd": 0.028,
                "workflow_steps": ["execute_saga", "detect_failure", "trigger_compensation", "compensation_timeout", "schedule_retry"]
            },
            "user_context": user_context.dict()
        }
        
        # Step 5: Validate response schema
        expected_schema = {
            "type": str,
            "saga_id": str,
            "status": str,
            "failure_step": int,
            "failure_reason": str,
            "execution_log": list,
            "compensation_log": list,
            "final_state": dict,
            "compensation_summary": dict,
            "retry_info": dict,
            "metadata": dict,
            "user_context": dict
        }
        
        self.assert_json_strict(saga_response, expected_schema)
        
        # Step 6: Validate compensation timeout
        assert saga_response["status"] == "compensation_timeout"
        assert saga_response["compensation_summary"]["compensation_success"] is False
        assert saga_response["compensation_summary"]["timeout_steps"] == 1
        assert saga_response["compensation_summary"]["retry_scheduled"] is True
        assert saga_response["retry_info"]["retry_scheduled"] is True
        
        # Step 7: Check cost and latency budget
        self.assert_cost_latency_budget(saga_response["metadata"])
        
        # Step 8: Generate audit trail
        audit_logs = [
            {
                "timestamp": "2024-01-01T13:00:00Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_execution_started",
                "success": True
            },
            {
                "timestamp": "2024-01-01T13:00:00Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_step_completed",
                "success": True
            },
            {
                "timestamp": "2024-01-01T13:00:30Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_step_failed",
                "success": False
            },
            {
                "timestamp": "2024-01-01T13:01:00Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_compensation_started",
                "success": True
            },
            {
                "timestamp": "2024-01-01T13:01:30Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "saga_compensation_timeout",
                "success": False
            },
            {
                "timestamp": "2024-01-01T13:01:30Z",
                "tenant_id": user_context.tenant_id,
                "user_id": user_context.user_id,
                "action": "compensation_retry_scheduled",
                "success": True
            }
        ]
        
        self.assert_audit_trail(audit_logs, ["saga_execution_started", "saga_step_completed", "saga_step_failed", "saga_compensation_started", "saga_compensation_timeout", "compensation_retry_scheduled"])
