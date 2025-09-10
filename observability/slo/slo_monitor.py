"""SLO monitoring and alerting system."""

import asyncio
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import structlog
import redis.asyncio as redis
from dataclasses import dataclass
from enum import Enum

logger = structlog.get_logger(__name__)


class SLOStatus(Enum):
    """SLO status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    BREACHED = "breached"


@dataclass
class SLOTarget:
    """SLO target definition."""
    name: str
    description: str
    target_percentage: float  # e.g., 99.9 for 99.9%
    measurement_window: int  # seconds
    alert_threshold: float  # percentage below target to alert
    critical_threshold: float  # percentage below target for critical alert


@dataclass
class SLOMeasurement:
    """SLO measurement result."""
    name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    success_rate: float
    target_percentage: float
    status: SLOStatus
    measurement_window: int
    timestamp: float


class SLOMonitor:
    """SLO monitoring and alerting system."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.slo_targets = {}
        self.measurements = {}
        self.alert_handlers = []
    
    def add_slo_target(self, target: SLOTarget) -> None:
        """Add SLO target for monitoring."""
        self.slo_targets[target.name] = target
        logger.info("SLO target added", name=target.name, target=target.target_percentage)
    
    def add_alert_handler(self, handler: callable) -> None:
        """Add alert handler for SLO breaches."""
        self.alert_handlers.append(handler)
    
    async def record_request(
        self,
        slo_name: str,
        tenant_id: str,
        success: bool,
        latency: float = 0.0,
        error_type: Optional[str] = None
    ) -> None:
        """Record a request for SLO measurement."""
        try:
            timestamp = int(time.time())
            window_start = timestamp - (timestamp % 60)  # 1-minute windows
            
            # Record request
            request_key = f"slo_requests:{slo_name}:{tenant_id}:{window_start}"
            await self.redis.hincrby(request_key, 'total', 1)
            
            if success:
                await self.redis.hincrby(request_key, 'successful', 1)
            else:
                await self.redis.hincrby(request_key, 'failed', 1)
                if error_type:
                    await self.redis.hincrby(request_key, f'error_{error_type}', 1)
            
            # Record latency
            if latency > 0:
                await self.redis.lpush(f"slo_latency:{slo_name}:{tenant_id}:{window_start}", latency)
                await self.redis.ltrim(f"slo_latency:{slo_name}:{tenant_id}:{window_start}", 0, 999)  # Keep last 1000
            
            # Set TTL
            await self.redis.expire(request_key, 86400)  # 24 hours
            await self.redis.expire(f"slo_latency:{slo_name}:{tenant_id}:{window_start}", 86400)
            
        except Exception as e:
            logger.error("Failed to record SLO request", error=str(e), slo_name=slo_name)
    
    async def measure_slo(
        self,
        slo_name: str,
        tenant_id: str,
        measurement_window: Optional[int] = None
    ) -> Optional[SLOMeasurement]:
        """Measure SLO for a specific target."""
        try:
            if slo_name not in self.slo_targets:
                logger.warning("SLO target not found", slo_name=slo_name)
                return None
            
            target = self.slo_targets[slo_name]
            window = measurement_window or target.measurement_window
            
            # Calculate measurement window
            end_time = int(time.time())
            start_time = end_time - window
            
            # Get all windows in measurement period
            windows = []
            current_time = start_time - (start_time % 60)  # Align to minute boundaries
            while current_time <= end_time:
                windows.append(current_time)
                current_time += 60
            
            # Aggregate data from all windows
            total_requests = 0
            successful_requests = 0
            failed_requests = 0
            
            for window_start in windows:
                request_key = f"slo_requests:{slo_name}:{tenant_id}:{window_start}"
                window_data = await self.redis.hgetall(request_key)
                
                if window_data:
                    total_requests += int(window_data.get('total', 0))
                    successful_requests += int(window_data.get('successful', 0))
                    failed_requests += int(window_data.get('failed', 0))
            
            # Calculate success rate
            success_rate = (successful_requests / total_requests * 100) if total_requests > 0 else 100.0
            
            # Determine status
            status = self._determine_slo_status(success_rate, target)
            
            # Create measurement
            measurement = SLOMeasurement(
                name=slo_name,
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                success_rate=success_rate,
                target_percentage=target.target_percentage,
                status=status,
                measurement_window=window,
                timestamp=time.time()
            )
            
            # Store measurement
            measurement_key = f"slo_measurement:{slo_name}:{tenant_id}:{int(time.time())}"
            await self.redis.setex(
                measurement_key,
                86400,  # 24 hours
                self._serialize_measurement(measurement)
            )
            
            # Check for alerts
            await self._check_slo_alerts(measurement, tenant_id)
            
            return measurement
            
        except Exception as e:
            logger.error("Failed to measure SLO", error=str(e), slo_name=slo_name)
            return None
    
    def _determine_slo_status(self, success_rate: float, target: SLOTarget) -> SLOStatus:
        """Determine SLO status based on success rate."""
        if success_rate >= target.target_percentage:
            return SLOStatus.HEALTHY
        elif success_rate >= target.target_percentage - target.alert_threshold:
            return SLOStatus.WARNING
        elif success_rate >= target.target_percentage - target.critical_threshold:
            return SLOStatus.CRITICAL
        else:
            return SLOStatus.BREACHED
    
    async def _check_slo_alerts(self, measurement: SLOMeasurement, tenant_id: str) -> None:
        """Check for SLO alerts and trigger handlers."""
        try:
            if measurement.status in [SLOStatus.WARNING, SLOStatus.CRITICAL, SLOStatus.BREACHED]:
                # Check if we've already alerted recently
                alert_key = f"slo_alert:{measurement.name}:{tenant_id}"
                last_alert = await self.redis.get(alert_key)
                
                if last_alert:
                    last_alert_time = float(last_alert)
                    if time.time() - last_alert_time < 300:  # 5 minutes cooldown
                        return
                
                # Trigger alert handlers
                for handler in self.alert_handlers:
                    try:
                        await handler(measurement, tenant_id)
                    except Exception as e:
                        logger.error("Alert handler failed", error=str(e))
                
                # Record alert time
                await self.redis.setex(alert_key, 300, str(time.time()))
                
                logger.warning(
                    "SLO alert triggered",
                    slo_name=measurement.name,
                    tenant_id=tenant_id,
                    status=measurement.status.value,
                    success_rate=measurement.success_rate,
                    target=measurement.target_percentage
                )
                
        except Exception as e:
            logger.error("Failed to check SLO alerts", error=str(e))
    
    async def get_slo_measurements(
        self,
        slo_name: str,
        tenant_id: str,
        hours: int = 24
    ) -> List[SLOMeasurement]:
        """Get SLO measurements for a time period."""
        try:
            end_time = int(time.time())
            start_time = end_time - (hours * 3600)
            
            measurements = []
            
            # Get measurement keys
            pattern = f"slo_measurement:{slo_name}:{tenant_id}:*"
            keys = await self.redis.keys(pattern)
            
            for key in keys:
                try:
                    # Extract timestamp from key
                    timestamp_str = key.decode().split(':')[-1]
                    timestamp = int(timestamp_str)
                    
                    if start_time <= timestamp <= end_time:
                        measurement_data = await self.redis.get(key)
                        if measurement_data:
                            measurement = self._deserialize_measurement(measurement_data)
                            measurements.append(measurement)
                except Exception as e:
                    logger.error("Failed to parse measurement key", error=str(e), key=key)
            
            # Sort by timestamp
            measurements.sort(key=lambda x: x.timestamp)
            
            return measurements
            
        except Exception as e:
            logger.error("Failed to get SLO measurements", error=str(e))
            return []
    
    async def get_slo_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get SLO summary for a tenant."""
        try:
            summary = {
                'tenant_id': tenant_id,
                'slo_targets': {},
                'overall_status': SLOStatus.HEALTHY,
                'timestamp': time.time()
            }
            
            for slo_name, target in self.slo_targets.items():
                measurement = await self.measure_slo(slo_name, tenant_id)
                
                if measurement:
                    summary['slo_targets'][slo_name] = {
                        'name': measurement.name,
                        'success_rate': measurement.success_rate,
                        'target_percentage': measurement.target_percentage,
                        'status': measurement.status.value,
                        'total_requests': measurement.total_requests,
                        'successful_requests': measurement.successful_requests,
                        'failed_requests': measurement.failed_requests
                    }
                    
                    # Update overall status
                    if measurement.status == SLOStatus.BREACHED:
                        summary['overall_status'] = SLOStatus.BREACHED
                    elif measurement.status == SLOStatus.CRITICAL and summary['overall_status'] != SLOStatus.BREACHED:
                        summary['overall_status'] = SLOStatus.CRITICAL
                    elif measurement.status == SLOStatus.WARNING and summary['overall_status'] == SLOStatus.HEALTHY:
                        summary['overall_status'] = SLOStatus.WARNING
            
            return summary
            
        except Exception as e:
            logger.error("Failed to get SLO summary", error=str(e))
            return {'tenant_id': tenant_id, 'error': str(e)}
    
    async def get_slo_trends(
        self,
        slo_name: str,
        tenant_id: str,
        hours: int = 24
    ) -> Dict[str, Any]:
        """Get SLO trends over time."""
        try:
            measurements = await self.get_slo_measurements(slo_name, tenant_id, hours)
            
            if not measurements:
                return {'slo_name': slo_name, 'tenant_id': tenant_id, 'trends': []}
            
            # Calculate trends
            trends = []
            for measurement in measurements:
                trends.append({
                    'timestamp': measurement.timestamp,
                    'success_rate': measurement.success_rate,
                    'status': measurement.status.value,
                    'total_requests': measurement.total_requests
                })
            
            # Calculate summary statistics
            success_rates = [m.success_rate for m in measurements]
            avg_success_rate = sum(success_rates) / len(success_rates) if success_rates else 0
            min_success_rate = min(success_rates) if success_rates else 0
            max_success_rate = max(success_rates) if success_rates else 0
            
            return {
                'slo_name': slo_name,
                'tenant_id': tenant_id,
                'trends': trends,
                'summary': {
                    'avg_success_rate': avg_success_rate,
                    'min_success_rate': min_success_rate,
                    'max_success_rate': max_success_rate,
                    'measurement_count': len(measurements)
                }
            }
            
        except Exception as e:
            logger.error("Failed to get SLO trends", error=str(e))
            return {'slo_name': slo_name, 'tenant_id': tenant_id, 'error': str(e)}
    
    def _serialize_measurement(self, measurement: SLOMeasurement) -> str:
        """Serialize SLO measurement to string."""
        import json
        return json.dumps({
            'name': measurement.name,
            'total_requests': measurement.total_requests,
            'successful_requests': measurement.successful_requests,
            'failed_requests': measurement.failed_requests,
            'success_rate': measurement.success_rate,
            'target_percentage': measurement.target_percentage,
            'status': measurement.status.value,
            'measurement_window': measurement.measurement_window,
            'timestamp': measurement.timestamp
        })
    
    def _deserialize_measurement(self, data: str) -> SLOMeasurement:
        """Deserialize SLO measurement from string."""
        import json
        data_dict = json.loads(data)
        return SLOMeasurement(
            name=data_dict['name'],
            total_requests=data_dict['total_requests'],
            successful_requests=data_dict['successful_requests'],
            failed_requests=data_dict['failed_requests'],
            success_rate=data_dict['success_rate'],
            target_percentage=data_dict['target_percentage'],
            status=SLOStatus(data_dict['status']),
            measurement_window=data_dict['measurement_window'],
            timestamp=data_dict['timestamp']
        )
    
    async def cleanup_old_data(self, days: int = 7) -> None:
        """Clean up old SLO data."""
        try:
            cutoff_time = int(time.time()) - (days * 86400)
            
            # Clean up old measurements
            pattern = "slo_measurement:*"
            keys = await self.redis.keys(pattern)
            
            deleted_count = 0
            for key in keys:
                try:
                    # Extract timestamp from key
                    timestamp_str = key.decode().split(':')[-1]
                    timestamp = int(timestamp_str)
                    
                    if timestamp < cutoff_time:
                        await self.redis.delete(key)
                        deleted_count += 1
                except Exception as e:
                    logger.error("Failed to parse key for cleanup", error=str(e), key=key)
            
            logger.info("SLO data cleanup completed", deleted_count=deleted_count, days=days)
            
        except Exception as e:
            logger.error("Failed to cleanup SLO data", error=str(e))
