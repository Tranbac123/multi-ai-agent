"""Event handlers for processing events."""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from uuid import UUID
import structlog

from .event_types import (
    EventType,
    AgentRunEvent,
    ToolCallEvent,
    IngestDocEvent,
    UsageMeteredEvent,
    RouterDecisionEvent,
    WebSocketMessageEvent,
    BillingEvent,
    AuditLogEvent,
)

logger = structlog.get_logger(__name__)


class EventHandler:
    """Base event handler class."""

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id

    async def handle(self, event_data: Dict[str, Any]) -> None:
        """Handle event data."""
        raise NotImplementedError


class AgentRunEventHandler(EventHandler):
    """Handler for agent run events."""

    async def handle(self, event_data: Dict[str, Any]) -> None:
        """Handle agent run event."""
        try:
            # Parse event data
            event = AgentRunEvent(**event_data["data"])

            # Log agent run
            logger.info(
                "Agent run event",
                run_id=event.run_id,
                agent_id=event.agent_id,
                status=event.status,
                duration_ms=event.duration_ms,
            )

            # Update metrics
            await self._update_metrics(event)

            # Store in database if needed
            await self._store_event(event)

        except Exception as e:
            logger.error(
                "Failed to handle agent run event", error=str(e), event_data=event_data
            )
            raise

    async def _update_metrics(self, event: AgentRunEvent) -> None:
        """Update metrics for agent run."""
        # Update Prometheus metrics
        from observability.metrics.prometheus_metrics import (
            agent_runs_total,
            agent_run_duration_seconds,
            agent_tokens_used,
        )

        agent_runs_total.labels(
            tenant_id=str(event.tenant_id), agent_id=event.agent_id, status=event.status
        ).inc()

        if event.duration_ms:
            agent_run_duration_seconds.labels(
                tenant_id=str(event.tenant_id), agent_id=event.agent_id
            ).observe(event.duration_ms / 1000.0)

        if event.tokens_used:
            agent_tokens_used.labels(
                tenant_id=str(event.tenant_id), agent_id=event.agent_id
            ).inc(event.tokens_used)

    async def _store_event(self, event: AgentRunEvent) -> None:
        """Store event in database."""
        # Store in agent_runs table
        from libs.clients.database import get_db_session
        from libs.contracts.database import AgentRun

        async with get_db_session() as db:
            agent_run = AgentRun(
                id=event.run_id,
                tenant_id=event.tenant_id,
                agent_id=event.agent_id,
                user_id=event.user_id,
                session_id=event.session_id,
                input_text=event.input_text,
                output_text=event.output_text,
                status=event.status,
                start_time=event.start_time,
                end_time=event.end_time,
                duration_ms=event.duration_ms,
                tokens_used=event.tokens_used,
                cost_usd=event.cost_usd,
                error_message=event.error_message,
                metadata=event.metadata,
            )

            db.add(agent_run)
            await db.commit()


class ToolCallEventHandler(EventHandler):
    """Handler for tool call events."""

    async def handle(self, event_data: Dict[str, Any]) -> None:
        """Handle tool call event."""
        try:
            # Parse event data
            event = ToolCallEvent(**event_data["data"])

            # Log tool call
            logger.info(
                "Tool call event",
                call_id=event.call_id,
                tool_name=event.tool_name,
                status=event.status,
                duration_ms=event.duration_ms,
            )

            # Update metrics
            await self._update_metrics(event)

            # Store in database if needed
            await self._store_event(event)

        except Exception as e:
            logger.error(
                "Failed to handle tool call event", error=str(e), event_data=event_data
            )
            raise

    async def _update_metrics(self, event: ToolCallEvent) -> None:
        """Update metrics for tool call."""
        from observability.metrics.prometheus_metrics import (
            tool_calls_total,
            tool_call_duration_seconds,
        )

        tool_calls_total.labels(
            tenant_id=str(event.tenant_id),
            tool_name=event.tool_name,
            status=event.status,
        ).inc()

        if event.duration_ms:
            tool_call_duration_seconds.labels(
                tenant_id=str(event.tenant_id), tool_name=event.tool_name
            ).observe(event.duration_ms / 1000.0)

    async def _store_event(self, event: ToolCallEvent) -> None:
        """Store event in database."""
        # Store in tool_calls table
        from libs.clients.database import get_db_session
        from libs.contracts.database import ToolCall

        async with get_db_session() as db:
            tool_call = ToolCall(
                id=event.call_id,
                run_id=event.run_id,
                tenant_id=event.tenant_id,
                tool_name=event.tool_name,
                tool_input=event.tool_input,
                tool_output=event.tool_output,
                status=event.status,
                start_time=event.start_time,
                end_time=event.end_time,
                duration_ms=event.duration_ms,
                error_message=event.error_message,
                metadata=event.metadata,
            )

            db.add(tool_call)
            await db.commit()


