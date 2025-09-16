"""
Locust Performance Testing Profiles

Comprehensive Locust profiles for load testing and performance validation
with realistic user scenarios and performance gates.
"""

import asyncio
import random
import time
import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime, timedelta

from locust import HttpUser, task, between, events
from locust.exception import RescheduleTask

logger = structlog.get_logger(__name__)


class TestScenario(Enum):
    """Test scenarios for different user behaviors."""
    LIGHT_USER = "light_user"
    MODERATE_USER = "moderate_user"
    HEAVY_USER = "heavy_user"
    BURST_USER = "burst_user"
    STRESS_USER = "stress_user"


class PerformanceGate(Enum):
    """Performance gates for validation."""
    LATENCY_P95_MS = "latency_p95_ms"
    LATENCY_P99_MS = "latency_p99_ms"
    ERROR_RATE_PERCENT = "error_rate_percent"
    THROUGHPUT_RPS = "throughput_rps"
    COST_PER_REQUEST = "cost_per_request"


@dataclass
class GateThreshold:
    """Performance gate threshold definition."""
    
    gate: PerformanceGate
    threshold_value: float
    unit: str
    severity: str  # "warning" or "critical"


@dataclass
class TestProfile:
    """Test profile configuration."""
    
    name: str
    description: str
    scenario: TestScenario
    user_count: int
    spawn_rate: int
    duration_minutes: int
    gates: List[GateThreshold]
    weight: int = 1


class BaseAIUser(HttpUser):
    """Base user class for AI agent platform testing."""
    
    abstract = True
    wait_time = between(1, 3)
    
    def on_start(self):
        """Called when a user starts."""
        self.tenant_id = f"test_tenant_{random.randint(1000, 9999)}"
        self.session_token = None
        self.headers = {
            "Content-Type": "application/json",
            "X-Tenant-ID": self.tenant_id
        }
        
        # Authenticate user
        self._authenticate()
    
    def _authenticate(self):
        """Authenticate user and get session token."""
        try:
            response = self.client.post(
                "/auth/login",
                json={
                    "email": f"test_{self.tenant_id}@example.com",
                    "password": "test_password"
                },
                headers=self.headers
            )
            
            if response.status_code == 200:
                data = response.json()
                self.session_token = data.get("access_token")
                self.headers["Authorization"] = f"Bearer {self.session_token}"
                logger.info("User authenticated", tenant_id=self.tenant_id)
            else:
                logger.warning("Authentication failed", 
                             status_code=response.status_code,
                             tenant_id=self.tenant_id)
        except Exception as e:
            logger.error("Authentication error", error=str(e), tenant_id=self.tenant_id)
    
    def _make_api_call(self, method: str, endpoint: str, data: Optional[Dict] = None) -> bool:
        """Make API call with error handling."""
        try:
            if method.upper() == "GET":
                response = self.client.get(endpoint, headers=self.headers)
            elif method.upper() == "POST":
                response = self.client.post(endpoint, json=data, headers=self.headers)
            elif method.upper() == "PUT":
                response = self.client.put(endpoint, json=data, headers=self.headers)
            elif method.upper() == "DELETE":
                response = self.client.delete(endpoint, headers=self.headers)
            else:
                logger.error("Unsupported HTTP method", method=method)
                return False
            
            # Record custom metrics
            self.environment.events.request.fire(
                request_type=method,
                name=endpoint,
                response_time=response.elapsed.total_seconds() * 1000,
                response_length=len(response.content),
                exception=None,
                context=self.user_context()
            )
            
            return response.status_code < 400
            
        except Exception as e:
            logger.error("API call failed", 
                        method=method, 
                        endpoint=endpoint, 
                        error=str(e),
                        tenant_id=self.tenant_id)
            
            self.environment.events.request.fire(
                request_type=method,
                name=endpoint,
                response_time=0,
                response_length=0,
                exception=e,
                context=self.user_context()
            )
            
            return False


