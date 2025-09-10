"""
Locust Load Test for AIaaS Platform

This script tests the platform under various load conditions using Locust.
"""

import json
import random
import time
from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask

# Test data
TENANTS = [
    'tenant_001',
    'tenant_002', 
    'tenant_003',
    'tenant_004',
    'tenant_005'
]

TEST_MESSAGES = [
    "Hello, I need help with my order",
    "What are your business hours?",
    "I want to return a product",
    "Can you help me track my shipment?",
    "I have a technical issue",
    "What payment methods do you accept?",
    "I need to update my account information",
    "Can you help me with billing?",
    "I want to cancel my subscription",
    "How do I contact customer support?"
]

class AIaaSUser(HttpUser):
    """AIaaS Platform user for load testing."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Initialize user session."""
        self.tenant_id = random.choice(TENANTS)
        self.user_id = f"user_{random.randint(1000, 9999)}"
        self.session_id = f"session_{random.randint(10000, 99999)}"
        
        # Set common headers
        self.headers = {
            'Content-Type': 'application/json',
            'X-Tenant-ID': self.tenant_id,
            'X-User-ID': self.user_id,
        }
    
    @task(3)
    def test_chat_endpoint(self):
        """Test chat endpoint with various messages."""
        url = "/chat/messages"
        payload = {
            "message": random.choice(TEST_MESSAGES),
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "metadata": {
                "source": "locust_test",
                "timestamp": int(time.time() * 1000)
            }
        }
        
        with self.client.post(
            url, 
            json=payload, 
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'response' in data or 'message' in data:
                        response.success()
                    else:
                        response.failure("Invalid response format")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 429:
                response.failure("Rate limit exceeded")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(2)
    def test_health_endpoint(self):
        """Test health check endpoint."""
        with self.client.get("/healthz", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")
    
    @task(1)
    def test_analytics_endpoint(self):
        """Test analytics endpoint."""
        url = "/analytics/kpi"
        params = {"time_window": "1h"}
        
        with self.client.get(
            url, 
            params=params, 
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'tenant_id' in data:
                        response.success()
                    else:
                        response.failure("Invalid analytics response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 401:
                response.failure("Unauthorized")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def test_billing_endpoint(self):
        """Test billing endpoint."""
        url = "/billing/usage"
        
        with self.client.get(
            url, 
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                try:
                    data = response.json()
                    if 'tenant_id' in data:
                        response.success()
                    else:
                        response.failure("Invalid billing response")
                except json.JSONDecodeError:
                    response.failure("Invalid JSON response")
            elif response.status_code == 401:
                response.failure("Unauthorized")
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def test_auth_endpoint(self):
        """Test authentication endpoint."""
        with self.client.get("/auth/status", catch_response=True) as response:
            if response.status_code in [200, 401]:
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    @task(1)
    def test_websocket_endpoint(self):
        """Test WebSocket endpoint (simulated with HTTP)."""
        url = "/ws/chat"
        params = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "session_id": self.session_id
        }
        
        with self.client.get(
            url, 
            params=params, 
            headers=self.headers,
            catch_response=True
        ) as response:
            # WebSocket endpoints typically return 101 or 400 for upgrade
            if response.status_code in [101, 400, 426]:
                response.success()
            else:
                response.failure(f"Unexpected WebSocket status: {response.status_code}")


class HighLoadUser(HttpUser):
    """High load user for stress testing."""
    
    wait_time = between(0.1, 0.5)
    weight = 1  # Lower weight for high load users
    
    def on_start(self):
        """Initialize high load user session."""
        self.tenant_id = random.choice(TENANTS)
        self.user_id = f"highload_user_{random.randint(1000, 9999)}"
        self.session_id = f"session_{random.randint(10000, 99999)}"
        
        self.headers = {
            'Content-Type': 'application/json',
            'X-Tenant-ID': self.tenant_id,
            'X-User-ID': self.user_id,
        }
    
    @task(5)
    def rapid_chat_requests(self):
        """Send rapid chat requests."""
        url = "/chat/messages"
        payload = {
            "message": random.choice(TEST_MESSAGES),
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "metadata": {
                "source": "locust_highload",
                "timestamp": int(time.time() * 1000)
            }
        }
        
        with self.client.post(
            url, 
            json=payload, 
            headers=self.headers,
            catch_response=True
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limit exceeded")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(2)
    def rapid_health_checks(self):
        """Send rapid health check requests."""
        with self.client.get("/healthz", catch_response=True) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


# Custom event handlers
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Custom request event handler."""
    if exception:
        print(f"Request failed: {name} - {exception}")
    elif response_time > 5000:  # 5 seconds
        print(f"Slow request: {name} - {response_time}ms")


@events.user_error.add_listener
def on_user_error(user_instance, exception, tb, **kwargs):
    """Custom user error event handler."""
    print(f"User error: {exception}")


# Test configuration
class TestConfig:
    """Test configuration for different scenarios."""
    
    @staticmethod
    def get_normal_load_config():
        """Normal load test configuration."""
        return {
            "spawn_rate": 10,
            "users": 100,
            "run_time": "10m"
        }
    
    @staticmethod
    def get_high_load_config():
        """High load test configuration."""
        return {
            "spawn_rate": 50,
            "users": 500,
            "run_time": "5m"
        }
    
    @staticmethod
    def get_stress_test_config():
        """Stress test configuration."""
        return {
            "spawn_rate": 100,
            "users": 1000,
            "run_time": "3m"
        }


if __name__ == "__main__":
    print("Locust load test for AIaaS Platform")
    print("Available test configurations:")
    print("1. Normal load: 100 users over 10 minutes")
    print("2. High load: 500 users over 5 minutes")
    print("3. Stress test: 1000 users over 3 minutes")
    print("\nRun with: locust -f locust_test.py --host=http://localhost:8000")
