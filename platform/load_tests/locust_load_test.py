"""
Locust Load Test Script for Multi-AI-Agent Platform
Tests capacity levers and degrade switches under peak traffic
"""

import random
import time
import json
from locust import HttpUser, task, between, events
from locust.exception import StopUser


class MultiAIAgentUser(HttpUser):
    """Locust user class for Multi-AI-Agent platform load testing."""
    
    wait_time = between(0.5, 2.5)  # Wait between 0.5-2.5 seconds between requests
    
    def on_start(self):
        """Called when a user starts."""
        self.tenant_id = self.environment.parsed_options.tenant_id or "load-test-tenant"
        self.headers = {
            "Content-Type": "application/json",
            "X-Tenant-ID": self.tenant_id
        }
        
        # Test scenarios with weights
        self.scenarios = [
            (self.test_api_call, 40),      # 40% weight
            (self.test_tool_call, 30),     # 30% weight
            (self.test_websocket, 20),     # 20% weight
            (self.test_file_upload, 10),   # 10% weight
        ]
    
    @task
    def execute_scenario(self):
        """Execute a random scenario based on weights."""
        # Select scenario based on weight
        total_weight = sum(weight for _, weight in self.scenarios)
        random_value = random.uniform(0, total_weight)
        
        cumulative_weight = 0
        for scenario_func, weight in self.scenarios:
            cumulative_weight += weight
            if random_value <= cumulative_weight:
                scenario_func()
                break
    
    def test_api_call(self):
        """Test API call scenario."""
        payload = {
            "model": "gpt-3.5-turbo",
            "messages": [
                {"role": "user", "content": self._get_random_message()}
            ],
            "max_tokens": random.randint(50, 200),
            "temperature": round(random.uniform(0.1, 1.0), 2)
        }
        
        with self.client.post(
            "/api/v1/chat/completions",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="api_call"
        ) as response:
            self._check_response(response, "API Call")
    
    def test_tool_call(self):
        """Test tool call scenario."""
        tools = ["search", "calculator", "weather", "translate", "summarize"]
        tool_name = random.choice(tools)
        
        payload = {
            "tool_name": tool_name,
            "parameters": self._get_tool_parameters(tool_name)
        }
        
        with self.client.post(
            "/api/v1/tools/execute",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="tool_call"
        ) as response:
            self._check_response(response, f"Tool Call ({tool_name})")
    
    def test_websocket(self):
        """Test WebSocket connection scenario."""
        # Simulate WebSocket connection by making a GET request to WS endpoint
        with self.client.get(
            "/ws",
            headers=self.headers,
            catch_response=True,
            name="websocket"
        ) as response:
            # WebSocket endpoints typically return 101 or 426
            if response.status_code in [101, 426, 200]:
                response.success()
            else:
                response.failure(f"Unexpected status code: {response.status_code}")
    
    def test_file_upload(self):
        """Test file upload scenario."""
        file_types = ["document", "image", "audio", "video"]
        file_type = random.choice(file_types)
        
        payload = {
            "file_type": file_type,
            "content": self._get_file_content(file_type)
        }
        
        with self.client.post(
            "/api/v1/upload",
            json=payload,
            headers=self.headers,
            catch_response=True,
            name="file_upload"
        ) as response:
            self._check_response(response, f"File Upload ({file_type})")
    
    def _check_response(self, response, scenario_name):
        """Check response and record metrics."""
        # Check for quota exceeded
        if response.status_code == 429:
            response.failure(f"Quota exceeded for {scenario_name}")
            return
        
        # Check for degrade mode
        degrade_mode = response.headers.get("X-Degrade-Mode")
        if degrade_mode:
            print(f"Degrade mode active: {degrade_mode}")
        
        # Check response time
        if response.elapsed.total_seconds() > 5.0:
            print(f"Slow response: {scenario_name} took {response.elapsed.total_seconds():.2f}s")
        
        # Check for success
        if response.status_code in [200, 201]:
            response.success()
        else:
            response.failure(f"Unexpected status code: {response.status_code}")
    
    def _get_random_message(self):
        """Get a random message for testing."""
        messages = [
            "Hello, how are you?",
            "What is the weather like today?",
            "Can you help me with a math problem?",
            "Tell me a joke",
            "Explain quantum computing",
            "What are the benefits of renewable energy?",
            "How do I learn a new language?",
            "What is artificial intelligence?",
            "Can you recommend a good book?",
            "What is the meaning of life?"
        ]
        return random.choice(messages)
    
    def _get_tool_parameters(self, tool_name):
        """Get parameters for tool calls."""
        parameters = {
            "search": {"query": random.choice(["AI", "machine learning", "python", "data science"]), "limit": 10},
            "calculator": {"expression": f"{random.randint(1, 100)} + {random.randint(1, 100)}"},
            "weather": {"location": random.choice(["New York", "London", "Tokyo", "Paris"])},
            "translate": {"text": "Hello world", "target_language": "es"},
            "summarize": {"text": "This is a long text that needs to be summarized for testing purposes."}
        }
        return parameters.get(tool_name, {})
    
    def _get_file_content(self, file_type):
        """Get file content for upload testing."""
        content_sizes = {
            "document": 1024,      # 1KB
            "image": 10240,        # 10KB
            "audio": 102400,       # 100KB
            "video": 1024000       # 1MB
        }
        size = content_sizes.get(file_type, 1024)
        return "x" * size