class LightUser(BaseAIUser):
    """Light user - occasional usage with simple tasks."""
    
    wait_time = between(5, 15)  # 5-15 seconds between requests
    
    @task(5)
    def simple_chat_request(self):
        """Simple chat request."""
        data = {
            "message": "Hello, how are you?",
            "context": {"user_type": "light_user"}
        }
        
        success = self._make_api_call("POST", "/chat/message", data)
        if not success:
            raise RescheduleTask()
    
    @task(2)
    def get_chat_history(self):
        """Get chat history."""
        success = self._make_api_call("GET", "/chat/history")
        if not success:
            raise RescheduleTask()
    
    @task(1)
    def simple_tool_call(self):
        """Simple tool call."""
        data = {
            "tool_name": "calculator",
            "parameters": {
                "expression": f"{random.randint(1, 10)} + {random.randint(1, 10)}"
            }
        }
        
        success = self._make_api_call("POST", "/tools/execute", data)
        if not success:
            raise RescheduleTask()


class ModerateUser(BaseAIUser):
    """Moderate user - regular usage with medium complexity tasks."""
    
    wait_time = between(2, 8)  # 2-8 seconds between requests
    
    @task(3)
    def complex_chat_request(self):
        """Complex chat request."""
        data = {
            "message": "Can you help me analyze this data and create a summary?",
            "context": {
                "user_type": "moderate_user",
                "data": [random.randint(1, 100) for _ in range(10)]
            }
        }
        
        success = self._make_api_call("POST", "/chat/message", data)
        if not success:
            raise RescheduleTask()
    
    @task(2)
    def multi_step_workflow(self):
        """Multi-step workflow."""
        data = {
            "workflow_type": "data_analysis",
            "steps": [
                {"action": "collect_data", "parameters": {"source": "database"}},
                {"action": "analyze_data", "parameters": {"method": "statistical"}},
                {"action": "generate_report", "parameters": {"format": "summary"}}
            ]
        }
        
        success = self._make_api_call("POST", "/workflows/execute", data)
        if not success:
            raise RescheduleTask()
    
    @task(1)
    def file_processing(self):
        """File processing request."""
        data = {
            "file_type": "csv",
            "operation": "analysis",
            "parameters": {
                "columns": ["id", "name", "value"],
                "filters": {"value": {"min": 0, "max": 100}}
            }
        }
        
        success = self._make_api_call("POST", "/files/process", data)
        if not success:
            raise RescheduleTask()


class HeavyUser(BaseAIUser):
    """Heavy user - intensive usage with complex tasks."""
    
    wait_time = between(1, 3)  # 1-3 seconds between requests
    
    @task(4)
    def complex_analysis_request(self):
        """Complex analysis request."""
        data = {
            "message": "Perform a comprehensive analysis of this dataset and provide insights",
            "context": {
                "user_type": "heavy_user",
                "dataset_size": random.randint(1000, 10000),
                "analysis_type": random.choice(["predictive", "descriptive", "prescriptive"])
            }
        }
        
        success = self._make_api_call("POST", "/chat/message", data)
        if not success:
            raise RescheduleTask()
    
    @task(3)
    def parallel_tool_execution(self):
        """Parallel tool execution."""
        tools = ["calculator", "data_analyzer", "text_processor", "chart_generator"]
        
        for tool in random.sample(tools, random.randint(2, 4)):
            data = {
                "tool_name": tool,
                "parameters": self._get_tool_parameters(tool)
            }
            
            success = self._make_api_call("POST", "/tools/execute", data)
            if not success:
                raise RescheduleTask()
    
    @task(2)
    def large_data_processing(self):
        """Large data processing request."""
        data = {
            "operation": "batch_processing",
            "data_size": random.randint(10000, 100000),
            "processing_type": random.choice(["aggregation", "transformation", "validation"])
        }
        
        success = self._make_api_call("POST", "/data/process", data)
        if not success:
            raise RescheduleTask()
    
    def _get_tool_parameters(self, tool_name: str) -> Dict[str, Any]:
        """Get tool-specific parameters."""
        if tool_name == "calculator":
            return {"expression": f"{random.randint(1, 100)} * {random.randint(1, 100)}"}
        elif tool_name == "data_analyzer":
            return {"dataset": [random.randint(1, 1000) for _ in range(100)]}
        elif tool_name == "text_processor":
            return {"text": "Sample text for processing", "operation": "summarize"}
        elif tool_name == "chart_generator":
            return {"data": [random.randint(1, 100) for _ in range(50)], "chart_type": "line"}
        else:
            return {}


