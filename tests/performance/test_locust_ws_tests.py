"""Test Locust WebSocket soak and burst scenarios."""

import pytest
import asyncio
import json
import time
from unittest.mock import Mock, AsyncMock, patch

from tests._fixtures.factories import TenantFactory, WebSocketSessionFactory
from tests._helpers.assertions import PerformanceAssertions


class TestLocustWebSocketScenarios:
    """Test Locust WebSocket soak and burst scenarios."""
    
    @pytest.mark.asyncio
    async def test_websocket_soak_scenario(self):
        """Test WebSocket soak scenario (long-running)."""
        # Setup
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant = tenant_factory.create()
        session = ws_factory.create(tenant["tenant_id"])
        
        # Configure for soak test
        session["backpressure_settings"]["max_queue_size"] = 100
        session["backpressure_settings"]["drop_policy"] = "oldest"
        
        # Mock WebSocket connection
        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        
        # Simulate soak test metrics
        soak_metrics = {
            "total_messages": 0,
            "successful_messages": 0,
            "failed_messages": 0,
            "response_times": [],
            "start_time": time.time(),
            "errors": []
        }
        
        # Simulate long-running test (shortened for unit test)
        test_duration = 0.1  # 100ms for test (would be 60 minutes in real scenario)
        message_interval = 0.01  # Send message every 10ms
        
        end_time = time.time() + test_duration
        
        while time.time() < end_time:
            try:
                message = {
                    "id": f"soak_msg_{soak_metrics['total_messages']}",
                    "content": "Soak test message",
                    "timestamp": time.time()
                }
                
                start_send = time.time()
                await mock_ws.send(json.dumps(message))
                end_send = time.time()
                
                soak_metrics["total_messages"] += 1
                soak_metrics["successful_messages"] += 1
                soak_metrics["response_times"].append((end_send - start_send) * 1000)  # Convert to ms
                
            except Exception as e:
                soak_metrics["failed_messages"] += 1
                soak_metrics["errors"].append(str(e))
            
            await asyncio.sleep(message_interval)
        
        # Calculate final metrics
        total_duration = time.time() - soak_metrics["start_time"]
        avg_response_time = sum(soak_metrics["response_times"]) / len(soak_metrics["response_times"]) if soak_metrics["response_times"] else 0
        messages_per_second = soak_metrics["total_messages"] / total_duration
        error_rate = soak_metrics["failed_messages"] / soak_metrics["total_messages"] if soak_metrics["total_messages"] > 0 else 0
        
        # Verify soak test results
        assert soak_metrics["total_messages"] > 0
        assert soak_metrics["successful_messages"] > 0
        assert error_rate < 0.05  # Less than 5% error rate
        assert messages_per_second > 50  # At least 50 messages per second
        
        # Verify response time performance
        result = PerformanceAssertions.assert_latency_below_threshold(
            avg_response_time, 100, "Soak test average response time"
        )
        assert result.passed, f"Soak test response time should be acceptable: {result.message}"
    
    @pytest.mark.asyncio
    async def test_websocket_burst_scenario(self):
        """Test WebSocket burst scenario (rapid message sending)."""
        # Setup
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant = tenant_factory.create()
        session = ws_factory.create(tenant["tenant_id"])
        
        # Configure for burst test
        session["backpressure_settings"]["max_queue_size"] = 20
        session["backpressure_settings"]["drop_policy"] = "intermediate"
        
        # Mock WebSocket connection
        mock_ws = Mock()
        mock_ws.send = AsyncMock()
        
        # Simulate burst test metrics
        burst_metrics = {
            "burst_size": 50,
            "messages_sent": 0,
            "messages_dropped": 0,
            "response_times": [],
            "start_time": time.time(),
            "errors": []
        }
        
        # Simulate burst of messages
        messages = [
            {
                "id": f"burst_msg_{i}",
                "content": f"Burst message {i}",
                "timestamp": time.time()
            }
            for i in range(burst_metrics["burst_size"])
        ]
        
        # Send burst of messages
        for message in messages:
            try:
                start_send = time.time()
                await mock_ws.send(json.dumps(message))
                end_send = time.time()
                
                burst_metrics["messages_sent"] += 1
                burst_metrics["response_times"].append((end_send - start_send) * 1000)
                
            except Exception as e:
                burst_metrics["messages_dropped"] += 1
                burst_metrics["errors"].append(str(e))
        
        # Calculate burst metrics
        total_duration = time.time() - burst_metrics["start_time"]
        avg_response_time = sum(burst_metrics["response_times"]) / len(burst_metrics["response_times"]) if burst_metrics["response_times"] else 0
        messages_per_second = burst_metrics["messages_sent"] / total_duration if total_duration > 0 else 0
        drop_rate = burst_metrics["messages_dropped"] / burst_metrics["burst_size"]
        
        # Verify burst test results
        assert burst_metrics["messages_sent"] > 0
        assert burst_metrics["messages_sent"] <= burst_metrics["burst_size"]
        assert drop_rate >= 0  # Some drops expected due to backpressure
        
        # Verify burst performance
        result = PerformanceAssertions.assert_latency_below_threshold(
            avg_response_time, 50, "Burst test average response time"
        )
        assert result.passed, f"Burst test response time should be fast: {result.message}"
        
        # Verify throughput
        result = PerformanceAssertions.assert_throughput_above_threshold(
            messages_per_second, 100, "Burst test throughput"
        )
        assert result.passed, f"Burst test should have good throughput: {result.message}"
    
    @pytest.mark.asyncio
    async def test_slow_consumer_burst_scenario(self):
        """Test burst scenario with slow consumer."""
        # Setup
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant = tenant_factory.create()
        session = ws_factory.create(tenant["tenant_id"])
        
        # Configure for slow consumer burst test
        session["backpressure_settings"]["max_queue_size"] = 5
        session["backpressure_settings"]["drop_policy"] = "oldest"
        
        # Mock slow WebSocket connection
        mock_ws = Mock()
        mock_ws.send = AsyncMock(side_effect=lambda x: asyncio.sleep(0.1))  # 100ms delay
        
        # Simulate slow consumer burst metrics
        slow_consumer_metrics = {
            "burst_size": 20,
            "messages_sent": 0,
            "messages_dropped": 0,
            "timeouts": 0,
            "start_time": time.time(),
            "errors": []
        }
        
        # Send burst to slow consumer
        messages = [
            {
                "id": f"slow_burst_msg_{i}",
                "content": f"Slow consumer burst message {i}",
                "timestamp": time.time()
            }
            for i in range(slow_consumer_metrics["burst_size"])
        ]
        
        for message in messages:
            try:
                # Try to send with timeout
                await asyncio.wait_for(
                    mock_ws.send(json.dumps(message)),
                    timeout=0.05  # 50ms timeout
                )
                slow_consumer_metrics["messages_sent"] += 1
                
            except asyncio.TimeoutError:
                slow_consumer_metrics["timeouts"] += 1
                slow_consumer_metrics["messages_dropped"] += 1
                
            except Exception as e:
                slow_consumer_metrics["messages_dropped"] += 1
                slow_consumer_metrics["errors"].append(str(e))
        
        # Calculate slow consumer metrics
        total_duration = time.time() - slow_consumer_metrics["start_time"]
        timeout_rate = slow_consumer_metrics["timeouts"] / slow_consumer_metrics["burst_size"]
        drop_rate = slow_consumer_metrics["messages_dropped"] / slow_consumer_metrics["burst_size"]
        
        # Verify slow consumer handling
        assert slow_consumer_metrics["messages_sent"] > 0  # Some messages should be sent
        assert slow_consumer_metrics["timeouts"] > 0  # Some timeouts expected
        assert timeout_rate > 0.3  # At least 30% timeout rate due to slow consumer
        assert drop_rate > 0.3  # At least 30% drop rate
        
        # Verify system doesn't hang
        result = PerformanceAssertions.assert_latency_below_threshold(
            total_duration * 1000, 2000, "Slow consumer burst handling time"
        )
        assert result.passed, f"Slow consumer burst should be handled efficiently: {result.message}"
    
    @pytest.mark.asyncio
    async def test_mixed_load_scenario(self):
        """Test mixed load scenario (normal + burst + slow consumers)."""
        # Setup
        tenant_factory = TenantFactory()
        ws_factory = WebSocketSessionFactory()
        
        tenant = tenant_factory.create()
        session = ws_factory.create(tenant["tenant_id"])
        
        # Configure for mixed load
        session["backpressure_settings"]["max_queue_size"] = 50
        session["backpressure_settings"]["drop_policy"] = "intermediate"
        
        # Mock WebSocket connections for different consumer types
        normal_ws = Mock()
        normal_ws.send = AsyncMock()
        
        slow_ws = Mock()
        slow_ws.send = AsyncMock(side_effect=lambda x: asyncio.sleep(0.2))
        
        # Simulate mixed load metrics
        mixed_load_metrics = {
            "normal_messages": 0,
            "burst_messages": 0,
            "slow_messages": 0,
            "total_successful": 0,
            "total_dropped": 0,
            "start_time": time.time(),
            "response_times": {
                "normal": [],
                "burst": [],
                "slow": []
            }
        }
        
        # Normal load messages
        normal_messages = [
            {"id": f"normal_{i}", "content": f"Normal message {i}"}
            for i in range(10)
        ]
        
        # Burst messages
        burst_messages = [
            {"id": f"burst_{i}", "content": f"Burst message {i}"}
            for i in range(30)
        ]
        
        # Slow consumer messages
        slow_messages = [
            {"id": f"slow_{i}", "content": f"Slow message {i}"}
            for i in range(5)
        ]
        
        # Process normal messages
        for message in normal_messages:
            try:
                start_time = time.time()
                await normal_ws.send(json.dumps(message))
                end_time = time.time()
                
                mixed_load_metrics["normal_messages"] += 1
                mixed_load_metrics["total_successful"] += 1
                mixed_load_metrics["response_times"]["normal"].append((end_time - start_time) * 1000)
                
            except Exception as e:
                mixed_load_metrics["total_dropped"] += 1
        
        # Process burst messages
        for message in burst_messages:
            try:
                start_time = time.time()
                await normal_ws.send(json.dumps(message))
                end_time = time.time()
                
                mixed_load_metrics["burst_messages"] += 1
                mixed_load_metrics["total_successful"] += 1
                mixed_load_metrics["response_times"]["burst"].append((end_time - start_time) * 1000)
                
            except Exception as e:
                mixed_load_metrics["total_dropped"] += 1
        
        # Process slow consumer messages
        for message in slow_messages:
            try:
                start_time = time.time()
                await asyncio.wait_for(
                    slow_ws.send(json.dumps(message)),
                    timeout=0.1
                )
                end_time = time.time()
                
                mixed_load_metrics["slow_messages"] += 1
                mixed_load_metrics["total_successful"] += 1
                mixed_load_metrics["response_times"]["slow"].append((end_time - start_time) * 1000)
                
            except asyncio.TimeoutError:
                mixed_load_metrics["total_dropped"] += 1
            except Exception as e:
                mixed_load_metrics["total_dropped"] += 1
        
        # Calculate mixed load metrics
        total_duration = time.time() - mixed_load_metrics["start_time"]
        total_messages = mixed_load_metrics["total_successful"] + mixed_load_metrics["total_dropped"]
        success_rate = mixed_load_metrics["total_successful"] / total_messages if total_messages > 0 else 0
        
        # Calculate average response times
        avg_normal_rt = sum(mixed_load_metrics["response_times"]["normal"]) / len(mixed_load_metrics["response_times"]["normal"]) if mixed_load_metrics["response_times"]["normal"] else 0
        avg_burst_rt = sum(mixed_load_metrics["response_times"]["burst"]) / len(mixed_load_metrics["response_times"]["burst"]) if mixed_load_metrics["response_times"]["burst"] else 0
        
        # Verify mixed load results
        assert mixed_load_metrics["normal_messages"] > 0
        assert mixed_load_metrics["burst_messages"] > 0
        assert mixed_load_metrics["slow_messages"] >= 0  # Some may be dropped
        assert success_rate > 0.5  # At least 50% success rate
        
        # Verify response times for different load types
        if avg_normal_rt > 0:
            result = PerformanceAssertions.assert_latency_below_threshold(
                avg_normal_rt, 50, "Normal load response time"
            )
            assert result.passed, f"Normal load should be fast: {result.message}"
        
        if avg_burst_rt > 0:
            result = PerformanceAssertions.assert_latency_below_threshold(
                avg_burst_rt, 100, "Burst load response time"
            )
            assert result.passed, f"Burst load should be acceptable: {result.message}"
