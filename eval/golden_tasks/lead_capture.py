"""Golden tasks for lead capture evaluation."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class TaskStatus(Enum):
    """Task status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


@dataclass
class GoldenTask:
    """Golden task definition."""
    task_id: str
    name: str
    description: str
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    assertions: List[Dict[str, Any]]
    timeout_seconds: int = 30
    max_retries: int = 3


@dataclass
class TaskResult:
    """Task execution result."""
    task_id: str
    status: TaskStatus
    actual_output: Dict[str, Any]
    execution_time_ms: float
    error_message: Optional[str] = None
    assertion_results: List[Dict[str, Any]] = None


class LeadCaptureGoldenTasks:
    """Golden tasks for lead capture evaluation."""
    
    def __init__(self):
        self.tasks = self._initialize_lead_tasks()
    
    def _initialize_lead_tasks(self) -> List[GoldenTask]:
        """Initialize lead capture golden tasks."""
        return [
            GoldenTask(
                task_id="lead_001",
                name="Capture Lead Information",
                description="Capture lead information from user input",
                input_data={
                    "message": "I'm interested in your AI platform. My name is John Doe and my email is john@example.com",
                    "user_id": "user_001",
                    "tenant_id": "tenant_001"
                },
                expected_output={
                    "lead_id": "lead_12345",
                    "name": "John Doe",
                    "email": "john@example.com",
                    "status": "captured",
                    "source": "chat"
                },
                assertions=[
                    {"type": "contains", "field": "lead_id", "value": "lead_"},
                    {"type": "equals", "field": "name", "value": "John Doe"},
                    {"type": "equals", "field": "email", "value": "john@example.com"},
                    {"type": "equals", "field": "status", "value": "captured"}
                ]
            ),
            GoldenTask(
                task_id="lead_002",
                name="Qualify Lead",
                description="Qualify lead based on company information",
                input_data={
                    "message": "I work at TechCorp, we have 500 employees and are looking for an AI solution",
                    "user_id": "user_001",
                    "tenant_id": "tenant_001",
                    "context": {
                        "lead_id": "lead_12345"
                    }
                },
                expected_output={
                    "lead_id": "lead_12345",
                    "company": "TechCorp",
                    "company_size": "500",
                    "qualification_score": 85,
                    "status": "qualified"
                },
                assertions=[
                    {"type": "equals", "field": "lead_id", "value": "lead_12345"},
                    {"type": "equals", "field": "company", "value": "TechCorp"},
                    {"type": "greater_than", "field": "qualification_score", "value": 80},
                    {"type": "equals", "field": "status", "value": "qualified"}
                ]
            )
        ]
    
    async def execute_task(self, task: GoldenTask) -> TaskResult:
        """Execute a golden task."""
        try:
            start_time = time.time()
            
            # Mock task execution
            actual_output = await self._mock_task_execution(task)
            
            execution_time = (time.time() - start_time) * 1000
            
            # Run assertions
            assertion_results = await self._run_assertions(task, actual_output)
            
            # Determine status
            all_passed = all(result['passed'] for result in assertion_results)
            status = TaskStatus.COMPLETED if all_passed else TaskStatus.FAILED
            
            return TaskResult(
                task_id=task.task_id,
                status=status,
                actual_output=actual_output,
                execution_time_ms=execution_time,
                assertion_results=assertion_results
            )
            
        except Exception as e:
            logger.error("Task execution failed", error=str(e), task_id=task.task_id)
            return TaskResult(
                task_id=task.task_id,
                status=TaskStatus.FAILED,
                actual_output={},
                execution_time_ms=0,
                error_message=str(e)
            )
    
    async def _mock_task_execution(self, task: GoldenTask) -> Dict[str, Any]:
        """Mock task execution."""
        try:
            await asyncio.sleep(0.1)
            output = task.expected_output.copy()
            return output
        except Exception as e:
            logger.error("Mock task execution failed", error=str(e))
            return {}
    
    async def _run_assertions(self, task: GoldenTask, actual_output: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Run assertions on task output."""
        try:
            results = []
            for assertion in task.assertions:
                result = await self._evaluate_assertion(assertion, actual_output)
                results.append(result)
            return results
        except Exception as e:
            logger.error("Assertion evaluation failed", error=str(e))
            return []
    
    async def _evaluate_assertion(self, assertion: Dict[str, Any], actual_output: Dict[str, Any]) -> Dict[str, Any]:
        """Evaluate a single assertion."""
        try:
            assertion_type = assertion['type']
            field = assertion['field']
            expected_value = assertion['value']
            
            actual_value = self._get_nested_value(actual_output, field)
            
            passed = False
            message = ""
            
            if assertion_type == "equals":
                passed = actual_value == expected_value
                message = f"Expected {expected_value}, got {actual_value}"
            elif assertion_type == "contains":
                passed = expected_value in str(actual_value)
                message = f"Expected {actual_value} to contain {expected_value}"
            elif assertion_type == "greater_than":
                passed = actual_value > expected_value
                message = f"Expected {actual_value} > {expected_value}"
            else:
                passed = False
                message = f"Unknown assertion type: {assertion_type}"
            
            return {
                'type': assertion_type,
                'field': field,
                'expected': expected_value,
                'actual': actual_value,
                'passed': passed,
                'message': message
            }
            
        except Exception as e:
            logger.error("Assertion evaluation failed", error=str(e))
            return {
                'type': assertion['type'],
                'field': assertion['field'],
                'expected': assertion['value'],
                'actual': None,
                'passed': False,
                'message': f"Assertion error: {str(e)}"
            }
    
    def _get_nested_value(self, data: Dict[str, Any], field: str) -> Any:
        """Get nested value from dictionary."""
        try:
            keys = field.split('.')
            value = data
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return None
            return value
        except Exception:
            return None
    
    async def get_all_tasks(self) -> List[GoldenTask]:
        """Get all golden tasks."""
        return self.tasks
    
    async def run_all_tasks(self) -> List[TaskResult]:
        """Run all golden tasks."""
        try:
            results = []
            for task in self.tasks:
                result = await self.execute_task(task)
                results.append(result)
            return results
        except Exception as e:
            logger.error("Failed to run all tasks", error=str(e))
            return []
    