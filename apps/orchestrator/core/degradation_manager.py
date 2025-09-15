"""Degradation Manager for system overload protection and graceful degradation."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum
import asyncio
import time
import structlog
import psutil

logger = structlog.get_logger(__name__)


class SystemLoadLevel(Enum):
    """System load levels for degradation triggers."""
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


class DegradationMode(Enum):
    """Degradation modes for different load levels."""
    NONE = "none"
    LIGHT = "light"
    MODERATE = "moderate"
    HEAVY = "heavy"
    EMERGENCY = "emergency"


@dataclass
class SystemLoad:
    """System load metrics."""
    cpu_percent: float
    memory_percent: float
    active_connections: int
    queue_depth: int
    response_time_p95: float
    error_rate: float
    load_level: SystemLoadLevel
    timestamp: float


@dataclass
class DegradationConfig:
    """Configuration for degradation switches."""
    verbose_critique: bool = True
    debate_mode: bool = True
    context_size: str = "full"  # "full", "medium", "minimal"
    llm_tier: str = "premium"  # "premium", "standard", "basic"
    parallel_processing: bool = True
    caching_enabled: bool = True
    detailed_logging: bool = True


class DegradationManager:
    """Manages system degradation and overload protection."""
    
    def __init__(self):
        self.degrade_switches = DegradationConfig()
        self.load_history: List[SystemLoad] = []
        self.degradation_modes: Dict[SystemLoadLevel, DegradationConfig] = {
            SystemLoadLevel.NORMAL: DegradationConfig(),
            SystemLoadLevel.HIGH: DegradationConfig(
                verbose_critique=False,
                context_size="medium",
                detailed_logging=False
            ),
            SystemLoadLevel.CRITICAL: DegradationConfig(
                verbose_critique=False,
                debate_mode=False,
                context_size="minimal",
                llm_tier="standard",
                parallel_processing=False,
                detailed_logging=False
            ),
            SystemLoadLevel.EMERGENCY: DegradationConfig(
                verbose_critique=False,
                debate_mode=False,
                context_size="minimal",
                llm_tier="basic",
                parallel_processing=False,
                caching_enabled=False,
                detailed_logging=False
            )
        }
        self.monitoring_task: Optional[asyncio.Task] = None
        self._start_monitoring()
    
    def _start_monitoring(self):
        """Start system load monitoring."""
        self.monitoring_task = asyncio.create_task(self._monitor_system_load())
    
    async def check_system_load(self) -> SystemLoad:
        """Check current system load metrics."""
        try:
            # Get system metrics
            cpu_percent = psutil.cpu_percent(interval=0.1)
            memory = psutil.virtual_memory()
            memory_percent = memory.percent
            
            # Get application metrics (these would come from your metrics system)
            active_connections = await self._get_active_connections()
            queue_depth = await self._get_queue_depth()
            response_time_p95 = await self._get_response_time_p95()
            error_rate = await self._get_error_rate()
            
            # Determine load level
            load_level = self._determine_load_level(
                cpu_percent, memory_percent, active_connections, 
                queue_depth, response_time_p95, error_rate
            )
            
            system_load = SystemLoad(
                cpu_percent=cpu_percent,
                memory_percent=memory_percent,
                active_connections=active_connections,
                queue_depth=queue_depth,
                response_time_p95=response_time_p95,
                error_rate=error_rate,
                load_level=load_level,
                timestamp=time.time()
            )
            
            # Store in history
            self.load_history.append(system_load)
            
            # Keep only last 100 measurements
            if len(self.load_history) > 100:
                self.load_history = self.load_history[-100:]
            
            logger.info("System load checked",
                       cpu_percent=cpu_percent,
                       memory_percent=memory_percent,
                       load_level=load_level.value,
                       active_connections=active_connections,
                       queue_depth=queue_depth)
            
            return system_load
            
        except Exception as e:
            logger.error("Failed to check system load", error=str(e))
            # Return conservative load level
            return SystemLoad(
                cpu_percent=100.0,
                memory_percent=100.0,
                active_connections=0,
                queue_depth=0,
                response_time_p95=10.0,
                error_rate=1.0,
                load_level=SystemLoadLevel.CRITICAL,
                timestamp=time.time()
            )
    
    def _determine_load_level(self, cpu_percent: float, memory_percent: float,
                            active_connections: int, queue_depth: int,
                            response_time_p95: float, error_rate: float) -> SystemLoadLevel:
        """Determine system load level based on metrics."""
        try:
            # Emergency conditions
            if (cpu_percent > 95 or memory_percent > 95 or 
                response_time_p95 > 10.0 or error_rate > 0.1):
                return SystemLoadLevel.EMERGENCY
            
            # Critical conditions
            if (cpu_percent > 85 or memory_percent > 85 or 
                response_time_p95 > 5.0 or error_rate > 0.05):
                return SystemLoadLevel.CRITICAL
            
            # High load conditions
            if (cpu_percent > 70 or memory_percent > 70 or 
                response_time_p95 > 2.0 or error_rate > 0.01):
                return SystemLoadLevel.HIGH
            
            # Normal conditions
            return SystemLoadLevel.NORMAL
            
        except Exception as e:
            logger.error("Error determining load level", error=str(e))
            return SystemLoadLevel.CRITICAL
    
    async def apply_degradation(self, load_level: SystemLoadLevel):
        """Apply degradation based on system load level."""
        try:
            # Get degradation config for load level
            config = self.degradation_modes.get(load_level, self.degradation_modes[SystemLoadLevel.CRITICAL])
            
            # Apply degradation switches
            self.degrade_switches = config
            
            logger.info("Degradation applied",
                       load_level=load_level.value,
                       verbose_critique=config.verbose_critique,
                       debate_mode=config.debate_mode,
                       context_size=config.context_size,
                       llm_tier=config.llm_tier,
                       parallel_processing=config.parallel_processing,
                       caching_enabled=config.caching_enabled,
                       detailed_logging=config.detailed_logging)
            
            # Notify other services about degradation
            await self._notify_degradation_change(load_level, config)
            
        except Exception as e:
            logger.error("Failed to apply degradation", load_level=load_level.value, error=str(e))
    
    async def get_degradation_config(self) -> DegradationConfig:
        """Get current degradation configuration."""
        return self.degrade_switches
    
    async def _monitor_system_load(self):
        """Background task to monitor system load and apply degradation."""
        while True:
            try:
                await asyncio.sleep(5.0)  # Check every 5 seconds
                
                # Check current system load
                system_load = await self.check_system_load()
                
                # Apply degradation if needed
                await self.apply_degradation(system_load.load_level)
                
            except Exception as e:
                logger.error("Error in system load monitoring", error=str(e))
                await asyncio.sleep(10.0)  # Wait longer on error
    
    async def _get_active_connections(self) -> int:
        """Get number of active connections."""
        try:
            # This would typically come from your connection manager
            # For now, return a mock value
            return 100
        except Exception as e:
            logger.error("Failed to get active connections", error=str(e))
            return 0
    
    async def _get_queue_depth(self) -> int:
        """Get current queue depth."""
        try:
            # This would typically come from your queue system
            # For now, return a mock value
            return 50
        except Exception as e:
            logger.error("Failed to get queue depth", error=str(e))
            return 0
    
    async def _get_response_time_p95(self) -> float:
        """Get 95th percentile response time."""
        try:
            # This would typically come from your metrics system
            # For now, return a mock value
            return 0.5
        except Exception as e:
            logger.error("Failed to get response time p95", error=str(e))
            return 10.0
    
    async def _get_error_rate(self) -> float:
        """Get current error rate."""
        try:
            # This would typically come from your metrics system
            # For now, return a mock value
            return 0.01
        except Exception as e:
            logger.error("Failed to get error rate", error=str(e))
            return 1.0
    
    async def _notify_degradation_change(self, load_level: SystemLoadLevel, config: DegradationConfig):
        """Notify other services about degradation changes."""
        try:
            # This would typically send events to other services
            # For now, just log the change
            
            logger.info("Degradation change notification",
                       load_level=load_level.value,
                       config=config.__dict__)
            
        except Exception as e:
            logger.error("Failed to notify degradation change", error=str(e))
    
    async def get_system_health(self) -> Dict[str, Any]:
        """Get comprehensive system health information."""
        try:
            current_load = await self.check_system_load()
            
            # Calculate load trends
            if len(self.load_history) >= 10:
                recent_loads = self.load_history[-10:]
                avg_cpu = sum(l.cpu_percent for l in recent_loads) / len(recent_loads)
                avg_memory = sum(l.memory_percent for l in recent_loads) / len(recent_loads)
                avg_response_time = sum(l.response_time_p95 for l in recent_loads) / len(recent_loads)
            else:
                avg_cpu = current_load.cpu_percent
                avg_memory = current_load.memory_percent
                avg_response_time = current_load.response_time_p95
            
            health = {
                "current_load": {
                    "cpu_percent": current_load.cpu_percent,
                    "memory_percent": current_load.memory_percent,
                    "active_connections": current_load.active_connections,
                    "queue_depth": current_load.queue_depth,
                    "response_time_p95": current_load.response_time_p95,
                    "error_rate": current_load.error_rate,
                    "load_level": current_load.load_level.value,
                    "timestamp": current_load.timestamp
                },
                "trends": {
                    "avg_cpu_percent": avg_cpu,
                    "avg_memory_percent": avg_memory,
                    "avg_response_time_p95": avg_response_time
                },
                "degradation_config": {
                    "verbose_critique": self.degrade_switches.verbose_critique,
                    "debate_mode": self.degrade_switches.debate_mode,
                    "context_size": self.degrade_switches.context_size,
                    "llm_tier": self.degrade_switches.llm_tier,
                    "parallel_processing": self.degrade_switches.parallel_processing,
                    "caching_enabled": self.degrade_switches.caching_enabled,
                    "detailed_logging": self.degrade_switches.detailed_logging
                },
                "recommendations": self._get_recommendations(current_load)
            }
            
            return health
            
        except Exception as e:
            logger.error("Failed to get system health", error=str(e))
            return {}
    
    def _get_recommendations(self, system_load: SystemLoad) -> List[str]:
        """Get system recommendations based on current load."""
        recommendations = []
        
        if system_load.cpu_percent > 80:
            recommendations.append("Consider scaling horizontally or reducing workload")
        
        if system_load.memory_percent > 80:
            recommendations.append("Monitor memory usage and consider memory optimization")
        
        if system_load.response_time_p95 > 2.0:
            recommendations.append("Investigate slow response times and optimize queries")
        
        if system_load.error_rate > 0.05:
            recommendations.append("High error rate detected, investigate error sources")
        
        if system_load.queue_depth > 1000:
            recommendations.append("High queue depth, consider increasing processing capacity")
        
        return recommendations
    
    async def shutdown(self):
        """Shutdown the degradation manager gracefully."""
        try:
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Degradation manager shutdown complete")
            
        except Exception as e:
            logger.error("Error during degradation manager shutdown", error=str(e))