class BurstUser(BaseAIUser):
    """Burst user - rapid requests in short bursts."""
    
    wait_time = between(0.1, 0.5)  # Very fast requests
    
    def on_start(self):
        """Start burst mode."""
        super().on_start()
        self.burst_count = 0
        self.max_bursts = random.randint(3, 8)
    
    @task(10)
    def rapid_requests(self):
        """Rapid burst of requests."""
        if self.burst_count >= self.max_bursts:
            # End burst, wait longer
            time.sleep(random.uniform(10, 30))
            self.burst_count = 0
            self.max_bursts = random.randint(3, 8)
            return
        
        self.burst_count += 1
        
        # Random endpoint selection
        endpoints = [
            ("POST", "/chat/message", {"message": "Quick question"}),
            ("GET", "/status", None),
            ("POST", "/tools/execute", {"tool_name": "calculator", "parameters": {"expression": "2+2"}})
        ]
        
        method, endpoint, data = random.choice(endpoints)
        success = self._make_api_call(method, endpoint, data)
        if not success:
            raise RescheduleTask()


class StressUser(BaseAIUser):
    """Stress user - extreme load testing."""
    
    wait_time = between(0.05, 0.2)  # Extremely fast requests
    
    @task(8)
    def stress_chat_request(self):
        """Stress chat request."""
        data = {
            "message": "Stress test message with complex context",
            "context": {
                "user_type": "stress_user",
                "stress_level": "maximum",
                "data": [random.randint(1, 10000) for _ in range(100)]
            }
        }
        
        success = self._make_api_call("POST", "/chat/message", data)
        if not success:
            raise RescheduleTask()
    
    @task(5)
    def stress_tool_execution(self):
        """Stress tool execution."""
        data = {
            "tool_name": "data_processor",
            "parameters": {
                "data_size": random.randint(100000, 1000000),
                "complexity": "maximum"
            }
        }
        
        success = self._make_api_call("POST", "/tools/execute", data)
        if not success:
            raise RescheduleTask()
    
    @task(3)
    def stress_file_upload(self):
        """Stress file upload simulation."""
        data = {
            "file_size": random.randint(1000000, 10000000),  # 1MB to 10MB
            "file_type": "large_dataset",
            "processing": "immediate"
        }
        
        success = self._make_api_call("POST", "/files/upload", data)
        if not success:
            raise RescheduleTask()


class PerformanceGateValidator:
    """Validates performance gates during testing."""
    
    def __init__(self):
        self.gates: Dict[str, GateThreshold] = {}
        self.metrics: Dict[str, List[float]] = {}
        
        # Register event handlers
        events.request.add_listener(self._on_request)
        events.test_stop.add_listener(self._on_test_stop)
    
    def add_gate(self, gate: PerformanceGate, threshold_value: float, unit: str, severity: str = "warning"):
        """Add a performance gate."""
        
        self.gates[gate.value] = GateThreshold(
            gate=gate,
            threshold_value=threshold_value,
            unit=unit,
            severity=severity
        )
        
        logger.info("Performance gate added", 
                   gate=gate.value,
                   threshold=threshold_value,
                   unit=unit,
                   severity=severity)
    
    def _on_request(self, request_type, name, response_time, response_length, exception, context, **kwargs):
        """Handle request events for metric collection."""
        
        # Collect latency metrics
        if "latency" in self.gates:
            if "latency" not in self.metrics:
                self.metrics["latency"] = []
            self.metrics["latency"].append(response_time)
        
        # Collect error metrics
        if exception:
            if "error_rate" not in self.metrics:
                self.metrics["error_rate"] = []
            self.metrics["error_rate"].append(1.0)  # Error occurred
        else:
            if "error_rate" not in self.metrics:
                self.metrics["error_rate"] = []
            self.metrics["error_rate"].append(0.0)  # No error
    
    def _on_test_stop(self, environment, **kwargs):
        """Validate performance gates when test stops."""
        
        logger.info("Validating performance gates")
        
        violations = []
        
        for gate_name, gate in self.gates.items():
            if gate_name not in self.metrics:
                continue
            
            metrics = self.metrics[gate_name]
            if not metrics:
                continue
            
            if gate.gate == PerformanceGate.LATENCY_P95_MS:
                p95 = self._percentile(metrics, 95)
                if p95 > gate.threshold_value:
                    violations.append({
                        "gate": gate_name,
                        "actual": p95,
                        "threshold": gate.threshold_value,
                        "severity": gate.severity
                    })
            
            elif gate.gate == PerformanceGate.LATENCY_P99_MS:
                p99 = self._percentile(metrics, 99)
                if p99 > gate.threshold_value:
                    violations.append({
                        "gate": gate_name,
                        "actual": p99,
                        "threshold": gate.threshold_value,
                        "severity": gate.severity
                    })
            
            elif gate.gate == PerformanceGate.ERROR_RATE_PERCENT:
                error_rate = (sum(metrics) / len(metrics)) * 100
                if error_rate > gate.threshold_value:
                    violations.append({
                        "gate": gate_name,
                        "actual": error_rate,
                        "threshold": gate.threshold_value,
                        "severity": gate.severity
                    })
        
        if violations:
            logger.error("Performance gate violations detected", violations=violations)
            
            # Check for critical violations
            critical_violations = [v for v in violations if v["severity"] == "critical"]
            if critical_violations:
                logger.critical("Critical performance gate violations", 
                              violations=critical_violations)
                # In a real implementation, this would trigger alerts or fail the test
        else:
            logger.info("All performance gates passed")
    
    def _percentile(self, values: List[float], percentile: int) -> float:
        """Calculate percentile of values."""
        
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int((percentile / 100) * len(sorted_values))
        index = min(index, len(sorted_values) - 1)
        
        return sorted_values[index]


