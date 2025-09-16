"""
Example Tool Adapter Implementation

Demonstrates how to implement a tool adapter using the BaseToolAdapter
with comprehensive reliability patterns.
"""

import asyncio
import random
from typing import Dict, Any, Optional
import structlog

from libs.reliability import BaseToolAdapter, RetryConfig, CircuitBreakerConfig, BulkheadConfig, TimeoutConfig

logger = structlog.get_logger(__name__)


class DatabaseAdapter(BaseToolAdapter):
    """Example database adapter with reliability patterns."""
    
    def __init__(self, redis_client=None):
        super().__init__(
            tool_id="database_adapter",
            retry_config=RetryConfig(
                max_attempts=3,
                base_delay_ms=100,
                max_delay_ms=2000,
                jitter=True
            ),
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=5,
                success_threshold=3,
                timeout_ms=30000
            ),
            bulkhead_config=BulkheadConfig(
                max_concurrent_calls=5,
                max_wait_time_ms=3000
            ),
            timeout_config=TimeoutConfig(
                connect_timeout_ms=2000,
                read_timeout_ms=10000,
                total_timeout_ms=15000
            ),
            redis_client=redis_client
        )
        
        # Simulate database connection
        self.connected = False
        self.failure_rate = 0.1  # 10% failure rate for testing
        
        logger.info("Database adapter initialized")
    
    async def _execute_tool(self, parameters: Dict[str, Any]) -> Any:
        """Execute database operation."""
        
        operation = parameters.get("operation", "select")
        query = parameters.get("query", "")
        
        if not self.connected:
            await self._connect()
        
        # Simulate operation execution
        await asyncio.sleep(random.uniform(0.1, 0.5))  # Simulate network delay
        
        # Simulate random failures for testing
        if random.random() < self.failure_rate:
            raise Exception("Database connection timeout")
        
        # Simulate different operations
        if operation == "select":
            return self._simulate_select(query)
        elif operation == "insert":
            return self._simulate_insert(parameters.get("data", {}))
        elif operation == "update":
            return self._simulate_update(parameters.get("data", {}), parameters.get("where", {}))
        elif operation == "delete":
            return self._simulate_delete(parameters.get("where", {}))
        else:
            raise ValueError(f"Unsupported operation: {operation}")
    
    async def _connect(self):
        """Simulate database connection."""
        await asyncio.sleep(0.1)
        self.connected = True
        logger.info("Database connected")
    
    def _simulate_select(self, query: str) -> Dict[str, Any]:
        """Simulate SELECT operation."""
        return {
            "operation": "select",
            "query": query,
            "rows": [
                {"id": 1, "name": "John Doe", "email": "john@example.com"},
                {"id": 2, "name": "Jane Smith", "email": "jane@example.com"}
            ],
            "row_count": 2
        }
    
    def _simulate_insert(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate INSERT operation."""
        return {
            "operation": "insert",
            "data": data,
            "inserted_id": random.randint(1000, 9999),
            "affected_rows": 1
        }
    
    def _simulate_update(self, data: Dict[str, Any], where: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate UPDATE operation."""
        return {
            "operation": "update",
            "data": data,
            "where": where,
            "affected_rows": random.randint(1, 10)
        }
    
    def _simulate_delete(self, where: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate DELETE operation."""
        return {
            "operation": "delete",
            "where": where,
            "affected_rows": random.randint(0, 5)
        }
    
    async def compensate(self, parameters: Dict[str, Any], result: Any) -> bool:
        """Compensate for database operations."""
        
        operation = parameters.get("operation", "select")
        
        logger.info("Compensating database operation", operation=operation)
        
        # Simulate compensation delay
        await asyncio.sleep(0.1)
        
        if operation == "insert":
            # Compensate INSERT by deleting the inserted record
            if result and "inserted_id" in result:
                logger.info("Compensating INSERT by deleting record", 
                           inserted_id=result["inserted_id"])
                return True
        
        elif operation == "update":
            # Compensate UPDATE by restoring original values
            logger.info("Compensating UPDATE by restoring original values")
            return True
        
        elif operation == "delete":
            # Compensate DELETE by restoring deleted records
            logger.info("Compensating DELETE by restoring deleted records")
            return True
        
        elif operation == "select":
            # SELECT operations don't need compensation
            logger.info("SELECT operation requires no compensation")
            return True
        
        return True


class APIClientAdapter(BaseToolAdapter):
    """Example API client adapter with reliability patterns."""
    
    def __init__(self, redis_client=None):
        super().__init__(
            tool_id="api_client_adapter",
            retry_config=RetryConfig(
                max_attempts=5,
                base_delay_ms=200,
                max_delay_ms=5000,
                jitter=True
            ),
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout_ms=60000
            ),
            bulkhead_config=BulkheadConfig(
                max_concurrent_calls=10,
                max_wait_time_ms=5000
            ),
            timeout_config=TimeoutConfig(
                connect_timeout_ms=5000,
                read_timeout_ms=30000,
                total_timeout_ms=60000
            ),
            redis_client=redis_client
        )
        
        self.base_url = "https://api.example.com"
        self.failure_rate = 0.05  # 5% failure rate for testing
        
        logger.info("API client adapter initialized", base_url=self.base_url)
    
    async def _execute_tool(self, parameters: Dict[str, Any]) -> Any:
        """Execute API request."""
        
        method = parameters.get("method", "GET").upper()
        endpoint = parameters.get("endpoint", "/")
        data = parameters.get("data", {})
        headers = parameters.get("headers", {})
        
        # Simulate API request
        await asyncio.sleep(random.uniform(0.2, 1.0))  # Simulate network delay
        
        # Simulate random failures for testing
        if random.random() < self.failure_rate:
            raise Exception("API request timeout")
        
        # Simulate different HTTP methods
        if method == "GET":
            return self._simulate_get(endpoint, headers)
        elif method == "POST":
            return self._simulate_post(endpoint, data, headers)
        elif method == "PUT":
            return self._simulate_put(endpoint, data, headers)
        elif method == "DELETE":
            return self._simulate_delete(endpoint, headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
    
    def _simulate_get(self, endpoint: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Simulate GET request."""
        return {
            "method": "GET",
            "endpoint": endpoint,
            "status_code": 200,
            "data": {
                "id": random.randint(1, 1000),
                "name": "Example Resource",
                "created_at": "2024-01-01T00:00:00Z"
            },
            "headers": headers
        }
    
    def _simulate_post(self, endpoint: str, data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Simulate POST request."""
        return {
            "method": "POST",
            "endpoint": endpoint,
            "status_code": 201,
            "data": {
                "id": random.randint(1000, 9999),
                "created": True,
                "resource": data
            },
            "headers": headers
        }
    
    def _simulate_put(self, endpoint: str, data: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        """Simulate PUT request."""
        return {
            "method": "PUT",
            "endpoint": endpoint,
            "status_code": 200,
            "data": {
                "id": data.get("id", random.randint(1, 1000)),
                "updated": True,
                "resource": data
            },
            "headers": headers
        }
    
    def _simulate_delete(self, endpoint: str, headers: Dict[str, str]) -> Dict[str, Any]:
        """Simulate DELETE request."""
        return {
            "method": "DELETE",
            "endpoint": endpoint,
            "status_code": 204,
            "data": {
                "deleted": True
            },
            "headers": headers
        }
    
    async def compensate(self, parameters: Dict[str, Any], result: Any) -> bool:
        """Compensate for API operations."""
        
        method = parameters.get("method", "GET").upper()
        
        logger.info("Compensating API operation", method=method)
        
        # Simulate compensation delay
        await asyncio.sleep(0.2)
        
        if method == "POST":
            # Compensate POST by deleting the created resource
            if result and result.get("status_code") == 201:
                resource_id = result.get("data", {}).get("id")
                if resource_id:
                    logger.info("Compensating POST by deleting resource", resource_id=resource_id)
                    return True
        
        elif method == "PUT":
            # Compensate PUT by restoring original values
            logger.info("Compensating PUT by restoring original values")
            return True
        
        elif method == "DELETE":
            # Compensate DELETE by restoring the deleted resource
            logger.info("Compensating DELETE by restoring deleted resource")
            return True
        
        elif method == "GET":
            # GET operations don't need compensation
            logger.info("GET operation requires no compensation")
            return True
        
        return True


class FileSystemAdapter(BaseToolAdapter):
    """Example file system adapter with reliability patterns."""
    
    def __init__(self, redis_client=None):
        super().__init__(
            tool_id="filesystem_adapter",
            retry_config=RetryConfig(
                max_attempts=3,
                base_delay_ms=100,
                max_delay_ms=1000,
                jitter=False  # File operations don't need jitter
            ),
            circuit_breaker_config=CircuitBreakerConfig(
                failure_threshold=10,
                success_threshold=5,
                timeout_ms=30000
            ),
            bulkhead_config=BulkheadConfig(
                max_concurrent_calls=20,
                max_wait_time_ms=2000
            ),
            timeout_config=TimeoutConfig(
                connect_timeout_ms=1000,
                read_timeout_ms=5000,
                total_timeout_ms=10000
            ),
            redis_client=redis_client
        )
        
        self.failure_rate = 0.02  # 2% failure rate for testing
        
        logger.info("File system adapter initialized")
    
    async def _execute_tool(self, parameters: Dict[str, Any]) -> Any:
        """Execute file system operation."""
        
        operation = parameters.get("operation", "read")
        path = parameters.get("path", "")
        
        # Simulate file operation
        await asyncio.sleep(random.uniform(0.05, 0.2))  # Simulate I/O delay
        
        # Simulate random failures for testing
        if random.random() < self.failure_rate:
            raise Exception("File system I/O error")
        
        # Simulate different operations
        if operation == "read":
            return self._simulate_read(path)
        elif operation == "write":
            return self._simulate_write(path, parameters.get("content", ""))
        elif operation == "delete":
            return self._simulate_delete(path)
        elif operation == "copy":
            return self._simulate_copy(path, parameters.get("destination", ""))
        else:
            raise ValueError(f"Unsupported file operation: {operation}")
    
    def _simulate_read(self, path: str) -> Dict[str, Any]:
        """Simulate file read operation."""
        return {
            "operation": "read",
            "path": path,
            "content": f"Content of {path}",
            "size_bytes": len(f"Content of {path}"),
            "modified_at": "2024-01-01T00:00:00Z"
        }
    
    def _simulate_write(self, path: str, content: str) -> Dict[str, Any]:
        """Simulate file write operation."""
        return {
            "operation": "write",
            "path": path,
            "content": content,
            "size_bytes": len(content),
            "created": True
        }
    
    def _simulate_delete(self, path: str) -> Dict[str, Any]:
        """Simulate file delete operation."""
        return {
            "operation": "delete",
            "path": path,
            "deleted": True
        }
    
    def _simulate_copy(self, source: str, destination: str) -> Dict[str, Any]:
        """Simulate file copy operation."""
        return {
            "operation": "copy",
            "source": source,
            "destination": destination,
            "copied": True,
            "size_bytes": random.randint(100, 10000)
        }
    
    async def compensate(self, parameters: Dict[str, Any], result: Any) -> bool:
        """Compensate for file system operations."""
        
        operation = parameters.get("operation", "read")
        
        logger.info("Compensating file system operation", operation=operation)
        
        # Simulate compensation delay
        await asyncio.sleep(0.05)
        
        if operation == "write":
            # Compensate WRITE by deleting the created file
            if result and result.get("created"):
                logger.info("Compensating WRITE by deleting file", 
                           path=parameters.get("path"))
                return True
        
        elif operation == "delete":
            # Compensate DELETE by restoring the deleted file
            logger.info("Compensating DELETE by restoring file", 
                       path=parameters.get("path"))
            return True
        
        elif operation == "copy":
            # Compensate COPY by deleting the copied file
            if result and result.get("copied"):
                logger.info("Compensating COPY by deleting copied file", 
                           destination=parameters.get("destination"))
                return True
        
        elif operation == "read":
            # READ operations don't need compensation
            logger.info("READ operation requires no compensation")
            return True
        
        return True
