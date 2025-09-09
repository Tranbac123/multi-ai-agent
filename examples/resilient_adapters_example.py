#!/usr/bin/env python3
"""
Example usage of resilient tool adapters and event system.
"""

import asyncio
import structlog
from typing import Dict, Any

from libs.adapters import (
    BaseToolAdapter, AdapterConfig, ToolAdapterManager,
    HTTPAdapter, HTTPAdapterConfig,
    DatabaseAdapter, DatabaseAdapterConfig
)
from libs.events import (
    EventBus, EventBusConfig, EventProducer, ProducerConfig,
    EventConsumer, ConsumerConfig, EventStore, EventStoreConfig,
    Event, EventType, EventMetadata
)

# Configure logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


class ExampleToolAdapter(BaseToolAdapter):
    """Example tool adapter for demonstration."""
    
    def __init__(self, name: str, config: AdapterConfig = None):
        super().__init__(name, config)
        self.call_count = 0
    
    async def _execute_tool(self, operation: str, data: Dict[str, Any] = None) -> Dict[str, Any]:
        """Execute a tool operation."""
        self.call_count += 1
        
        # Simulate some work
        await asyncio.sleep(0.1)
        
        # Simulate occasional failures
        if self.call_count % 10 == 0:
            raise Exception("Simulated failure")
        
        return {
            "operation": operation,
            "data": data or {},
            "call_count": self.call_count,
            "timestamp": asyncio.get_event_loop().time()
        }


async def demonstrate_resilient_adapters():
    """Demonstrate resilient tool adapters."""
    logger.info("Starting resilient adapters demonstration")
    
    # Create adapter manager
    manager = ToolAdapterManager()
    
    # Create example adapters with different configurations
    config1 = AdapterConfig()
    config1.circuit_breaker.failure_threshold = 3
    config1.retry_policy.max_attempts = 2
    config1.bulkhead.max_concurrent = 5
    config1.rate_limiter.requests_per_second = 10.0
    
    adapter1 = ExampleToolAdapter("example_adapter_1", config1)
    manager.add_adapter("adapter1", adapter1)
    
    # Create HTTP adapter
    http_config = HTTPAdapterConfig(
        base_url="https://httpbin.org",
        timeout=10.0
    )
    http_adapter = HTTPAdapter("http_adapter", http_config)
    manager.add_adapter("http", http_adapter)
    
    # Create database adapter
    db_config = DatabaseAdapterConfig(
        connection_string="sqlite:///example.db"
    )
    db_adapter = DatabaseAdapter("db_adapter", db_config)
    manager.add_adapter("database", db_adapter)
    
    # Start all adapters
    await manager.start_all()
    
    try:
        # Demonstrate normal operation
        logger.info("Testing normal operation")
        result = await adapter1.execute("test_operation", {"key": "value"})
        logger.info("Adapter result", result=result)
        
        # Demonstrate concurrent execution
        logger.info("Testing concurrent execution")
        tasks = [
            adapter1.execute(f"operation_{i}", {"index": i})
            for i in range(20)
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if isinstance(r, dict))
        logger.info("Concurrent execution results", 
                   total=len(results), successful=success_count)
        
        # Demonstrate HTTP adapter
        logger.info("Testing HTTP adapter")
        try:
            response = await http_adapter.get("/get")
            logger.info("HTTP response", status=response.status_code)
        except Exception as e:
            logger.warning("HTTP request failed", error=str(e))
        
        # Show adapter statistics
        logger.info("Adapter statistics", stats=manager.get_all_stats())
        
    finally:
        # Stop all adapters
        await manager.stop_all()
        logger.info("All adapters stopped")