# Test Profiles Configuration

def get_test_profiles() -> List[TestProfile]:
    """Get available test profiles."""
    
    return [
        TestProfile(
            name="light_load",
            description="Light load testing with occasional users",
            scenario=TestScenario.LIGHT_USER,
            user_count=10,
            spawn_rate=2,
            duration_minutes=10,
            gates=[
                GateThreshold(PerformanceGate.LATENCY_P95_MS, 500.0, "ms", "warning"),
                GateThreshold(PerformanceGate.ERROR_RATE_PERCENT, 1.0, "%", "critical")
            ]
        ),
        TestProfile(
            name="moderate_load",
            description="Moderate load testing with regular users",
            scenario=TestScenario.MODERATE_USER,
            user_count=50,
            spawn_rate=5,
            duration_minutes=15,
            gates=[
                GateThreshold(PerformanceGate.LATENCY_P95_MS, 1000.0, "ms", "warning"),
                GateThreshold(PerformanceGate.LATENCY_P99_MS, 2000.0, "ms", "critical"),
                GateThreshold(PerformanceGate.ERROR_RATE_PERCENT, 2.0, "%", "critical")
            ]
        ),
        TestProfile(
            name="heavy_load",
            description="Heavy load testing with intensive users",
            scenario=TestScenario.HEAVY_USER,
            user_count=100,
            spawn_rate=10,
            duration_minutes=20,
            gates=[
                GateThreshold(PerformanceGate.LATENCY_P95_MS, 2000.0, "ms", "warning"),
                GateThreshold(PerformanceGate.LATENCY_P99_MS, 5000.0, "ms", "critical"),
                GateThreshold(PerformanceGate.ERROR_RATE_PERCENT, 5.0, "%", "critical")
            ]
        ),
        TestProfile(
            name="burst_load",
            description="Burst load testing with rapid requests",
            scenario=TestScenario.BURST_USER,
            user_count=30,
            spawn_rate=15,
            duration_minutes=5,
            gates=[
                GateThreshold(PerformanceGate.LATENCY_P95_MS, 1000.0, "ms", "warning"),
                GateThreshold(PerformanceGate.ERROR_RATE_PERCENT, 3.0, "%", "critical")
            ]
        ),
        TestProfile(
            name="stress_load",
            description="Stress testing with extreme load",
            scenario=TestScenario.STRESS_USER,
            user_count=200,
            spawn_rate=20,
            duration_minutes=30,
            gates=[
                GateThreshold(PerformanceGate.LATENCY_P95_MS, 5000.0, "ms", "warning"),
                GateThreshold(PerformanceGate.LATENCY_P99_MS, 10000.0, "ms", "critical"),
                GateThreshold(PerformanceGate.ERROR_RATE_PERCENT, 10.0, "%", "critical")
            ]
        )
    ]


# Initialize performance gate validator
gate_validator = PerformanceGateValidator()

# Add default gates
gate_validator.add_gate(PerformanceGate.LATENCY_P95_MS, 1000.0, "ms", "warning")
gate_validator.add_gate(PerformanceGate.LATENCY_P99_MS, 2000.0, "ms", "critical")
gate_validator.add_gate(PerformanceGate.ERROR_RATE_PERCENT, 2.0, "%", "critical")
