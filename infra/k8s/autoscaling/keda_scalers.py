"""KEDA scalers for Kubernetes-native event-driven autoscaling."""

import asyncio
import time
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class ScalerType(Enum):
    """Scaler type."""
    NATS_QUEUE = "nats_queue"
    REDIS_QUEUE = "redis_queue"
    PROMETHEUS = "prometheus"
    CPU = "cpu"
    MEMORY = "memory"
    CUSTOM = "custom"


@dataclass
class ScalerConfig:
    """Scaler configuration."""
    name: str
    scaler_type: ScalerType
    min_replicas: int = 1
    max_replicas: int = 10
    target_value: float = 1.0
    scale_up_threshold: float = 0.8
    scale_down_threshold: float = 0.2
    scale_up_period: int = 60  # seconds
    scale_down_period: int = 300  # seconds
    cooldown_period: int = 300  # seconds


@dataclass
class ScalerMetrics:
    """Scaler metrics."""
    current_value: float
    target_value: float
    scale_decision: str
    last_scaled: float
    replicas: int


class KEDAScaler:
    """KEDA scaler for event-driven autoscaling."""
    
    def __init__(
        self,
        config: ScalerConfig,
        redis_client: redis.Redis
    ):
        self.config = config
        self.redis = redis_client
        self.metrics = ScalerMetrics(
            current_value=0.0,
            target_value=config.target_value,
            scale_decision="none",
            last_scaled=0.0,
            replicas=config.min_replicas
        )
    
    async def get_scale_decision(self) -> Dict[str, Any]:
        """Get scale decision based on current metrics."""
        try:
            # Get current metrics
            current_value = await self._get_current_metric_value()
            self.metrics.current_value = current_value
            
            # Determine scale decision
            scale_decision = await self._determine_scale_decision(current_value)
            self.metrics.scale_decision = scale_decision
            
            # Update last scaled time if scaling occurred
            if scale_decision != "none":
                self.metrics.last_scaled = time.time()
            
            return {
                'scaler_name': self.config.name,
                'scaler_type': self.config.scaler_type.value,
                'current_value': current_value,
                'target_value': self.config.target_value,
                'scale_decision': scale_decision,
                'current_replicas': self.metrics.replicas,
                'min_replicas': self.config.min_replicas,
                'max_replicas': self.config.max_replicas,
                'last_scaled': self.metrics.last_scaled
            }
            
        except Exception as e:
            logger.error("Failed to get scale decision", error=str(e), scaler=self.config.name)
            return {
                'scaler_name': self.config.name,
                'error': str(e),
                'scale_decision': 'none'
            }
    
    async def _get_current_metric_value(self) -> float:
        """Get current metric value based on scaler type."""
        try:
            if self.config.scaler_type == ScalerType.NATS_QUEUE:
                return await self._get_nats_queue_depth()
            elif self.config.scaler_type == ScalerType.REDIS_QUEUE:
                return await self._get_redis_queue_length()
            elif self.config.scaler_type == ScalerType.PROMETHEUS:
                return await self._get_prometheus_metric()
            elif self.config.scaler_type == ScalerType.CPU:
                return await self._get_cpu_usage()
            elif self.config.scaler_type == ScalerType.MEMORY:
                return await self._get_memory_usage()
            else:
                return 0.0
                
        except Exception as e:
            logger.error("Failed to get metric value", error=str(e), scaler=self.config.name)
            return 0.0
    
    async def _get_nats_queue_depth(self) -> float:
        """Get NATS queue depth."""
        try:
            # Mock NATS queue depth
            # In production, this would query NATS JetStream
            queue_depth = await self.redis.get(f"nats_queue_depth:{self.config.name}")
            if queue_depth:
                return float(queue_depth)
            
            # Return mock value
            return 5.0
            
        except Exception as e:
            logger.error("Failed to get NATS queue depth", error=str(e))
            return 0.0
    
    async def _get_redis_queue_length(self) -> float:
        """Get Redis queue length."""
        try:
            # Get Redis queue length
            queue_length = await self.redis.llen(f"queue:{self.config.name}")
            return float(queue_length)
            
        except Exception as e:
            logger.error("Failed to get Redis queue length", error=str(e))
            return 0.0
    
    async def _get_prometheus_metric(self) -> float:
        """Get Prometheus metric value."""
        try:
            # Mock Prometheus metric
            # In production, this would query Prometheus API
            metric_value = await self.redis.get(f"prometheus_metric:{self.config.name}")
            if metric_value:
                return float(metric_value)
            
            # Return mock value
            return 0.5
            
        except Exception as e:
            logger.error("Failed to get Prometheus metric", error=str(e))
            return 0.0
    
    async def _get_cpu_usage(self) -> float:
        """Get CPU usage percentage."""
        try:
            # Mock CPU usage
            # In production, this would query Kubernetes metrics API
            cpu_usage = await self.redis.get(f"cpu_usage:{self.config.name}")
            if cpu_usage:
                return float(cpu_usage)
            
            # Return mock value
            return 0.3
            
        except Exception as e:
            logger.error("Failed to get CPU usage", error=str(e))
            return 0.0
    
    async def _get_memory_usage(self) -> float:
        """Get memory usage percentage."""
        try:
            # Mock memory usage
            # In production, this would query Kubernetes metrics API
            memory_usage = await self.redis.get(f"memory_usage:{self.config.name}")
            if memory_usage:
                return float(memory_usage)
            
            # Return mock value
            return 0.4
            
        except Exception as e:
            logger.error("Failed to get memory usage", error=str(e))
            return 0.0
    
    async def _determine_scale_decision(self, current_value: float) -> str:
        """Determine scale decision based on current value."""
        try:
            # Check cooldown period
            if time.time() - self.metrics.last_scaled < self.config.cooldown_period:
                return "cooldown"
            
            # Check if we need to scale up
            if current_value > self.config.scale_up_threshold:
                if self.metrics.replicas < self.config.max_replicas:
                    return "scale_up"
                else:
                    return "max_replicas_reached"
            
            # Check if we need to scale down
            if current_value < self.config.scale_down_threshold:
                if self.metrics.replicas > self.config.min_replicas:
                    return "scale_down"
                else:
                    return "min_replicas_reached"
            
            return "none"
            
        except Exception as e:
            logger.error("Failed to determine scale decision", error=str(e))
            return "error"


