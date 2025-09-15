"""
Locust performance test file for API endpoints.

Usage:
    locust -f tests/performance/locustfile.py --host=http://localhost:8000
    locust -f tests/performance/locustfile.py --host=http://localhost:8000 --users=100 --spawn-rate=10 --run-time=60s
"""

import time
import random
from locust import HttpUser, task, between


class WebsiteUser(HttpUser):
    """Locust user for API endpoint performance testing."""
    
    wait_time = between(1, 3)  # Wait 1-3 seconds between tasks
    
    def on_start(self):
        """Called when a user starts."""
        self.tenant_id = f"tenant_{random.randint(1000, 9999)}"
        self.user_id = f"user_{random.randint(1000, 9999)}"
    
    @task(10)
    def query_endpoint(self):
        """Test query endpoint performance."""
        payload = {
            "message": f"Test query from {self.user_id}",
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "context": {
                "session_id": f"session_{random.randint(10000, 99999)}",
                "timestamp": time.time()
            }
        }
        
        with self.client.post(
            "/api/query",
            json=payload,
            catch_response=True,
            name="POST /api/query"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(5)
    def workflow_endpoint(self):
        """Test workflow endpoint performance."""
        payload = {
            "workflow_id": f"workflow_{random.randint(100, 999)}",
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "input_data": {
                "action": "process_request",
                "data": f"Workflow data {random.randint(1, 1000)}"
            }
        }
        
        with self.client.post(
            "/api/workflow",
            json=payload,
            catch_response=True,
            name="POST /api/workflow"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(3)
    def ingest_endpoint(self):
        """Test ingest endpoint performance."""
        payload = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "content": f"Test content {random.randint(1, 1000)}",
            "metadata": {
                "source": "locust_test",
                "type": "test_document",
                "timestamp": time.time()
            }
        }
        
        with self.client.post(
            "/api/ingest",
            json=payload,
            catch_response=True,
            name="POST /api/ingest"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limited")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(2)
    def status_endpoint(self):
        """Test status endpoint performance."""
        with self.client.get(
            f"/api/status?tenant_id={self.tenant_id}&user_id={self.user_id}",
            catch_response=True,
            name="GET /api/status"
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 404:
                response.failure("Not found")
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(1)
    def health_check(self):
        """Test health check endpoint."""
        with self.client.get(
            "/health",
            catch_response=True,
            name="GET /health"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health check failed: {response.status_code}")


class StressTestUser(HttpUser):
    """Locust user for stress testing."""
    
    wait_time = between(0.1, 0.5)  # Faster requests for stress testing
    weight = 1  # Lower weight for stress testing
    
    def on_start(self):
        """Called when a user starts."""
        self.tenant_id = f"stress_tenant_{random.randint(1000, 9999)}"
        self.user_id = f"stress_user_{random.randint(1000, 9999)}"
    
    @task(20)
    def rapid_queries(self):
        """Rapid query requests for stress testing."""
        payload = {
            "message": f"Stress test query {random.randint(1, 10000)}",
            "tenant_id": self.tenant_id,
            "user_id": self.user_id
        }
        
        with self.client.post(
            "/api/query",
            json=payload,
            catch_response=True,
            name="POST /api/query (stress)"
        ) as response:
            if response.status_code in [200, 429]:  # Accept rate limiting
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(10)
    def rapid_workflows(self):
        """Rapid workflow requests for stress testing."""
        payload = {
            "workflow_id": f"stress_workflow_{random.randint(100, 999)}",
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "input_data": {"action": "stress_test"}
        }
        
        with self.client.post(
            "/api/workflow",
            json=payload,
            catch_response=True,
            name="POST /api/workflow (stress)"
        ) as response:
            if response.status_code in [200, 429]:  # Accept rate limiting
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class SpikeTestUser(HttpUser):
    """Locust user for spike testing."""
    
    wait_time = between(0.05, 0.2)  # Very fast requests for spike testing
    weight = 1  # Lower weight for spike testing
    
    def on_start(self):
        """Called when a user starts."""
        self.tenant_id = f"spike_tenant_{random.randint(1000, 9999)}"
        self.user_id = f"spike_user_{random.randint(1000, 9999)}"
    
    @task(30)
    def spike_queries(self):
        """Spike query requests."""
        payload = {
            "message": f"Spike test query {random.randint(1, 50000)}",
            "tenant_id": self.tenant_id,
            "user_id": self.user_id
        }
        
        with self.client.post(
            "/api/query",
            json=payload,
            catch_response=True,
            name="POST /api/query (spike)"
        ) as response:
            if response.status_code in [200, 429, 503]:  # Accept rate limiting and service unavailable
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(15)
    def spike_ingest(self):
        """Spike ingest requests."""
        payload = {
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "content": f"Spike test content {random.randint(1, 50000)}"
        }
        
        with self.client.post(
            "/api/ingest",
            json=payload,
            catch_response=True,
            name="POST /api/ingest (spike)"
        ) as response:
            if response.status_code in [200, 429, 503]:  # Accept rate limiting and service unavailable
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")


class EnduranceTestUser(HttpUser):
    """Locust user for endurance testing."""
    
    wait_time = between(5, 15)  # Slower requests for endurance testing
    weight = 1  # Lower weight for endurance testing
    
    def on_start(self):
        """Called when a user starts."""
        self.tenant_id = f"endurance_tenant_{random.randint(1000, 9999)}"
        self.user_id = f"endurance_user_{random.randint(1000, 9999)}"
        self.start_time = time.time()
    
    @task(5)
    def endurance_query(self):
        """Endurance query requests."""
        payload = {
            "message": f"Endurance test query {int(time.time() - self.start_time)}",
            "tenant_id": self.tenant_id,
            "user_id": self.user_id
        }
        
        with self.client.post(
            "/api/query",
            json=payload,
            catch_response=True,
            name="POST /api/query (endurance)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")
    
    @task(2)
    def endurance_workflow(self):
        """Endurance workflow requests."""
        payload = {
            "workflow_id": f"endurance_workflow_{random.randint(100, 999)}",
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
            "input_data": {"action": "endurance_test"}
        }
        
        with self.client.post(
            "/api/workflow",
            json=payload,
            catch_response=True,
            name="POST /api/workflow (endurance)"
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")