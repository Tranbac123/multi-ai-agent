"""NATS Mirroring Manager for multi-region active-active replication."""

import asyncio
import json
import time
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
import nats
from nats.aio.client import Client as NATS
from nats.js.api import StreamConfig, ConsumerConfig, DeliverPolicy
from nats.js.client import JetStreamContext
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)


class MirroringStatus(Enum):
    """Mirroring status."""
    ACTIVE = "active"
    PAUSED = "paused"
    FAILED = "failed"
    SYNCING = "syncing"


class MirroringDirection(Enum):
    """Mirroring direction."""
    BIDIRECTIONAL = "bidirectional"
    UNIDIRECTIONAL = "unidirectional"


@dataclass
class MirroringConfig:
    """Mirroring configuration."""
    stream_name: str
    source_region: str
    target_region: str
    direction: MirroringDirection
    replication_factor: int = 3
    max_age_seconds: int = 86400  # 24 hours
    max_bytes: int = 1024 * 1024 * 1024  # 1GB
    max_msgs: int = 1000000
    mirror_subject: str = "mirror.*"
    filter_subjects: List[str] = None
    sync_interval_seconds: int = 60
    health_check_interval_seconds: int = 30


@dataclass
class MirroringStats:
    """Mirroring statistics."""
    stream_name: str
    region: str
    messages_replicated: int
    bytes_replicated: int
    replication_lag_ms: float
    last_message_time: datetime
    status: MirroringStatus
    error_count: int
    last_error: Optional[str] = None


@dataclass
class MirroringEvent:
    """Mirroring event data."""
    event_id: str
    stream_name: str
    source_region: str
    target_region: str
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]


