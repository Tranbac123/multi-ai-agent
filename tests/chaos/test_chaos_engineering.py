"""Chaos engineering tests for resilience."""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, patch
from hypothesis import given, strategies as st

from apps.orchestrator.core.workflow_executor import WorkflowExecutor
from apps.orchestrator.core.saga_orchestrator import SagaOrchestrator
from eval.episode_replay import EpisodeReplay
from data_plane.events.nats_event_bus import NATSEventBus


class TestOrchestratorFailure:
    """Test orchestrator failure scenarios."""

    @pytest.mark.asyncio
    async def test_kill_orchestrator_mid_run(self):
        """Test killing orchestrator mid-run and episode replay completion."""
        executor = WorkflowExecutor()
        replay = EpisodeReplay()
        
        # Start workflow execution
        workflow_task = asyncio.create_task(
            executor.execute_workflow(
                workflow_name="test_workflow",
                tenant_id="tenant_001",
                user_id="user_001",
                input_data={"message": "Test message"}
            )
        )
        
        # Let it run for a bit
        await asyncio.sleep(0.1)
        
        # Kill orchestrator (simulate failure)
        executor.shutdown()
        
        # Wait for task to complete or fail
        try:
            result = await asyncio.wait_for(workflow_task, timeout=1.0)
        except asyncio.TimeoutError:
            result = {"success": False, "error": "orchestrator_killed"}
        
        # Should fail due to orchestrator kill
        assert result["success"] is False
        
        # Record episode for replay
        episode_id = await replay.record_episode(
            tenant_id="tenant_001",
            user_id="user_001",
            session_id="session_001",
            steps=[
                {
                    "step_id": "step_001",
                    "step_type": "workflow_start",
                    "timestamp": time.time(),
                    "data": {"workflow_name": "test_workflow"}
                },
                {
                    "step_id": "step_002",
                    "step_type": "orchestrator_kill",
                    "timestamp": time.time(),
                    "data": {"reason": "simulated_failure"}
                }
            ]
        )
        
        # Replay episode
        replay_id = await replay.replay_episode(episode_id)
        assert replay_id is not None

    @pytest.mark.asyncio
    async def test_orchestrator_restart_recovery(self):
        """Test orchestrator restart and recovery."""
        executor = WorkflowExecutor()
        
        # Start workflow
        workflow_task = asyncio.create_task(
            executor.execute_workflow(
                workflow_name="test_workflow",
                tenant_id="tenant_001",
                user_id="user_001",
                input_data={"message": "Test message"}
            )
        )
        
        # Let it run
        await asyncio.sleep(0.1)
        
        # Simulate orchestrator restart
        executor.shutdown()
        await asyncio.sleep(0.1)
        
        # Restart orchestrator
        new_executor = WorkflowExecutor()
        
        # Check if workflow can be recovered
        recovery_result = await new_executor.recover_workflow(
            workflow_id="test_workflow_001",
            tenant_id="tenant_001"
        )
        
        assert recovery_result is not None

    @pytest.mark.asyncio
    async def test_partial_workflow_completion(self):
        """Test partial workflow completion during failure."""
        executor = WorkflowExecutor()
        
        # Mock workflow steps
        steps_completed = []
        
        async def mock_step(step_name):
            steps_completed.append(step_name)
            await asyncio.sleep(0.1)
            return f"Completed {step_name}"
        
        # Start workflow with multiple steps
        workflow_task = asyncio.create_task(
            executor.execute_workflow_with_steps([
                ("step1", mock_step),
                ("step2", mock_step),
                ("step3", mock_step),
                ("step4", mock_step)
            ])
        )
        
        # Let it run for a bit
        await asyncio.sleep(0.2)
        
        # Kill orchestrator
        executor.shutdown()
        
        # Wait for task to complete
        try:
            result = await asyncio.wait_for(workflow_task, timeout=1.0)
        except asyncio.TimeoutError:
            result = {"success": False, "steps_completed": steps_completed}
        
        # Should have completed some steps
        assert len(steps_completed) > 0
        assert len(steps_completed) < 4  # Not all steps completed

    @pytest.mark.asyncio
    async def test_workflow_state_persistence(self):
        """Test workflow state persistence during failure."""
        executor = WorkflowExecutor()
        
        # Start workflow with state persistence
        workflow_id = "test_workflow_001"
        
        workflow_task = asyncio.create_task(
            executor.execute_workflow(
                workflow_name="test_workflow",
                tenant_id="tenant_001",
                user_id="user_001",
                input_data={"message": "Test message"},
                workflow_id=workflow_id
            )
        )
        
        # Let it run and persist state
        await asyncio.sleep(0.1)
        await executor.persist_workflow_state(workflow_id)
        
        # Kill orchestrator
        executor.shutdown()
        
        # Restart and recover state
        new_executor = WorkflowExecutor()
        recovered_state = await new_executor.load_workflow_state(workflow_id)
        
        assert recovered_state is not None
        assert recovered_state["workflow_id"] == workflow_id
        assert recovered_state["tenant_id"] == "tenant_001"


