"""Locust WebSocket load tests for sustained stream and burst testing."""

import asyncio
import json
import time
from typing import Dict, Any, List
from datetime import datetime

from locust import HttpUser, task, between
from locust.contrib.fasthttp import FastHttpUser
from locust.exception import RescheduleTask


class WebSocketLoadUser(HttpUser):
    """Locust user for WebSocket load testing."""
    
    wait_time = between(0.1, 0.5)  # Wait between tasks
    
    def on_start(self):
        """Initialize user session."""
        self.session_id = f"locust_session_{self.user_id}"
        self.connection_count = 0
        self.messages_sent = 0
        self.messages_received = 0
        self.start_time = time.time()
    
    @task(10)
    def send_chat_message(self):
        """Send chat message (most frequent task)."""
        payload = {
            "request_id": f"chat_{self.user_id}_{int(time.time())}",
            "tenant_id": "test_tenant",
            "user_id": f"user_{self.user_id}",
            "message": f"Chat message from user {self.user_id}",
            "context": {
                "source": "websocket",
                "session_id": self.session_id,
                "message_type": "chat"
            },
            "metadata": {"priority": "normal"}
        }
        
        try:
            response = self.client.post("/api/chat", json=payload)
            if response.status_code == 200:
                self.messages_sent += 1
                self.environment.events.request_success.fire(
                    request_type="WebSocket Chat",
                    name="send_chat_message",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content)
                )
            else:
                self.environment.events.request_failure.fire(
                    request_type="WebSocket Chat",
                    name="send_chat_message",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content),
                    exception=f"HTTP {response.status_code}"
                )
        except Exception as e:
            self.environment.events.request_failure.fire(
                request_type="WebSocket Chat",
                name="send_chat_message",
                response_time=0,
                response_length=0,
                exception=str(e)
            )
    
    @task(3)
    def send_notification_subscription(self):
        """Subscribe to notifications."""
        payload = {
            "request_id": f"notif_sub_{self.user_id}_{int(time.time())}",
            "tenant_id": "test_tenant",
            "user_id": f"user_{self.user_id}",
            "message": "Subscribe to notifications",
            "context": {
                "source": "websocket",
                "session_id": self.session_id,
                "subscription_type": "notifications"
            },
            "metadata": {"priority": "normal"}
        }
        
        try:
            response = self.client.post("/api/notifications/subscribe", json=payload)
            if response.status_code == 200:
                self.environment.events.request_success.fire(
                    request_type="WebSocket Notification",
                    name="notification_subscription",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content)
                )
            else:
                self.environment.events.request_failure.fire(
                    request_type="WebSocket Notification",
                    name="notification_subscription",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content),
                    exception=f"HTTP {response.status_code}"
                )
        except Exception as e:
            self.environment.events.request_failure.fire(
                request_type="WebSocket Notification",
                name="notification_subscription",
                response_time=0,
                response_length=0,
                exception=str(e)
            )
    
    @task(2)
    def send_high_priority_message(self):
        """Send high priority message."""
        payload = {
            "request_id": f"urgent_{self.user_id}_{int(time.time())}",
            "tenant_id": "test_tenant",
            "user_id": f"user_{self.user_id}",
            "message": f"Urgent message from user {self.user_id}",
            "context": {
                "source": "websocket",
                "session_id": self.session_id,
                "message_type": "urgent"
            },
            "metadata": {"priority": "high"}
        }
        
        try:
            response = self.client.post("/api/urgent", json=payload)
            if response.status_code == 200:
                self.environment.events.request_success.fire(
                    request_type="WebSocket Urgent",
                    name="high_priority_message",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content)
                )
            else:
                self.environment.events.request_failure.fire(
                    request_type="WebSocket Urgent",
                    name="high_priority_message",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content),
                    exception=f"HTTP {response.status_code}"
                )
        except Exception as e:
            self.environment.events.request_failure.fire(
                request_type="WebSocket Urgent",
                name="high_priority_message",
                response_time=0,
                response_length=0,
                exception=str(e)
            )
    
    @task(1)
    def send_large_message(self):
        """Send large message to test backpressure."""
        large_content = "Large message content " * 100  # ~2KB message
        
        payload = {
            "request_id": f"large_{self.user_id}_{int(time.time())}",
            "tenant_id": "test_tenant",
            "user_id": f"user_{self.user_id}",
            "message": large_content,
            "context": {
                "source": "websocket",
                "session_id": self.session_id,
                "message_type": "large_content"
            },
            "metadata": {"priority": "normal", "size": "large"}
        }
        
        try:
            response = self.client.post("/api/large-message", json=payload)
            if response.status_code == 200:
                self.environment.events.request_success.fire(
                    request_type="WebSocket Large",
                    name="large_message",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content)
                )
            else:
                self.environment.events.request_failure.fire(
                    request_type="WebSocket Large",
                    name="large_message",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content),
                    exception=f"HTTP {response.status_code}"
                )
        except Exception as e:
            self.environment.events.request_failure.fire(
                request_type="WebSocket Large",
                name="large_message",
                response_time=0,
                response_length=0,
                exception=str(e)
            )
    
    @task(5)
    def heartbeat_ping(self):
        """Send heartbeat ping to maintain connection."""
        payload = {
            "request_id": f"heartbeat_{self.user_id}_{int(time.time())}",
            "tenant_id": "test_tenant",
            "user_id": f"user_{self.user_id}",
            "message": "ping",
            "context": {
                "source": "websocket",
                "session_id": self.session_id,
                "message_type": "heartbeat"
            },
            "metadata": {"priority": "low"}
        }
        
        try:
            response = self.client.post("/api/heartbeat", json=payload)
            if response.status_code == 200:
                self.environment.events.request_success.fire(
                    request_type="WebSocket Heartbeat",
                    name="heartbeat_ping",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content)
                )
            else:
                self.environment.events.request_failure.fire(
                    request_type="WebSocket Heartbeat",
                    name="heartbeat_ping",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content),
                    exception=f"HTTP {response.status_code}"
                )
        except Exception as e:
            self.environment.events.request_failure.fire(
                request_type="WebSocket Heartbeat",
                name="heartbeat_ping",
                response_time=0,
                response_length=0,
                exception=str(e)
            )
    
    def on_stop(self):
        """Cleanup when user stops."""
        duration = time.time() - self.start_time
        self.environment.events.user_error.fire(
            user=self,
            error=f"User {self.user_id} completed {self.messages_sent} messages in {duration:.2f}s"
        )


