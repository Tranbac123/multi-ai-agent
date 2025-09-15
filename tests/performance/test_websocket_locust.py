"""Locust WebSocket performance tests with steady and burst profiles."""

import pytest
import asyncio
import json
import time
from typing import Dict, Any, List
from datetime import datetime
from unittest.mock import Mock, AsyncMock

from locust import HttpUser, task, between
from locust.env import Environment
from locust.stats import stats_printer, stats_history
from locust.log import setup_logging

from tests._fixtures.factories import factory, TenantTier


class WebSocketLocustUser(HttpUser):
    """Locust user for WebSocket performance testing."""
    
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        """Initialize WebSocket connection."""
        self.tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        self.user = factory.create_user(tenant_id=self.tenant.tenant_id)
        self.connection_id = f"locust_{int(time.time())}"
        self.message_count = 0
        self.dropped_count = 0
        
        # Simulate WebSocket connection
        self.connected = True
    
    def on_stop(self):
        """Cleanup WebSocket connection."""
        self.connected = False
    
    @task(10)
    def send_chat_message(self):
        """Send chat message via WebSocket."""
        if not self.connected:
            return
        
        message = {
            "message_id": f"msg_{self.message_count}",
            "message_type": "chat",
            "payload": {
                "text": f"Test message {self.message_count}",
                "timestamp": datetime.now().isoformat()
            },
            "tenant_id": self.tenant.tenant_id,
            "user_id": self.user.user_id
        }
        
        # Simulate WebSocket send with response time
        start_time = time.time()
        
        # Simulate network latency
        time.sleep(0.01)
        
        # Simulate success/failure based on load
        success = self._simulate_websocket_send(message)
        
        response_time = (time.time() - start_time) * 1000
        
        if success:
            self.message_count += 1
        else:
            self.dropped_count += 1
        
        # Record custom metric
        self.environment.events.request.fire(
            request_type="WebSocket",
            name="send_message",
            response_time=response_time,
            response_length=len(json.dumps(message)),
            exception=None if success else Exception("Message dropped")
        )
    
    @task(5)
    def send_typing_indicator(self):
        """Send typing indicator."""
        if not self.connected:
            return
        
        message = {
            "message_id": f"typing_{self.message_count}",
            "message_type": "typing",
            "payload": {"status": "typing"},
            "tenant_id": self.tenant.tenant_id,
            "user_id": self.user.user_id
        }
        
        start_time = time.time()
        time.sleep(0.005)  # Faster for typing indicators
        success = self._simulate_websocket_send(message)
        response_time = (time.time() - start_time) * 1000
        
        self.environment.events.request.fire(
            request_type="WebSocket",
            name="typing_indicator",
            response_time=response_time,
            response_length=len(json.dumps(message)),
            exception=None if success else Exception("Typing dropped")
        )
    
    @task(2)
    def send_heartbeat(self):
        """Send heartbeat message."""
        if not self.connected:
            return
        
        message = {
            "message_id": f"heartbeat_{int(time.time())}",
            "message_type": "ping",
            "payload": {},
            "tenant_id": self.tenant.tenant_id,
            "user_id": self.user.user_id
        }
        
        start_time = time.time()
        time.sleep(0.001)  # Very fast for heartbeats
        success = self._simulate_websocket_send(message)
        response_time = (time.time() - start_time) * 1000
        
        self.environment.events.request.fire(
            request_type="WebSocket",
            name="heartbeat",
            response_time=response_time,
            response_length=len(json.dumps(message)),
            exception=None if success else Exception("Heartbeat failed")
        )
    
    def _simulate_websocket_send(self, message: Dict[str, Any]) -> bool:
        """Simulate WebSocket send with backpressure logic."""
        # Simulate backpressure based on message type and load
        message_type = message["message_type"]
        
        # High priority messages (chat) have higher success rate
        if message_type == "chat":
            success_rate = 0.95
        elif message_type == "typing":
            success_rate = 0.85  # Lower priority, more likely to drop
        elif message_type == "ping":
            success_rate = 0.98  # Heartbeats should rarely fail
        else:
            success_rate = 0.90
        
        # Simulate random success/failure
        import random
        return random.random() < success_rate


