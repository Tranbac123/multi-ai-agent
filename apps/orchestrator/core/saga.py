"""Saga manager for distributed transaction coordination."""

import asyncio
from typing import Dict, Any, Optional, List
from uuid import UUID, uuid4
import structlog
from opentelemetry import trace

from libs.contracts.agent import AgentRun
from libs.contracts.tool import ToolCall, ToolResult
from libs.contracts.error import ErrorSpec, ErrorCode
from .event_store import EventStore

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class SagaManager:
    """Manages distributed transactions using saga patterns."""

    def __init__(self):
        self.active_sagas: Dict[UUID, Saga] = {}
        self.compensation_handlers: Dict[str, callable] = {}
        self._ready = False

    def initialize(self):
        """Initialize saga manager."""
        try:
            # Register compensation handlers
            self._register_compensation_handlers()

            self._ready = True
            logger.info("Saga manager initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize saga manager", error=str(e))
            self._ready = False

    def is_ready(self) -> bool:
        """Check if saga manager is ready."""
        return self._ready

    def _register_compensation_handlers(self):
        """Register compensation handlers for different operations."""
        self.compensation_handlers = {
            "email_send": self._compensate_email_send,
            "payment_process": self._compensate_payment_process,
            "crm_update": self._compensate_crm_update,
            "order_create": self._compensate_order_create,
            "notification_send": self._compensate_notification_send,
        }

    async def start_saga(self, run_id: UUID, operations: List[Dict[str, Any]]) -> UUID:
        """Start new saga."""
        with tracer.start_as_current_span("start_saga") as span:
            span.set_attribute("run_id", str(run_id))
            span.set_attribute("operations_count", len(operations))

            try:
                saga_id = uuid4()

                # Create saga
                saga = Saga(
                    saga_id=saga_id,
                    run_id=run_id,
                    operations=operations,
                    status="pending",
                )

                # Store saga
                self.active_sagas[saga_id] = saga

                # Start saga execution
                asyncio.create_task(self._execute_saga(saga))

                logger.info(
                    "Saga started",
                    saga_id=str(saga_id),
                    run_id=str(run_id),
                    operations_count=len(operations),
                )

                return saga_id

            except Exception as e:
                logger.error("Failed to start saga", run_id=str(run_id), error=str(e))
                raise

    async def _execute_saga(self, saga: "Saga") -> None:
        """Execute saga operations."""
        try:
            saga.status = "running"

            # Execute operations in sequence
            for i, operation in enumerate(saga.operations):
                try:
                    # Execute operation
                    result = await self._execute_operation(operation)

                    # Update saga state
                    saga.completed_operations.append(
                        {"index": i, "operation": operation, "result": result}
                    )

                except Exception as e:
                    logger.error(
                        "Operation failed, starting compensation",
                        saga_id=str(saga.saga_id),
                        operation_index=i,
                        error=str(e),
                    )

                    # Start compensation
                    await self._compensate_saga(saga, i)
                    return

            # All operations completed successfully
            saga.status = "completed"

            logger.info(
                "Saga completed successfully",
                saga_id=str(saga.saga_id),
                run_id=str(saga.run_id),
            )

        except Exception as e:
            logger.error(
                "Saga execution failed", saga_id=str(saga.saga_id), error=str(e)
            )

            saga.status = "failed"
            saga.error = str(e)

    async def _execute_operation(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        """Execute individual operation."""
        operation_type = operation.get("type")
        operation_data = operation.get("data", {})

        if operation_type == "tool_call":
            return await self._execute_tool_call(operation_data)
        elif operation_type == "api_call":
            return await self._execute_api_call(operation_data)
        elif operation_type == "database_operation":
            return await self._execute_database_operation(operation_data)
        else:
            raise ValueError(f"Unknown operation type: {operation_type}")

    async def _execute_tool_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute tool call operation."""
        # In production, this would call the actual tool
        # For now, return mock result
        return {
            "success": True,
            "result": "mock_tool_result",
            "tokens_used": 100,
            "cost_usd": 0.01,
        }

    async def _execute_api_call(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute API call operation."""
        # In production, this would make the actual API call
        # For now, return mock result
        return {"success": True, "result": "mock_api_result", "status_code": 200}

    async def _execute_database_operation(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute database operation."""
        # In production, this would execute the actual database operation
        # For now, return mock result
        return {"success": True, "result": "mock_db_result", "rows_affected": 1}

    async def _compensate_saga(self, saga: "Saga", failed_index: int) -> None:
        """Compensate saga operations."""
        try:
            saga.status = "compensating"

            # Compensate operations in reverse order
            for i in range(failed_index - 1, -1, -1):
                operation = saga.completed_operations[i]

                try:
                    # Execute compensation
                    await self._execute_compensation(operation)

                    logger.info(
                        "Compensation executed",
                        saga_id=str(saga.saga_id),
                        operation_index=i,
                    )

                except Exception as e:
                    logger.error(
                        "Compensation failed",
                        saga_id=str(saga.saga_id),
                        operation_index=i,
                        error=str(e),
                    )

            saga.status = "compensated"

            logger.info(
                "Saga compensated", saga_id=str(saga.saga_id), run_id=str(saga.run_id)
            )

        except Exception as e:
            logger.error(
                "Saga compensation failed", saga_id=str(saga.saga_id), error=str(e)
            )

            saga.status = "compensation_failed"
            saga.error = str(e)

    async def _execute_compensation(self, operation: Dict[str, Any]) -> None:
        """Execute compensation for operation."""
        operation_data = operation["operation"]
        operation_type = operation_data.get("type")

        if operation_type == "tool_call":
            await self._compensate_tool_call(operation_data)
        elif operation_type == "api_call":
            await self._compensate_api_call(operation_data)
        elif operation_type == "database_operation":
            await self._compensate_database_operation(operation_data)
        else:
            logger.warning(
                "No compensation handler for operation type",
                operation_type=operation_type,
            )

    async def _compensate_tool_call(self, operation: Dict[str, Any]) -> None:
        """Compensate tool call operation."""
        tool_id = operation.get("tool_id")

        if tool_id in self.compensation_handlers:
            await self.compensation_handlers[tool_id](operation)
        else:
            logger.warning("No compensation handler for tool", tool_id=tool_id)

    async def _compensate_api_call(self, operation: Dict[str, Any]) -> None:
        """Compensate API call operation."""
        # In production, this would call the compensation API
        logger.info("API call compensated", operation=operation)

    async def _compensate_database_operation(self, operation: Dict[str, Any]) -> None:
        """Compensate database operation."""
        # In production, this would execute the compensation SQL
        logger.info("Database operation compensated", operation=operation)

    # Compensation handlers for specific operations
    async def _compensate_email_send(self, operation: Dict[str, Any]) -> None:
        """Compensate email send operation."""
        # In production, this would send a cancellation email
        logger.info("Email send compensated", operation=operation)

    async def _compensate_payment_process(self, operation: Dict[str, Any]) -> None:
        """Compensate payment process operation."""
        # In production, this would refund the payment
        logger.info("Payment process compensated", operation=operation)

    async def _compensate_crm_update(self, operation: Dict[str, Any]) -> None:
        """Compensate CRM update operation."""
        # In production, this would revert the CRM update
        logger.info("CRM update compensated", operation=operation)

    async def _compensate_order_create(self, operation: Dict[str, Any]) -> None:
        """Compensate order create operation."""
        # In production, this would cancel the order
        logger.info("Order create compensated", operation=operation)

    async def _compensate_notification_send(self, operation: Dict[str, Any]) -> None:
        """Compensate notification send operation."""
        # In production, this would send a cancellation notification
        logger.info("Notification send compensated", operation=operation)

    async def get_saga_status(self, saga_id: UUID) -> Dict[str, Any]:
        """Get saga status."""
        saga = self.active_sagas.get(saga_id)
        if not saga:
            raise ValueError(f"Saga {saga_id} not found")

        return {
            "saga_id": str(saga.saga_id),
            "run_id": str(saga.run_id),
            "status": saga.status,
            "operations_count": len(saga.operations),
            "completed_count": len(saga.completed_operations),
            "error": saga.error,
        }


class Saga:
    """Individual saga instance."""

    def __init__(
        self,
        saga_id: UUID,
        run_id: UUID,
        operations: List[Dict[str, Any]],
        status: str = "pending",
    ):
        self.saga_id = saga_id
        self.run_id = run_id
        self.operations = operations
        self.status = status
        self.completed_operations: List[Dict[str, Any]] = []
        self.error: Optional[str] = None
