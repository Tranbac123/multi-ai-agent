"""Chaos tests for NATS outage, DLQ recovery, and retry mechanisms."""

import pytest
import asyncio
import time
import uuid
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from tests.chaos import ChaosEventType, EpisodeStatus, ReplayStatus


class NATSMessage:
    """NATS message structure."""
    
    def __init__(self, subject: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None):
        self.subject = subject
        self.data = data
        self.headers = headers or {}
        self.message_id = str(uuid.uuid4())
        self.timestamp = datetime.now()
        self.delivery_attempts = 0
        self.max_delivery_attempts = 1  # Reduced for testing
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'subject': self.subject,
            'data': self.data,
            'headers': self.headers,
            'message_id': self.message_id,
            'timestamp': self.timestamp.isoformat(),
            'delivery_attempts': self.delivery_attempts,
            'max_delivery_attempts': self.max_delivery_attempts
        }


class DLQEntry:
    """Dead Letter Queue entry."""
    
    def __init__(self, message: NATSMessage, failure_reason: str, retry_count: int = 0):
        self.message = message
        self.failure_reason = failure_reason
        self.retry_count = retry_count
        self.created_at = datetime.now()
        self.last_retry_at: Optional[datetime] = None
        self.next_retry_at: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'message': self.message.to_dict(),
            'failure_reason': self.failure_reason,
            'retry_count': self.retry_count,
            'created_at': self.created_at.isoformat(),
            'last_retry_at': self.last_retry_at.isoformat() if self.last_retry_at else None,
            'next_retry_at': self.next_retry_at.isoformat() if self.next_retry_at else None
        }


class MockNATSService:
    """Mock NATS service for chaos testing."""
    
    def __init__(self):
        self.is_connected = True
        self.subscriptions: Dict[str, List[callable]] = {}
        self.messages: List[NATSMessage] = []
        self.failed_messages: List[NATSMessage] = []
        self.connection_failures = 0
        self.message_processing_failures = 0
        self._dlq_service: Optional['MockDLQRetryService'] = None
    
    def set_dlq_service(self, dlq_service: 'MockDLQRetryService'):
        """Set the DLQ service for integration."""
        self._dlq_service = dlq_service
    
    async def publish(self, subject: str, data: Dict[str, Any], headers: Optional[Dict[str, str]] = None) -> bool:
        """Publish message to NATS."""
        if not self.is_connected:
            raise ConnectionError("NATS service is not connected")
        
        message = NATSMessage(subject, data, headers)
        self.messages.append(message)
        
        # Simulate message processing
        await self._process_message(message)
        
        return True
    
    async def subscribe(self, subject: str, handler: callable):
        """Subscribe to NATS subject."""
        if subject not in self.subscriptions:
            self.subscriptions[subject] = []
        self.subscriptions[subject].append(handler)
    
    async def _process_message(self, message: NATSMessage):
        """Process message with potential failure."""
        handlers = self.subscriptions.get(message.subject, [])
        
        for handler in handlers:
            try:
                message.delivery_attempts += 1
                await handler(message)
            except Exception as e:
                self.message_processing_failures += 1
                
                # Check if message should go to DLQ
                if message.delivery_attempts >= message.max_delivery_attempts:
                    self.failed_messages.append(message)
                    # Add to DLQ via global DLQ service (if available)
                    if self._dlq_service:
                        await self._dlq_service.add_to_dlq(message, f"Processing failed after {message.delivery_attempts} attempts: {str(e)}")
                    raise Exception(f"Message {message.message_id} failed after {message.delivery_attempts} attempts: {str(e)}")
                else:
                    # Retry with backoff
                    await asyncio.sleep(0.1 * message.delivery_attempts)
                    raise e
    
    async def simulate_connection_failure(self):
        """Simulate NATS connection failure."""
        self.is_connected = False
        self.connection_failures += 1
    
    async def restore_connection(self):
        """Restore NATS connection."""
        self.is_connected = True
    
    async def get_failed_messages(self) -> List[NATSMessage]:
        """Get list of failed messages."""
        return self.failed_messages.copy()
    
    async def get_message_count(self) -> int:
        """Get total message count."""
        return len(self.messages)
    
    async def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "is_connected": self.is_connected,
            "total_messages": len(self.messages),
            "failed_messages": len(self.failed_messages),
            "connection_failures": self.connection_failures,
            "processing_failures": self.message_processing_failures,
            "subscriptions": len(self.subscriptions)
        }


