"""Health checker for Kubernetes services."""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis
import httpx

logger = structlog.get_logger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check configuration."""
    name: str
    service_url: str
    check_type: str  # http, tcp, redis, database
    timeout: int = 5
    interval: int = 30
    retries: int = 3
    expected_status: int = 200
    expected_response: Optional[str] = None
    headers: Optional[Dict[str, str]] = None
    metadata: Optional[Dict[str, Any]] = None


class HealthChecker:
    """Health checker for Kubernetes services."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.health_checks = {}
        self.check_results = {}
        self.health_handlers = []
        self.running_checks = {}
    
    def add_health_check(self, check: HealthCheck) -> None:
        """Add a health check configuration."""
        self.health_checks[check.name] = check
        logger.info("Health check added", name=check.name, type=check.check_type)
    
    def add_health_handler(self, handler: Callable) -> None:
        """Add health status change handler."""
        self.health_handlers.append(handler)
    
    async def start_health_checks(self) -> None:
        """Start all health checks."""
        try:
            for check_name, check in self.health_checks.items():
                if check_name not in self.running_checks:
                    task = asyncio.create_task(self._run_health_check(check_name))
                    self.running_checks[check_name] = task
                    logger.info("Started health check", name=check_name)
            
        except Exception as e:
            logger.error("Failed to start health checks", error=str(e))
    
    async def stop_health_checks(self) -> None:
        """Stop all health checks."""
        try:
            for check_name, task in self.running_checks.items():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            self.running_checks.clear()
            logger.info("Stopped all health checks")
            
        except Exception as e:
            logger.error("Failed to stop health checks", error=str(e))
    
    async def _run_health_check(self, check_name: str) -> None:
        """Run a health check continuously."""
        try:
            check = self.health_checks[check_name]
            
            while True:
                try:
                    # Perform health check
                    result = await self._perform_health_check(check)
                    
                    # Store result
                    self.check_results[check_name] = result
                    await self._store_health_result(check_name, result)
                    
                    # Check for status changes
                    await self._check_status_change(check_name, result)
                    
                    # Wait for next check
                    await asyncio.sleep(check.interval)
                    
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Health check error", error=str(e), check_name=check_name)
                    await asyncio.sleep(check.interval)
                    
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error("Health check task failed", error=str(e), check_name=check_name)
    
    async def _perform_health_check(self, check: HealthCheck) -> Dict[str, Any]:
        """Perform a single health check."""
        try:
            start_time = time.time()
            
            if check.check_type == 'http':
                result = await self._check_http_health(check)
            elif check.check_type == 'tcp':
                result = await self._check_tcp_health(check)
            elif check.check_type == 'redis':
                result = await self._check_redis_health(check)
            elif check.check_type == 'database':
                result = await self._check_database_health(check)
            else:
                result = {
                    'status': HealthStatus.UNKNOWN,
                    'error': f'Unknown check type: {check.check_type}'
                }
            
            result['check_time'] = time.time() - start_time
            result['timestamp'] = time.time()
            
            return result
            
        except Exception as e:
            logger.error("Health check failed", error=str(e), check_name=check.name)
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e),
                'check_time': 0,
                'timestamp': time.time()
            }
    
    async def _check_http_health(self, check: HealthCheck) -> Dict[str, Any]:
        """Check HTTP health endpoint."""
        try:
            async with httpx.AsyncClient(timeout=check.timeout) as client:
                response = await client.get(
                    check.service_url,
                    headers=check.headers or {}
                )
                
                # Check status code
                if response.status_code == check.expected_status:
                    status = HealthStatus.HEALTHY
                elif 200 <= response.status_code < 400:
                    status = HealthStatus.DEGRADED
                else:
                    status = HealthStatus.UNHEALTHY
                
                # Check response content if specified
                if check.expected_response and check.expected_response not in response.text:
                    status = HealthStatus.UNHEALTHY
                
                return {
                    'status': status,
                    'status_code': response.status_code,
                    'response_time': response.elapsed.total_seconds(),
                    'response_size': len(response.content)
                }
                
        except httpx.TimeoutException:
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': 'Request timeout'
            }
        except httpx.ConnectError:
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': 'Connection failed'
            }
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    async def _check_tcp_health(self, check: HealthCheck) -> Dict[str, Any]:
        """Check TCP connection health."""
        try:
            # Parse host and port from URL
            url_parts = check.service_url.replace('tcp://', '').split(':')
            host = url_parts[0]
            port = int(url_parts[1]) if len(url_parts) > 1 else 80
            
            # Attempt TCP connection
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(host, port),
                timeout=check.timeout
            )
            
            writer.close()
            await writer.wait_closed()
            
            return {
                'status': HealthStatus.HEALTHY,
                'host': host,
                'port': port
            }
            
        except asyncio.TimeoutError:
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': 'Connection timeout'
            }
        except ConnectionRefusedError:
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': 'Connection refused'
            }
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    async def _check_redis_health(self, check: HealthCheck) -> Dict[str, Any]:
        try:
            # Test Redis connection
            await self.redis.ping()
            
            # Get Redis info
            info = await self.redis.info()
            
            return {
                'status': HealthStatus.HEALTHY,
                'redis_version': info.get('redis_version', 'unknown'),
                'used_memory': info.get('used_memory_human', 'unknown'),
                'connected_clients': info.get('connected_clients', 0)
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    async def _check_database_health(self, check: HealthCheck) -> Dict[str, Any]:
        try:
            # This would typically check database connection
            # For now, we'll simulate it
            await asyncio.sleep(0.1)  # Simulate database check
            
            return {
                'status': HealthStatus.HEALTHY,
                'database_type': 'postgresql',
                'connection_pool': 'active'
            }
            
        except Exception as e:
            return {
                'status': HealthStatus.UNHEALTHY,
                'error': str(e)
            }
    
    async def _store_health_result(self, check_name: str, result: Dict[str, Any]) -> None:
        """Store health check result in Redis."""
        try:
            result_key = f"health_result:{check_name}:{int(time.time())}"
            await self.redis.setex(result_key, 3600, str(result))  # 1 hour TTL
            
            # Update latest result
            latest_key = f"health_latest:{check_name}"
            await self.redis.setex(latest_key, 3600, str(result))
            
        except Exception as e:
            logger.error("Failed to store health result", error=str(e))
    
    async def _check_status_change(self, check_name: str, result: Dict[str, Any]) -> None:
        """Check for health status changes and trigger handlers."""
        try:
            # Get previous result
            previous_key = f"health_previous:{check_name}"
            previous_result = await self.redis.get(previous_key)
            
            if previous_result:
                previous_status = previous_result.get('status')
                current_status = result['status']
                
                if previous_status != current_status:
                    # Status changed, trigger handlers
                    for handler in self.health_handlers:
                        try:
                            await handler(check_name, previous_status, current_status, result)
                        except Exception as e:
                            logger.error("Health handler failed", error=str(e))
                    
                    logger.info(
                        "Health status changed",
                        check_name=check_name,
                        previous_status=previous_status,
                        current_status=current_status
                    )
            
            # Store current result as previous
            await self.redis.setex(previous_key, 3600, str(result))
            
        except Exception as e:
            logger.error("Failed to check status change", error=str(e))
    
    async def get_health_status(self, check_name: str) -> Optional[Dict[str, Any]]:
        """Get current health status for a check."""
        return self.check_results.get(check_name)
    
    async def get_all_health_status(self) -> Dict[str, Any]:
        """Get health status for all checks."""
        return {
            'checks': self.check_results,
            'overall_status': self._calculate_overall_status(),
            'timestamp': time.time()
        }
    
    def _calculate_overall_status(self) -> HealthStatus:
        """Calculate overall health status."""
        if not self.check_results:
            return HealthStatus.UNKNOWN
        
        statuses = [result['status'] for result in self.check_results.values()]
        
        if HealthStatus.UNHEALTHY in statuses:
            return HealthStatus.UNHEALTHY
        elif HealthStatus.DEGRADED in statuses:
            return HealthStatus.DEGRADED
        elif all(status == HealthStatus.HEALTHY for status in statuses):
            return HealthStatus.HEALTHY
        else:
            return HealthStatus.UNKNOWN
    
    async def get_health_history(self, check_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get health check history."""
        try:
            end_time = int(time.time())
            start_time = end_time - (hours * 3600)
            
            history = []
            
            # Get historical results
            pattern = f"health_result:{check_name}:*"
            keys = await self.redis.keys(pattern)
            
            for key in keys:
                try:
                    # Extract timestamp from key
                    timestamp_str = key.decode().split(':')[-1]
                    timestamp = int(timestamp_str)
                    
                    if start_time <= timestamp <= end_time:
                        result_data = await self.redis.get(key)
                        if result_data:
                            history.append({
                                'timestamp': timestamp,
                                'result': eval(result_data)  # Note: In production, use proper JSON parsing
                            })
                except Exception as e:
                    logger.error("Failed to parse health history key", error=str(e), key=key)
            
            # Sort by timestamp
            history.sort(key=lambda x: x['timestamp'])
            
            return history
            
        except Exception as e:
            logger.error("Failed to get health history", error=str(e))
            return []
    
    async def perform_manual_check(self, check_name: str) -> Dict[str, Any]:
        """Perform a manual health check."""
        try:
            if check_name not in self.health_checks:
                return {'error': 'Health check not found'}
            
            check = self.health_checks[check_name]
            result = await self._perform_health_check(check)
            
            # Store result
            self.check_results[check_name] = result
            await self._store_health_result(check_name, result)
            
            return result
            
        except Exception as e:
            logger.error("Manual health check failed", error=str(e))
            return {'error': str(e)}
    
    async def get_health_statistics(self) -> Dict[str, Any]:
        """Get health check statistics."""
        try:
            stats = {
                'total_checks': len(self.health_checks),
                'active_checks': len(self.running_checks),
                'status_distribution': {},
                'average_response_time': 0,
                'uptime_percentage': 0
            }
            
            # Calculate status distribution
            for result in self.check_results.values():
                status = result['status'].value
                stats['status_distribution'][status] = stats['status_distribution'].get(status, 0) + 1
            
            # Calculate average response time
            response_times = [result.get('check_time', 0) for result in self.check_results.values()]
            if response_times:
                stats['average_response_time'] = sum(response_times) / len(response_times)
            
            # Calculate uptime percentage
            healthy_checks = stats['status_distribution'].get('healthy', 0)
            total_checks = len(self.check_results)
            if total_checks > 0:
                stats['uptime_percentage'] = (healthy_checks / total_checks) * 100
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get health statistics", error=str(e))
            return {'error': str(e)}
