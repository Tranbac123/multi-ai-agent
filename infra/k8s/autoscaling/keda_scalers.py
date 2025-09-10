"""KEDA scalers for Kubernetes autoscaling."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class ScalerType(Enum):
    """KEDA scaler types."""
    REDIS = "redis"
    NATS = "nats"
    PROMETHEUS = "prometheus"
    CPU = "cpu"
    MEMORY = "memory"
    CUSTOM = "custom"


@dataclass
class ScalerConfig:
    """KEDA scaler configuration."""
    name: str
    scaler_type: ScalerType
    min_replicas: int = 1
    max_replicas: int = 10
    target_value: float = 1.0
    cooldown_period: int = 300  # 5 minutes
    scale_up_period: int = 60   # 1 minute
    scale_down_period: int = 300  # 5 minutes
    metadata: Dict[str, Any] = None


class KEDAScaler:
    """KEDA scaler for Kubernetes autoscaling."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.scalers = {}
        self.metrics_cache = {}
        self.cache_ttl = 30  # 30 seconds
    
    def add_scaler(self, config: ScalerConfig) -> None:
        """Add a KEDA scaler configuration."""
        self.scalers[config.name] = config
        logger.info("KEDA scaler added", name=config.name, type=config.scaler_type.value)
    
    async def get_metric_value(self, scaler_name: str) -> float:
        """Get current metric value for scaler."""
        try:
            if scaler_name not in self.scalers:
                logger.warning("Scaler not found", name=scaler_name)
                return 0.0
            
            config = self.scalers[scaler_name]
            
            # Check cache first
            cache_key = f"scaler_metric:{scaler_name}"
            cached_value = await self.redis.get(cache_key)
            if cached_value:
                return float(cached_value)
            
            # Get metric value based on scaler type
            if config.scaler_type == ScalerType.REDIS:
                value = await self._get_redis_metric(config)
            elif config.scaler_type == ScalerType.NATS:
                value = await self._get_nats_metric(config)
            elif config.scaler_type == ScalerType.PROMETHEUS:
                value = await self._get_prometheus_metric(config)
            elif config.scaler_type == ScalerType.CPU:
                value = await self._get_cpu_metric(config)
            elif config.scaler_type == ScalerType.MEMORY:
                value = await self._get_memory_metric(config)
            else:
                value = 0.0
            
            # Cache the value
            await self.redis.setex(cache_key, self.cache_ttl, str(value))
            
            return value
            
        except Exception as e:
            logger.error("Failed to get metric value", error=str(e), scaler_name=scaler_name)
            return 0.0
    
    async def _get_redis_metric(self, config: ScalerConfig) -> float:
        """Get Redis-based metric value."""
        try:
            metadata = config.metadata or {}
            list_name = metadata.get('listName', 'queue')
            address = metadata.get('address', 'localhost:6379')
            password = metadata.get('password', '')
            database = int(metadata.get('database', 0))
            
            # Get list length
            list_length = await self.redis.llen(list_name)
            
            # Get list memory usage
            memory_usage = await self.redis.memory_usage(list_name)
            
            # Calculate metric value
            if metadata.get('metricType') == 'listLength':
                return float(list_length)
            elif metadata.get('metricType') == 'memoryUsage':
                return float(memory_usage) / (1024 * 1024)  # Convert to MB
            else:
                return float(list_length)
                
        except Exception as e:
            logger.error("Failed to get Redis metric", error=str(e))
            return 0.0
    
    async def _get_nats_metric(self, config: ScalerConfig) -> float:
        """Get NATS-based metric value."""
        try:
            metadata = config.metadata or {}
            server_endpoint = metadata.get('serverEndpoint', 'nats://localhost:4222')
            subject = metadata.get('subject', 'events.*')
            queue_group = metadata.get('queueGroup', '')
            
            # This would typically connect to NATS and get consumer info
            # For now, we'll simulate it
            logger.info("Getting NATS metric", subject=subject, queue_group=queue_group)
            
            # Simulate getting consumer lag
            consumer_lag = await self._simulate_nats_consumer_lag(subject, queue_group)
            
            return float(consumer_lag)
            
        except Exception as e:
            logger.error("Failed to get NATS metric", error=str(e))
            return 0.0
    
    async def _get_prometheus_metric(self, config: ScalerConfig) -> float:
        """Get Prometheus-based metric value."""
        try:
            metadata = config.metadata or {}
            server_address = metadata.get('serverAddress', 'http://localhost:9090')
            metric_name = metadata.get('metricName', '')
            threshold = float(metadata.get('threshold', 1.0))
            
            # This would typically query Prometheus API
            # For now, we'll simulate it
            logger.info("Getting Prometheus metric", metric_name=metric_name)
            
            # Simulate getting metric value
            metric_value = await self._simulate_prometheus_query(metric_name)
            
            return metric_value
            
        except Exception as e:
            logger.error("Failed to get Prometheus metric", error=str(e))
            return 0.0
    
    async def _get_cpu_metric(self, config: ScalerConfig) -> float:
        """Get CPU-based metric value."""
        try:
            metadata = config.metadata or {}
            target_deployment = metadata.get('targetDeployment', '')
            namespace = metadata.get('namespace', 'default')
            
            # This would typically query Kubernetes metrics API
            # For now, we'll simulate it
            logger.info("Getting CPU metric", deployment=target_deployment, namespace=namespace)
            
            # Simulate getting CPU usage
            cpu_usage = await self._simulate_cpu_usage(target_deployment, namespace)
            
            return cpu_usage
            
        except Exception as e:
            logger.error("Failed to get CPU metric", error=str(e))
            return 0.0
    
    async def _get_memory_metric(self, config: ScalerConfig) -> float:
        """Get memory-based metric value."""
        try:
            metadata = config.metadata or {}
            target_deployment = metadata.get('targetDeployment', '')
            namespace = metadata.get('namespace', 'default')
            
            # This would typically query Kubernetes metrics API
            # For now, we'll simulate it
            logger.info("Getting memory metric", deployment=target_deployment, namespace=namespace)
            
            # Simulate getting memory usage
            memory_usage = await self._simulate_memory_usage(target_deployment, namespace)
            
            return memory_usage
            
        except Exception as e:
            logger.error("Failed to get memory metric", error=str(e))
            return 0.0
    
    async def _simulate_nats_consumer_lag(self, subject: str, queue_group: str) -> int:
        """Simulate NATS consumer lag."""
        # This would typically connect to NATS and get consumer info
        # For now, we'll return a simulated value
        await asyncio.sleep(0.1)  # Simulate network delay
        return 50  # Simulated consumer lag
    
    async def _simulate_prometheus_query(self, metric_name: str) -> float:
        """Simulate Prometheus query."""
        # This would typically query Prometheus API
        # For now, we'll return a simulated value
        await asyncio.sleep(0.1)  # Simulate network delay
        return 0.75  # Simulated metric value
    
    async def _simulate_cpu_usage(self, deployment: str, namespace: str) -> float:
        """Simulate CPU usage."""
        # This would typically query Kubernetes metrics API
        # For now, we'll return a simulated value
        await asyncio.sleep(0.1)  # Simulate network delay
        return 0.65  # Simulated CPU usage (65%)
    
    async def _simulate_memory_usage(self, deployment: str, namespace: str) -> float:
        """Simulate memory usage."""
        # This would typically query Kubernetes metrics API
        # For now, we'll return a simulated value
        await asyncio.sleep(0.1)  # Simulate network delay
        return 0.45  # Simulated memory usage (45%)
    
    async def calculate_desired_replicas(self, scaler_name: str) -> int:
        """Calculate desired number of replicas based on metric value."""
        try:
            if scaler_name not in self.scalers:
                return 1
            
            config = self.scalers[scaler_name]
            metric_value = await self.get_metric_value(scaler_name)
            
            # Calculate desired replicas
            desired_replicas = int(metric_value / config.target_value)
            
            # Apply min/max constraints
            desired_replicas = max(desired_replicas, config.min_replicas)
            desired_replicas = min(desired_replicas, config.max_replicas)
            
            logger.info(
                "Calculated desired replicas",
                scaler_name=scaler_name,
                metric_value=metric_value,
                target_value=config.target_value,
                desired_replicas=desired_replicas
            )
            
            return desired_replicas
            
        except Exception as e:
            logger.error("Failed to calculate desired replicas", error=str(e))
            return 1
    
    async def get_scaler_status(self, scaler_name: str) -> Dict[str, Any]:
        """Get scaler status and metrics."""
        try:
            if scaler_name not in self.scalers:
                return {'error': 'Scaler not found'}
            
            config = self.scalers[scaler_name]
            metric_value = await self.get_metric_value(scaler_name)
            desired_replicas = await self.calculate_desired_replicas(scaler_name)
            
            return {
                'name': scaler_name,
                'type': config.scaler_type.value,
                'min_replicas': config.min_replicas,
                'max_replicas': config.max_replicas,
                'target_value': config.target_value,
                'current_metric_value': metric_value,
                'desired_replicas': desired_replicas,
                'cooldown_period': config.cooldown_period,
                'scale_up_period': config.scale_up_period,
                'scale_down_period': config.scale_down_period,
                'metadata': config.metadata or {}
            }
            
        except Exception as e:
            logger.error("Failed to get scaler status", error=str(e))
            return {'error': str(e)}
    
    async def get_all_scalers_status(self) -> Dict[str, Any]:
        """Get status of all scalers."""
        try:
            status = {}
            
            for scaler_name in self.scalers:
                status[scaler_name] = await self.get_scaler_status(scaler_name)
            
            return status
            
        except Exception as e:
            logger.error("Failed to get all scalers status", error=str(e))
            return {}
    
    async def update_scaler_config(self, scaler_name: str, updates: Dict[str, Any]) -> bool:
        """Update scaler configuration."""
        try:
            if scaler_name not in self.scalers:
                return False
            
            config = self.scalers[scaler_name]
            
            # Update configuration
            if 'min_replicas' in updates:
                config.min_replicas = updates['min_replicas']
            if 'max_replicas' in updates:
                config.max_replicas = updates['max_replicas']
            if 'target_value' in updates:
                config.target_value = updates['target_value']
            if 'cooldown_period' in updates:
                config.cooldown_period = updates['cooldown_period']
            if 'scale_up_period' in updates:
                config.scale_up_period = updates['scale_up_period']
            if 'scale_down_period' in updates:
                config.scale_down_period = updates['scale_down_period']
            if 'metadata' in updates:
                config.metadata = updates['metadata']
            
            logger.info("Scaler configuration updated", scaler_name=scaler_name, updates=updates)
            return True
            
        except Exception as e:
            logger.error("Failed to update scaler config", error=str(e))
            return False
    
    async def remove_scaler(self, scaler_name: str) -> bool:
        """Remove scaler configuration."""
        try:
            if scaler_name in self.scalers:
                del self.scalers[scaler_name]
                logger.info("Scaler removed", name=scaler_name)
                return True
            return False
            
        except Exception as e:
            logger.error("Failed to remove scaler", error=str(e))
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """Perform health check on all scalers."""
        try:
            health_status = {
                'status': 'healthy',
                'scalers': {},
                'timestamp': time.time()
            }
            
            for scaler_name in self.scalers:
                try:
                    metric_value = await self.get_metric_value(scaler_name)
                    health_status['scalers'][scaler_name] = {
                        'status': 'healthy',
                        'metric_value': metric_value
                    }
                except Exception as e:
                    health_status['scalers'][scaler_name] = {
                        'status': 'unhealthy',
                        'error': str(e)
                    }
                    health_status['status'] = 'unhealthy'
            
            return health_status
            
        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {'status': 'unhealthy', 'error': str(e)}
