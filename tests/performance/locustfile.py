"""Performance tests using Locust."""

from locust import HttpUser, task, between
import random
import json


class AIaaSUser(HttpUser):
    """Simulate user behavior for AIaaS platform."""
    
    wait_time = between(1, 3)
    
    def on_start(self):
        """Setup user session."""
        self.tenant_id = "test-tenant-123"
        self.session_id = f"session-{random.randint(1000, 9999)}"
        self.headers = {
            "Content-Type": "application/json",
            "X-Tenant-ID": self.tenant_id
        }
    
    @task(3)
    def chat_message(self):
        """Send chat message."""
        payload = {
            "message": "Hello, I need help with my order",
            "session_id": self.session_id
        }
        
        response = self.client.post(
            "/api/v1/chat/message",
            json=payload,
            headers=self.headers
        )
        
        if response.status_code != 200:
            print(f"Chat message failed: {response.status_code}")
    
    @task(2)
    def get_agents(self):
        """Get available agents."""
        response = self.client.get(
            "/api/v1/agents",
            headers=self.headers
        )
        
        if response.status_code != 200:
            print(f"Get agents failed: {response.status_code}")
    
    @task(1)
    def get_conversation_history(self):
        """Get conversation history."""
        response = self.client.get(
            f"/api/v1/chat/history/{self.session_id}",
            headers=self.headers
        )
        
        if response.status_code != 200:
            print(f"Get history failed: {response.status_code}")
    
    @task(1)
    def upload_document(self):
        """Upload document."""
        files = {
            'file': ('test.txt', 'This is a test document', 'text/plain')
        }
        
        response = self.client.post(
            "/api/v1/ingestion/upload",
            files=files,
            headers={"X-Tenant-ID": self.tenant_id}
        )
        
        if response.status_code != 200:
            print(f"Upload failed: {response.status_code}")
    
    @task(1)
    def get_usage_stats(self):
        """Get usage statistics."""
        response = self.client.get(
            "/api/v1/usage/stats",
            headers=self.headers
        )
        
        if response.status_code != 200:
            print(f"Get usage stats failed: {response.status_code}")


class HighLoadUser(HttpUser):
    """Simulate high load scenarios."""
    
    wait_time = between(0.1, 0.5)
    
    def on_start(self):
        """Setup high load session."""
        self.tenant_id = "load-test-tenant"
        self.headers = {
            "Content-Type": "application/json",
            "X-Tenant-ID": self.tenant_id
        }
    
    @task(10)
    def rapid_chat_messages(self):
        """Send rapid chat messages."""
        payload = {
            "message": f"Load test message {random.randint(1, 1000)}",
            "session_id": f"load-session-{random.randint(1, 100)}"
        }
        
        self.client.post(
            "/api/v1/chat/message",
            json=payload,
            headers=self.headers
        )
    
    @task(5)
    def concurrent_uploads(self):
        """Concurrent document uploads."""
        files = {
            'file': (f'test-{random.randint(1, 1000)}.txt', 
                    f'Load test document {random.randint(1, 1000)}', 
                    'text/plain')
        }
        
        self.client.post(
            "/api/v1/ingestion/upload",
            files=files,
            headers={"X-Tenant-ID": self.tenant_id}
        )
