"""Integration tests for event system with NATS and DLQ."""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock
import structlog

from libs.events import (
    EventBus, EventBusConfig, EventProducer, ProducerConfig,
    EventConsumer, ConsumerConfig, DLQHandler, DLQConfig,
    EventStore, EventStoreConfig, Event, EventType, EventMetadata
)

logger = structlog.get_logger(__name__)


@pytest.mark.asyncio
class TestEventSystem:
    """Test event system components."""
    
    async def test_event_creation(self):
        """Test event creation and serialization."""
        metadata = EventMetadata(
            event_type=EventType.AGENT_RUN_STARTED,
            source="test",
            tenant_id="tenant123",
            correlation_id="run456"
        )
        
        payload = {"run_id": "run456", "agent_name": "test_agent"}
        event = Event(payload=payload, metadata=metadata)
        
        # Test serialization
        event_dict = event.to_dict()
        assert event_dict["payload"] == payload
        assert event_dict["metadata"]["event_type"] == "agent.run.started"
        
        # Test deserialization
        event_from_dict = Event.from_dict(event_dict)
        assert event_from_dict.payload == payload
        assert event_from_dict.metadata.event_type == EventType.AGENT_RUN_STARTED
        
        # Test JSON serialization
        event_json = event.to_json()
        event_from_json = Event.from_json(event_json)
        assert event_from_json.payload == payload
    
    async def test_event_bus_mock(self):
        """Test event bus with mock NATS."""
        config = EventBusConfig(servers=["nats://localhost:4222"])
        bus = EventBus(config)
        
        # Connect (will use mock if NATS not available)
        await bus.connect()
        assert bus.is_connected()
        
        # Test event publishing
        metadata = EventMetadata(event_type=EventType.AGENT_RUN_STARTED)
        payload = {"test": "data"}
        event = Event(payload=payload, metadata=metadata)
        
        # This will work with mock implementation
        success = await bus.publish(event)
        assert success
        
        # Test subscription
        received_events = []
        
        async def event_handler(event: Event):
            received_events.append(event)
        
        subscription_id = await bus.subscribe("test.subject", event_handler)
        assert subscription_id
        
        # Test unsubscription
        success = await bus.unsubscribe(subscription_id)
        assert success
        
        # Disconnect
        await bus.disconnect()
        assert not bus.is_connected()
    
    async def test_event_producer(self):
        """Test event producer with batching."""
        bus = EventBus()
        await bus.connect()
        
        config = ProducerConfig(
            batch_size=5,
            batch_timeout=0.1,
            enable_batching=True
        )
        producer = EventProducer(bus, config)
        
        await producer.start()
        
        try:
            # Publish multiple events
            for i in range(10):
                await producer.publish(
                    EventType.AGENT_RUN_STARTED,
                    {"run_id": f"run_{i}"}
                )
            
            # Wait for batching
            await asyncio.sleep(0.2)
            
            # Check stats
            stats = producer.get_stats()
            assert stats["events_published"] > 0
            assert stats["batches_sent"] > 0
            
        finally:
            await producer.stop()
            await bus.disconnect()
    
    async def test_event_consumer(self):
        """Test event consumer with concurrency control."""
        bus = EventBus()
        await bus.connect()
        
        config = ConsumerConfig(
            max_concurrent_events=3,
            event_timeout=1.0,
            enable_dlq=True
        )
        consumer = EventConsumer(bus, config)
        
        await consumer.start()
        
        try:
            # Register handler
            processed_events = []
            
            async def event_handler(event: Event):
                processed_events.append(event)
                await asyncio.sleep(0.1)  # Simulate processing
            
            consumer.register_handler(EventType.AGENT_RUN_STARTED, event_handler)
            
            # Subscribe to events
            await consumer.subscribe_to_event_type(EventType.AGENT_RUN_STARTED)
            
            # Publish events
            producer = EventProducer(bus)
            await producer.start()
            
            for i in range(5):
                await producer.publish(
                    EventType.AGENT_RUN_STARTED,
                    {"run_id": f"run_{i}"}
                )
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Check stats
            stats = consumer.get_stats()
            assert stats["events_processed"] > 0
            
            await producer.stop()
            
        finally:
            await consumer.stop()
            await bus.disconnect()
    
    async def test_dlq_handler(self):
        """Test dead letter queue handler."""
        config = DLQConfig(
            max_dlq_size=100,
            max_retry_attempts=2,
            retry_delay=0.1,
            enable_auto_retry=True
        )
        dlq = DLQHandler(config)
        
        await dlq.start()
        
        try:
            # Create test event
            metadata = EventMetadata(event_type=EventType.AGENT_RUN_STARTED)
            payload = {"test": "data"}
            event = Event(payload=payload, metadata=metadata)
            
            # Send to DLQ
            await dlq.send_to_dlq(event, "test failure")
            
            # Check DLQ stats
            stats = dlq.get_stats()
            assert stats["events_received"] == 1
            assert stats["dlq_size"] == 1
            
            # Get DLQ events
            events = await dlq.get_dlq_events()
            assert len(events) == 1
            assert events[0]["reason"] == "test failure"
            
            # Test manual retry
            success = await dlq.manual_retry(event.metadata.event_id)
            assert success
            
            # Test clear DLQ
            cleared = await dlq.clear_dlq()
            assert cleared == 1
            
        finally:
            await dlq.stop()
    
    async def test_event_store(self):
        """Test event store functionality."""
        config = EventStoreConfig(
            max_events=1000,
            retention_days=1,
            batch_size=10
        )
        store = EventStore(config)
        
        await store.start()
        
        try:
            # Store events
            for i in range(5):
                metadata = EventMetadata(
                    event_type=EventType.AGENT_RUN_STARTED,
                    tenant_id=f"tenant_{i % 2}"
                )
                payload = {"run_id": f"run_{i}"}
                event = Event(payload=payload, metadata=metadata)
                
                success = await store.store_event(event)
                assert success
            
            # Get events
            events = await store.get_events(limit=10)
            assert len(events) == 5
            
            # Get events by tenant
            tenant_events = await store.get_events(tenant_id="tenant_0")
            assert len(tenant_events) > 0
            
            # Get event by ID
            event_id = events[0].metadata.event_id
            event = await store.get_event(event_id)
            assert event is not None
            assert event.metadata.event_id == event_id
            
            # Test statistics
            stats = await store.get_event_statistics()
            assert stats["total_events"] == 5
            assert "event_types" in stats
            
            # Test deletion
            success = await store.delete_event(event_id)
            assert success
            
            # Verify deletion
            event = await store.get_event(event_id)
            assert event is None
            
        finally:
            await store.stop()
    
    async def test_integration_scenario(self):
        """Test complete event system integration."""
        # Setup components
        bus = EventBus()
        await bus.connect()
        
        producer_config = ProducerConfig(batch_size=3, batch_timeout=0.1)
        producer = EventProducer(bus, producer_config)
        
        consumer_config = ConsumerConfig(
            max_concurrent_events=2,
            enable_dlq=True
        )
        consumer = EventConsumer(bus, consumer_config)
        
        store_config = EventStoreConfig(max_events=100)
        store = EventStore(store_config)
        
        # Start all components
        await producer.start()
        await consumer.start()
        await store.start()
        
        try:
            # Setup event processing
            processed_events = []
            
            async def event_handler(event: Event):
                processed_events.append(event)
                # Store event
                await store.store_event(event)
            
            consumer.register_handler(EventType.AGENT_RUN_STARTED, event_handler)
            await consumer.subscribe_to_event_type(EventType.AGENT_RUN_STARTED)
            
            # Publish events
            for i in range(10):
                await producer.publish_agent_run_started(
                    run_id=f"run_{i}",
                    tenant_id="tenant_123",
                    agent_name="test_agent"
                )
            
            # Wait for processing
            await asyncio.sleep(0.5)
            
            # Verify processing
            assert len(processed_events) > 0
            
            # Check stored events
            stored_events = await store.get_events(tenant_id="tenant_123")
            assert len(stored_events) > 0
            
            # Check statistics
            producer_stats = producer.get_stats()
            consumer_stats = consumer.get_stats()
            store_stats = store.get_stats()
            
            assert producer_stats["events_published"] > 0
            assert consumer_stats["events_processed"] > 0
            assert store_stats["events_stored"] > 0
            
        finally:
            # Cleanup
            await producer.stop()
            await consumer.stop()
            await store.stop()
            await bus.disconnect()
    
    async def test_error_handling(self):
        """Test error handling in event system."""
        bus = EventBus()
        await bus.connect()
        
        consumer_config = ConsumerConfig(
            max_concurrent_events=1,
            event_timeout=0.5,
            retry_attempts=2,
            enable_dlq=True
        )
        consumer = EventConsumer(bus, consumer_config)
        
        await consumer.start()
        
        try:
            # Setup failing handler
            async def failing_handler(event: Event):
                raise Exception("Handler failure")
            
            consumer.register_handler(EventType.AGENT_RUN_STARTED, failing_handler)
            await consumer.subscribe_to_event_type(EventType.AGENT_RUN_STARTED)
            
            # Publish event
            producer = EventProducer(bus)
            await producer.start()
            
            await producer.publish(
                EventType.AGENT_RUN_STARTED,
                {"run_id": "failing_run"}
            )
            
            # Wait for processing and retries
            await asyncio.sleep(1.0)
            
            # Check that event went to DLQ
            dlq_stats = consumer.dlq_handler.get_stats()
            assert dlq_stats["events_received"] > 0
            
            await producer.stop()
            
        finally:
            await consumer.stop()
            await bus.disconnect()


if __name__ == "__main__":
    pytest.main([__file__])