class WebSocketBurstUser(FastHttpUser):
    """Locust user for WebSocket burst testing."""
    
    wait_time = between(0.01, 0.05)  # Very short wait for burst testing
    
    def on_start(self):
        """Initialize burst user."""
        self.burst_start_time = time.time()
        self.burst_messages_sent = 0
        self.burst_active = True
    
    @task(20)
    def rapid_fire_messages(self):
        """Send rapid-fire messages for burst testing."""
        if not self.burst_active:
            return
        
        # Stop burst after 30 seconds
        if time.time() - self.burst_start_time > 30:
            self.burst_active = False
            return
        
        payload = {
            "request_id": f"burst_{self.user_id}_{int(time.time() * 1000)}",
            "tenant_id": "test_tenant",
            "user_id": f"burst_user_{self.user_id}",
            "message": f"Burst message {self.burst_messages_sent}",
            "context": {
                "source": "websocket",
                "session_id": f"burst_session_{self.user_id}",
                "message_type": "burst"
            },
            "metadata": {"priority": "normal", "burst": True}
        }
        
        try:
            response = self.client.post("/api/burst", json=payload)
            if response.status_code == 200:
                self.burst_messages_sent += 1
                self.environment.events.request_success.fire(
                    request_type="WebSocket Burst",
                    name="rapid_fire_messages",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content)
                )
            else:
                self.environment.events.request_failure.fire(
                    request_type="WebSocket Burst",
                    name="rapid_fire_messages",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content),
                    exception=f"HTTP {response.status_code}"
                )
        except Exception as e:
            self.environment.events.request_failure.fire(
                request_type="WebSocket Burst",
                name="rapid_fire_messages",
                response_time=0,
                response_length=0,
                exception=str(e)
            )
    
    @task(5)
    def burst_notifications(self):
        """Send burst notifications."""
        if not self.burst_active:
            return
        
        payload = {
            "request_id": f"burst_notif_{self.user_id}_{int(time.time() * 1000)}",
            "tenant_id": "test_tenant",
            "user_id": f"burst_user_{self.user_id}",
            "message": "Burst notification",
            "context": {
                "source": "websocket",
                "session_id": f"burst_session_{self.user_id}",
                "message_type": "notification"
            },
            "metadata": {"priority": "high", "burst": True}
        }
        
        try:
            response = self.client.post("/api/burst-notification", json=payload)
            if response.status_code == 200:
                self.environment.events.request_success.fire(
                    request_type="WebSocket Burst Notification",
                    name="burst_notifications",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content)
                )
            else:
                self.environment.events.request_failure.fire(
                    request_type="WebSocket Burst Notification",
                    name="burst_notifications",
                    response_time=response.elapsed.total_seconds() * 1000,
                    response_length=len(response.content),
                    exception=f"HTTP {response.status_code}"
                )
        except Exception as e:
            self.environment.events.request_failure.fire(
                request_type="WebSocket Burst Notification",
                name="burst_notifications",
                response_time=0,
                response_length=0,
                exception=str(e)
            )


