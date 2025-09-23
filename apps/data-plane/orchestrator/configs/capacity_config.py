"""Capacity configuration management for peak traffic handling."""

import os
import json
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import structlog

logger = structlog.get_logger(__name__)


class Environment(Enum):
    """Deployment environment."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"


class DegradeMode(Enum):
    """Degrade mode for overload handling."""
    NORMAL = "normal"
    DEGRADED = "degraded"
    EMERGENCY = "emergency"


@dataclass
class PoolConfig:
    """Connection pool configuration."""
    min_size: int = 5
    max_size: int = 20
    timeout: float = 30.0
    retry_attempts: int = 3
    retry_delay: float = 1.0


@dataclass
class ConcurrencyConfig:
    """Concurrency configuration."""
    max_concurrent_requests: int = 100
    max_concurrent_tasks: int = 50
    max_concurrent_connections: int = 1000
    request_timeout: float = 30.0
    task_timeout: float = 60.0


@dataclass
class TimeoutConfig:
    """Timeout configuration."""
    api_timeout: float = 30.0
    database_timeout: float = 10.0
    redis_timeout: float = 5.0
    nats_timeout: float = 5.0
    external_api_timeout: float = 15.0


@dataclass
class BackoffConfig:
    """Backoff configuration for retries."""
    initial_delay: float = 1.0
    max_delay: float = 60.0
    multiplier: float = 2.0
    jitter: bool = True
    max_attempts: int = 3


@dataclass
class DegradeConfig:
    """Degrade configuration for overload handling."""
    disable_verbose_critique: bool = False
    disable_debate: bool = False
    shrink_context: bool = False
    prefer_slm_tiers: bool = False
    reduce_logging: bool = False
    skip_non_essential_features: bool = False


@dataclass
class CapacityConfig:
    """Main capacity configuration."""
    environment: Environment
    pool_config: PoolConfig
    concurrency_config: ConcurrencyConfig
    timeout_config: TimeoutConfig
    backoff_config: BackoffConfig
    degrade_config: DegradeConfig
    degrade_mode: DegradeMode = DegradeMode.NORMAL
    enable_metrics: bool = True
    enable_tracing: bool = True
    enable_profiling: bool = False


class CapacityConfigManager:
    """Manages capacity configuration across environments."""
    
    def __init__(self, config_dir: str = "configs"):
        self.config_dir = Path(config_dir)
        self.configs: Dict[Environment, CapacityConfig] = {}
        self.current_environment = self._detect_environment()
        self._load_configurations()
    
    def _detect_environment(self) -> Environment:
        """Detect current environment."""
        env = os.getenv("ENVIRONMENT", "development").lower()
        try:
            return Environment(env)
        except ValueError:
            logger.warning(f"Unknown environment: {env}, defaulting to development")
            return Environment.DEVELOPMENT
    
    def _load_configurations(self) -> None:
        """Load configurations for all environments."""
        # Development configuration
        self.configs[Environment.DEVELOPMENT] = CapacityConfig(
            environment=Environment.DEVELOPMENT,
            pool_config=PoolConfig(
                min_size=2,
                max_size=10,
                timeout=15.0,
                retry_attempts=2,
                retry_delay=0.5
            ),
            concurrency_config=ConcurrencyConfig(
                max_concurrent_requests=20,
                max_concurrent_tasks=10,
                max_concurrent_connections=100,
                request_timeout=15.0,
                task_timeout=30.0
            ),
            timeout_config=TimeoutConfig(
                api_timeout=15.0,
                database_timeout=5.0,
                redis_timeout=2.0,
                nats_timeout=2.0,
                external_api_timeout=10.0
            ),
            backoff_config=BackoffConfig(
                initial_delay=0.5,
                max_delay=10.0,
                multiplier=1.5,
                jitter=True,
                max_attempts=2
            ),
            degrade_config=DegradeConfig(
                disable_verbose_critique=False,
                disable_debate=False,
                shrink_context=False,
                prefer_slm_tiers=False,
                reduce_logging=False,
                skip_non_essential_features=False
            ),
            enable_metrics=True,
            enable_tracing=True,
            enable_profiling=True
        )
        
        # Staging configuration
        self.configs[Environment.STAGING] = CapacityConfig(
            environment=Environment.STAGING,
            pool_config=PoolConfig(
                min_size=5,
                max_size=50,
                timeout=30.0,
                retry_attempts=3,
                retry_delay=1.0
            ),
            concurrency_config=ConcurrencyConfig(
                max_concurrent_requests=100,
                max_concurrent_tasks=50,
                max_concurrent_connections=500,
                request_timeout=30.0,
                task_timeout=60.0
            ),
            timeout_config=TimeoutConfig(
                api_timeout=30.0,
                database_timeout=10.0,
                redis_timeout=5.0,
                nats_timeout=5.0,
                external_api_timeout=15.0
            ),
            backoff_config=BackoffConfig(
                initial_delay=1.0,
                max_delay=30.0,
                multiplier=2.0,
                jitter=True,
                max_attempts=3
            ),
            degrade_config=DegradeConfig(
                disable_verbose_critique=False,
                disable_debate=False,
                shrink_context=False,
                prefer_slm_tiers=False,
                reduce_logging=False,
                skip_non_essential_features=False
            ),
            enable_metrics=True,
            enable_tracing=True,
            enable_profiling=False
        )
        
        # Production configuration
        self.configs[Environment.PRODUCTION] = CapacityConfig(
            environment=Environment.PRODUCTION,
            pool_config=PoolConfig(
                min_size=10,
                max_size=100,
                timeout=60.0,
                retry_attempts=5,
                retry_delay=2.0
            ),
            concurrency_config=ConcurrencyConfig(
                max_concurrent_requests=500,
                max_concurrent_tasks=200,
                max_concurrent_connections=2000,
                request_timeout=60.0,
                task_timeout=120.0
            ),
            timeout_config=TimeoutConfig(
                api_timeout=60.0,
                database_timeout=15.0,
                redis_timeout=10.0,
                nats_timeout=10.0,
                external_api_timeout=30.0
            ),
            backoff_config=BackoffConfig(
                initial_delay=2.0,
                max_delay=120.0,
                multiplier=2.0,
                jitter=True,
                max_attempts=5
            ),
            degrade_config=DegradeConfig(
                disable_verbose_critique=False,
                disable_debate=False,
                shrink_context=False,
                prefer_slm_tiers=False,
                reduce_logging=False,
                skip_non_essential_features=False
            ),
            enable_metrics=True,
            enable_tracing=True,
            enable_profiling=False
        )
    
    def get_config(self, environment: Optional[Environment] = None) -> CapacityConfig:
        """Get configuration for environment."""
        env = environment or self.current_environment
        return self.configs[env]
    
    def get_degraded_config(self, environment: Optional[Environment] = None) -> CapacityConfig:
        """Get degraded configuration for overload handling."""
        config = self.get_config(environment)
        
        # Create degraded version
        degraded_config = CapacityConfig(
            environment=config.environment,
            pool_config=PoolConfig(
                min_size=max(1, config.pool_config.min_size // 2),
                max_size=max(5, config.pool_config.max_size // 2),
                timeout=config.pool_config.timeout * 2,
                retry_attempts=max(1, config.pool_config.retry_attempts - 1),
                retry_delay=config.pool_config.retry_delay * 2
            ),
            concurrency_config=ConcurrencyConfig(
                max_concurrent_requests=max(10, config.concurrency_config.max_concurrent_requests // 2),
                max_concurrent_tasks=max(5, config.concurrency_config.max_concurrent_tasks // 2),
                max_concurrent_connections=max(50, config.concurrency_config.max_concurrent_connections // 2),
                request_timeout=config.concurrency_config.request_timeout * 2,
                task_timeout=config.concurrency_config.task_timeout * 2
            ),
            timeout_config=TimeoutConfig(
                api_timeout=config.timeout_config.api_timeout * 2,
                database_timeout=config.timeout_config.database_timeout * 2,
                redis_timeout=config.timeout_config.redis_timeout * 2,
                nats_timeout=config.timeout_config.nats_timeout * 2,
                external_api_timeout=config.timeout_config.external_api_timeout * 2
            ),
            backoff_config=BackoffConfig(
                initial_delay=config.backoff_config.initial_delay * 2,
                max_delay=config.backoff_config.max_delay * 2,
                multiplier=config.backoff_config.multiplier,
                jitter=config.backoff_config.jitter,
                max_attempts=max(1, config.backoff_config.max_attempts - 1)
            ),
            degrade_config=DegradeConfig(
                disable_verbose_critique=True,
                disable_debate=True,
                shrink_context=True,
                prefer_slm_tiers=True,
                reduce_logging=True,
                skip_non_essential_features=True
            ),
            degrade_mode=DegradeMode.DEGRADED,
            enable_metrics=config.enable_metrics,
            enable_tracing=config.enable_tracing,
            enable_profiling=False
        )
        
        return degraded_config
    
    def get_emergency_config(self, environment: Optional[Environment] = None) -> CapacityConfig:
        """Get emergency configuration for critical overload."""
        config = self.get_config(environment)
        
        # Create emergency version
        emergency_config = CapacityConfig(
            environment=config.environment,
            pool_config=PoolConfig(
                min_size=1,
                max_size=5,
                timeout=config.pool_config.timeout * 4,
                retry_attempts=1,
                retry_delay=config.pool_config.retry_delay * 4
            ),
            concurrency_config=ConcurrencyConfig(
                max_concurrent_requests=5,
                max_concurrent_tasks=2,
                max_concurrent_connections=10,
                request_timeout=config.concurrency_config.request_timeout * 4,
                task_timeout=config.concurrency_config.task_timeout * 4
            ),
            timeout_config=TimeoutConfig(
                api_timeout=config.timeout_config.api_timeout * 4,
                database_timeout=config.timeout_config.database_timeout * 4,
                redis_timeout=config.timeout_config.redis_timeout * 4,
                nats_timeout=config.timeout_config.nats_timeout * 4,
                external_api_timeout=config.timeout_config.external_api_timeout * 4
            ),
            backoff_config=BackoffConfig(
                initial_delay=config.backoff_config.initial_delay * 4,
                max_delay=config.backoff_config.max_delay * 4,
                multiplier=config.backoff_config.multiplier,
                jitter=config.backoff_config.jitter,
                max_attempts=1
            ),
            degrade_config=DegradeConfig(
                disable_verbose_critique=True,
                disable_debate=True,
                shrink_context=True,
                prefer_slm_tiers=True,
                reduce_logging=True,
                skip_non_essential_features=True
            ),
            degrade_mode=DegradeMode.EMERGENCY,
            enable_metrics=True,
            enable_tracing=False,
            enable_profiling=False
        )
        
        return emergency_config
    
    def save_config(self, config: CapacityConfig, filename: Optional[str] = None) -> None:
        """Save configuration to file."""
        if filename is None:
            filename = f"capacity_{config.environment.value}.json"
        
        filepath = self.config_dir / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        
        config_dict = {
            "environment": config.environment.value,
            "pool_config": {
                "min_size": config.pool_config.min_size,
                "max_size": config.pool_config.max_size,
                "timeout": config.pool_config.timeout,
                "retry_attempts": config.pool_config.retry_attempts,
                "retry_delay": config.pool_config.retry_delay
            },
            "concurrency_config": {
                "max_concurrent_requests": config.concurrency_config.max_concurrent_requests,
                "max_concurrent_tasks": config.concurrency_config.max_concurrent_tasks,
                "max_concurrent_connections": config.concurrency_config.max_concurrent_connections,
                "request_timeout": config.concurrency_config.request_timeout,
                "task_timeout": config.concurrency_config.task_timeout
            },
            "timeout_config": {
                "api_timeout": config.timeout_config.api_timeout,
                "database_timeout": config.timeout_config.database_timeout,
                "redis_timeout": config.timeout_config.redis_timeout,
                "nats_timeout": config.timeout_config.nats_timeout,
                "external_api_timeout": config.timeout_config.external_api_timeout
            },
            "backoff_config": {
                "initial_delay": config.backoff_config.initial_delay,
                "max_delay": config.backoff_config.max_delay,
                "multiplier": config.backoff_config.multiplier,
                "jitter": config.backoff_config.jitter,
                "max_attempts": config.backoff_config.max_attempts
            },
            "degrade_config": {
                "disable_verbose_critique": config.degrade_config.disable_verbose_critique,
                "disable_debate": config.degrade_config.disable_debate,
                "shrink_context": config.degrade_config.shrink_context,
                "prefer_slm_tiers": config.degrade_config.prefer_slm_tiers,
                "reduce_logging": config.degrade_config.reduce_logging,
                "skip_non_essential_features": config.degrade_config.skip_non_essential_features
            },
            "degrade_mode": config.degrade_mode.value,
            "enable_metrics": config.enable_metrics,
            "enable_tracing": config.enable_tracing,
            "enable_profiling": config.enable_profiling
        }
        
        with open(filepath, 'w') as f:
            json.dump(config_dict, f, indent=2)
        
        logger.info("Configuration saved", filepath=str(filepath))
    
    def load_config(self, filename: str) -> CapacityConfig:
        """Load configuration from file."""
        filepath = self.config_dir / filename
        
        with open(filepath, 'r') as f:
            config_dict = json.load(f)
        
        # Reconstruct configuration
        environment = Environment(config_dict["environment"])
        
        pool_config = PoolConfig(**config_dict["pool_config"])
        concurrency_config = ConcurrencyConfig(**config_dict["concurrency_config"])
        timeout_config = TimeoutConfig(**config_dict["timeout_config"])
        backoff_config = BackoffConfig(**config_dict["backoff_config"])
        degrade_config = DegradeConfig(**config_dict["degrade_config"])
        
        config = CapacityConfig(
            environment=environment,
            pool_config=pool_config,
            concurrency_config=concurrency_config,
            timeout_config=timeout_config,
            backoff_config=backoff_config,
            degrade_config=degrade_config,
            degrade_mode=DegradeMode(config_dict["degrade_mode"]),
            enable_metrics=config_dict["enable_metrics"],
            enable_tracing=config_dict["enable_tracing"],
            enable_profiling=config_dict["enable_profiling"]
        )
        
        logger.info("Configuration loaded", filepath=str(filepath))
        return config
    
    def get_all_configs(self) -> Dict[Environment, CapacityConfig]:
        """Get all configurations."""
        return self.configs.copy()
    
    def update_config(self, environment: Environment, **kwargs) -> None:
        """Update configuration for environment."""
        if environment not in self.configs:
            raise ValueError(f"Unknown environment: {environment}")
        
        config = self.configs[environment]
        
        # Update pool config
        if "pool_config" in kwargs:
            for key, value in kwargs["pool_config"].items():
                setattr(config.pool_config, key, value)
        
        # Update concurrency config
        if "concurrency_config" in kwargs:
            for key, value in kwargs["concurrency_config"].items():
                setattr(config.concurrency_config, key, value)
        
        # Update timeout config
        if "timeout_config" in kwargs:
            for key, value in kwargs["timeout_config"].items():
                setattr(config.timeout_config, key, value)
        
        # Update backoff config
        if "backoff_config" in kwargs:
            for key, value in kwargs["backoff_config"].items():
                setattr(config.backoff_config, key, value)
        
        # Update degrade config
        if "degrade_config" in kwargs:
            for key, value in kwargs["degrade_config"].items():
                setattr(config.degrade_config, key, value)
        
        # Update other attributes
        for key, value in kwargs.items():
            if key not in ["pool_config", "concurrency_config", "timeout_config", "backoff_config", "degrade_config"]:
                setattr(config, key, value)
        
        logger.info("Configuration updated", environment=environment.value, updates=kwargs)