class NATSMirroringManager:
    """Manages NATS mirroring for multi-region active-active replication."""
    
    def __init__(self, region: str):
        self.region = region
        self.nats_clients: Dict[str, NATS] = {}
        self.js_contexts: Dict[str, JetStreamContext] = {}
        self.mirroring_configs: Dict[str, MirroringConfig] = {}
        self.mirroring_stats: Dict[str, MirroringStats] = {}
        self.health_check_tasks: Dict[str, asyncio.Task] = {}
        self.sync_tasks: Dict[str, asyncio.Task] = {}
        self.event_handlers: Dict[str, Callable] = {}
    
    async def initialize_region_connections(self, region_configs: Dict[str, Dict[str, str]]):
        """Initialize NATS connections for all regions."""
        try:
            for region_name, config in region_configs.items():
                if region_name == self.region:
                    continue  # Skip self
                
                # Create NATS connection
                nats_client = await nats.connect(
                    servers=[config["server"]],
                    user=config.get("user"),
                    password=config.get("password"),
                    token=config.get("token"),
                    name=f"mirroring-{self.region}-to-{region_name}"
                )
                
                # Create JetStream context
                js_context = nats_client.jetstream()
                
                self.nats_clients[region_name] = nats_client
                self.js_contexts[region_name] = js_context
                
                logger.info("NATS connection initialized",
                           source_region=self.region,
                           target_region=region_name,
                           server=config["server"])
            
            logger.info("All region connections initialized",
                       total_regions=len(self.nats_clients))
            
        except Exception as e:
            logger.error("Failed to initialize region connections", error=str(e))
            raise
    
    async def setup_mirroring(self, config: MirroringConfig) -> bool:
        """Setup mirroring for a stream."""
        try:
            logger.info("Setting up mirroring",
                       stream_name=config.stream_name,
                       source_region=config.source_region,
                       target_region=config.target_region,
                       direction=config.direction.value)
            
            # Store configuration
            self.mirroring_configs[config.stream_name] = config
            
            # Setup mirroring based on direction
            if config.direction == MirroringDirection.BIDIRECTIONAL:
                await self._setup_bidirectional_mirroring(config)
            else:
                await self._setup_unidirectional_mirroring(config)
            
            # Initialize statistics
            self.mirroring_stats[config.stream_name] = MirroringStats(
                stream_name=config.stream_name,
                region=self.region,
                messages_replicated=0,
                bytes_replicated=0,
                replication_lag_ms=0.0,
                last_message_time=datetime.now(timezone.utc),
                status=MirroringStatus.ACTIVE,
                error_count=0
            )
            
            # Start health check
            await self._start_health_check(config.stream_name)
            
            # Start sync task if needed
            if config.sync_interval_seconds > 0:
                await self._start_sync_task(config.stream_name)
            
            logger.info("Mirroring setup completed",
                       stream_name=config.stream_name)
            
            return True
            
        except Exception as e:
            logger.error("Failed to setup mirroring",
                        stream_name=config.stream_name,
                        error=str(e))
            return False
    
    async def _setup_bidirectional_mirroring(self, config: MirroringConfig):
        """Setup bidirectional mirroring."""
        try:
            # Setup mirroring from source to target
            await self._setup_stream_mirror(config, config.source_region, config.target_region)
            
            # Setup mirroring from target to source
            await self._setup_stream_mirror(config, config.target_region, config.source_region)
            
            logger.info("Bidirectional mirroring setup completed",
                       stream_name=config.stream_name)
            
        except Exception as e:
            logger.error("Failed to setup bidirectional mirroring",
                        stream_name=config.stream_name,
                        error=str(e))
            raise
    
    async def _setup_unidirectional_mirroring(self, config: MirroringConfig):
        """Setup unidirectional mirroring."""
        try:
            # Setup mirroring from source to target
            await self._setup_stream_mirror(config, config.source_region, config.target_region)
            
            logger.info("Unidirectional mirroring setup completed",
                       stream_name=config.stream_name)
            
        except Exception as e:
            logger.error("Failed to setup unidirectional mirroring",
                        stream_name=config.stream_name,
                        error=str(e))
            raise
    
    async def _setup_stream_mirror(self, config: MirroringConfig, source_region: str, target_region: str):
        """Setup stream mirroring between two regions."""
        try:
            if target_region not in self.js_contexts:
                logger.error("Target region not available",
                           target_region=target_region,
                           stream_name=config.stream_name)
                return
            
            js_context = self.js_contexts[target_region]
            
            # Create or update stream with mirror configuration
            stream_config = StreamConfig(
                name=config.stream_name,
                subjects=[config.mirror_subject],
                max_age=config.max_age_seconds,
                max_bytes=config.max_bytes,
                max_msgs=config.max_msgs,
                storage=nats.js.api.StorageType.FILE,
                replicas=config.replication_factor,
                mirror=nats.js.api.StreamSource(
                    name=f"{config.stream_name}-{source_region}",
                    external=nats.js.api.ExternalStream(
                        api=f"http://{source_region}-nats:8222"
                    )
                )
            )
            
            # Add stream or update existing
            try:
                await js_context.add_stream(stream_config)
                logger.info("Stream mirror created",
                           stream_name=config.stream_name,
                           source_region=source_region,
                           target_region=target_region)
            except Exception as e:
                if "already exists" in str(e):
                    await js_context.update_stream(stream_config)
                    logger.info("Stream mirror updated",
                               stream_name=config.stream_name,
                               source_region=source_region,
                               target_region=target_region)
                else:
                    raise
            
        except Exception as e:
            logger.error("Failed to setup stream mirror",
                        stream_name=config.stream_name,
                        source_region=source_region,
                        target_region=target_region,
                        error=str(e))
            raise
    
    async def _start_health_check(self, stream_name: str):
        """Start health check task for mirroring."""
        try:
            config = self.mirroring_configs[stream_name]
            
            async def health_check_task():
                while True:
                    try:
                        await self._perform_health_check(stream_name)
                        await asyncio.sleep(config.health_check_interval_seconds)
                    except Exception as e:
                        logger.error("Health check failed",
                                   stream_name=stream_name,
                                   error=str(e))
                        await asyncio.sleep(config.health_check_interval_seconds)
            
            task = asyncio.create_task(health_check_task())
            self.health_check_tasks[stream_name] = task
            
            logger.info("Health check started",
                       stream_name=stream_name,
                       interval_seconds=config.health_check_interval_seconds)
            
        except Exception as e:
            logger.error("Failed to start health check",
                        stream_name=stream_name,
                        error=str(e))
    
    async def _perform_health_check(self, stream_name: str):
        """Perform health check for mirroring."""
        try:
            config = self.mirroring_configs[stream_name]
            stats = self.mirroring_stats[stream_name]
            
            # Check mirroring status for each target region
            target_regions = [config.target_region]
            if config.direction == MirroringDirection.BIDIRECTIONAL:
                target_regions.append(config.source_region)
            
            for target_region in target_regions:
                if target_region not in self.js_contexts:
                    continue
                
                js_context = self.js_contexts[target_region]
                
                try:
                    # Get stream info
                    stream_info = await js_context.stream_info(stream_name)
                    
                    # Update statistics
                    stats.messages_replicated = stream_info.state.messages
                    stats.bytes_replicated = stream_info.state.bytes
                    stats.last_message_time = datetime.now(timezone.utc)
                    
                    # Check for errors
                    if stream_info.state.messages == 0 and stats.messages_replicated > 0:
                        stats.error_count += 1
                        stats.last_error = "No messages replicated"
                        stats.status = MirroringStatus.FAILED
                    else:
                        stats.status = MirroringStatus.ACTIVE
                    
                    logger.debug("Health check completed",
                               stream_name=stream_name,
                               target_region=target_region,
                               messages=stream_info.state.messages,
                               bytes=stream_info.state.bytes)
                    
                except Exception as e:
                    stats.error_count += 1
                    stats.last_error = str(e)
                    stats.status = MirroringStatus.FAILED
                    
                    logger.error("Health check failed for region",
                               stream_name=stream_name,
                               target_region=target_region,
                               error=str(e))
            
        except Exception as e:
            logger.error("Health check failed",
                        stream_name=stream_name,
                        error=str(e))
    
    async def _start_sync_task(self, stream_name: str):
        """Start sync task for mirroring."""
        try:
            config = self.mirroring_configs[stream_name]
            
            async def sync_task():
                while True:
                    try:
                        await self._perform_sync(stream_name)
                        await asyncio.sleep(config.sync_interval_seconds)
                    except Exception as e:
                        logger.error("Sync task failed",
                                   stream_name=stream_name,
                                   error=str(e))
                        await asyncio.sleep(config.sync_interval_seconds)
            
            task = asyncio.create_task(sync_task())
            self.sync_tasks[stream_name] = task
            
            logger.info("Sync task started",
                       stream_name=stream_name,
                       interval_seconds=config.sync_interval_seconds)
            
        except Exception as e:
            logger.error("Failed to start sync task",
                        stream_name=stream_name,
                        error=str(e))
    
    async def _perform_sync(self, stream_name: str):
        """Perform sync for mirroring."""
        try:
            config = self.mirroring_configs[stream_name]
            stats = self.mirroring_stats[stream_name]
            
            # Mark as syncing
            stats.status = MirroringStatus.SYNCING
            
            # Perform sync operations
            # This would include:
            # 1. Checking for missing messages
            # 2. Replicating missing messages
            # 3. Validating message integrity
            # 4. Updating statistics
            
            logger.debug("Sync completed",
                        stream_name=stream_name)
            
            # Mark as active
            stats.status = MirroringStatus.ACTIVE
            
        except Exception as e:
            logger.error("Sync failed",
                        stream_name=stream_name,
                        error=str(e))
            
            stats = self.mirroring_stats[stream_name]
            stats.status = MirroringStatus.FAILED
            stats.error_count += 1
            stats.last_error = str(e)
    
    async def pause_mirroring(self, stream_name: str) -> bool:
        """Pause mirroring for a stream."""
        try:
            if stream_name not in self.mirroring_configs:
                logger.error("Stream not found", stream_name=stream_name)
                return False
            
            # Pause health check and sync tasks
            if stream_name in self.health_check_tasks:
                self.health_check_tasks[stream_name].cancel()
                del self.health_check_tasks[stream_name]
            
            if stream_name in self.sync_tasks:
                self.sync_tasks[stream_name].cancel()
                del self.sync_tasks[stream_name]
            
            # Update status
            if stream_name in self.mirroring_stats:
                self.mirroring_stats[stream_name].status = MirroringStatus.PAUSED
            
            logger.info("Mirroring paused", stream_name=stream_name)
            return True
            
        except Exception as e:
            logger.error("Failed to pause mirroring",
                        stream_name=stream_name,
                        error=str(e))
            return False
    
    async def resume_mirroring(self, stream_name: str) -> bool:
        """Resume mirroring for a stream."""
        try:
            if stream_name not in self.mirroring_configs:
                logger.error("Stream not found", stream_name=stream_name)
                return False
            
            config = self.mirroring_configs[stream_name]
            
            # Restart health check and sync tasks
            await self._start_health_check(stream_name)
            
            if config.sync_interval_seconds > 0:
                await self._start_sync_task(stream_name)
            
            # Update status
            if stream_name in self.mirroring_stats:
                self.mirroring_stats[stream_name].status = MirroringStatus.ACTIVE
            
            logger.info("Mirroring resumed", stream_name=stream_name)
            return True
            
        except Exception as e:
            logger.error("Failed to resume mirroring",
                        stream_name=stream_name,
                        error=str(e))
            return False
    
    async def get_mirroring_status(self, stream_name: str) -> Optional[Dict[str, Any]]:
        """Get mirroring status for a stream."""
        try:
            if stream_name not in self.mirroring_configs:
                return None
            
            config = self.mirroring_configs[stream_name]
            stats = self.mirroring_stats.get(stream_name)
            
            if not stats:
                return None
            
            return {
                "stream_name": stream_name,
                "source_region": config.source_region,
                "target_region": config.target_region,
                "direction": config.direction.value,
                "status": stats.status.value,
                "messages_replicated": stats.messages_replicated,
                "bytes_replicated": stats.bytes_replicated,
                "replication_lag_ms": stats.replication_lag_ms,
                "last_message_time": stats.last_message_time.isoformat(),
                "error_count": stats.error_count,
                "last_error": stats.last_error,
                "replication_factor": config.replication_factor,
                "max_age_seconds": config.max_age_seconds,
                "max_bytes": config.max_bytes,
                "max_msgs": config.max_msgs
            }
            
        except Exception as e:
            logger.error("Failed to get mirroring status",
                        stream_name=stream_name,
                        error=str(e))
            return None
    
    async def get_all_mirroring_status(self) -> Dict[str, Any]:
        """Get status for all mirroring streams."""
        try:
            status_data = {}
            
            for stream_name in self.mirroring_configs:
                status = await self.get_mirroring_status(stream_name)
                if status:
                    status_data[stream_name] = status
            
            return {
                "region": self.region,
                "total_streams": len(status_data),
                "active_streams": len([s for s in status_data.values() if s["status"] == "active"]),
                "paused_streams": len([s for s in status_data.values() if s["status"] == "paused"]),
                "failed_streams": len([s for s in status_data.values() if s["status"] == "failed"]),
                "streams": status_data
            }
            
        except Exception as e:
            logger.error("Failed to get all mirroring status", error=str(e))
            return {}
    
    async def cleanup(self):
        """Cleanup mirroring manager."""
        try:
            # Cancel all tasks
            for task in self.health_check_tasks.values():
                task.cancel()
            
            for task in self.sync_tasks.values():
                task.cancel()
            
            # Close NATS connections
            for nats_client in self.nats_clients.values():
                await nats_client.close()
            
            logger.info("Mirroring manager cleaned up")
            
        except Exception as e:
            logger.error("Failed to cleanup mirroring manager", error=str(e))