class CapacityTestUser(MultiAIAgentUser):
    """Specialized user for capacity testing."""
    
    def on_start(self):
        """Setup for capacity testing."""
        super().on_start()
        self.test_phase = "normal"
        self.phase_start_time = time.time()
    
    @task
    def capacity_test_scenario(self):
        """Execute capacity test scenario."""
        current_time = time.time()
        
        # Phase transitions based on time
        if current_time - self.phase_start_time > 300:  # 5 minutes
            self.test_phase = "degraded"
        if current_time - self.phase_start_time > 600:  # 10 minutes
            self.test_phase = "emergency"
        
        # Adjust behavior based on phase
        if self.test_phase == "degraded":
            self._test_degraded_mode()
        elif self.test_phase == "emergency":
            self._test_emergency_mode()
        else:
            self.execute_scenario()
    
    def _test_degraded_mode(self):
        """Test degraded mode behavior."""
        # In degraded mode, prefer simpler operations
        if random.random() < 0.7:  # 70% chance for simple API calls
            self.test_api_call()
        else:
            self.execute_scenario()
    
    def _test_emergency_mode(self):
        """Test emergency mode behavior."""
        # In emergency mode, only basic operations
        if random.random() < 0.9:  # 90% chance for basic API calls
            self.test_api_call()
        else:
            self.test_websocket()


# Event handlers
@events.request.add_listener
def on_request(request_type, name, response_time, response_length, exception, context, **kwargs):
    """Handle request events."""
    if exception:
        print(f"Request failed: {name} - {exception}")
    elif response_time > 5000:  # 5 seconds
        print(f"Slow request: {name} took {response_time}ms")


@events.user_error.add_listener
def on_user_error(user_instance, exception, tb, **kwargs):
    """Handle user errors."""
    print(f"User error: {exception}")


# Custom metrics
class CustomMetrics:
    """Custom metrics for load testing."""
    
    def __init__(self):
        self.quota_exceeded_count = 0
        self.degrade_mode_count = 0
        self.slow_response_count = 0
    
    def record_quota_exceeded(self):
        """Record quota exceeded event."""
        self.quota_exceeded_count += 1
    
    def record_degrade_mode(self):
        """Record degrade mode event."""
        self.degrade_mode_count += 1
    
    def record_slow_response(self):
        """Record slow response event."""
        self.slow_response_count += 1


# Global metrics instance
metrics = CustomMetrics()


# Locust configuration
class LoadTestConfig:
    """Configuration for load testing."""
    
    def __init__(self):
        self.host = "http://localhost:8000"
        self.tenant_id = "load-test-tenant"
        self.users = 100
        self.spawn_rate = 10
        self.run_time = "10m"
    
    def get_command(self):
        """Get locust command for running the test."""
        return f"""
        locust -f {__file__} \\
            --host={self.host} \\
            --users={self.users} \\
            --spawn-rate={self.spawn_rate} \\
            --run-time={self.run_time} \\
            --tenant-id={self.tenant_id} \\
            --html=load_test_results.html \\
            --csv=load_test_results
        """


if __name__ == "__main__":
    config = LoadTestConfig()
    print("Load Test Configuration:")
    print(f"Host: {config.host}")
    print(f"Tenant ID: {config.tenant_id}")
    print(f"Users: {config.users}")
    print(f"Spawn Rate: {config.spawn_rate}")
    print(f"Run Time: {config.run_time}")
    print("\nTo run the test, execute:")
    print(config.get_command())
