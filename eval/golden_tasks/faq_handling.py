"""Golden tasks for FAQ handling evaluation."""

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


class FAQHandlingGoldenTasks:
    """Golden tasks for FAQ handling evaluation."""
    
    def __init__(self):
        self.tasks = self._initialize_faq_tasks()
    
    def _initialize_faq_tasks(self) -> List[GoldenTask]:
        """Initialize FAQ handling golden tasks."""
        return [
            GoldenTask(
                task_id="faq_001",
                name="Basic FAQ Question",
                description="Handle a basic FAQ question about product features",
                input_data={
                    "message": "What features does your product offer?",
                    "user_id": "user_001",
                    "tenant_id": "tenant_001"
                },
                expected_output={
                    "response": "Our AI Platform offers the following features:",
                    "confidence": 0.95,
                    "source": "faq_database"
                },
                assertions=[
                    {"type": "contains", "field": "response", "value": "features"},
                    {"type": "greater_than", "field": "confidence", "value": 0.9}
                ]
            ),
            GoldenTask(
                task_id="faq_002",
                name="Pricing Question",
                description="Handle a pricing-related FAQ question",
                input_data={
                    "message": "How much does the platform cost?",
                    "user_id": "user_002",
                    "tenant_id": "tenant_001"
                },
                expected_output={
                    "response": "Our pricing is based on usage:",
                    "confidence": 0.92,
                    "source": "pricing_database"
                },
                assertions=[
                    {"type": "contains", "field": "response", "value": "pricing"},
                    {"type": "greater_than", "field": "confidence", "value": 0.8}
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
            if 'confidence' in output:
                output['confidence'] = max(0.8, min(0.99, output['confidence'] + 0.02))
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