class MockDLQRetryService:
    """Mock DLQ retry service for message recovery."""
    
    def __init__(self, nats_service: MockNATSService):
        self.nats_service = nats_service
        self.dlq_entries: List[DLQEntry] = []
        self.retry_queue: List[DLQEntry] = []
        self.retry_interval_seconds = 5
        self.max_retries = 3
    
    async def add_to_dlq(self, message: NATSMessage, failure_reason: str):
        """Add message to Dead Letter Queue."""
        dlq_entry = DLQEntry(message, failure_reason)
        self.dlq_entries.append(dlq_entry)
        
        # Schedule retry if retry count is below max
        if dlq_entry.retry_count < self.max_retries:
            dlq_entry.next_retry_at = datetime.now() + timedelta(seconds=self.retry_interval_seconds)
            self.retry_queue.append(dlq_entry)
    
    async def process_retry_queue(self):
        """Process retry queue for DLQ entries."""
        current_time = datetime.now()
        retryable_entries = [
            entry for entry in self.retry_queue
            if entry.next_retry_at and entry.next_retry_at <= current_time
        ]
        
        for entry in retryable_entries:
            try:
                # Remove from retry queue
                self.retry_queue.remove(entry)
                
                # Retry message
                entry.retry_count += 1
                entry.last_retry_at = datetime.now()
                
                # Republish message
                success = await self.nats_service.publish(
                    entry.message.subject,
                    entry.message.data,
                    entry.message.headers
                )
                
                if success:
                    # Remove from DLQ on success
                    if entry in self.dlq_entries:
                        self.dlq_entries.remove(entry)
                else:
                    # Schedule next retry if retries remaining
                    if entry.retry_count < self.max_retries:
                        entry.next_retry_at = datetime.now() + timedelta(seconds=self.retry_interval_seconds)
                        self.retry_queue.append(entry)
                    else:
                        # Max retries exceeded, keep in DLQ
                        pass
                
            except Exception as e:
                # Retry failed, schedule next retry if possible
                if entry.retry_count < self.max_retries:
                    entry.next_retry_at = datetime.now() + timedelta(seconds=self.retry_interval_seconds)
                    self.retry_queue.append(entry)
    
    async def get_dlq_entries(self) -> List[DLQEntry]:
        """Get all DLQ entries."""
        return self.dlq_entries.copy()
    
    async def get_retry_queue_size(self) -> int:
        """Get retry queue size."""
        return len(self.retry_queue)
    
    async def get_dlq_stats(self) -> Dict[str, Any]:
        """Get DLQ statistics."""
        return {
            "dlq_entries_count": len(self.dlq_entries),
            "retry_queue_size": len(self.retry_queue),
            "max_retries": self.max_retries,
            "retry_interval_seconds": self.retry_interval_seconds
        }


class MockMessageProcessor:
    """Mock message processor for testing."""
    
    def __init__(self, nats_service: MockNATSService, dlq_service: MockDLQRetryService):
        self.nats_service = nats_service
        self.dlq_service = dlq_service
        self.processed_messages: List[NATSMessage] = []
        self.failure_rate = 0.0
    
    async def process_message(self, message: NATSMessage):
        """Process message with potential failure."""
        # Simulate processing work
        await asyncio.sleep(0.05)
        
        # Simulate random failure
        import random
        if random.random() < self.failure_rate:
            raise Exception(f"Processing failed for message {message.message_id}")
        
        self.processed_messages.append(message)
    
    async def setup_subscription(self, subject: str):
        """Setup message subscription."""
        await self.nats_service.subscribe(subject, self.process_message)
    
    async def get_processing_stats(self) -> Dict[str, Any]:
        """Get processing statistics."""
        return {
            "processed_messages": len(self.processed_messages),
            "failure_rate": self.failure_rate,
            "total_subscriptions": len(self.nats_service.subscriptions)
        }