async def demonstrate_event_system():
    """Demonstrate event system with NATS and DLQ."""
    logger.info("Starting event system demonstration")
    
    # Create event bus
    bus_config = EventBusConfig(servers=["nats://localhost:4222"])
    bus = EventBus(bus_config)
    await bus.connect()
    
    # Create event store
    store_config = EventStoreConfig(max_events=1000)
    store = EventStore(store_config)
    await store.start()
    
    # Create producer
    producer_config = ProducerConfig(
        batch_size=5,
        batch_timeout=1.0,
        enable_batching=True
    )
    producer = EventProducer(bus, producer_config)
    await producer.start()
    
    # Create consumer
    consumer_config = ConsumerConfig(
        max_concurrent_events=3,
        enable_dlq=True
    )
    consumer = EventConsumer(bus, consumer_config)
    await consumer.start()
    
    try:
        # Setup event processing
        processed_events = []
        
        async def event_handler(event: Event):
            processed_events.append(event)
            logger.info("Processing event", 
                       event_id=event.metadata.event_id,
                       event_type=event.metadata.event_type.value)
            
            # Store event
            await store.store_event(event)
        
        # Register handlers
        consumer.register_handler(EventType.AGENT_RUN_STARTED, event_handler)
        consumer.register_handler(EventType.ROUTER_DECISION_MADE, event_handler)
        consumer.register_handler(EventType.SYSTEM_ALERT, event_handler)
        
        # Subscribe to event types
        await consumer.subscribe_to_event_type(EventType.AGENT_RUN_STARTED)
        await consumer.subscribe_to_event_type(EventType.ROUTER_DECISION_MADE)
        await consumer.subscribe_to_event_type(EventType.SYSTEM_ALERT)
        
        # Publish various events
        logger.info("Publishing events")
        
        # Agent events
        for i in range(5):
            await producer.publish_agent_run_started(
                run_id=f"run_{i}",
                tenant_id="tenant_123",
                agent_name="example_agent"
            )
        
        # Router events
        for i in range(3):
            await producer.publish_router_decision(
                request_id=f"req_{i}",
                tenant_id="tenant_123",
                decision={"tier": "SLM_A", "confidence": 0.8}
            )
        
        # System events
        await producer.publish_system_alert(
            alert_type="high_cpu",
            message="CPU usage is above 90%",
            severity="warning"
        )
        
        # Wait for processing
        await asyncio.sleep(2.0)
        
        # Show results
        logger.info("Event processing results",
                   processed=len(processed_events))
        
        # Show stored events
        stored_events = await store.get_events(limit=10)
        logger.info("Stored events", count=len(stored_events))
        
        # Show statistics
        producer_stats = producer.get_stats()
        consumer_stats = consumer.get_stats()
        store_stats = store.get_stats()
        
        logger.info("Event system statistics",
                   producer=producer_stats,
                   consumer=consumer_stats,
                   store=store_stats)
        
    finally:
        # Cleanup
        await producer.stop()
        await consumer.stop()
        await store.stop()
        await bus.disconnect()
        logger.info("Event system stopped")


async def demonstrate_integration():
    """Demonstrate integrated system with adapters and events."""
    logger.info("Starting integrated demonstration")
    
    # Setup event system
    bus = EventBus()
    await bus.connect()
    
    producer = EventProducer(bus)
    await producer.start()
    
    consumer = EventConsumer(bus)
    await consumer.start()
    
    # Setup adapter manager
    manager = ToolAdapterManager()
    
    # Create adapter that publishes events
    class EventPublishingAdapter(BaseToolAdapter):
        def __init__(self, name: str, producer: EventProducer):
            super().__init__(name)
            self.producer = producer
            self.operation_count = 0
        
        async def _execute_tool(self, operation: str, data: Dict[str, Any] = None):
            self.operation_count += 1
            
            # Publish tool call started event
            await self.producer.publish(
                EventType.TOOL_CALL_STARTED,
                {
                    "operation": operation,
                    "data": data,
                    "count": self.operation_count
                }
            )
            
            # Simulate work
            await asyncio.sleep(0.1)
            
            # Publish tool call completed event
            await self.producer.publish(
                EventType.TOOL_CALL_COMPLETED,
                {
                    "operation": operation,
                    "result": "success",
                    "count": self.operation_count
                }
            )
            
            return {"operation": operation, "count": self.operation_count}
    
    # Create event publishing adapter
    event_adapter = EventPublishingAdapter("event_adapter", producer)
    manager.add_adapter("event_adapter", event_adapter)
    
    # Setup event processing
    tool_events = []
    
    async def tool_event_handler(event: Event):
        tool_events.append(event)
        logger.info("Tool event received",
                   event_type=event.metadata.event_type.value,
                   operation=event.payload.get("operation"))
    
    consumer.register_handler(EventType.TOOL_CALL_STARTED, tool_event_handler)
    consumer.register_handler(EventType.TOOL_CALL_COMPLETED, tool_event_handler)
    
    await consumer.subscribe_to_event_type(EventType.TOOL_CALL_STARTED)
    await consumer.subscribe_to_event_type(EventType.TOOL_CALL_COMPLETED)
    
    # Start adapters
    await manager.start_all()
    
    try:
        # Execute operations
        logger.info("Executing operations with event publishing")
        
        for i in range(10):
            result = await event_adapter.execute(f"operation_{i}", {"index": i})
            logger.info("Operation result", result=result)
        
        # Wait for event processing
        await asyncio.sleep(1.0)
        
        # Show results
        logger.info("Integration results",
                   tool_events=len(tool_events),
                   adapter_stats=event_adapter.get_stats())
        
    finally:
        # Cleanup
        await manager.stop_all()
        await producer.stop()
        await consumer.stop()
        await bus.disconnect()
        logger.info("Integrated demonstration completed")


async def main():
    """Main demonstration function."""
    logger.info("Starting resilient adapters and event system demonstration")
    
    try:
        # Demonstrate resilient adapters
        await demonstrate_resilient_adapters()
        
        # Demonstrate event system
        await demonstrate_event_system()
        
        # Demonstrate integration
        await demonstrate_integration()
        
        logger.info("Demonstration completed successfully")
        
    except Exception as e:
        logger.error("Demonstration failed", error=str(e))
        raise


if __name__ == "__main__":
    asyncio.run(main())
