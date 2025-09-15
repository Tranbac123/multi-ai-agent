"""Timeout Manager for enforcing end-to-end request timeouts."""

import asyncio
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)


class TimeoutType(Enum):
    """Types of timeouts."""
    CONNECT = "connect"
    READ = "read"
    WRITE = "write"
    TOTAL = "total"
    WORKFLOW_STEP = "workflow_step"


class TimeoutSeverity(Enum):
    """Timeout severity levels."""
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class TimeoutConfig:
    """Timeout configuration for different operation types."""
    operation_type: str
    connect_timeout_ms: int = 1000
    read_timeout_ms: int = 5000
    write_timeout_ms: int = 2000
    total_timeout_ms: int = 10000
    workflow_step_timeout_ms: int = 30000
    retry_timeout_ms: int = 1000
    max_retries: int = 3


@dataclass
class TimeoutEvent:
    """Timeout event data."""
    event_id: str
    operation_type: str
    timeout_type: TimeoutType
    timeout_value_ms: int
    actual_duration_ms: float
    severity: TimeoutSeverity
    occurred_at: datetime
    context: Dict[str, Any]


class TimeoutManager:
    """Manages timeouts for various operations with enforcement and monitoring."""
    
    def __init__(self):
        self.timeout_configs: Dict[str, TimeoutConfig] = {}
        self.active_operations: Dict[str, Dict[str, Any]] = {}
        self.timeout_events: List[TimeoutEvent] = []
        self._initialize_default_configs()
    
    def _initialize_default_configs(self):
        """Initialize default timeout configurations."""
        try:
            # API Gateway timeouts
            self.timeout_configs["api_gateway"] = TimeoutConfig(
                operation_type="api_gateway",
                connect_timeout_ms=500,
                read_timeout_ms=2000,
                write_timeout_ms=1000,
                total_timeout_ms=5000,
                workflow_step_timeout_ms=15000,
                max_retries=2
            )
            
            # LLM Service timeouts
            self.timeout_configs["llm_service"] = TimeoutConfig(
                operation_type="llm_service",
                connect_timeout_ms=1000,
                read_timeout_ms=30000,
                write_timeout_ms=5000,
                total_timeout_ms=60000,
                workflow_step_timeout_ms=120000,
                max_retries=1
            )
            
            # Vector Service timeouts
            self.timeout_configs["vector_service"] = TimeoutConfig(
                operation_type="vector_service",
                connect_timeout_ms=1000,
                read_timeout_ms=10000,
                write_timeout_ms=2000,
                total_timeout_ms=15000,
                workflow_step_timeout_ms=30000,
                max_retries=2
            )
            
            # Router Service timeouts
            self.timeout_configs["router_service"] = TimeoutConfig(
                operation_type="router_service",
                connect_timeout_ms=500,
                read_timeout_ms=3000,
                write_timeout_ms=1000,
                total_timeout_ms=8000,
                workflow_step_timeout_ms=10000,
                max_retries=3
            )
            
            # Billing Service timeouts
            self.timeout_configs["billing_service"] = TimeoutConfig(
                operation_type="billing_service",
                connect_timeout_ms=1000,
                read_timeout_ms=5000,
                write_timeout_ms=2000,
                total_timeout_ms=10000,
                workflow_step_timeout_ms=20000,
                max_retries=2
            )
            
            logger.info("Default timeout configurations initialized",
                       config_count=len(self.timeout_configs))
            
        except Exception as e:
            logger.error("Failed to initialize default timeout configs", error=str(e))
    
    async def execute_with_timeout(self, operation: Callable, operation_type: str,
                                 timeout_type: TimeoutType = TimeoutType.TOTAL,
                                 context: Optional[Dict[str, Any]] = None) -> Any:
        """Execute operation with timeout enforcement."""
        try:
            operation_id = f"{operation_type}_{int(time.time() * 1000)}"
            start_time = time.time()
            
            # Get timeout configuration
            config = self.timeout_configs.get(operation_type)
            if not config:
                logger.warning("No timeout config found, using defaults",
                             operation_type=operation_type)
                config = TimeoutConfig(operation_type=operation_type)
            
            # Get timeout value
            timeout_value = self._get_timeout_value(config, timeout_type)
            
            # Track active operation
            self.active_operations[operation_id] = {
                "operation_type": operation_type,
                "timeout_type": timeout_type,
                "start_time": start_time,
                "timeout_value_ms": timeout_value,
                "context": context or {}
            }
            
            logger.info("Starting operation with timeout",
                       operation_id=operation_id,
                       operation_type=operation_type,
                       timeout_type=timeout_type.value,
                       timeout_value_ms=timeout_value)
            
            try:
                # Execute operation with timeout
                result = await asyncio.wait_for(
                    operation(),
                    timeout=timeout_value / 1000.0
                )
                
                # Calculate actual duration
                actual_duration = (time.time() - start_time) * 1000
                
                # Log successful completion
                logger.info("Operation completed successfully",
                           operation_id=operation_id,
                           operation_type=operation_type,
                           actual_duration_ms=actual_duration,
                           timeout_value_ms=timeout_value)
                
                return result
                
            except asyncio.TimeoutError:
                # Handle timeout
                actual_duration = (time.time() - start_time) * 1000
                
                await self._handle_timeout(
                    operation_id, operation_type, timeout_type,
                    timeout_value, actual_duration, context
                )
                
                raise asyncio.TimeoutError(
                    f"Operation {operation_type} timed out after {actual_duration:.2f}ms "
                    f"(limit: {timeout_value}ms)"
                )
            
            finally:
                # Cleanup
                if operation_id in self.active_operations:
                    del self.active_operations[operation_id]
            
        except Exception as e:
            logger.error("Operation execution failed",
                        operation_id=operation_id,
                        operation_type=operation_type,
                        error=str(e))
            raise
    
    def _get_timeout_value(self, config: TimeoutConfig, timeout_type: TimeoutType) -> int:
        """Get timeout value based on type."""
        if timeout_type == TimeoutType.CONNECT:
            return config.connect_timeout_ms
        elif timeout_type == TimeoutType.READ:
            return config.read_timeout_ms
        elif timeout_type == TimeoutType.WRITE:
            return config.write_timeout_ms
        elif timeout_type == TimeoutType.TOTAL:
            return config.total_timeout_ms
        elif timeout_type == TimeoutType.WORKFLOW_STEP:
            return config.workflow_step_timeout_ms
        else:
            return config.total_timeout_ms
    
    async def _handle_timeout(self, operation_id: str, operation_type: str,
                            timeout_type: TimeoutType, timeout_value: int,
                            actual_duration: float, context: Optional[Dict[str, Any]]):
        """Handle timeout event."""
        try:
            # Determine severity
            severity = self._determine_timeout_severity(actual_duration, timeout_value)
            
            # Create timeout event
            timeout_event = TimeoutEvent(
                event_id=f"timeout_{operation_id}",
                operation_type=operation_type,
                timeout_type=timeout_type,
                timeout_value_ms=timeout_value,
                actual_duration_ms=actual_duration,
                severity=severity,
                occurred_at=datetime.now(timezone.utc),
                context=context or {}
            )
            
            # Store event
            self.timeout_events.append(timeout_event)
            
            # Keep only recent events (last 1000)
            if len(self.timeout_events) > 1000:
                self.timeout_events = self.timeout_events[-1000:]
            
            logger.warning("Timeout event recorded",
                          event_id=timeout_event.event_id,
                          operation_type=operation_type,
                          timeout_type=timeout_type.value,
                          actual_duration_ms=actual_duration,
                          timeout_value_ms=timeout_value,
                          severity=severity.value)
            
            # Handle based on severity
            await self._handle_timeout_by_severity(timeout_event)
            
        except Exception as e:
            logger.error("Failed to handle timeout",
                        operation_id=operation_id,
                        error=str(e))
    
    def _determine_timeout_severity(self, actual_duration: float, timeout_value: int) -> TimeoutSeverity:
        """Determine timeout severity based on duration."""
        try:
            ratio = actual_duration / timeout_value
            
            if ratio <= 1.0:
                return TimeoutSeverity.WARNING
            elif ratio <= 2.0:
                return TimeoutSeverity.CRITICAL
            else:
                return TimeoutSeverity.EMERGENCY
                
        except Exception as e:
            logger.error("Failed to determine timeout severity", error=str(e))
            return TimeoutSeverity.WARNING
    
    async def _handle_timeout_by_severity(self, timeout_event: TimeoutEvent):
        """Handle timeout based on severity level."""
        try:
            if timeout_event.severity == TimeoutSeverity.WARNING:
                # Log warning, no action needed
                logger.warning("Timeout warning",
                              event_id=timeout_event.event_id,
                              operation_type=timeout_event.operation_type)
                
            elif timeout_event.severity == TimeoutSeverity.CRITICAL:
                # Log critical timeout, consider circuit breaker
                logger.error("Critical timeout detected",
                           event_id=timeout_event.event_id,
                           operation_type=timeout_event.operation_type)
                
                # Here you would integrate with circuit breaker
                await self._notify_circuit_breaker(timeout_event)
                
            elif timeout_event.severity == TimeoutSeverity.EMERGENCY:
                # Emergency timeout, immediate action required
                logger.critical("Emergency timeout detected",
                              event_id=timeout_event.event_id,
                              operation_type=timeout_event.operation_type)
                
                # Immediate circuit breaker activation
                await self._activate_emergency_circuit_breaker(timeout_event)
            
        except Exception as e:
            logger.error("Failed to handle timeout by severity",
                        event_id=timeout_event.event_id,
                        error=str(e))
    
    async def _notify_circuit_breaker(self, timeout_event: TimeoutEvent):
        """Notify circuit breaker about critical timeout."""
        try:
            # In production, this would integrate with your circuit breaker
            logger.info("Notifying circuit breaker",
                       operation_type=timeout_event.operation_type,
                       severity=timeout_event.severity.value)
            
        except Exception as e:
            logger.error("Failed to notify circuit breaker", error=str(e))
    
    async def _activate_emergency_circuit_breaker(self, timeout_event: TimeoutEvent):
        """Activate emergency circuit breaker."""
        try:
            # In production, this would immediately activate circuit breaker
            logger.critical("Activating emergency circuit breaker",
                          operation_type=timeout_event.operation_type)
            
        except Exception as e:
            logger.error("Failed to activate emergency circuit breaker", error=str(e))
    
    def update_timeout_config(self, operation_type: str, config: TimeoutConfig):
        """Update timeout configuration for operation type."""
        try:
            self.timeout_configs[operation_type] = config
            
            logger.info("Timeout configuration updated",
                       operation_type=operation_type,
                       total_timeout_ms=config.total_timeout_ms,
                       max_retries=config.max_retries)
            
        except Exception as e:
            logger.error("Failed to update timeout config",
                        operation_type=operation_type,
                        error=str(e))
    
    def get_timeout_stats(self, operation_type: Optional[str] = None) -> Dict[str, Any]:
        """Get timeout statistics."""
        try:
            stats = {
                "total_operations": len(self.active_operations),
                "timeout_events_count": len(self.timeout_events),
                "timeout_events_by_type": {},
                "timeout_events_by_severity": {},
                "recent_timeout_rate": 0.0,
                "avg_timeout_duration": 0.0
            }
            
            # Filter events by operation type if specified
            events = self.timeout_events
            if operation_type:
                events = [e for e in events if e.operation_type == operation_type]
            
            if events:
                # Count by timeout type
                for timeout_type in TimeoutType:
                    count = sum(1 for e in events if e.timeout_type == timeout_type)
                    stats["timeout_events_by_type"][timeout_type.value] = count
                
                # Count by severity
                for severity in TimeoutSeverity:
                    count = sum(1 for e in events if e.severity == severity)
                    stats["timeout_events_by_severity"][severity.value] = count
                
                # Calculate recent timeout rate (last 100 events)
                recent_events = events[-100:] if len(events) > 100 else events
                stats["recent_timeout_rate"] = len(recent_events) / 100.0 if recent_events else 0.0
                
                # Calculate average timeout duration
                total_duration = sum(e.actual_duration_ms for e in events)
                stats["avg_timeout_duration"] = total_duration / len(events)
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get timeout stats", error=str(e))
            return {}
    
    def get_active_operations(self) -> Dict[str, Any]:
        """Get currently active operations."""
        try:
            current_time = time.time()
            active_ops = {}
            
            for operation_id, operation_data in self.active_operations.items():
                duration = (current_time - operation_data["start_time"]) * 1000
                timeout_value = operation_data["timeout_value_ms"]
                
                active_ops[operation_id] = {
                    "operation_type": operation_data["operation_type"],
                    "timeout_type": operation_data["timeout_type"].value,
                    "duration_ms": duration,
                    "timeout_value_ms": timeout_value,
                    "timeout_ratio": duration / timeout_value,
                    "context": operation_data["context"]
                }
            
            return active_ops
            
        except Exception as e:
            logger.error("Failed to get active operations", error=str(e))
            return {}
    
    async def cleanup_stale_operations(self, max_age_minutes: int = 30):
        """Clean up stale operations that may have been abandoned."""
        try:
            current_time = time.time()
            max_age_seconds = max_age_minutes * 60
            stale_operations = []
            
            for operation_id, operation_data in self.active_operations.items():
                age = current_time - operation_data["start_time"]
                if age > max_age_seconds:
                    stale_operations.append(operation_id)
            
            # Remove stale operations
            for operation_id in stale_operations:
                del self.active_operations[operation_id]
            
            if stale_operations:
                logger.warning("Cleaned up stale operations",
                             count=len(stale_operations),
                             operation_ids=stale_operations)
            
        except Exception as e:
            logger.error("Failed to cleanup stale operations", error=str(e))
    
    def get_timeout_recommendations(self, operation_type: str) -> Dict[str, Any]:
        """Get timeout recommendations based on historical data."""
        try:
            # Get timeout events for operation type
            events = [e for e in self.timeout_events if e.operation_type == operation_type]
            
            if not events:
                return {"recommendations": [], "confidence": "low"}
            
            recommendations = []
            confidence = "medium"
            
            # Analyze timeout patterns
            recent_events = events[-50:] if len(events) > 50 else events
            timeout_ratio = len(recent_events) / len(events) if events else 0
            
            if timeout_ratio > 0.1:  # More than 10% timeouts
                avg_timeout = sum(e.actual_duration_ms for e in recent_events) / len(recent_events)
                current_config = self.timeout_configs.get(operation_type)
                
                if current_config and avg_timeout > current_config.total_timeout_ms:
                    recommendations.append({
                        "type": "increase_timeout",
                        "current_timeout_ms": current_config.total_timeout_ms,
                        "recommended_timeout_ms": int(avg_timeout * 1.2),
                        "reason": f"Average timeout duration ({avg_timeout:.0f}ms) exceeds current limit"
                    })
                    confidence = "high"
            
            # Check for severity patterns
            critical_events = [e for e in recent_events if e.severity == TimeoutSeverity.CRITICAL]
            if len(critical_events) > 5:
                recommendations.append({
                    "type": "circuit_breaker",
                    "reason": "High number of critical timeouts detected",
                    "critical_timeouts": len(critical_events)
                })
                confidence = "high"
            
            return {
                "operation_type": operation_type,
                "recommendations": recommendations,
                "confidence": confidence,
                "total_events": len(events),
                "recent_events": len(recent_events),
                "timeout_ratio": timeout_ratio
            }
            
        except Exception as e:
            logger.error("Failed to get timeout recommendations",
                        operation_type=operation_type,
                        error=str(e))
            return {"recommendations": [], "confidence": "low", "error": str(e)}