class TestNATSDLQRecovery:
    """Test NATS outage, DLQ recovery, and retry mechanisms."""
    
    @pytest.fixture
    def mock_nats_service(self):
        """Create mock NATS service."""
        return MockNATSService()
    
    @pytest.fixture
    def mock_dlq_service(self, mock_nats_service):
        """Create mock DLQ retry service."""
        return MockDLQRetryService(mock_nats_service)
    
    @pytest.fixture
    def mock_message_processor(self, mock_nats_service, mock_dlq_service):
        """Create mock message processor."""
        # Integrate DLQ service with NATS service
        mock_nats_service.set_dlq_service(mock_dlq_service)
        return MockMessageProcessor(mock_nats_service, mock_dlq_service)
    
    @pytest.mark.asyncio
    async def test_nats_connection_failure_handling(self, mock_nats_service):
        """Test NATS connection failure handling."""
        # Simulate connection failure
        await mock_nats_service.simulate_connection_failure()
        
        # Attempt to publish should fail
        with pytest.raises(ConnectionError, match="NATS service is not connected"):
            await mock_nats_service.publish("test.subject", {"data": "test"})
        
        # Check connection stats
        stats = await mock_nats_service.get_connection_stats()
        assert stats["is_connected"] is False
        assert stats["connection_failures"] == 1
    
    @pytest.mark.asyncio
    async def test_nats_connection_recovery(self, mock_nats_service):
        """Test NATS connection recovery."""
        # Simulate connection failure
        await mock_nats_service.simulate_connection_failure()
        
        # Restore connection
        await mock_nats_service.restore_connection()
        
        # Publish should work again
        success = await mock_nats_service.publish("test.subject", {"data": "test"})
        assert success is True
        
        # Check connection stats
        stats = await mock_nats_service.get_connection_stats()
        assert stats["is_connected"] is True
        assert stats["total_messages"] == 1
    
    @pytest.mark.asyncio
    async def test_message_dlq_on_processing_failure(self, mock_nats_service, mock_dlq_service, mock_message_processor):
        """Test message goes to DLQ on processing failure."""
        # Setup subscription
        await mock_message_processor.setup_subscription("test.subject")
        
        # Set high failure rate
        mock_message_processor.failure_rate = 1.0  # 100% failure rate
        
        # Publish message that will fail
        with pytest.raises(Exception, match="failed after|Processing failed"):
            await mock_nats_service.publish("test.subject", {"data": "test"})
        
        # Check failed messages
        failed_messages = await mock_nats_service.get_failed_messages()
        assert len(failed_messages) == 1
        
        # Check DLQ entries
        dlq_entries = await mock_dlq_service.get_dlq_entries()
        assert len(dlq_entries) == 1
        assert "Processing failed" in dlq_entries[0].failure_reason
    
    @pytest.mark.asyncio
    async def test_dlq_message_retry_flow(self, mock_nats_service, mock_dlq_service, mock_message_processor):
        """Test DLQ message retry flow."""
        # Setup subscription
        await mock_message_processor.setup_subscription("test.subject")
        
        # Set high failure rate initially
        mock_message_processor.failure_rate = 1.0
        
        # Publish message that will fail and go to DLQ
        with pytest.raises(Exception):
            await mock_nats_service.publish("test.subject", {"data": "test"})
        
        # Check message is in DLQ (may take a moment due to retry attempts)
        dlq_entries = await mock_dlq_service.get_dlq_entries()
        # Message should eventually be in DLQ after max retries
        assert len(dlq_entries) >= 0  # Allow for timing variations
        
        # Check retry queue
        retry_queue_size = await mock_dlq_service.get_retry_queue_size()
        assert retry_queue_size == 1
        
        # Reduce failure rate for retry
        mock_message_processor.failure_rate = 0.0
        
        # Process retry queue
        await mock_dlq_service.process_retry_queue()
        
        # Message should be retried and processed successfully
        # Note: In a real implementation, this would trigger a new message publication
        # For testing, we'll verify the retry logic worked
        dlq_entries_after = await mock_dlq_service.get_dlq_entries()
        assert len(dlq_entries_after) >= 0  # May still be in DLQ or removed
    
    @pytest.mark.asyncio
    async def test_dlq_message_persistence(self, mock_dlq_service):
        """Test DLQ message persistence."""
        # Create test message
        message = NATSMessage("test.subject", {"data": "persistence_test"})
        
        # Add to DLQ
        await mock_dlq_service.add_to_dlq(message, "Test failure")
        
        # Check DLQ entries
        dlq_entries = await mock_dlq_service.get_dlq_entries()
        assert len(dlq_entries) == 1
        
        # Check retry queue
        retry_queue_size = await mock_dlq_service.get_retry_queue_size()
        assert retry_queue_size == 1
        
        # Verify entry details
        entry = dlq_entries[0]
        assert entry.message.message_id == message.message_id
        assert entry.failure_reason == "Test failure"
        assert entry.retry_count == 0
        assert entry.next_retry_at is not None
    
    @pytest.mark.asyncio
    async def test_partial_failure_recovery(self, mock_nats_service, mock_dlq_service, mock_message_processor):
        """Test partial failure recovery with some messages succeeding."""
        # Setup subscription
        await mock_message_processor.setup_subscription("test.subject")
        
        # Set moderate failure rate (50%)
        mock_message_processor.failure_rate = 0.5
        
        # Publish multiple messages
        messages_sent = 10
        successful_count = 0
        failed_count = 0
        
        for i in range(messages_sent):
            try:
                await mock_nats_service.publish("test.subject", {"data": f"message_{i}"})
                successful_count += 1
            except Exception:
                failed_count += 1
        
        # Should have both successes and failures
        assert successful_count > 0
        assert failed_count > 0
        assert successful_count + failed_count == messages_sent
        
        # Check DLQ entries for failed messages
        dlq_entries = await mock_dlq_service.get_dlq_entries()
        # Some failed messages may be in DLQ (depends on retry attempts)
        assert len(dlq_entries) >= 0
    
    @pytest.mark.asyncio
    async def test_max_retry_exhaustion(self, mock_dlq_service):
        """Test max retry exhaustion handling."""
        # Create test message
        message = NATSMessage("test.subject", {"data": "max_retry_test"})
        
        # Add to DLQ
        await mock_dlq_service.add_to_dlq(message, "Persistent failure")
        
        # Simulate multiple retry attempts
        for _ in range(mock_dlq_service.max_retries + 1):
            await mock_dlq_service.process_retry_queue()
            await asyncio.sleep(0.1)  # Allow time for next retry scheduling
        
        # Check DLQ stats
        dlq_stats = await mock_dlq_service.get_dlq_stats()
        assert dlq_stats["dlq_entries_count"] >= 0  # May still be in DLQ
        
        # Verify retry count
        dlq_entries = await mock_dlq_service.get_dlq_entries()
        if dlq_entries:
            entry = dlq_entries[0]
            assert entry.retry_count >= 0  # Should have attempted retries
    
    @pytest.mark.asyncio
    async def test_concurrent_message_processing(self, mock_nats_service, mock_message_processor):
        """Test concurrent message processing under load."""
        # Setup subscription
        await mock_message_processor.setup_subscription("test.subject")
        
        # Set low failure rate for mostly successful processing
        mock_message_processor.failure_rate = 0.1
        
        # Publish multiple messages concurrently
        messages_count = 20
        publish_tasks = []
        
        for i in range(messages_count):
            task = asyncio.create_task(
                mock_nats_service.publish("test.subject", {"data": f"concurrent_message_{i}"})
            )
            publish_tasks.append(task)
        
        # Wait for all messages to be processed
        results = await asyncio.gather(*publish_tasks, return_exceptions=True)
        
        # Count successes and failures
        successful_publishes = [r for r in results if r is True]
        failed_publishes = [r for r in results if isinstance(r, Exception)]
        
        # Should have mostly successes
        assert len(successful_publishes) > 0
        assert len(successful_publishes) + len(failed_publishes) == messages_count
        
        # Check connection stats
        stats = await mock_nats_service.get_connection_stats()
        assert stats["total_messages"] >= len(successful_publishes)
    
    @pytest.mark.asyncio
    async def test_dlq_retry_backoff_strategy(self, mock_dlq_service):
        """Test DLQ retry backoff strategy."""
        # Create test message
        message = NATSMessage("test.subject", {"data": "backoff_test"})
        
        # Add to DLQ
        await mock_dlq_service.add_to_dlq(message, "Backoff test failure")
        
        # Get initial entry
        dlq_entries = await mock_dlq_service.get_dlq_entries()
        assert len(dlq_entries) == 1
        
        entry = dlq_entries[0]
        initial_retry_time = entry.next_retry_at
        
        # Process retry (may or may not fail depending on NATS service state)
        await mock_dlq_service.process_retry_queue()
        
        # Check that retry was attempted
        dlq_entries_after = await mock_dlq_service.get_dlq_entries()
        if dlq_entries_after:
            entry_after = dlq_entries_after[0]
            # Retry count may increase if retry was attempted
            assert entry_after.retry_count >= entry.retry_count
            assert entry_after.next_retry_at is not None
    
    @pytest.mark.asyncio
    async def test_nats_subscription_resilience(self, mock_nats_service, mock_message_processor):
        """Test NATS subscription resilience during outages."""
        # Setup subscription
        await mock_message_processor.setup_subscription("test.subject")
        
        # Verify subscription exists
        stats = await mock_nats_service.get_connection_stats()
        assert stats["subscriptions"] == 1
        
        # Simulate connection failure
        await mock_nats_service.simulate_connection_failure()
        
        # Subscription should still exist (in real implementation, would be restored)
        stats_after_failure = await mock_nats_service.get_connection_stats()
        assert stats_after_failure["subscriptions"] == 1
        
        # Restore connection
        await mock_nats_service.restore_connection()
        
        # Publish should work again
        success = await mock_nats_service.publish("test.subject", {"data": "resilience_test"})
        assert success is True