"""Health checker for resilient tool adapters."""

import asyncio
import time
from typing import Callable, Any, Optional, Dict, List
from dataclasses import dataclass
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class HealthStatus(Enum):
    """Health status values."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckConfig:
    """Configuration for health checker."""
    check_interval: float = 30.0  # Seconds between checks
    timeout: float = 10.0         # Timeout for individual checks
    failure_threshold: int = 3    # Failures before marking unhealthy
    success_threshold: int = 2    # Successes needed to mark healthy
    enabled: bool = True


class HealthChecker:
    """Health checker for monitoring service health."""
    
    def __init__(self, name: str, config: HealthCheckConfig = None):
        self.name = name
        self.config = config or HealthCheckConfig()
        self.status = HealthStatus.UNKNOWN
        self.last_check = None
        self.last_success = None
        self.last_failure = None
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.check_function: Optional[Callable] = None
        self._task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()
    
    def set_check_function(self, func: Callable):
        """Set the health check function."""
        self.check_function = func
    
    async def start(self):
        """Start the health checker."""
        if not self.config.enabled:
            logger.info(f"Health checker {self.name} is disabled")
            return
        
        if self.check_function is None:
            logger.warning(f"No check function set for health checker {self.name}")
            return
        
        self._task = asyncio.create_task(self._run_checks())
        logger.info(f"Health checker {self.name} started")
    
    async def stop(self):
        """Stop the health checker."""
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            logger.info(f"Health checker {self.name} stopped")
    
    async def _run_checks(self):
        """Run periodic health checks."""
        while True:
            try:
                await self._perform_check()
                await asyncio.sleep(self.config.check_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Health checker {self.name} error: {e}")
                await asyncio.sleep(self.config.check_interval)
    
    async def _perform_check(self):
        """Perform a single health check."""
        if not self.check_function:
            return
        
        start_time = time.time()
        self.last_check = start_time
        
        try:
            # Execute health check with timeout
            result = await asyncio.wait_for(
                self.check_function(),
                timeout=self.config.timeout
            )
            
            # Check if result indicates health
            is_healthy = self._evaluate_result(result)
            
            if is_healthy:
                await self._on_success()
            else:
                await self._on_failure(f"Health check returned unhealthy result: {result}")
                
        except asyncio.TimeoutError:
            await self._on_failure("Health check timed out")
        except Exception as e:
            await self._on_failure(f"Health check failed: {e}")
    
    def _evaluate_result(self, result: Any) -> bool:
        """Evaluate health check result."""
        if isinstance(result, bool):
            return result
        elif isinstance(result, dict):
            return result.get("healthy", False)
        elif isinstance(result, str):
            return result.lower() in ["healthy", "ok", "up"]
        else:
            # Default to True for non-falsy values
            return bool(result)
    
    async def _on_success(self):
        """Handle successful health check."""
        async with self._lock:
            self.last_success = time.time()
            self.consecutive_successes += 1
            self.consecutive_failures = 0
            
            # Update status based on consecutive successes
            if self.status == HealthStatus.UNHEALTHY:
                if self.consecutive_successes >= self.config.success_threshold:
                    self.status = HealthStatus.HEALTHY
                    logger.info(f"Health checker {self.name} status changed to HEALTHY")
            elif self.status == HealthStatus.UNKNOWN:
                self.status = HealthStatus.HEALTHY
                logger.info(f"Health checker {self.name} status changed to HEALTHY")
    
    async def _on_failure(self, reason: str):
        """Handle failed health check."""
        async with self._lock:
            self.last_failure = time.time()
            self.consecutive_failures += 1
            self.consecutive_successes = 0
            
            # Update status based on consecutive failures
            if self.consecutive_failures >= self.config.failure_threshold:
                if self.status != HealthStatus.UNHEALTHY:
                    self.status = HealthStatus.UNHEALTHY
                    logger.warning(f"Health checker {self.name} status changed to UNHEALTHY: {reason}")
            elif self.status == HealthStatus.UNKNOWN:
                self.status = HealthStatus.DEGRADED
                logger.warning(f"Health checker {self.name} status changed to DEGRADED: {reason}")
    
    async def check_now(self) -> HealthStatus:
        """Perform an immediate health check."""
        if not self.check_function:
            return HealthStatus.UNKNOWN
        
        try:
            result = await asyncio.wait_for(
                self.check_function(),
                timeout=self.config.timeout
            )
            
            is_healthy = self._evaluate_result(result)
            if is_healthy:
                await self._on_success()
            else:
                await self._on_failure("Immediate health check failed")
                
        except Exception as e:
            await self._on_failure(f"Immediate health check error: {e}")
        
        return self.status
    
    def get_status(self) -> Dict[str, Any]:
        """Get current health status."""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_check": self.last_check,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "config": {
                "check_interval": self.config.check_interval,
                "timeout": self.config.timeout,
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "enabled": self.config.enabled
            }
        }


class HealthCheckManager:
    """Manager for multiple health checkers."""
    
    def __init__(self):
        self.checkers: Dict[str, HealthChecker] = {}
        self._lock = asyncio.Lock()
    
    def add_checker(self, name: str, checker: HealthChecker):
        """Add a health checker."""
        self.checkers[name] = checker
    
    async def start_all(self):
        """Start all health checkers."""
        tasks = []
        for checker in self.checkers.values():
            tasks.append(checker.start())
        await asyncio.gather(*tasks)
    
    async def stop_all(self):
        """Stop all health checkers."""
        tasks = []
        for checker in self.checkers.values():
            tasks.append(checker.stop())
        await asyncio.gather(*tasks)
    
    def get_overall_status(self) -> HealthStatus:
        """Get overall health status."""
        if not self.checkers:
            return HealthStatus.UNKNOWN
        
        statuses = [checker.status for checker in self.checkers.values()]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            return HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.UNKNOWN
    
    def get_all_statuses(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all health checkers."""
        return {name: checker.get_status() for name, checker in self.checkers.items()}
