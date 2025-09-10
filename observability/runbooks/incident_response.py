"""Incident response and runbook automation."""

import asyncio
import time
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime, timedelta
from enum import Enum
import structlog
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class IncidentSeverity(Enum):
    """Incident severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(Enum):
    """Incident status."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    IDENTIFIED = "identified"
    MONITORING = "monitoring"
    RESOLVED = "resolved"
    CLOSED = "closed"


class IncidentType(Enum):
    """Incident types."""
    SLO_BREACH = "slo_breach"
    HIGH_ERROR_RATE = "high_error_rate"
    HIGH_LATENCY = "high_latency"
    SERVICE_DOWN = "service_down"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    SECURITY_INCIDENT = "security_incident"
    DATA_LOSS = "data_loss"


class Incident:
    """Incident representation."""
    
    def __init__(
        self,
        incident_id: str,
        title: str,
        description: str,
        severity: IncidentSeverity,
        incident_type: IncidentType,
        tenant_id: str,
        affected_services: List[str],
        created_by: str = "system"
    ):
        self.incident_id = incident_id
        self.title = title
        self.description = description
        self.severity = severity
        self.incident_type = incident_type
        self.tenant_id = tenant_id
        self.affected_services = affected_services
        self.created_by = created_by
        self.status = IncidentStatus.OPEN
        self.created_at = time.time()
        self.updated_at = time.time()
        self.resolved_at = None
        self.assigned_to = None
        self.runbook_steps = []
        self.completed_steps = []
        self.notes = []
        self.metrics = {}