class IngestDocEventHandler(EventHandler):
    """Handler for document ingestion events."""

    async def handle(self, event_data: Dict[str, Any]) -> None:
        """Handle document ingestion event."""
        try:
            # Parse event data
            event = IngestDocEvent(**event_data["data"])

            # Log document ingestion
            logger.info(
                "Document ingestion event",
                doc_id=event.doc_id,
                filename=event.filename,
                status=event.status,
                chunks_created=event.chunks_created,
            )

            # Update metrics
            await self._update_metrics(event)

            # Store in database if needed
            await self._store_event(event)

        except Exception as e:
            logger.error(
                "Failed to handle document ingestion event",
                error=str(e),
                event_data=event_data,
            )
            raise

    async def _update_metrics(self, event: IngestDocEvent) -> None:
        """Update metrics for document ingestion."""
        from observability.metrics.prometheus_metrics import (
            documents_ingested_total,
            document_ingestion_duration_seconds,
            document_chunks_created_total,
        )

        documents_ingested_total.labels(
            tenant_id=str(event.tenant_id),
            content_type=event.content_type,
            status=event.status,
        ).inc()

        if event.duration_ms:
            document_ingestion_duration_seconds.labels(
                tenant_id=str(event.tenant_id), content_type=event.content_type
            ).observe(event.duration_ms / 1000.0)

        if event.chunks_created:
            document_chunks_created_total.labels(
                tenant_id=str(event.tenant_id), content_type=event.content_type
            ).inc(event.chunks_created)

    async def _store_event(self, event: IngestDocEvent) -> None:
        """Store event in database."""
        # Store in document_ingestions table
        from libs.clients.database import get_db_session
        from libs.contracts.database import DocumentIngestion

        async with get_db_session() as db:
            doc_ingestion = DocumentIngestion(
                id=event.doc_id,
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                filename=event.filename,
                content_type=event.content_type,
                file_size=event.file_size,
                status=event.status,
                start_time=event.start_time,
                end_time=event.end_time,
                duration_ms=event.duration_ms,
                chunks_created=event.chunks_created,
                embeddings_generated=event.embeddings_generated,
                error_message=event.error_message,
                metadata=event.metadata,
            )

            db.add(doc_ingestion)
            await db.commit()


class UsageMeteredEventHandler(EventHandler):
    """Handler for usage metering events."""

    async def handle(self, event_data: Dict[str, Any]) -> None:
        """Handle usage metering event."""
        try:
            # Parse event data
            event = UsageMeteredEvent(**event_data["data"])

            # Log usage metering
            logger.info(
                "Usage metering event",
                usage_id=event.usage_id,
                resource_type=event.resource_type,
                quantity=event.quantity,
                unit=event.unit,
            )

            # Update metrics
            await self._update_metrics(event)

            # Store in database if needed
            await self._store_event(event)

        except Exception as e:
            logger.error(
                "Failed to handle usage metering event",
                error=str(e),
                event_data=event_data,
            )
            raise

    async def _update_metrics(self, event: UsageMeteredEvent) -> None:
        """Update metrics for usage metering."""
        from observability.metrics.prometheus_metrics import (
            usage_metered_total,
            usage_cost_usd_total,
        )

        usage_metered_total.labels(
            tenant_id=str(event.tenant_id),
            resource_type=event.resource_type,
            unit=event.unit,
        ).inc(event.quantity)

        if event.cost_usd:
            usage_cost_usd_total.labels(
                tenant_id=str(event.tenant_id), resource_type=event.resource_type
            ).inc(event.cost_usd)

    async def _store_event(self, event: UsageMeteredEvent) -> None:
        """Store event in database."""
        # Store in usage_metered table
        from libs.clients.database import get_db_session
        from libs.contracts.database import UsageMetered

        async with get_db_session() as db:
            usage = UsageMetered(
                id=event.usage_id,
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                quantity=event.quantity,
                unit=event.unit,
                timestamp=event.timestamp,
                cost_usd=event.cost_usd,
                metadata=event.metadata,
            )

            db.add(usage)
            await db.commit()


