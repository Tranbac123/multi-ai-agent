"""Health checker for Kubernetes readiness and liveness probes."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class HealthStatus(Enum):
    """Health status."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check definition."""
    name: str
    check_type: str  # "readiness" or "liveness"
    timeout_seconds: int = 5
    interval_seconds: int = 10
    failure_threshold: int = 3
    success_threshold: int = 1
    initial_delay_seconds: int = 0


@dataclass
class HealthResult:
    """Health check result."""
    name: str
    status: HealthStatus
    message: str
    timestamp: float
    response_time_ms: float
    details: Dict[str, Any] = None


class HealthChecker:
    """Health checker for Kubernetes probes."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.health_checks = self._initialize_health_checks()
        self.health_results = {}
    
    def _initialize_health_checks(self) -> List[HealthCheck]:
        """Initialize health checks for all services."""
        return [
            # API Gateway health checks
            HealthCheck(
                name="api-gateway-readiness",
                check_type="readiness",
                timeout_seconds=5,
                interval_seconds=10,
                failure_threshold=3,
                success_threshold=1
            ),
            HealthCheck(
                name="api-gateway-liveness",
                check_type="liveness",
                timeout_seconds=5,
                interval_seconds=30,
                failure_threshold=3,
                success_threshold=1
            ),
            
            # Router Service health checks
            HealthCheck(
                name="router-service-readiness",
                check_type="readiness",
                timeout_seconds=5,
                interval_seconds=10,
                failure_threshold=3,
                success_threshold=1
            ),
            HealthCheck(
                name="router-service-liveness",
                check_type="liveness",
                timeout_seconds=5,
                interval_seconds=30,
                failure_threshold=3,
                success_threshold=1
            ),
            
            # Orchestrator health checks
            HealthCheck(
                name="orchestrator-readiness",
                check_type="readiness",
                timeout_seconds=5,
                interval_seconds=10,
                failure_threshold=3,
                success_threshold=1
            ),
            HealthCheck(
                name="orchestrator-liveness",
                check_type="liveness",
                timeout_seconds=5,
                interval_seconds=30,
                failure_threshold=3,
                success_threshold=1
            ),
            
            # Realtime Service health checks
            HealthCheck(
                name="realtime-readiness",
                check_type="readiness",
                timeout_seconds=5,
                interval_seconds=10,
                failure_threshold=3,
                success_threshold=1
            ),
            HealthCheck(
                name="realtime-liveness",
                check_type="liveness",
                timeout_seconds=5,
                interval_seconds=30,
                failure_threshold=3,
                success_threshold=1
            ),
            
            # Analytics Service health checks
            HealthCheck(
                name="analytics-service-readiness",
                check_type="readiness",
                timeout_seconds=5,
                interval_seconds=10,
                failure_threshold=3,
                success_threshold=1
            ),
            HealthCheck(
                name="analytics-service-liveness",
                check_type="liveness",
                timeout_seconds=5,
                interval_seconds=30,
                failure_threshold=3,
                success_threshold=1
            ),
            
            # Billing Service health checks
            HealthCheck(
                name="billing-service-readiness",
                check_type="readiness",
                timeout_seconds=5,
                interval_seconds=10,
                failure_threshold=3,
                success_threshold=1
            ),
            HealthCheck(
                name="billing-service-liveness",
                check_type="liveness",
                timeout_seconds=5,
                interval_seconds=30,
                failure_threshold=3,
                success_threshold=1
            )
        ]
    
    async def check_health(self, check_name: str) -> HealthResult:
        """Check health for specific service."""
        try:
            start_time = time.time()
            
            # Find health check configuration
            health_check = None
            for check in self.health_checks:
                if check.name == check_name:
                    health_check = check
                    break
            
            if not health_check:
                return HealthResult(
                    name=check_name,
                    status=HealthStatus.UNKNOWN,
                    message=f"Health check not found: {check_name}",
                    timestamp=time.time(),
                    response_time_ms=0
                )
            
            # Perform health check
            status, message, details = await self._perform_health_check(health_check)
            
            response_time = (time.time() - start_time) * 1000
            
            result = HealthResult(
                name=check_name,
                status=status,
                message=message,
                timestamp=time.time(),
                response_time_ms=response_time,
                details=details
            )
            
            # Store result
            self.health_results[check_name] = result
            
            # Store in Redis for persistence
            await self._store_health_result(result)
            
            return result
            
        except Exception as e:
            logger.error("Health check failed", error=str(e), check=check_name)
            return HealthResult(
                name=check_name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check error: {str(e)}",
                timestamp=time.time(),
                response_time_ms=0
            )
    
    async def _perform_health_check(self, health_check: HealthCheck) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Perform actual health check."""
        try:
            # Extract service name from check name
            service_name = health_check.name.replace(f"-{health_check.check_type}", "")
            
            # Perform service-specific health checks
            if health_check.check_type == "readiness":
                return await self._check_readiness(service_name)
            elif health_check.check_type == "liveness":
                return await self._check_liveness(service_name)
            else:
                return HealthStatus.UNKNOWN, f"Unknown check type: {health_check.check_type}", {}
                
        except Exception as e:
            logger.error("Health check execution failed", error=str(e), check=health_check.name)
            return HealthStatus.UNHEALTHY, f"Health check execution failed: {str(e)}", {}
    
    async def _check_readiness(self, service_name: str) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check service readiness."""
        try:
            # Check if service is ready to accept traffic
            readiness_checks = {
                'api-gateway': await self._check_api_gateway_readiness(),
                'router-service': await self._check_router_service_readiness(),
                'orchestrator': await self._check_orchestrator_readiness(),
                'realtime': await self._check_realtime_readiness(),
                'analytics-service': await self._check_analytics_service_readiness(),
                'billing-service': await self._check_billing_service_readiness()
            }
            
            if service_name in readiness_checks:
                return readiness_checks[service_name]
            else:
                return HealthStatus.UNKNOWN, f"Unknown service: {service_name}", {}
                
        except Exception as e:
            logger.error("Readiness check failed", error=str(e), service=service_name)
            return HealthStatus.UNHEALTHY, f"Readiness check failed: {str(e)}", {}
    
    async def _check_liveness(self, service_name: str) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check service liveness."""
        try:
            # Check if service is alive and responding
            liveness_checks = {
                'api-gateway': await self._check_api_gateway_liveness(),
                'router-service': await self._check_router_service_liveness(),
                'orchestrator': await self._check_orchestrator_liveness(),
                'realtime': await self._check_realtime_liveness(),
                'analytics-service': await self._check_analytics_service_liveness(),
                'billing-service': await self._check_billing_service_liveness()
            }
            
            if service_name in liveness_checks:
                return liveness_checks[service_name]
            else:
                return HealthStatus.UNKNOWN, f"Unknown service: {service_name}", {}
                
        except Exception as e:
            logger.error("Liveness check failed", error=str(e), service=service_name)
            return HealthStatus.UNHEALTHY, f"Liveness check failed: {str(e)}", {}
    
    async def _check_api_gateway_readiness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check API Gateway readiness."""
        try:
            # Check if API Gateway is ready to accept requests
            # In production, this would make actual HTTP calls
            
            # Mock readiness check
            return HealthStatus.HEALTHY, "API Gateway is ready", {
                'endpoints': ['/health', '/api/v1/chat', '/api/v1/websocket'],
                'dependencies': ['router-service', 'orchestrator']
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"API Gateway readiness check failed: {str(e)}", {}
    
    async def _check_api_gateway_liveness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check API Gateway liveness."""
        try:
            # Check if API Gateway is alive
            # In production, this would make actual HTTP calls
            
            # Mock liveness check
            return HealthStatus.HEALTHY, "API Gateway is alive", {
                'uptime': time.time(),
                'memory_usage': 0.6,
                'cpu_usage': 0.3
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"API Gateway liveness check failed: {str(e)}", {}
    
    async def _check_router_service_readiness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Router Service readiness."""
        try:
            # Check if Router Service is ready
            # In production, this would make actual HTTP calls
            
            # Mock readiness check
            return HealthStatus.HEALTHY, "Router Service is ready", {
                'endpoints': ['/health', '/route', '/outcome'],
                'dependencies': ['redis', 'analytics-service']
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Router Service readiness check failed: {str(e)}", {}
    
    async def _check_router_service_liveness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Router Service liveness."""
        try:
            # Check if Router Service is alive
            # In production, this would make actual HTTP calls
            
            # Mock liveness check
            return HealthStatus.HEALTHY, "Router Service is alive", {
                'uptime': time.time(),
                'memory_usage': 0.4,
                'cpu_usage': 0.2
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Router Service liveness check failed: {str(e)}", {}
    
    async def _check_orchestrator_readiness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Orchestrator readiness."""
        try:
            # Check if Orchestrator is ready
            # In production, this would make actual HTTP calls
            
            # Mock readiness check
            return HealthStatus.HEALTHY, "Orchestrator is ready", {
                'endpoints': ['/health', '/workflow', '/tools'],
                'dependencies': ['nats', 'redis', 'database']
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Orchestrator readiness check failed: {str(e)}", {}
    
    async def _check_orchestrator_liveness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Orchestrator liveness."""
        try:
            # Check if Orchestrator is alive
            # In production, this would make actual HTTP calls
            
            # Mock liveness check
            return HealthStatus.HEALTHY, "Orchestrator is alive", {
                'uptime': time.time(),
                'memory_usage': 0.7,
                'cpu_usage': 0.4
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Orchestrator liveness check failed: {str(e)}", {}
    
    async def _check_realtime_readiness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Realtime Service readiness."""
        try:
            # Check if Realtime Service is ready
            # In production, this would make actual HTTP calls
            
            # Mock readiness check
            return HealthStatus.HEALTHY, "Realtime Service is ready", {
                'endpoints': ['/health', '/websocket'],
                'dependencies': ['nats', 'redis']
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Realtime Service readiness check failed: {str(e)}", {}
    
    async def _check_realtime_liveness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Realtime Service liveness."""
        try:
            # Check if Realtime Service is alive
            # In production, this would make actual HTTP calls
            
            # Mock liveness check
            return HealthStatus.HEALTHY, "Realtime Service is alive", {
                'uptime': time.time(),
                'memory_usage': 0.5,
                'cpu_usage': 0.3,
                'websocket_connections': 150
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Realtime Service liveness check failed: {str(e)}", {}
    
    async def _check_analytics_service_readiness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Analytics Service readiness."""
        try:
            # Check if Analytics Service is ready
            # In production, this would make actual HTTP calls
            
            # Mock readiness check
            return HealthStatus.HEALTHY, "Analytics Service is ready", {
                'endpoints': ['/health', '/kpi', '/dashboard'],
                'dependencies': ['redis', 'database']
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Analytics Service readiness check failed: {str(e)}", {}
    
    async def _check_analytics_service_liveness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Analytics Service liveness."""
        try:
            # Check if Analytics Service is alive
            # In production, this would make actual HTTP calls
            
            # Mock liveness check
            return HealthStatus.HEALTHY, "Analytics Service is alive", {
                'uptime': time.time(),
                'memory_usage': 0.8,
                'cpu_usage': 0.2
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Analytics Service liveness check failed: {str(e)}", {}
    
    async def _check_billing_service_readiness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Billing Service readiness."""
        try:
            # Check if Billing Service is ready
            # In production, this would make actual HTTP calls
            
            # Mock readiness check
            return HealthStatus.HEALTHY, "Billing Service is ready", {
                'endpoints': ['/health', '/usage', '/billing'],
                'dependencies': ['redis', 'database']
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Billing Service readiness check failed: {str(e)}", {}
    
    async def _check_billing_service_liveness(self) -> tuple[HealthStatus, str, Dict[str, Any]]:
        """Check Billing Service liveness."""
        try:
            # Check if Billing Service is alive
            # In production, this would make actual HTTP calls
            
            # Mock liveness check
            return HealthStatus.HEALTHY, "Billing Service is alive", {
                'uptime': time.time(),
                'memory_usage': 0.6,
                'cpu_usage': 0.3
            }
            
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Billing Service liveness check failed: {str(e)}", {}
    
    async def _store_health_result(self, result: HealthResult) -> None:
        """Store health result in Redis."""
        try:
            import json
            
            result_dict = {
                'name': result.name,
                'status': result.status.value,
                'message': result.message,
                'timestamp': result.timestamp,
                'response_time_ms': result.response_time_ms,
                'details': result.details or {}
            }
            
            key = f"health_result:{result.name}"
            await self.redis.setex(key, 3600, json.dumps(result_dict, default=str))  # 1 hour TTL
            
        except Exception as e:
            logger.error("Failed to store health result", error=str(e), check=result.name)
    
    async def get_health_summary(self) -> Dict[str, Any]:
        """Get health summary for all services."""
        try:
            summary = {
                'total_checks': len(self.health_checks),
                'healthy': 0,
                'unhealthy': 0,
                'degraded': 0,
                'unknown': 0,
                'services': {}
            }
            
            # Count health results
            for result in self.health_results.values():
                if result.status == HealthStatus.HEALTHY:
                    summary['healthy'] += 1
                elif result.status == HealthStatus.UNHEALTHY:
                    summary['unhealthy'] += 1
                elif result.status == HealthStatus.DEGRADED:
                    summary['degraded'] += 1
                else:
                    summary['unknown'] += 1
                
                # Group by service
                service_name = result.name.replace('-readiness', '').replace('-liveness', '')
                if service_name not in summary['services']:
                    summary['services'][service_name] = {
                        'readiness': None,
                        'liveness': None
                    }
                
                if 'readiness' in result.name:
                    summary['services'][service_name]['readiness'] = result.status.value
                elif 'liveness' in result.name:
                    summary['services'][service_name]['liveness'] = result.status.value
            
            return summary
            
        except Exception as e:
            logger.error("Failed to get health summary", error=str(e))
            return {'error': str(e)}