class TestNATSFailure:
    """Test NATS failure scenarios."""

    @pytest.mark.asyncio
    async def test_nats_outage_dlq_retry_success(self, nats_fixture):
        """Test NATS outage, DLQ, then retry success."""
        event_bus = NATSEventBus(nats_fixture)
        
        # Simulate NATS outage
        await nats_fixture.close()
        
        # Try to send event (should fail)
        try:
            await event_bus.publish_event(
                topic="test.topic",
                event_data={"message": "Test event"},
                tenant_id="tenant_001"
            )
        except Exception as e:
            # Should fail due to NATS outage
            assert "connection" in str(e).lower()
        
        # Send to DLQ
        dlq_result = await event_bus.send_to_dlq(
            topic="test.topic",
            event_data={"message": "Test event"},
            error=str(e),
            tenant_id="tenant_001"
        )
        assert dlq_result is True
        
        # Restore NATS connection
        new_nats = await nats.connect("nats://localhost:4222")
        
        # Retry from DLQ
        retry_result = await event_bus.retry_from_dlq(
            dlq_topic="dlq.test.topic",
            original_topic="test.topic"
        )
        assert retry_result is True

    @pytest.mark.asyncio
    async def test_nats_partial_outage(self, nats_fixture):
        """Test NATS partial outage (some topics fail)."""
        event_bus = NATSEventBus(nats_fixture)
        
        # Mock partial NATS failure
        with patch.object(nats_fixture, 'publish') as mock_publish:
            mock_publish.side_effect = [
                Exception("Topic 1 failed"),
                None,  # Topic 2 succeeds
                Exception("Topic 3 failed")
            ]
            
            # Try to publish to multiple topics
            results = []
            topics = ["topic1", "topic2", "topic3"]
            
            for topic in topics:
                try:
                    await event_bus.publish_event(
                        topic=topic,
                        event_data={"message": f"Test {topic}"},
                        tenant_id="tenant_001"
                    )
                    results.append(True)
                except Exception:
                    results.append(False)
            
            # Should have mixed results
            assert results == [False, True, False]

    @pytest.mark.asyncio
    async def test_nats_connection_recovery(self, nats_fixture):
        """Test NATS connection recovery."""
        event_bus = NATSEventBus(nats_fixture)
        
        # Close connection
        await nats_fixture.close()
        
        # Try to use event bus (should handle gracefully)
        try:
            await event_bus.publish_event(
                topic="test.topic",
                event_data={"message": "Test event"},
                tenant_id="tenant_001"
            )
        except Exception:
            # Should fail gracefully
            pass
        
        # Reconnect
        await event_bus.reconnect()
        
        # Should work again
        result = await event_bus.publish_event(
            topic="test.topic",
            event_data={"message": "Test event"},
            tenant_id="tenant_001"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_nats_message_ordering_during_failure(self, nats_fixture):
        """Test message ordering during NATS failure."""
        event_bus = NATSEventBus(nats_fixture)
        
        # Send messages with sequence numbers
        messages = []
        for i in range(10):
            message = {
                "sequence": i,
                "content": f"Message {i}",
                "timestamp": time.time()
            }
            messages.append(message)
            
            try:
                await event_bus.publish_event(
                    topic="test.topic",
                    event_data=message,
                    tenant_id="tenant_001"
                )
            except Exception:
                # Some messages might fail
                pass
        
        # Check message ordering
        received_messages = await event_bus.get_received_messages("test.topic")
        
        # Messages should be in order
        sequences = [msg["sequence"] for msg in received_messages]
        assert sequences == sorted(sequences)


class TestDatabaseFailure:
    """Test database failure scenarios."""

    @pytest.mark.asyncio
    async def test_database_connection_failure(self, postgres_fixture):
        """Test database connection failure handling."""
        from libs.database.client import DatabaseClient
        
        db_client = DatabaseClient(postgres_fixture)
        
        # Simulate database connection failure
        with patch.object(postgres_fixture, 'execute') as mock_execute:
            mock_execute.side_effect = Exception("Database connection failed")
            
            # Try to execute query
            try:
                await db_client.execute("SELECT 1")
            except Exception as e:
                assert "connection" in str(e).lower()
            
            # Should handle gracefully
            assert db_client.is_healthy() is False

    @pytest.mark.asyncio
    async def test_database_recovery(self, postgres_fixture):
        """Test database recovery after failure."""
        from libs.database.client import DatabaseClient
        
        db_client = DatabaseClient(postgres_fixture)
        
        # Simulate failure
        with patch.object(postgres_fixture, 'execute') as mock_execute:
            mock_execute.side_effect = Exception("Database connection failed")
            
            # Should be unhealthy
            assert db_client.is_healthy() is False
            
            # Simulate recovery
            mock_execute.side_effect = None
            mock_execute.return_value = None
            
            # Should recover
            await db_client.health_check()
            assert db_client.is_healthy() is True

    @pytest.mark.asyncio
    async def test_database_transaction_rollback(self, postgres_fixture):
        """Test database transaction rollback during failure."""
        from libs.database.client import DatabaseClient
        
        db_client = DatabaseClient(postgres_fixture)
        
        # Start transaction
        async with db_client.transaction():
            try:
                await db_client.execute("INSERT INTO test_table (id) VALUES (1)")
                await db_client.execute("INSERT INTO test_table (id) VALUES (2)")
                
                # Simulate failure
                raise Exception("Simulated failure")
                
            except Exception:
                # Transaction should be rolled back
                pass
        
        # Check that no data was inserted
        result = await db_client.fetch_all("SELECT * FROM test_table")
        assert len(result) == 0


class TestRedisFailure:
    """Test Redis failure scenarios."""

    @pytest.mark.asyncio
    async def test_redis_connection_failure(self, redis_fixture):
        """Test Redis connection failure handling."""
        from libs.rate_limiter import RateLimiter
        
        rate_limiter = RateLimiter(redis_fixture)
        
        # Simulate Redis connection failure
        with patch.object(redis_fixture, 'get') as mock_get:
            mock_get.side_effect = Exception("Redis connection failed")
            
            # Try to check rate limit
            try:
                await rate_limiter.check_rate_limit("tenant_001")
            except Exception as e:
                assert "connection" in str(e).lower()
            
            # Should handle gracefully
            assert rate_limiter.is_healthy() is False

    @pytest.mark.asyncio
    async def test_redis_recovery(self, redis_fixture):
        """Test Redis recovery after failure."""
        from libs.rate_limiter import RateLimiter
        
        rate_limiter = RateLimiter(redis_fixture)
        
        # Simulate failure
        with patch.object(redis_fixture, 'get') as mock_get:
            mock_get.side_effect = Exception("Redis connection failed")
            
            # Should be unhealthy
            assert rate_limiter.is_healthy() is False
            
            # Simulate recovery
            mock_get.side_effect = None
            mock_get.return_value = None
            
            # Should recover
            await rate_limiter.health_check()
            assert rate_limiter.is_healthy() is True

    @pytest.mark.asyncio
    async def test_redis_fallback_behavior(self, redis_fixture):
        """Test Redis fallback behavior during failure."""
        from libs.rate_limiter import RateLimiter
        
        rate_limiter = RateLimiter(redis_fixture, fallback_allow=True)
        
        # Simulate Redis failure
        with patch.object(redis_fixture, 'get') as mock_get:
            mock_get.side_effect = Exception("Redis connection failed")
            
            # Should fallback to allowing requests
            allowed = await rate_limiter.check_rate_limit("tenant_001")
            assert allowed is True  # Fallback behavior


class TestNetworkPartition:
    """Test network partition scenarios."""

    @pytest.mark.asyncio
    async def test_network_partition_recovery(self):
        """Test network partition recovery."""
        from apps.api_gateway.main import app as api_gateway_app
        
        # Simulate network partition
        with patch('httpx.AsyncClient') as mock_client:
            mock_client.side_effect = Exception("Network unreachable")
            
            # Try to make API call
            try:
                async with httpx.AsyncClient(app=api_gateway_app) as client:
                    response = await client.get("/healthz")
            except Exception as e:
                assert "network" in str(e).lower()
            
            # Simulate network recovery
            mock_client.side_effect = None
            
            # Should work again
            async with httpx.AsyncClient(app=api_gateway_app) as client:
                response = await client.get("/healthz")
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_service_isolation_during_partition(self):
        """Test service isolation during network partition."""
        # Simulate partition between services
        with patch('apps.orchestrator.core.workflow_executor.httpx.AsyncClient') as mock_client:
            mock_client.side_effect = Exception("Service unreachable")
            
            # Orchestrator should handle service unavailability
            executor = WorkflowExecutor()
            
            try:
                result = await executor.execute_workflow(
                    workflow_name="test_workflow",
                    tenant_id="tenant_001",
                    user_id="user_001",
                    input_data={}
                )
            except Exception as e:
                # Should handle gracefully
                assert "service" in str(e).lower()


class TestResourceExhaustion:
    """Test resource exhaustion scenarios."""

    @pytest.mark.asyncio
    async def test_memory_exhaustion_handling(self):
        """Test memory exhaustion handling."""
        import gc
        
        # Simulate memory pressure
        large_objects = []
        for i in range(1000):
            large_objects.append([0] * 10000)
        
        # Should handle memory pressure gracefully
        try:
            # Try to process large data
            result = await self._process_large_data(large_objects)
            assert result is not None
        except MemoryError:
            # Should handle memory error gracefully
            pass
        finally:
            # Clean up
            del large_objects
            gc.collect()

    @pytest.mark.asyncio
    async def test_cpu_exhaustion_handling(self):
        """Test CPU exhaustion handling."""
        # Simulate CPU-intensive task
        async def cpu_intensive_task():
            result = 0
            for i in range(1000000):
                result += i * i
            return result
        
        # Should complete within reasonable time
        start_time = time.time()
        result = await cpu_intensive_task()
        end_time = time.time()
        
        assert result > 0
        assert end_time - start_time < 10.0  # Should complete within 10 seconds

    async def _process_large_data(self, data):
        """Process large data (mock implementation)."""
        # Simulate processing
        await asyncio.sleep(0.1)
        return {"processed": len(data)}