class RouterDecisionEventHandler(EventHandler):
    """Handler for router decision events."""

    async def handle(self, event_data: Dict[str, Any]) -> None:
        """Handle router decision event."""
        try:
            # Parse event data
            event = RouterDecisionEvent(**event_data["data"])

            # Log router decision
            logger.info(
                "Router decision event",
                decision_id=event.decision_id,
                selected_agent=event.selected_agent,
                confidence=event.confidence,
            )

            # Update metrics
            await self._update_metrics(event)

            # Store in database if needed
            await self._store_event(event)

        except Exception as e:
            logger.error(
                "Failed to handle router decision event",
                error=str(e),
                event_data=event_data,
            )
            raise

    async def _update_metrics(self, event: RouterDecisionEvent) -> None:
        """Update metrics for router decision."""
        from observability.metrics.prometheus_metrics import (
            router_decisions_total,
            router_confidence_histogram,
        )

        router_decisions_total.labels(
            tenant_id=str(event.tenant_id), selected_agent=event.selected_agent
        ).inc()

        router_confidence_histogram.labels(
            tenant_id=str(event.tenant_id), selected_agent=event.selected_agent
        ).observe(event.confidence)

    async def _store_event(self, event: RouterDecisionEvent) -> None:
        """Store event in database."""
        # Store in router_decisions table
        from libs.clients.database import get_db_session
        from libs.contracts.database import RouterDecision

        async with get_db_session() as db:
            decision = RouterDecision(
                id=event.decision_id,
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                input_text=event.input_text,
                selected_agent=event.selected_agent,
                confidence=event.confidence,
                reasoning=event.reasoning,
                features=event.features,
                timestamp=event.timestamp,
                metadata=event.metadata,
            )

            db.add(decision)
            await db.commit()


class WebSocketMessageEventHandler(EventHandler):
    """Handler for WebSocket message events."""

    async def handle(self, event_data: Dict[str, Any]) -> None:
        """Handle WebSocket message event."""
        try:
            # Parse event data
            event = WebSocketMessageEvent(**event_data["data"])

            # Log WebSocket message
            logger.info(
                "WebSocket message event",
                message_id=event.message_id,
                session_id=event.session_id,
                message_type=event.message_type,
            )

            # Update metrics
            await self._update_metrics(event)

            # Store in database if needed
            await self._store_event(event)

        except Exception as e:
            logger.error(
                "Failed to handle WebSocket message event",
                error=str(e),
                event_data=event_data,
            )
            raise

    async def _update_metrics(self, event: WebSocketMessageEvent) -> None:
        """Update metrics for WebSocket message."""
        from observability.metrics.prometheus_metrics import websocket_messages_total

        websocket_messages_total.labels(
            tenant_id=str(event.tenant_id), message_type=event.message_type
        ).inc()

    async def _store_event(self, event: WebSocketMessageEvent) -> None:
        """Store event in database."""
        # Store in websocket_messages table
        from libs.clients.database import get_db_session
        from libs.contracts.database import WebSocketMessage

        async with get_db_session() as db:
            message = WebSocketMessage(
                id=event.message_id,
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                session_id=event.session_id,
                message_type=event.message_type,
                content=event.content,
                timestamp=event.timestamp,
                metadata=event.metadata,
            )

            db.add(message)
            await db.commit()