class KEDAManager:
    """KEDA manager for managing multiple scalers."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.scalers = {}
        self.scaler_configs = self._initialize_scaler_configs()
    
    def _initialize_scaler_configs(self) -> List[ScalerConfig]:
        """Initialize scaler configurations for all services."""
        return [
            # Orchestrator - NATS queue depth
            ScalerConfig(
                name="orchestrator-nats",
                scaler_type=ScalerType.NATS_QUEUE,
                min_replicas=2,
                max_replicas=20,
                target_value=5.0,
                scale_up_threshold=10.0,
                scale_down_threshold=2.0
            ),
            
            # Ingestion - NATS queue depth
            ScalerConfig(
                name="ingestion-nats",
                scaler_type=ScalerType.NATS_QUEUE,
                min_replicas=1,
                max_replicas=15,
                target_value=3.0,
                scale_up_threshold=8.0,
                scale_down_threshold=1.0
            ),
            
            # Router Service - CPU usage
            ScalerConfig(
                name="router-service-cpu",
                scaler_type=ScalerType.CPU,
                min_replicas=2,
                max_replicas=10,
                target_value=0.7,
                scale_up_threshold=0.8,
                scale_down_threshold=0.3
            ),
            
            # Realtime Service - CPU usage
            ScalerConfig(
                name="realtime-cpu",
                scaler_type=ScalerType.CPU,
                min_replicas=2,
                max_replicas=15,
                target_value=0.6,
                scale_up_threshold=0.75,
                scale_down_threshold=0.25
            ),
            
            # Analytics Service - Memory usage
            ScalerConfig(
                name="analytics-service-memory",
                scaler_type=ScalerType.MEMORY,
                min_replicas=1,
                max_replicas=8,
                target_value=0.7,
                scale_up_threshold=0.8,
                scale_down_threshold=0.3
            ),
            
            # Billing Service - Redis queue length
            ScalerConfig(
                name="billing-service-redis",
                scaler_type=ScalerType.REDIS_QUEUE,
                min_replicas=1,
                max_replicas=5,
                target_value=10.0,
                scale_up_threshold=20.0,
                scale_down_threshold=5.0
            )
        ]
    
    async def initialize_scalers(self) -> None:
        """Initialize all scalers."""
        try:
            for config in self.scaler_configs:
                scaler = KEDAScaler(config, self.redis)
                self.scalers[config.name] = scaler
                logger.info("Scaler initialized", name=config.name, type=config.scaler_type.value)
            
            logger.info("All scalers initialized", count=len(self.scalers))
            
        except Exception as e:
            logger.error("Failed to initialize scalers", error=str(e))
    
    async def get_all_scale_decisions(self) -> List[Dict[str, Any]]:
        """Get scale decisions for all scalers."""
        try:
            decisions = []
            
            for scaler_name, scaler in self.scalers.items():
                decision = await scaler.get_scale_decision()
                decisions.append(decision)
            
            return decisions
            
        except Exception as e:
            logger.error("Failed to get scale decisions", error=str(e))
            return []
    
    async def get_scaler_metrics(self, scaler_name: str) -> Optional[Dict[str, Any]]:
        """Get metrics for specific scaler."""
        try:
            if scaler_name not in self.scalers:
                return None
            
            scaler = self.scalers[scaler_name]
            return await scaler.get_scale_decision()
            
        except Exception as e:
            logger.error("Failed to get scaler metrics", error=str(e), scaler=scaler_name)
            return None
    
    async def update_scaler_config(self, scaler_name: str, config_updates: Dict[str, Any]) -> bool:
        """Update scaler configuration."""
        try:
            if scaler_name not in self.scalers:
                return False
            
            scaler = self.scalers[scaler_name]
            
            # Update configuration
            for key, value in config_updates.items():
                if hasattr(scaler.config, key):
                    setattr(scaler.config, key, value)
            
            logger.info("Scaler configuration updated", scaler=scaler_name, updates=config_updates)
            return True
            
        except Exception as e:
            logger.error("Failed to update scaler config", error=str(e), scaler=scaler_name)
            return False
    
    async def get_autoscaling_summary(self) -> Dict[str, Any]:
        """Get autoscaling summary."""
        try:
            decisions = await self.get_all_scale_decisions()
            
            summary = {
                'total_scalers': len(self.scalers),
                'scale_decisions': {
                    'scale_up': 0,
                    'scale_down': 0,
                    'none': 0,
                    'cooldown': 0,
                    'error': 0
                },
                'scalers': decisions
            }
            
            # Count scale decisions
            for decision in decisions:
                scale_decision = decision.get('scale_decision', 'none')
                if scale_decision in summary['scale_decisions']:
                    summary['scale_decisions'][scale_decision] += 1
            
            return summary
            
        except Exception as e:
            logger.error("Failed to get autoscaling summary", error=str(e))
            return {'error': str(e)}