class IncidentResponse:
    """Incident response and runbook automation."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.active_incidents = {}
        self.runbooks = {}
        self.escalation_rules = {}
        self.notification_handlers = []
    
    def add_runbook(
        self,
        incident_type: IncidentType,
        steps: List[Dict[str, Any]]
    ) -> None:
        """Add runbook for incident type."""
        self.runbooks[incident_type] = steps
        logger.info("Runbook added", incident_type=incident_type.value, steps_count=len(steps))
    
    def add_escalation_rule(
        self,
        severity: IncidentSeverity,
        delay_minutes: int,
        escalation_target: str
    ) -> None:
        """Add escalation rule."""
        self.escalation_rules[severity] = {
            'delay_minutes': delay_minutes,
            'escalation_target': escalation_target
        }
        logger.info("Escalation rule added", severity=severity.value, delay=delay_minutes)
    
    def add_notification_handler(self, handler: Callable) -> None:
        """Add notification handler."""
        self.notification_handlers.append(handler)
    
    async def create_incident(
        self,
        title: str,
        description: str,
        severity: IncidentSeverity,
        incident_type: IncidentType,
        tenant_id: str,
        affected_services: List[str],
        created_by: str = "system"
    ) -> str:
        """Create a new incident."""
        try:
            incident_id = f"inc_{int(time.time())}_{tenant_id}"
            
            incident = Incident(
                incident_id=incident_id,
                title=title,
                description=description,
                severity=severity,
                incident_type=incident_type,
                tenant_id=tenant_id,
                affected_services=affected_services,
                created_by=created_by
            )
            
            # Load runbook steps
            if incident_type in self.runbooks:
                incident.runbook_steps = self.runbooks[incident_type]
            
            # Store incident
            await self._store_incident(incident)
            self.active_incidents[incident_id] = incident
            
            # Send notifications
            await self._send_notifications(incident, "created")
            
            # Start escalation timer
            await self._start_escalation_timer(incident)
            
            logger.info(
                "Incident created",
                incident_id=incident_id,
                title=title,
                severity=severity.value,
                incident_type=incident_type.value,
                tenant_id=tenant_id
            )
            
            return incident_id
            
        except Exception as e:
            logger.error("Failed to create incident", error=str(e))
            raise
    
    async def update_incident_status(
        self,
        incident_id: str,
        status: IncidentStatus,
        notes: Optional[str] = None,
        updated_by: str = "system"
    ) -> bool:
        """Update incident status."""
        try:
            if incident_id not in self.active_incidents:
                logger.warning("Incident not found", incident_id=incident_id)
                return False
            
            incident = self.active_incidents[incident_id]
            old_status = incident.status
            incident.status = status
            incident.updated_at = time.time()
            
            if status == IncidentStatus.RESOLVED:
                incident.resolved_at = time.time()
            
            # Add notes if provided
            if notes:
                incident.notes.append({
                    'timestamp': time.time(),
                    'author': updated_by,
                    'note': notes
                })
            
            # Store updated incident
            await self._store_incident(incident)
            
            # Send notifications
            await self._send_notifications(incident, "status_updated", {
                'old_status': old_status.value,
                'new_status': status.value,
                'updated_by': updated_by
            })
            
            logger.info(
                "Incident status updated",
                incident_id=incident_id,
                old_status=old_status.value,
                new_status=status.value,
                updated_by=updated_by
            )
            
            return True
            
        except Exception as e:
            logger.error("Failed to update incident status", error=str(e))
            return False
    
    async def execute_runbook_step(
        self,
        incident_id: str,
        step_index: int,
        executed_by: str = "system"
    ) -> bool:
        """Execute a runbook step."""
        try:
            if incident_id not in self.active_incidents:
                logger.warning("Incident not found", incident_id=incident_id)
                return False
            
            incident = self.active_incidents[incident_id]
            
            if step_index >= len(incident.runbook_steps):
                logger.warning("Invalid step index", incident_id=incident_id, step_index=step_index)
                return False
            
            step = incident.runbook_steps[step_index]
            
            # Execute step
            success = await self._execute_step(step, incident)
            
            # Record completion
            incident.completed_steps.append({
                'step_index': step_index,
                'step': step,
                'executed_by': executed_by,
                'executed_at': time.time(),
                'success': success
            })
            
            # Update incident
            incident.updated_at = time.time()
            await self._store_incident(incident)
            
            logger.info(
                "Runbook step executed",
                incident_id=incident_id,
                step_index=step_index,
                step_title=step.get('title', ''),
                success=success,
                executed_by=executed_by
            )
            
            return success
            
        except Exception as e:
            logger.error("Failed to execute runbook step", error=str(e))
            return False
    
    async def _execute_step(self, step: Dict[str, Any], incident: Incident) -> bool:
        """Execute a runbook step."""
        try:
            step_type = step.get('type', 'manual')
            
            if step_type == 'check_metric':
                return await self._check_metric_step(step, incident)
            elif step_type == 'restart_service':
                return await self._restart_service_step(step, incident)
            elif step_type == 'scale_service':
                return await self._scale_service_step(step, incident)
            elif step_type == 'clear_cache':
                return await self._clear_cache_step(step, incident)
            elif step_type == 'manual':
                return True  # Manual steps are considered successful
            else:
                logger.warning("Unknown step type", step_type=step_type)
                return False
                
        except Exception as e:
            logger.error("Failed to execute step", error=str(e), step=step)
            return False
    
    async def _check_metric_step(self, step: Dict[str, Any], incident: Incident) -> bool:
        """Execute metric check step."""
        try:
            metric_name = step.get('metric_name')
            threshold = step.get('threshold')
            operator = step.get('operator', 'gt')
            
            # Get current metric value
            metric_key = f"metric:{incident.tenant_id}:{metric_name}"
            current_value = await self.redis.get(metric_key)
            
            if not current_value:
                return False
            
            current_value = float(current_value)
            
            # Check threshold
            if operator == 'gt':
                return current_value > threshold
            elif operator == 'lt':
                return current_value < threshold
            elif operator == 'eq':
                return current_value == threshold
            else:
                return False
                
        except Exception as e:
            logger.error("Failed to check metric", error=str(e))
            return False
    
    async def _restart_service_step(self, step: Dict[str, Any], incident: Incident) -> bool:
        """Execute service restart step."""
        try:
            service_name = step.get('service_name')
            
            # This would typically call the actual service restart API
            # For now, we'll simulate it
            logger.info("Simulating service restart", service_name=service_name)
            await asyncio.sleep(1)  # Simulate restart time
            
            return True
            
        except Exception as e:
            logger.error("Failed to restart service", error=str(e))
            return False
    
    async def _scale_service_step(self, step: Dict[str, Any], incident: Incident) -> bool:
        """Execute service scaling step."""
        try:
            service_name = step.get('service_name')
            target_replicas = step.get('target_replicas')
            
            # This would typically call the actual scaling API
            # For now, we'll simulate it
            logger.info("Simulating service scaling", service_name=service_name, replicas=target_replicas)
            await asyncio.sleep(2)  # Simulate scaling time
            
            return True
            
        except Exception as e:
            logger.error("Failed to scale service", error=str(e))
            return False
    
    async def _clear_cache_step(self, step: Dict[str, Any], incident: Incident) -> bool:
        """Execute cache clear step."""
        try:
            cache_pattern = step.get('cache_pattern', '*')
            
            # Clear cache entries
            keys = await self.redis.keys(cache_pattern)
            if keys:
                await self.redis.delete(*keys)
            
            logger.info("Cache cleared", pattern=cache_pattern, keys_count=len(keys))
            return True
            
        except Exception as e:
            logger.error("Failed to clear cache", error=str(e))
            return False
    
    async def _store_incident(self, incident: Incident) -> None:
        """Store incident in Redis."""
        try:
            incident_key = f"incident:{incident.tenant_id}:{incident.incident_id}"
            
            incident_data = {
                'incident_id': incident.incident_id,
                'title': incident.title,
                'description': incident.description,
                'severity': incident.severity.value,
                'incident_type': incident.incident_type.value,
                'tenant_id': incident.tenant_id,
                'affected_services': ','.join(incident.affected_services),
                'created_by': incident.created_by,
                'status': incident.status.value,
                'created_at': incident.created_at,
                'updated_at': incident.updated_at,
                'resolved_at': incident.resolved_at or 0,
                'assigned_to': incident.assigned_to or '',
                'runbook_steps': str(incident.runbook_steps),
                'completed_steps': str(incident.completed_steps),
                'notes': str(incident.notes),
                'metrics': str(incident.metrics)
            }
            
            await self.redis.hset(incident_key, mapping=incident_data)
            await self.redis.expire(incident_key, 86400 * 30)  # 30 days TTL
            
        except Exception as e:
            logger.error("Failed to store incident", error=str(e))
    
    async def _send_notifications(
        self,
        incident: Incident,
        event_type: str,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """Send notifications for incident events."""
        try:
            for handler in self.notification_handlers:
                try:
                    await handler(incident, event_type, additional_data)
                except Exception as e:
                    logger.error("Notification handler failed", error=str(e))
                    
        except Exception as e:
            logger.error("Failed to send notifications", error=str(e))
    
    async def _start_escalation_timer(self, incident: Incident) -> None:
        """Start escalation timer for incident."""
        try:
            if incident.severity in self.escalation_rules:
                rule = self.escalation_rules[incident.severity]
                delay_seconds = rule['delay_minutes'] * 60
                
                # Schedule escalation
                asyncio.create_task(self._escalate_incident(incident.incident_id, delay_seconds))
                
        except Exception as e:
            logger.error("Failed to start escalation timer", error=str(e))
    
    async def _escalate_incident(self, incident_id: str, delay_seconds: int) -> None:
        """Escalate incident after delay."""
        try:
            await asyncio.sleep(delay_seconds)
            
            if incident_id in self.active_incidents:
                incident = self.active_incidents[incident_id]
                
                # Check if incident is still open
                if incident.status in [IncidentStatus.OPEN, IncidentStatus.INVESTIGATING]:
                    # Escalate
                    await self._send_notifications(incident, "escalated")
                    
                    logger.warning(
                        "Incident escalated",
                        incident_id=incident_id,
                        severity=incident.severity.value
                    )
                    
        except Exception as e:
            logger.error("Failed to escalate incident", error=str(e))
    
    async def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get incident by ID."""
        return self.active_incidents.get(incident_id)
    
    async def get_active_incidents(self, tenant_id: Optional[str] = None) -> List[Incident]:
        """Get active incidents."""
        incidents = list(self.active_incidents.values())
        
        if tenant_id:
            incidents = [i for i in incidents if i.tenant_id == tenant_id]
        
        return incidents
    
    async def get_incident_statistics(self, tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Get incident statistics."""
        try:
            incidents = await self.get_active_incidents(tenant_id)
            
            stats = {
                'total_incidents': len(incidents),
                'by_severity': {},
                'by_status': {},
                'by_type': {},
                'avg_resolution_time': 0,
                'open_incidents': 0
            }
            
            resolution_times = []
            
            for incident in incidents:
                # Count by severity
                severity = incident.severity.value
                stats['by_severity'][severity] = stats['by_severity'].get(severity, 0) + 1
                
                # Count by status
                status = incident.status.value
                stats['by_status'][status] = stats['by_status'].get(status, 0) + 1
                
                # Count by type
                incident_type = incident.incident_type.value
                stats['by_type'][incident_type] = stats['by_type'].get(incident_type, 0) + 1
                
                # Count open incidents
                if incident.status in [IncidentStatus.OPEN, IncidentStatus.INVESTIGATING]:
                    stats['open_incidents'] += 1
                
                # Calculate resolution time
                if incident.resolved_at:
                    resolution_time = incident.resolved_at - incident.created_at
                    resolution_times.append(resolution_time)
            
            # Calculate average resolution time
            if resolution_times:
                stats['avg_resolution_time'] = sum(resolution_times) / len(resolution_times)
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get incident statistics", error=str(e))
            return {}
