"""Locust performance tests for the multi-tenant AI platform."""

import json
import random
import time
import asyncio
from locust import HttpUser, task, between, events
from locust.contrib.fasthttp import FastHttpUser
import websocket
import threading


class APIUser(HttpUser):
    """HTTP user for REST API testing."""
    wait_time = between(0.1, 0.5)
    host = "http://localhost:8000"
    
    def on_start(self):
        """Initialize user session."""
        self.tenant_id = f"tenant_{random.randint(1000, 9999)}"
        self.user_id = f"user_{random.randint(1000, 9999)}"
        self.session_id = f"session_{random.randint(1000, 9999)}"
        
        # Authenticate
        auth_response = self.client.post("/auth/login", json={
            "tenant_id": self.tenant_id,
            "user_id": self.user_id
        })
        if auth_response.status_code == 200:
            self.auth_token = auth_response.json().get("token")
            self.client.headers.update({"Authorization": f"Bearer {self.auth_token}"})
    
    @task(10)
    def test_faq_request(self):
        """Test FAQ requests (high frequency)."""
        with self.client.post("/api/v1/chat", 
            json={
                "message": random.choice([
                    "What are your business hours?",
                    "How do I reset my password?",
                    "What is your refund policy?",
                    "How do I contact support?"
                ]),
                "context": {
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "channel": "web"
                }
            },
            catch_response=True
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "response" in data:
                    response.success()
                else:
                    response.failure("Missing response field")
            elif response.status_code == 429:
                response.success()  # Rate limited is expected under load
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(5)
    def test_order_request(self):
        """Test order-related requests (medium frequency)."""
        with self.client.post("/api/v1/chat",
            json={
                "message": random.choice([
                    "I want to upgrade my plan",
                    "What's the status of my order?",
                    "I need to cancel my subscription",
                    "Can you help me with billing?"
                ]),
                "context": {
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "channel": "web"
                }
            },
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(2)
    def test_complex_request(self):
        """Test complex requests (low frequency)."""
        with self.client.post("/api/v1/chat",
            json={
                "message": "I need help with integrating your API with our existing CRM system. Can you provide detailed technical documentation and examples?",
                "context": {
                    "user_id": self.user_id,
                    "session_id": self.session_id,
                    "channel": "web"
                }
            },
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class WSUser:
    """WebSocket user for realtime testing."""
    
    def __init__(self, host="localhost", port=8001, tenant_id=None):
        self.host = host
        self.port = port
        self.tenant_id = tenant_id or f"tenant_{random.randint(1000, 9999)}"
        self.user_id = f"user_{random.randint(1000, 9999)}"
        self.ws = None
        self.connected = False
        self.message_count = 0
        self.response_times = []
    
    def connect(self):
        """Connect to WebSocket."""
        try:
            url = f"ws://{self.host}:{self.port}/ws/{self.tenant_id}"
            self.ws = websocket.WebSocket()
            self.ws.connect(url)
            self.connected = True
            return True
        except Exception as e:
            print(f"WebSocket connection failed: {e}")
            return False
    
    def send_message(self, message):
        """Send message via WebSocket."""
        if not self.connected or not self.ws:
            return None
        
        try:
            start_time = time.time()
            self.ws.send(json.dumps({
                "message": message,
                "user_id": self.user_id,
                "timestamp": time.time()
            }))
            
            # Wait for response
            response = self.ws.recv()
            end_time = time.time()
            
            self.message_count += 1
            self.response_times.append(end_time - start_time)
            
            return {
                "response": response,
                "response_time": end_time - start_time,
                "success": True
            }
        except Exception as e:
            print(f"WebSocket send failed: {e}")
            return {"success": False, "error": str(e)}
    
    def disconnect(self):
        """Disconnect from WebSocket."""
        if self.ws:
            self.ws.close()
            self.connected = False


class WebSocketUser(HttpUser):
    """Locust user for WebSocket testing."""
    wait_time = between(0.1, 1.0)
    host = "http://localhost:8001"
    
    def on_start(self):
        """Initialize WebSocket connection."""
        self.tenant_id = f"tenant_{random.randint(1000, 9999)}"
        self.user_id = f"user_{random.randint(1000, 9999)}"
        self.ws_user = WSUser(
            host="localhost",
            port=8001,
            tenant_id=self.tenant_id
        )
        self.ws_user.connect()
    
    @task(20)
    def test_websocket_message(self):
        """Test WebSocket message sending."""
        if not self.ws_user.connected:
            return
        
        message = random.choice([
            "Hello, I need help",
            "What's the status of my request?",
            "Can you help me with my account?",
            "I have a question about billing"
        ])
        
        result = self.ws_user.send_message(message)
        
        if result and result.get("success"):
            # Record successful response time
            events.request.fire(
                request_type="WebSocket",
                name="websocket_message",
                response_time=result["response_time"] * 1000,  # Convert to ms
                response_length=len(str(result["response"])),
                context={"tenant_id": self.tenant_id}
            )
        else:
            # Record failure
            events.request.fire(
                request_type="WebSocket",
                name="websocket_message",
                response_time=0,
                response_length=0,
                exception=Exception("WebSocket send failed"),
                context={"tenant_id": self.tenant_id}
            )
    
    def on_stop(self):
        """Clean up WebSocket connection."""
        if self.ws_user:
            self.ws_user.disconnect()


class SlowConsumerUser(WebSocketUser):
    """User that simulates slow message consumption."""
    wait_time = between(2.0, 5.0)  # Slow consumption
    
    @task(5)
    def test_slow_consumption(self):
        """Test slow message consumption."""
        if not self.ws_user.connected:
            return
        
        message = "I need detailed help with a complex issue"
        result = self.ws_user.send_message(message)
        
        if result and result.get("success"):
            # Simulate slow processing
            time.sleep(random.uniform(1.0, 3.0))
            
            events.request.fire(
                request_type="WebSocket",
                name="slow_consumption",
                response_time=result["response_time"] * 1000,
                response_length=len(str(result["response"])),
                context={"tenant_id": self.tenant_id, "slow": True}
            )


class BurstUser(HttpUser):
    """User that sends bursts of requests."""
    wait_time = between(0.01, 0.05)  # Very fast
    
    def on_start(self):
        """Initialize burst user."""
        self.tenant_id = f"tenant_{random.randint(1000, 9999)}"
        self.burst_size = random.randint(5, 20)
        self.burst_interval = random.randint(10, 30)
    
    @task
    def test_burst_requests(self):
        """Send burst of requests."""
        start_time = time.time()
        
        for i in range(self.burst_size):
            with self.client.post("/api/v1/chat",
                json={
                    "message": f"Burst message {i}",
                    "context": {
                        "user_id": f"user_{self.tenant_id}",
                        "session_id": f"session_{self.tenant_id}",
                        "channel": "web"
                    }
                },
                catch_response=True
            ) as response:
                if response.status_code in [200, 429]:  # Accept rate limiting
                    response.success()
                else:
                    response.failure(f"Status: {response.status_code}")
        
        # Record burst metrics
        burst_duration = time.time() - start_time
        events.request.fire(
            request_type="Burst",
            name="burst_requests",
            response_time=burst_duration * 1000,
            response_length=self.burst_size,
            context={
                "tenant_id": self.tenant_id,
                "burst_size": self.burst_size,
                "burst_duration": burst_duration
            }
        )
        
        # Wait before next burst
        time.sleep(self.burst_interval)


class SoakUser(HttpUser):
    """User for soak testing (long-running)."""
    wait_time = between(1.0, 3.0)
    
    def on_start(self):
        """Initialize soak user."""
        self.tenant_id = f"tenant_{random.randint(1000, 9999)}"
        self.start_time = time.time()
    
    @task
    def test_soak_request(self):
        """Send request during soak test."""
        with self.client.post("/api/v1/chat",
            json={
                "message": "Soak test message",
                "context": {
                    "user_id": f"user_{self.tenant_id}",
                    "session_id": f"session_{self.tenant_id}",
                    "channel": "web"
                }
            },
            catch_response=True
        ) as response:
            if response.status_code in [200, 429]:
                response.success()
            else:
                response.failure(f"Status: {response.status_code}")
    
    @task(1)
    def test_health_check(self):
        """Periodic health check during soak test."""
        with self.client.get("/health", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


# Performance test configurations
class BaselineTest:
    """Baseline performance test configuration."""
    users = [APIUser] * 50
    spawn_rate = 10
    run_time = "5m"
    
class StressTest:
    """Stress test configuration."""
    users = [APIUser] * 200 + [WebSocketUser] * 100
    spawn_rate = 20
    run_time = "10m"
    
class SpikeTest:
    """Spike test configuration."""
    users = [BurstUser] * 100
    spawn_rate = 50
    run_time = "3m"
    
class SoakTest:
    """Soak test configuration."""
    users = [SoakUser] * 30 + [WebSocketUser] * 20
    spawn_rate = 5
    run_time = "60m"
    
class BackpressureTest:
    """Backpressure test configuration."""
    users = [SlowConsumerUser] * 50 + [BurstUser] * 30
    spawn_rate = 15
    run_time = "15m"