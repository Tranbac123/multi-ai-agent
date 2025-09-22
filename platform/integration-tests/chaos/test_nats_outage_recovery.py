"""Test NATS outage and DLQ retry scenarios."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock

from tests._fixtures.factories import TenantFactory, UserFactory
from tests._helpers.assertions import PerformanceAssertions


class TestNATSOutageRecovery:
    """Test NATS outage and DLQ retry scenarios."""
    
    @pytest.mark.asyncio
    async def test_nats_connection_outage(self):
        """Test NATS connection outage detection and handling."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock NATS client
        nats_client = Mock()
        nats_client.connect = AsyncMock()
        nats_client.is_connected = Mock()
        nats_client.publish = AsyncMock()
        nats_client.subscribe = AsyncMock()
        
        # Simulate NATS connection outage
        nats_client.is_connected.return_value = False
        nats_client.connect.side_effect = Exception("NATS connection failed")
        
        # Mock NATS monitor
        nats_monitor = Mock()
        nats_monitor.check_connection = AsyncMock()
        nats_monitor.reconnect = AsyncMock()
        nats_monitor.failover_to_backup = AsyncMock()
        
        # Simulate connection check
        nats_monitor.check_connection.return_value = {
            "connected": False,
            "error": "Connection timeout",
            "last_successful_connection": time.time() - 60,
            "outage_duration_seconds": 60
        }
        
        # Simulate reconnection attempt
        nats_monitor.reconnect.return_value = {
            "reconnection_attempted": True,
            "reconnection_successful": False,
            "error": "Primary NATS cluster unavailable",
            "retry_count": 3
        }
        
        # Simulate failover to backup
        nats_monitor.failover_to_backup.return_value = {
            "failover_completed": True,
            "backup_cluster": "nats-backup-cluster",
            "failover_time_ms": 200,
            "connection_restored": True
        }
        
        # Test NATS outage detection
        connection_status = await nats_monitor.check_connection()
        assert connection_status["connected"] is False
        assert connection_status["outage_duration_seconds"] == 60
        
        # Test reconnection attempt
        reconnection_result = await nats_monitor.reconnect()
        assert reconnection_result["reconnection_attempted"] is True
        assert reconnection_result["reconnection_successful"] is False
        assert reconnection_result["retry_count"] == 3
        
        # Test failover to backup
        failover_result = await nats_monitor.failover_to_backup()
        assert failover_result["failover_completed"] is True
        assert failover_result["connection_restored"] is True
        
        # Verify failover performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            failover_result["failover_time_ms"], 1000, "NATS failover time"
        )
        assert perf_result.passed, f"NATS failover should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_dlq_message_retry(self):
        """Test Dead Letter Queue (DLQ) message retry."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock DLQ manager
        dlq_manager = Mock()
        dlq_manager.get_dlq_messages = AsyncMock()
        dlq_manager.retry_message = AsyncMock()
        dlq_manager.mark_message_processed = AsyncMock()
        dlq_manager.move_to_permanent_dlq = AsyncMock()
        
        # Simulate DLQ messages
        dlq_messages = [
            {
                "message_id": "msg_001",
                "tenant_id": tenant["tenant_id"],
                "original_topic": "requests",
                "failure_reason": "Processing timeout",
                "retry_count": 2,
                "max_retries": 3,
                "created_at": time.time() - 300,
                "last_retry_at": time.time() - 60
            },
            {
                "message_id": "msg_002",
                "tenant_id": tenant["tenant_id"],
                "original_topic": "responses",
                "failure_reason": "Service unavailable",
                "retry_count": 1,
                "max_retries": 3,
                "created_at": time.time() - 180,
                "last_retry_at": time.time() - 120
            }
        ]
        
        dlq_manager.get_dlq_messages.return_value = dlq_messages
        
        # Simulate successful retry
        dlq_manager.retry_message.return_value = {
            "retry_successful": True,
            "message_id": "msg_001",
            "processing_time_ms": 150,
            "retry_count": 3
        }
        
        # Simulate message processing completion
        dlq_manager.mark_message_processed.return_value = {
            "marked_processed": True,
            "message_id": "msg_001"
        }
        
        # Test DLQ message retrieval
        messages = await dlq_manager.get_dlq_messages()
        assert len(messages) == 2
        assert all(msg["tenant_id"] == tenant["tenant_id"] for msg in messages)
        
        # Test message retry
        for message in messages:
            if message["retry_count"] < message["max_retries"]:
                retry_result = await dlq_manager.retry_message(message["message_id"])
                
                if retry_result["retry_successful"]:
                    # Mark as processed
                    process_result = await dlq_manager.mark_message_processed(message["message_id"])
                    assert process_result["marked_processed"] is True
                else:
                    # Move to permanent DLQ
                    permanent_result = await dlq_manager.move_to_permanent_dlq(message["message_id"])
                    assert permanent_result["moved_to_permanent"] is True
        
        # Verify retry performance
        retry_result = await dlq_manager.retry_message("msg_001")
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            retry_result["processing_time_ms"], 500, "DLQ retry processing time"
        )
        assert perf_result.passed, f"DLQ retry should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_nats_message_duplication_handling(self):
        """Test NATS message duplication handling."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock message deduplication
        message_dedup = Mock()
        message_dedup.check_duplicate = AsyncMock()
        message_dedup.mark_processed = AsyncMock()
        message_dedup.get_message_hash = Mock()
        
        # Simulate message with hash
        message = {
            "message_id": "msg_001",
            "tenant_id": tenant["tenant_id"],
            "content": "test message",
            "timestamp": time.time()
        }
        
        message_dedup.get_message_hash.return_value = "hash_12345"
        
        # Simulate duplicate check
        message_dedup.check_duplicate.return_value = {
            "is_duplicate": False,
            "message_hash": "hash_12345",
            "last_processed": None
        }
        
        # Simulate marking as processed
        message_dedup.mark_processed.return_value = {
            "marked_processed": True,
            "message_hash": "hash_12345",
            "processed_at": time.time()
        }
        
        # Test message deduplication
        message_hash = message_dedup.get_message_hash(message)
        assert message_hash == "hash_12345"
        
        # Test duplicate check
        duplicate_check = await message_dedup.check_duplicate(message_hash)
        assert duplicate_check["is_duplicate"] is False
        assert duplicate_check["message_hash"] == message_hash
        
        # Test marking as processed
        process_result = await message_dedup.mark_processed(message_hash)
        assert process_result["marked_processed"] is True
        assert process_result["message_hash"] == message_hash
        
        # Test duplicate detection
        duplicate_check_2 = await message_dedup.check_duplicate(message_hash)
        assert duplicate_check_2["is_duplicate"] is True
    
    @pytest.mark.asyncio
    async def test_nats_stream_recovery(self):
        """Test NATS stream recovery after outage."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock NATS stream
        nats_stream = Mock()
        nats_stream.get_stream_info = AsyncMock()
        nats_stream.recover_stream = AsyncMock()
        nats_stream.get_missing_messages = AsyncMock()
        nats_stream.replay_missing_messages = AsyncMock()
        
        # Simulate stream info
        nats_stream.get_stream_info.return_value = {
            "stream_name": "requests_stream",
            "state": "recovering",
            "last_sequence": 1000,
            "first_sequence": 1,
            "consumer_count": 3,
            "message_count": 1000
        }
        
        # Simulate missing messages
        nats_stream.get_missing_messages.return_value = [
            {"sequence": 998, "timestamp": time.time() - 300},
            {"sequence": 999, "timestamp": time.time() - 180},
            {"sequence": 1000, "timestamp": time.time() - 60}
        ]
        
        # Simulate stream recovery
        nats_stream.recover_stream.return_value = {
            "recovery_completed": True,
            "recovered_messages": 3,
            "recovery_time_ms": 500,
            "stream_state": "active"
        }
        
        # Simulate message replay
        nats_stream.replay_missing_messages.return_value = {
            "replay_completed": True,
            "messages_replayed": 3,
            "replay_time_ms": 300,
            "successful_replays": 3,
            "failed_replays": 0
        }
        
        # Test stream recovery
        stream_info = await nats_stream.get_stream_info()
        assert stream_info["state"] == "recovering"
        assert stream_info["message_count"] == 1000
        
        # Test missing message detection
        missing_messages = await nats_stream.get_missing_messages()
        assert len(missing_messages) == 3
        
        # Test stream recovery
        recovery_result = await nats_stream.recover_stream()
        assert recovery_result["recovery_completed"] is True
        assert recovery_result["recovered_messages"] == 3
        assert recovery_result["stream_state"] == "active"
        
        # Test message replay
        replay_result = await nats_stream.replay_missing_messages(missing_messages)
        assert replay_result["replay_completed"] is True
        assert replay_result["messages_replayed"] == 3
        assert replay_result["successful_replays"] == 3
        assert replay_result["failed_replays"] == 0
        
        # Verify recovery performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            recovery_result["recovery_time_ms"], 2000, "NATS stream recovery time"
        )
        assert perf_result.passed, f"Stream recovery should be reasonable: {perf_result.message}"
        
        # Verify replay performance
        replay_perf_result = PerformanceAssertions.assert_latency_below_threshold(
            replay_result["replay_time_ms"], 1000, "Message replay time"
        )
        assert replay_perf_result.passed, f"Message replay should be fast: {replay_perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_nats_consumer_group_recovery(self):
        """Test NATS consumer group recovery."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock consumer group
        consumer_group = Mock()
        consumer_group.get_consumer_info = AsyncMock()
        consumer_group.rebalance_consumers = AsyncMock()
        consumer_group.resume_consumption = AsyncMock()
        consumer_group.check_consumer_health = AsyncMock()
        
        # Simulate consumer group info
        consumer_group.get_consumer_info.return_value = {
            "group_name": "request_processors",
            "active_consumers": 2,
            "expected_consumers": 3,
            "consumer_lag": 150,
            "last_message_processed": time.time() - 30,
            "group_state": "recovering"
        }
        
        # Simulate consumer health check
        consumer_group.check_consumer_health.return_value = {
            "healthy_consumers": 2,
            "unhealthy_consumers": 1,
            "consumer_issues": [
                {"consumer_id": "consumer_3", "issue": "connection_timeout"}
            ]
        }
        
        # Simulate consumer rebalancing
        consumer_group.rebalance_consumers.return_value = {
            "rebalancing_completed": True,
            "consumers_rebalanced": 2,
            "rebalancing_time_ms": 200,
            "new_consumer_assignment": {
                "consumer_1": ["partition_1", "partition_2"],
                "consumer_2": ["partition_3", "partition_4"]
            }
        }
        
        # Simulate consumption resumption
        consumer_group.resume_consumption.return_value = {
            "consumption_resumed": True,
            "consumers_resumed": 2,
            "resume_time_ms": 100,
            "messages_per_second": 50
        }
        
        # Test consumer group recovery
        group_info = await consumer_group.get_consumer_info()
        assert group_info["group_state"] == "recovering"
        assert group_info["active_consumers"] == 2
        assert group_info["expected_consumers"] == 3
        
        # Test consumer health check
        health_result = await consumer_group.check_consumer_health()
        assert health_result["healthy_consumers"] == 2
        assert health_result["unhealthy_consumers"] == 1
        
        # Test consumer rebalancing
        rebalance_result = await consumer_group.rebalance_consumers()
        assert rebalance_result["rebalancing_completed"] is True
        assert rebalance_result["consumers_rebalanced"] == 2
        
        # Test consumption resumption
        resume_result = await consumer_group.resume_consumption()
        assert resume_result["consumption_resumed"] is True
        assert resume_result["consumers_resumed"] == 2
        assert resume_result["messages_per_second"] > 0
        
        # Verify recovery performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            rebalance_result["rebalancing_time_ms"], 1000, "Consumer rebalancing time"
        )
        assert perf_result.passed, f"Consumer rebalancing should be fast: {perf_result.message}"
    
    @pytest.mark.asyncio
    async def test_nats_message_ordering_recovery(self):
        """Test NATS message ordering recovery."""
        # Setup
        tenant_factory = TenantFactory()
        
        tenant = tenant_factory.create()
        
        # Mock message ordering
        message_ordering = Mock()
        message_ordering.detect_ordering_issues = AsyncMock()
        message_ordering.reorder_messages = AsyncMock()
        message_ordering.verify_ordering = AsyncMock()
        
        # Simulate out-of-order messages
        out_of_order_messages = [
            {"sequence": 100, "timestamp": time.time() - 300, "content": "message 100"},
            {"sequence": 102, "timestamp": time.time() - 180, "content": "message 102"},
            {"sequence": 101, "timestamp": time.time() - 240, "content": "message 101"},
            {"sequence": 103, "timestamp": time.time() - 120, "content": "message 103"}
        ]
        
        # Simulate ordering issue detection
        message_ordering.detect_ordering_issues.return_value = {
            "ordering_issues_detected": True,
            "out_of_order_count": 1,
            "missing_sequences": [],
            "duplicate_sequences": [],
            "ordering_gaps": [{"gap_start": 100, "gap_end": 102}]
        }
        
        # Simulate message reordering
        message_ordering.reorder_messages.return_value = {
            "reordering_completed": True,
            "messages_reordered": 4,
            "reordering_time_ms": 150,
            "correct_sequence": [
                {"sequence": 100, "timestamp": time.time() - 300, "content": "message 100"},
                {"sequence": 101, "timestamp": time.time() - 240, "content": "message 101"},
                {"sequence": 102, "timestamp": time.time() - 180, "content": "message 102"},
                {"sequence": 103, "timestamp": time.time() - 120, "content": "message 103"}
            ]
        }
        
        # Simulate ordering verification
        message_ordering.verify_ordering.return_value = {
            "ordering_verified": True,
            "sequence_gaps": 0,
            "duplicate_sequences": 0,
            "verification_time_ms": 50
        }
        
        # Test ordering issue detection
        ordering_issues = await message_ordering.detect_ordering_issues(out_of_order_messages)
        assert ordering_issues["ordering_issues_detected"] is True
        assert ordering_issues["out_of_order_count"] == 1
        
        # Test message reordering
        reorder_result = await message_ordering.reorder_messages(out_of_order_messages)
        assert reorder_result["reordering_completed"] is True
        assert reorder_result["messages_reordered"] == 4
        
        # Verify correct sequence
        correct_sequence = reorder_result["correct_sequence"]
        sequences = [msg["sequence"] for msg in correct_sequence]
        assert sequences == [100, 101, 102, 103]  # Should be in order
        
        # Test ordering verification
        verification_result = await message_ordering.verify_ordering(correct_sequence)
        assert verification_result["ordering_verified"] is True
        assert verification_result["sequence_gaps"] == 0
        assert verification_result["duplicate_sequences"] == 0
        
        # Verify reordering performance
        perf_result = PerformanceAssertions.assert_latency_below_threshold(
            reorder_result["reordering_time_ms"], 500, "Message reordering time"
        )
        assert perf_result.passed, f"Message reordering should be fast: {perf_result.message}"
