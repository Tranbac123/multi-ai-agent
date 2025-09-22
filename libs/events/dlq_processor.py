"""Dead Letter Queue processor for handling failed events."""

import asyncio
import json
import time
from typing import Dict, Any, List, Optional
from uuid import UUID
import structlog

from src.event_types import EventType
from src.event_handlers import create_event_handler

logger = structlog.get_logger(__name__)


class DLQProcessor:
    """Dead Letter Queue processor for handling failed events."""

    def __init__(self, tenant_id: UUID):
        self.tenant_id = tenant_id
        self.retry_attempts = 3
        self.retry_delay = 60  # seconds
        self.max_retry_delay = 3600  # 1 hour
        self.exponential_backoff = True

    async def process_dlq_message(self, dlq_data: Dict[str, Any]) -> None:
        """Process message from Dead Letter Queue."""
        try:
            # Extract original event data
            original_subject = dlq_data.get("original_subject", "")
            original_data = json.loads(dlq_data.get("original_data", "{}"))
            original_headers = dlq_data.get("original_headers", {})
            error = dlq_data.get("error", "Unknown error")
            failed_at = dlq_data.get("failed_at", time.time())
            retry_count = dlq_data.get("retry_count", 0)

            # Determine event type from subject
            event_type = self._extract_event_type(original_subject)
            if not event_type:
                logger.warning(
                    "Unknown event type in DLQ", original_subject=original_subject
                )
                return

            # Check if we should retry
            if retry_count >= self.retry_attempts:
                logger.error(
                    "Max retry attempts exceeded",
                    event_type=event_type,
                    retry_count=retry_count,
                    error=error,
                )
                await self._handle_final_failure(dlq_data, event_type, error)
                return

            # Calculate retry delay
            delay = self._calculate_retry_delay(retry_count)

            logger.info(
                "Retrying failed event",
                event_type=event_type,
                retry_count=retry_count,
                delay=delay,
                error=error,
            )

            # Wait before retry
            await asyncio.sleep(delay)

            # Create event handler and retry
            handler = await create_event_handler(event_type, self.tenant_id)
            await handler.handle(original_data)

            logger.info(
                "Successfully retried event",
                event_type=event_type,
                retry_count=retry_count,
            )

        except Exception as e:
            logger.error(
                "Failed to process DLQ message", error=str(e), dlq_data=dlq_data
            )
            await self._handle_processing_error(dlq_data, str(e))

    def _extract_event_type(self, subject: str) -> Optional[EventType]:
        """Extract event type from NATS subject."""
        # Extract event type from subject pattern: event_type.*
        parts = subject.split(".")
        if len(parts) >= 2:
            event_type_str = parts[0]
            try:
                return EventType(event_type_str)
            except ValueError:
                return None
        return None

    def _calculate_retry_delay(self, retry_count: int) -> int:
        """Calculate retry delay with exponential backoff."""
        if not self.exponential_backoff:
            return self.retry_delay

        delay = self.retry_delay * (2**retry_count)
        return min(delay, self.max_retry_delay)

    async def _handle_final_failure(
        self, dlq_data: Dict[str, Any], event_type: EventType, error: str
    ) -> None:
        """Handle final failure after max retries."""
        try:
            # Log final failure
            logger.error(
                "Event permanently failed",
                event_type=event_type,
                error=error,
                dlq_data=dlq_data,
            )

            # Store in permanent failure table
            await self._store_permanent_failure(dlq_data, event_type, error)

            # Send alert if configured
            await self._send_failure_alert(dlq_data, event_type, error)

        except Exception as e:
            logger.error(
                "Failed to handle final failure", error=str(e), dlq_data=dlq_data
            )

    async def _handle_processing_error(
        self, dlq_data: Dict[str, Any], error: str
    ) -> None:
        """Handle error during DLQ processing."""
        try:
            # Log processing error
            logger.error("DLQ processing error", error=error, dlq_data=dlq_data)

            # Store in error table
            await self._store_processing_error(dlq_data, error)

        except Exception as e:
            logger.error(
                "Failed to handle processing error", error=str(e), dlq_data=dlq_data
            )

    async def _store_permanent_failure(
        self, dlq_data: Dict[str, Any], event_type: EventType, error: str
    ) -> None:
        """Store permanently failed event."""
        from libs.clients.database import get_db_session
        from libs.contracts.database import PermanentFailure

        async with get_db_session() as db:
            failure = PermanentFailure(
                id=str(UUID()),
                tenant_id=self.tenant_id,
                event_type=event_type.value,
                original_subject=dlq_data.get("original_subject", ""),
                original_data=dlq_data.get("original_data", ""),
                original_headers=dlq_data.get("original_headers", {}),
                error=error,
                failed_at=dlq_data.get("failed_at", time.time()),
                retry_count=dlq_data.get("retry_count", 0),
                created_at=time.time(),
            )

            db.add(failure)
            await db.commit()

    async def _store_processing_error(
        self, dlq_data: Dict[str, Any], error: str
    ) -> None:
        """Store DLQ processing error."""
        from libs.clients.database import get_db_session
        from libs.contracts.database import DLQProcessingError

        async with get_db_session() as db:
            processing_error = DLQProcessingError(
                id=str(UUID()),
                tenant_id=self.tenant_id,
                dlq_data=dlq_data,
                error=error,
                created_at=time.time(),
            )

            db.add(processing_error)
            await db.commit()

    async def _send_failure_alert(
        self, dlq_data: Dict[str, Any], event_type: EventType, error: str
    ) -> None:
        """Send alert for permanent failure."""
        try:
            # Send alert to monitoring system
            alert_data = {
                "type": "dlq_permanent_failure",
                "tenant_id": str(self.tenant_id),
                "event_type": event_type.value,
                "error": error,
                "failed_at": dlq_data.get("failed_at", time.time()),
                "retry_count": dlq_data.get("retry_count", 0),
                "original_subject": dlq_data.get("original_subject", ""),
            }

            # Publish alert event
            from src.event_bus import publish_event

            await publish_event(
                event_type="alert",
                data=alert_data,
                tenant_id=self.tenant_id,
                headers={"alert_type": "dlq_permanent_failure"},
            )

            logger.info(
                "Sent failure alert", event_type=event_type, tenant_id=self.tenant_id
            )

        except Exception as e:
            logger.error(
                "Failed to send failure alert", error=str(e), event_type=event_type
            )

    async def get_dlq_stats(self) -> Dict[str, Any]:
        """Get DLQ statistics."""
        try:
            from libs.clients.database import get_db_session
            from libs.contracts.database import PermanentFailure, DLQProcessingError

            async with get_db_session() as db:
                # Count permanent failures
                permanent_failures = await db.execute(
                    "SELECT COUNT(*) FROM permanent_failures WHERE tenant_id = :tenant_id",
                    {"tenant_id": self.tenant_id},
                )
                permanent_failure_count = permanent_failures.scalar()

                # Count processing errors
                processing_errors = await db.execute(
                    "SELECT COUNT(*) FROM dlq_processing_errors WHERE tenant_id = :tenant_id",
                    {"tenant_id": self.tenant_id},
                )
                processing_error_count = processing_errors.scalar()

                # Get failures by event type
                failures_by_type = await db.execute(
                    """
                    SELECT event_type, COUNT(*) as count 
                    FROM permanent_failures 
                    WHERE tenant_id = :tenant_id 
                    GROUP BY event_type
                    """,
                    {"tenant_id": self.tenant_id},
                )
                failures_by_type_data = failures_by_type.fetchall()

                return {
                    "tenant_id": str(self.tenant_id),
                    "permanent_failures": permanent_failure_count,
                    "processing_errors": processing_error_count,
                    "failures_by_type": [
                        {"event_type": row[0], "count": row[1]}
                        for row in failures_by_type_data
                    ],
                    "timestamp": time.time(),
                }

        except Exception as e:
            logger.error("Failed to get DLQ stats", error=str(e))
            return {
                "tenant_id": str(self.tenant_id),
                "error": str(e),
                "timestamp": time.time(),
            }

    async def cleanup_old_failures(self, days: int = 30) -> int:
        """Clean up old permanent failures."""
        try:
            from libs.clients.database import get_db_session

            cutoff_time = time.time() - (days * 24 * 60 * 60)

            async with get_db_session() as db:
                result = await db.execute(
                    """
                    DELETE FROM permanent_failures 
                    WHERE tenant_id = :tenant_id AND created_at < :cutoff_time
                    """,
                    {"tenant_id": self.tenant_id, "cutoff_time": cutoff_time},
                )

                deleted_count = result.rowcount
                await db.commit()

                logger.info(
                    "Cleaned up old failures",
                    tenant_id=self.tenant_id,
                    deleted_count=deleted_count,
                    days=days,
                )

                return deleted_count

        except Exception as e:
            logger.error(
                "Failed to cleanup old failures", error=str(e), tenant_id=self.tenant_id
            )
            return 0


# Global DLQ processor instance
dlq_processor = DLQProcessor(tenant_id=UUID("00000000-0000-0000-0000-000000000000"))


async def process_dlq_message(dlq_data: Dict[str, Any]) -> None:
    """Process DLQ message using global processor."""
    await dlq_processor.process_dlq_message(dlq_data)