class WebSocketMetricsCollector:
    """Collect WebSocket metrics during load testing."""
    
    def __init__(self):
        self.metrics = {
            'total_connections': 0,
            'active_connections': 0,
            'messages_sent': 0,
            'messages_dropped': 0,
            'avg_response_time': 0.0,
            'p95_response_time': 0.0,
            'p99_response_time': 0.0,
            'error_rate': 0.0,
            'backpressure_events': 0,
            'reconnection_events': 0
        }
    
    def collect_metrics(self, stats_data: Dict[str, Any]) -> Dict[str, Any]:
        """Collect metrics from Locust stats."""
        if stats_data:
            # Calculate response time percentiles
            response_times = []
            total_requests = 0
            total_errors = 0
            
            for entry in stats_data.get('entries', []):
                if entry.get('name') in ['send_chat_message', 'notification_subscription', 
                                       'high_priority_message', 'large_message', 'heartbeat_ping']:
                    total_requests += entry.get('num_requests', 0)
                    total_errors += entry.get('num_failures', 0)
                    response_times.extend([entry.get('avg_response_time', 0)] * entry.get('num_requests', 0))
            
            # Update metrics
            self.metrics['total_connections'] = len(stats_data.get('users', []))
            self.metrics['active_connections'] = len([u for u in stats_data.get('users', []) if u.get('active', False)])
            self.metrics['messages_sent'] = total_requests
            self.metrics['error_rate'] = (total_errors / total_requests) * 100 if total_requests > 0 else 0
            
            if response_times:
                response_times.sort()
                self.metrics['avg_response_time'] = sum(response_times) / len(response_times)
                self.metrics['p95_response_time'] = response_times[int(len(response_times) * 0.95)]
                self.metrics['p99_response_time'] = response_times[int(len(response_times) * 0.99)]
        
        return self.metrics


# Locust configuration for different test scenarios
class SustainedStreamConfig:
    """Configuration for sustained stream testing."""
    
    # Run with: locust -f tests/performance/test_websocket_load.py WebSocketLoadUser
    # --users 100 --spawn-rate 10 --run-time 300s --html reports/sustained_stream.html
    
    @staticmethod
    def get_test_config():
        return {
            'users': 100,
            'spawn_rate': 10,
            'run_time': '300s',  # 5 minutes
            'host': 'http://localhost:8000',
            'html_report': 'reports/sustained_stream.html'
        }


class BurstLoadConfig:
    """Configuration for burst load testing."""
    
    # Run with: locust -f tests/performance/test_websocket_load.py WebSocketBurstUser
    # --users 50 --spawn-rate 20 --run-time 60s --html reports/burst_load.html
    
    @staticmethod
    def get_test_config():
        return {
            'users': 50,
            'spawn_rate': 20,
            'run_time': '60s',  # 1 minute burst
            'host': 'http://localhost:8000',
            'html_report': 'reports/burst_load.html'
        }