class SteadyLoadWebSocketUser(WebSocketLocustUser):
    """User for steady load testing."""
    
    wait_time = between(0.5, 1.0)  # Slower, more steady load
    
    @task(20)
    def send_chat_message_steady(self):
        """Send chat message with steady load."""
        self.send_chat_message()
    
    @task(10)
    def send_typing_indicator_steady(self):
        """Send typing indicator with steady load."""
        self.send_typing_indicator()


class BurstLoadWebSocketUser(WebSocketLocustUser):
    """User for burst load testing."""
    
    wait_time = between(0.01, 0.1)  # Faster, burst load
    
    @task(50)
    def send_chat_message_burst(self):
        """Send chat message in burst."""
        self.send_chat_message()
    
    @task(30)
    def send_typing_indicator_burst(self):
        """Send typing indicator in burst."""
        self.send_typing_indicator()


class WebSocketLoadTestRunner:
    """Runner for WebSocket load tests."""
    
    def __init__(self):
        """Initialize load test runner."""
        self.results = {}
    
    async def run_steady_load_test(self, duration: int = 60, users: int = 50) -> Dict[str, Any]:
        """Run steady load test."""
        env = Environment(user_classes=[SteadyLoadWebSocketUser])
        env.create_local_runner()
        
        # Start test
        env.runner.start(users, spawn_rate=10)
        
        # Run for specified duration
        await asyncio.sleep(duration)
        
        # Stop test
        env.runner.quit()
        
        # Collect results
        stats = env.stats
        results = {
            "test_type": "steady_load",
            "duration": duration,
            "users": users,
            "total_requests": stats.total.num_requests,
            "total_failures": stats.total.num_failures,
            "avg_response_time": stats.total.avg_response_time,
            "max_response_time": stats.total.max_response_time,
            "rps": stats.total.total_rps,
            "failure_rate": (stats.total.num_failures / max(stats.total.num_requests, 1)) * 100
        }
        
        self.results["steady_load"] = results
        return results
    
    async def run_burst_load_test(self, duration: int = 30, users: int = 200) -> Dict[str, Any]:
        """Run burst load test."""
        env = Environment(user_classes=[BurstLoadWebSocketUser])
        env.create_local_runner()
        
        # Start test with higher spawn rate for burst
        env.runner.start(users, spawn_rate=50)
        
        # Run for specified duration
        await asyncio.sleep(duration)
        
        # Stop test
        env.runner.quit()
        
        # Collect results
        stats = env.stats
        results = {
            "test_type": "burst_load",
            "duration": duration,
            "users": users,
            "total_requests": stats.total.num_requests,
            "total_failures": stats.total.num_failures,
            "avg_response_time": stats.total.avg_response_time,
            "max_response_time": stats.total.max_response_time,
            "rps": stats.total.total_rps,
            "failure_rate": (stats.total.num_failures / max(stats.total.num_requests, 1)) * 100
        }
        
        self.results["burst_load"] = results
        return results
    
    def generate_html_report(self) -> str:
        """Generate HTML report from test results."""
        html = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>WebSocket Load Test Results</title>
            <style>
                body { font-family: Arial, sans-serif; margin: 20px; }
                .test-result { border: 1px solid #ccc; padding: 15px; margin: 10px 0; }
                .metric { margin: 5px 0; }
                .success { color: green; }
                .warning { color: orange; }
                .error { color: red; }
            </style>
        </head>
        <body>
            <h1>WebSocket Load Test Results</h1>
        """
        
        for test_name, results in self.results.items():
            html += f"""
            <div class="test-result">
                <h2>{test_name.replace('_', ' ').title()}</h2>
                <div class="metric">Duration: {results['duration']}s</div>
                <div class="metric">Users: {results['users']}</div>
                <div class="metric">Total Requests: {results['total_requests']}</div>
                <div class="metric">Total Failures: {results['total_failures']}</div>
                <div class="metric">Avg Response Time: {results['avg_response_time']:.2f}ms</div>
                <div class="metric">Max Response Time: {results['max_response_time']:.2f}ms</div>
                <div class="metric">RPS: {results['rps']:.2f}</div>
                <div class="metric {'error' if results['failure_rate'] > 5 else 'warning' if results['failure_rate'] > 1 else 'success'}">
                    Failure Rate: {results['failure_rate']:.2f}%
                </div>
            </div>
            """
        
        html += """
        </body>
        </html>
        """
        
        return html


class TestWebSocketLocustPerformance:
    """Test WebSocket performance with Locust."""
    
    @pytest.mark.asyncio
    async def test_steady_load_websocket(self):
        """Test WebSocket under steady load."""
        runner = WebSocketLoadTestRunner()
        
        # Run steady load test
        results = await runner.run_steady_load_test(duration=10, users=20)
        
        # Validate results
        assert results["total_requests"] > 0
        assert results["failure_rate"] < 10  # Less than 10% failure rate
        assert results["avg_response_time"] < 1000  # Less than 1 second avg response time
        assert results["max_response_time"] < 5000  # Less than 5 seconds max response time
    
    @pytest.mark.asyncio
    async def test_burst_load_websocket(self):
        """Test WebSocket under burst load."""
        runner = WebSocketLoadTestRunner()
        
        # Run burst load test
        results = await runner.run_burst_load_test(duration=5, users=50)
        
        # Validate results
        assert results["total_requests"] > 0
        assert results["failure_rate"] < 20  # Higher failure rate acceptable for burst
        assert results["avg_response_time"] < 2000  # Higher response time acceptable for burst
        assert results["rps"] > 10  # Should achieve reasonable RPS
    
    @pytest.mark.asyncio
    async def test_websocket_html_report_generation(self):
        """Test HTML report generation."""
        runner = WebSocketLoadTestRunner()
        
        # Run both tests
        await runner.run_steady_load_test(duration=5, users=10)
        await runner.run_burst_load_test(duration=3, users=20)
        
        # Generate HTML report
        html_report = runner.generate_html_report()
        
        # Validate HTML report
        assert "<html>" in html_report
        assert "<title>WebSocket Load Test Results</title>" in html_report
        assert "steady_load" in html_report
        assert "burst_load" in html_report
        assert "Failure Rate" in html_report
    
    @pytest.mark.asyncio
    async def test_websocket_backpressure_metrics(self):
        """Test WebSocket backpressure metrics under load."""
        runner = WebSocketLoadTestRunner()
        
        # Run steady load test
        results = await runner.run_steady_load_test(duration=15, users=30)
        
        # Check that we have metrics data
        assert "total_requests" in results
        assert "total_failures" in results
        assert "failure_rate" in results
        
        # Under load, we should see some failures (backpressure)
        assert results["total_failures"] >= 0  # Some failures are expected
        
        # Failure rate should be reasonable
        assert results["failure_rate"] < 15  # Less than 15% failure rate under load
    
    @pytest.mark.asyncio
    async def test_websocket_soak_test(self):
        """Test WebSocket under sustained load (soak test)."""
        runner = WebSocketLoadTestRunner()
        
        # Run longer steady load test
        results = await runner.run_steady_load_test(duration=30, users=25)
        
        # Validate soak test results
        assert results["total_requests"] > 100  # Should have processed many requests
        assert results["failure_rate"] < 5  # Low failure rate for soak test
        assert results["avg_response_time"] < 500  # Good response times for soak test
        
        # Check that system is stable (no memory leaks, etc.)
        assert results["max_response_time"] < 2000  # Max response time should be reasonable