class BillingEventHandler(EventHandler):
    """Handler for billing events."""

    async def handle(self, event_data: Dict[str, Any]) -> None:
        """Handle billing event."""
        try:
            # Parse event data
            event = BillingEvent(**event_data["data"])

            # Log billing event
            logger.info(
                "Billing event",
                billing_id=event.billing_id,
                event_type=event.event_type,
                amount_usd=event.amount_usd,
            )

            # Update metrics
            await self._update_metrics(event)

            # Store in database if needed
            await self._store_event(event)

        except Exception as e:
            logger.error(
                "Failed to handle billing event", error=str(e), event_data=event_data
            )
            raise

    async def _update_metrics(self, event: BillingEvent) -> None:
        """Update metrics for billing event."""
        from observability.metrics.prometheus_metrics import (
            billing_events_total,
            billing_amount_usd_total,
        )

        billing_events_total.labels(
            tenant_id=str(event.tenant_id), event_type=event.event_type
        ).inc()

        billing_amount_usd_total.labels(
            tenant_id=str(event.tenant_id), event_type=event.event_type
        ).inc(event.amount_usd)

    async def _store_event(self, event: BillingEvent) -> None:
        """Store event in database."""
        # Store in billing_events table
        from libs.clients.database import get_db_session
        from libs.contracts.database import BillingEvent as BillingEventModel

        async with get_db_session() as db:
            billing_event = BillingEventModel(
                id=event.billing_id,
                tenant_id=event.tenant_id,
                event_type=event.event_type,
                amount_usd=event.amount_usd,
                currency=event.currency,
                timestamp=event.timestamp,
                description=event.description,
                metadata=event.metadata,
            )

            db.add(billing_event)
            await db.commit()


class AuditLogEventHandler(EventHandler):
    """Handler for audit log events."""

    async def handle(self, event_data: Dict[str, Any]) -> None:
        """Handle audit log event."""
        try:
            # Parse event data
            event = AuditLogEvent(**event_data["data"])

            # Log audit log event
            logger.info(
                "Audit log event",
                log_id=event.log_id,
                action=event.action,
                resource_type=event.resource_type,
            )

            # Update metrics
            await self._update_metrics(event)

            # Store in database if needed
            await self._store_event(event)

        except Exception as e:
            logger.error(
                "Failed to handle audit log event", error=str(e), event_data=event_data
            )
            raise

    async def _update_metrics(self, event: AuditLogEvent) -> None:
        """Update metrics for audit log event."""
        from observability.metrics.prometheus_metrics import audit_logs_total

        audit_logs_total.labels(
            tenant_id=str(event.tenant_id),
            action=event.action,
            resource_type=event.resource_type,
        ).inc()

    async def _store_event(self, event: AuditLogEvent) -> None:
        """Store event in database."""
        # Store in audit_logs table
        from libs.clients.database import get_db_session
        from libs.contracts.database import AuditLog as AuditLogModel

        async with get_db_session() as db:
            audit_log = AuditLogModel(
                id=event.log_id,
                tenant_id=event.tenant_id,
                user_id=event.user_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                old_values=event.old_values,
                new_values=event.new_values,
                timestamp=event.timestamp,
                ip_address=event.ip_address,
                user_agent=event.user_agent,
                metadata=event.metadata,
            )

            db.add(audit_log)
            await db.commit()


# Event handler registry
EVENT_HANDLERS = {
    EventType.AGENT_RUN: AgentRunEventHandler,
    EventType.TOOL_CALL: ToolCallEventHandler,
    EventType.INGEST_DOC: IngestDocEventHandler,
    EventType.USAGE_METERED: UsageMeteredEventHandler,
    EventType.ROUTER_DECISION: RouterDecisionEventHandler,
    EventType.WEBSOCKET_MESSAGE: WebSocketMessageEventHandler,
    EventType.BILLING_EVENT: BillingEventHandler,
    EventType.AUDIT_LOG: AuditLogEventHandler,
}


async def create_event_handler(event_type: EventType, tenant_id: UUID) -> EventHandler:
    """Create event handler for event type."""
    handler_class = EVENT_HANDLERS.get(event_type)
    if not handler_class:
        raise ValueError(f"No handler found for event type: {event_type}")

    return handler_class(tenant_id)
