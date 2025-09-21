#!/usr/bin/env python3
"""Enhanced health checker for Multi-Tenant AIaaS Platform."""

import asyncio
import aiohttp
import json
import time
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import sys

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status enumeration."""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    """Health check configuration."""
    name: str
    url: str
    timeout: float = 5.0
    expected_status: int = 200
    expected_response: Optional[Dict] = None
    critical: bool = True
    retries: int = 3
    retry_delay: float = 1.0


@dataclass
class HealthResult:
    """Health check result."""
    name: str
    status: HealthStatus
    response_time: float
    error: Optional[str] = None
    details: Optional[Dict] = None


class EnhancedHealthChecker:
    """Enhanced health checker with comprehensive monitoring."""
    
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.health_checks: List[HealthCheck] = []
        self.results: List[HealthResult] = []
        
    async def __aenter__(self):
        """Async context manager entry."""
        self.session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30),
            connector=aiohttp.TCPConnector(limit=100)
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def add_health_check(self, health_check: HealthCheck):
        """Add a health check to the checker."""
        self.health_checks.append(health_check)
        logger.info(f"Added health check: {health_check.name}")
    
    async def check_service_health(self, health_check: HealthCheck) -> HealthResult:
        """Check the health of a single service."""
        start_time = time.time()
        
        for attempt in range(health_check.retries + 1):
            try:
                async with self.session.get(
                    health_check.url,
                    timeout=aiohttp.ClientTimeout(total=health_check.timeout)
                ) as response:
                    response_time = time.time() - start_time
                    
                    # Check status code
                    if response.status != health_check.expected_status:
                        error_msg = f"Expected status {health_check.expected_status}, got {response.status}"
                        if attempt < health_check.retries:
                            logger.warning(f"Health check {health_check.name} failed (attempt {attempt + 1}): {error_msg}")
                            await asyncio.sleep(health_check.retry_delay)
                            continue
                        else:
                            return HealthResult(
                                name=health_check.name,
                                status=HealthStatus.UNHEALTHY,
                                response_time=response_time,
                                error=error_msg
                            )
                    
                    # Check response content if expected
                    details = None
                    if health_check.expected_response:
                        try:
                            response_data = await response.json()
                            details = response_data
                            
                            # Validate expected response structure
                            for key, expected_value in health_check.expected_response.items():
                                if key not in response_data:
                                    error_msg = f"Missing expected key '{key}' in response"
                                    if attempt < health_check.retries:
                                        logger.warning(f"Health check {health_check.name} failed (attempt {attempt + 1}): {error_msg}")
                                        await asyncio.sleep(health_check.retry_delay)
                                        continue
                                    else:
                                        return HealthResult(
                                            name=health_check.name,
                                            status=HealthStatus.UNHEALTHY,
                                            response_time=response_time,
                                            error=error_msg,
                                            details=details
                                        )
                                
                                if response_data[key] != expected_value:
                                    error_msg = f"Expected '{key}' to be '{expected_value}', got '{response_data[key]}'"
                                    if attempt < health_check.retries:
                                        logger.warning(f"Health check {health_check.name} failed (attempt {attempt + 1}): {error_msg}")
                                        await asyncio.sleep(health_check.retry_delay)
                                        continue
                                    else:
                                        return HealthResult(
                                            name=health_check.name,
                                            status=HealthStatus.UNHEALTHY,
                                            response_time=response_time,
                                            error=error_msg,
                                            details=details
                                        )
                        except json.JSONDecodeError as e:
                            error_msg = f"Invalid JSON response: {str(e)}"
                            if attempt < health_check.retries:
                                logger.warning(f"Health check {health_check.name} failed (attempt {attempt + 1}): {error_msg}")
                                await asyncio.sleep(health_check.retry_delay)
                                continue
                            else:
                                return HealthResult(
                                    name=health_check.name,
                                    status=HealthStatus.UNHEALTHY,
                                    response_time=response_time,
                                    error=error_msg
                                )
                    else:
                        # Basic health check - just check if response is successful
                        try:
                            details = await response.json()
                        except:
                            details = {"status": "ok"}
                    
                    # Check response time thresholds
                    if response_time > 5.0:  # 5 seconds threshold
                        status = HealthStatus.DEGRADED
                        logger.warning(f"Health check {health_check.name} is slow: {response_time:.2f}s")
                    else:
                        status = HealthStatus.HEALTHY
                    
                    return HealthResult(
                        name=health_check.name,
                        status=status,
                        response_time=response_time,
                        details=details
                    )
                    
            except asyncio.TimeoutError:
                error_msg = f"Timeout after {health_check.timeout}s"
                if attempt < health_check.retries:
                    logger.warning(f"Health check {health_check.name} timed out (attempt {attempt + 1}): {error_msg}")
                    await asyncio.sleep(health_check.retry_delay)
                    continue
                else:
                    return HealthResult(
                        name=health_check.name,
                        status=HealthStatus.UNHEALTHY,
                        response_time=time.time() - start_time,
                        error=error_msg
                    )
                    
            except Exception as e:
                error_msg = f"Unexpected error: {str(e)}"
                if attempt < health_check.retries:
                    logger.warning(f"Health check {health_check.name} failed (attempt {attempt + 1}): {error_msg}")
                    await asyncio.sleep(health_check.retry_delay)
                    continue
                else:
                    return HealthResult(
                        name=health_check.name,
                        status=HealthStatus.UNHEALTHY,
                        response_time=time.time() - start_time,
                        error=error_msg
                    )
        
        # This should never be reached, but just in case
        return HealthResult(
            name=health_check.name,
            status=HealthStatus.UNKNOWN,
            response_time=time.time() - start_time,
            error="Maximum retries exceeded"
        )
    
    async def run_all_health_checks(self) -> List[HealthResult]:
        """Run all health checks concurrently."""
        if not self.health_checks:
            logger.warning("No health checks configured")
            return []
        
        logger.info(f"Running {len(self.health_checks)} health checks...")
        
        # Run all health checks concurrently
        tasks = [
            self.check_service_health(health_check)
            for health_check in self.health_checks
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results and handle exceptions
        self.results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Health check {self.health_checks[i].name} failed with exception: {result}")
                self.results.append(HealthResult(
                    name=self.health_checks[i].name,
                    status=HealthStatus.UNHEALTHY,
                    response_time=0.0,
                    error=str(result)
                ))
            else:
                self.results.append(result)
        
        return self.results
    
    def get_overall_status(self) -> HealthStatus:
        """Get the overall health status."""
        if not self.results:
            return HealthStatus.UNKNOWN
        
        # Check if any critical services are unhealthy
        critical_unhealthy = any(
            result.status == HealthStatus.UNHEALTHY and 
            any(check.critical for check in self.health_checks if check.name == result.name)
            for result in self.results
        )
        
        if critical_unhealthy:
            return HealthStatus.UNHEALTHY
        
        # Check if any services are degraded
        any_degraded = any(result.status == HealthStatus.DEGRADED for result in self.results)
        if any_degraded:
            return HealthStatus.DEGRADED
        
        # Check if all services are healthy
        all_healthy = all(result.status == HealthStatus.HEALTHY for result in self.results)
        if all_healthy:
            return HealthStatus.HEALTHY
        
        return HealthStatus.UNKNOWN
    
    def generate_report(self) -> Dict:
        """Generate a comprehensive health report."""
        overall_status = self.get_overall_status()
        
        report = {
            "timestamp": time.time(),
            "overall_status": overall_status.value,
            "total_checks": len(self.results),
            "healthy_checks": len([r for r in self.results if r.status == HealthStatus.HEALTHY]),
            "degraded_checks": len([r for r in self.results if r.status == HealthStatus.DEGRADED]),
            "unhealthy_checks": len([r for r in self.results if r.status == HealthStatus.UNHEALTHY]),
            "unknown_checks": len([r for r in self.results if r.status == HealthStatus.UNKNOWN]),
            "checks": [
                {
                    "name": result.name,
                    "status": result.status.value,
                    "response_time": result.response_time,
                    "error": result.error,
                    "details": result.details
                }
                for result in self.results
            ]
        }
        
        return report


async def main():
    """Main function for health checking."""
    # Define health checks for all services
    health_checks = [
        # API Gateway
        HealthCheck(
            name="api-gateway",
            url="http://api-gateway:8000/health",
            expected_status=200,
            expected_response={"status": "ok"},
            critical=True
        ),
        HealthCheck(
            name="api-gateway-ready",
            url="http://api-gateway:8000/health/ready",
            expected_status=200,
            critical=True
        ),
        
        # Router Service
        HealthCheck(
            name="router_service",
            url="http://router_service:8002/health",
            expected_status=200,
            expected_response={"status": "ok"},
            critical=True
        ),
        HealthCheck(
            name="router_service-ready",
            url="http://router_service:8002/health/ready",
            expected_status=200,
            critical=True
        ),
        
        # Orchestrator
        HealthCheck(
            name="orchestrator",
            url="http://orchestrator:8001/health",
            expected_status=200,
            expected_response={"status": "ok"},
            critical=True
        ),
        HealthCheck(
            name="orchestrator-ready",
            url="http://orchestrator:8001/health/ready",
            expected_status=200,
            critical=True
        ),
        
        # Realtime Service
        HealthCheck(
            name="realtime",
            url="http://realtime:8003/health",
            expected_status=200,
            expected_response={"status": "ok"},
            critical=True
        ),
        HealthCheck(
            name="realtime-ready",
            url="http://realtime:8003/health/ready",
            expected_status=200,
            critical=True
        ),
        
        # Analytics Service
        HealthCheck(
            name="analytics-service",
            url="http://analytics-service:8005/health",
            expected_status=200,
            expected_response={"status": "ok"},
            critical=False
        ),
        HealthCheck(
            name="analytics-service-ready",
            url="http://analytics-service:8005/health/ready",
            expected_status=200,
            critical=False
        ),
        
        # Billing Service
        HealthCheck(
            name="billing-service",
            url="http://billing-service:8004/health",
            expected_status=200,
            expected_response={"status": "ok"},
            critical=False
        ),
        HealthCheck(
            name="billing-service-ready",
            url="http://billing-service:8004/health/ready",
            expected_status=200,
            critical=False
        ),
        
        # Database
        HealthCheck(
            name="postgres",
            url="http://postgres:5432/health",
            expected_status=200,
            critical=True
        ),
        
        # Cache
        HealthCheck(
            name="redis",
            url="http://redis:6379/health",
            expected_status=200,
            critical=True
        ),
        
        # Messaging
        HealthCheck(
            name="nats",
            url="http://nats:8222/healthz",
            expected_status=200,
            critical=True
        ),
    ]
    
    async with EnhancedHealthChecker() as checker:
        # Add all health checks
        for health_check in health_checks:
            checker.add_health_check(health_check)
        
        # Run health checks
        results = await checker.run_all_health_checks()
        
        # Generate report
        report = checker.generate_report()
        
        # Print report
        print(json.dumps(report, indent=2))
        
        # Exit with appropriate code
        overall_status = checker.get_overall_status()
        if overall_status == HealthStatus.HEALTHY:
            sys.exit(0)
        elif overall_status == HealthStatus.DEGRADED:
            sys.exit(1)
        else:
            sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
