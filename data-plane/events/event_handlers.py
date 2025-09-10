"""Event handlers for system events."""

import asyncio
import time
from typing import Dict, List, Any, Optional
import structlog
import redis.asyncio as redis

from data-plane.events.nats_event_bus import EventType, EventPriority, NATSEventBus

logger = structlog.get_logger(__name__)


class EventHandlers:
    """Event handlers for system events."""
    
    def __init__(self, redis_client: redis.Redis, event_bus: NATSEventBus):
        self.redis = redis_client
        self.event_bus = event_bus
    
    async def handle_agent_run_started(self, event: Dict[str, Any]) -> None:
        """Handle agent run started event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            run_id = event_data.get('run_id')
            
            # Update agent run status
            run_key = f"agent_run:{tenant_id}:{run_id}"
            await self.redis.hset(run_key, mapping={
                'status': 'running',
                'started_at': time.time(),
                'updated_at': time.time()
            })
            await self.redis.expire(run_key, 86400)  # 24 hours TTL
            
            # Update tenant metrics
            await self._update_tenant_metrics(tenant_id, 'agent_runs_started', 1)
            
            logger.info(
                "Agent run started",
                tenant_id=tenant_id,
                run_id=run_id,
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle agent run started event",
                error=str(e),
                event=event
            )
    
    async def handle_agent_run_completed(self, event: Dict[str, Any]) -> None:
        """Handle agent run completed event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            run_id = event_data.get('run_id')
            
            # Update agent run status
            run_key = f"agent_run:{tenant_id}:{run_id}"
            await self.redis.hset(run_key, mapping={
                'status': 'completed',
                'completed_at': time.time(),
                'updated_at': time.time(),
                'result': event_data.get('result', ''),
                'tokens_used': event_data.get('tokens_used', 0),
                'cost': event_data.get('cost', 0.0)
            })
            
            # Update tenant metrics
            await self._update_tenant_metrics(tenant_id, 'agent_runs_completed', 1)
            await self._update_tenant_metrics(tenant_id, 'tokens_used', event_data.get('tokens_used', 0))
            await self._update_tenant_metrics(tenant_id, 'cost', event_data.get('cost', 0.0))
            
            logger.info(
                "Agent run completed",
                tenant_id=tenant_id,
                run_id=run_id,
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle agent run completed event",
                error=str(e),
                event=event
            )
    
    async def handle_agent_run_failed(self, event: Dict[str, Any]) -> None:
        """Handle agent run failed event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            run_id = event_data.get('run_id')
            
            # Update agent run status
            run_key = f"agent_run:{tenant_id}:{run_id}"
            await self.redis.hset(run_key, mapping={
                'status': 'failed',
                'failed_at': time.time(),
                'updated_at': time.time(),
                'error': event_data.get('error', ''),
                'error_type': event_data.get('error_type', 'unknown')
            })
            
            # Update tenant metrics
            await self._update_tenant_metrics(tenant_id, 'agent_runs_failed', 1)
            
            # Check if we need to send alert
            if event_data.get('error_type') == 'critical':
                await self._send_alert(tenant_id, f"Critical agent run failure: {run_id}")
            
            logger.error(
                "Agent run failed",
                tenant_id=tenant_id,
                run_id=run_id,
                error=event_data.get('error'),
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle agent run failed event",
                error=str(e),
                event=event
            )
    
    async def handle_router_decision(self, event: Dict[str, Any]) -> None:
        """Handle router decision event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            
            # Update router metrics
            await self._update_tenant_metrics(tenant_id, 'router_decisions', 1)
            
            # Track decision latency
            decision_latency = event_data.get('decision_latency', 0)
            await self._update_tenant_metrics(tenant_id, 'router_latency', decision_latency)
            
            # Track tier distribution
            tier = event_data.get('tier', 'A')
            await self._update_tenant_metrics(tenant_id, f'tier_{tier}_decisions', 1)
            
            logger.info(
                "Router decision recorded",
                tenant_id=tenant_id,
                tier=tier,
                latency=decision_latency,
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle router decision event",
                error=str(e),
                event=event
            )
    
    async def handle_router_misroute(self, event: Dict[str, Any]) -> None:
        """Handle router misroute event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            
            # Update misroute metrics
            await self._update_tenant_metrics(tenant_id, 'router_misroutes', 1)
            
            # Track misroute types
            misroute_type = event_data.get('misroute_type', 'unknown')
            await self._update_tenant_metrics(tenant_id, f'misroute_{misroute_type}', 1)
            
            # Send alert for high misroute rate
            misroute_rate = await self._get_misroute_rate(tenant_id)
            if misroute_rate > 0.1:  # 10% threshold
                await self._send_alert(tenant_id, f"High misroute rate: {misroute_rate:.2%}")
            
            logger.warning(
                "Router misroute detected",
                tenant_id=tenant_id,
                misroute_type=misroute_type,
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle router misroute event",
                error=str(e),
                event=event
            )
    
    async def handle_tool_call_started(self, event: Dict[str, Any]) -> None:
        """Handle tool call started event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            tool_id = event_data.get('tool_id')
            
            # Update tool metrics
            await self._update_tenant_metrics(tenant_id, 'tool_calls_started', 1)
            await self._update_tenant_metrics(tenant_id, f'tool_{tool_id}_calls', 1)
            
            logger.info(
                "Tool call started",
                tenant_id=tenant_id,
                tool_id=tool_id,
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle tool call started event",
                error=str(e),
                event=event
            )
    
    async def handle_tool_call_completed(self, event: Dict[str, Any]) -> None:
        """Handle tool call completed event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            tool_id = event_data.get('tool_id')
            
            # Update tool metrics
            await self._update_tenant_metrics(tenant_id, 'tool_calls_completed', 1)
            
            # Track tool latency
            tool_latency = event_data.get('latency', 0)
            await self._update_tenant_metrics(tenant_id, f'tool_{tool_id}_latency', tool_latency)
            
            logger.info(
                "Tool call completed",
                tenant_id=tenant_id,
                tool_id=tool_id,
                latency=tool_latency,
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle tool call completed event",
                error=str(e),
                event=event
            )
    
    async def handle_tool_call_failed(self, event: Dict[str, Any]) -> None:
        """Handle tool call failed event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            tool_id = event_data.get('tool_id')
            
            # Update tool metrics
            await self._update_tenant_metrics(tenant_id, 'tool_calls_failed', 1)
            await self._update_tenant_metrics(tenant_id, f'tool_{tool_id}_failures', 1)
            
            # Track error types
            error_type = event_data.get('error_type', 'unknown')
            await self._update_tenant_metrics(tenant_id, f'tool_error_{error_type}', 1)
            
            logger.error(
                "Tool call failed",
                tenant_id=tenant_id,
                tool_id=tool_id,
                error=event_data.get('error'),
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle tool call failed event",
                error=str(e),
                event=event
            )
    
    async def handle_user_message(self, event: Dict[str, Any]) -> None:
        """Handle user message event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            user_id = event_data.get('user_id')
            
            # Update user metrics
            await self._update_tenant_metrics(tenant_id, 'user_messages', 1)
            
            # Update user activity
            if user_id:
                user_key = f"user_activity:{tenant_id}:{user_id}"
                await self.redis.hset(user_key, mapping={
                    'last_message_at': time.time(),
                    'message_count': await self.redis.hincrby(user_key, 'message_count', 1)
                })
                await self.redis.expire(user_key, 86400)  # 24 hours TTL
            
            logger.info(
                "User message recorded",
                tenant_id=tenant_id,
                user_id=user_id,
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle user message event",
                error=str(e),
                event=event
            )
    
    async def handle_user_session_started(self, event: Dict[str, Any]) -> None:
        """Handle user session started event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            session_id = event_data.get('session_id')
            
            # Update session metrics
            await self._update_tenant_metrics(tenant_id, 'user_sessions_started', 1)
            
            # Store session info
            session_key = f"user_session:{tenant_id}:{session_id}"
            await self.redis.hset(session_key, mapping={
                'started_at': time.time(),
                'user_id': event_data.get('user_id', ''),
                'status': 'active'
            })
            await self.redis.expire(session_key, 86400)  # 24 hours TTL
            
            logger.info(
                "User session started",
                tenant_id=tenant_id,
                session_id=session_id,
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle user session started event",
                error=str(e),
                event=event
            )
    
    async def handle_user_session_ended(self, event: Dict[str, Any]) -> None:
        """Handle user session ended event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            session_id = event_data.get('session_id')
            
            # Update session metrics
            await self._update_tenant_metrics(tenant_id, 'user_sessions_ended', 1)
            
            # Update session info
            session_key = f"user_session:{tenant_id}:{session_id}"
            await self.redis.hset(session_key, mapping={
                'ended_at': time.time(),
                'status': 'ended',
                'duration': event_data.get('duration', 0)
            })
            
            logger.info(
                "User session ended",
                tenant_id=tenant_id,
                session_id=session_id,
                duration=event_data.get('duration', 0),
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle user session ended event",
                error=str(e),
                event=event
            )
    
    async def handle_system_health_check(self, event: Dict[str, Any]) -> None:
        """Handle system health check event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            
            # Update health metrics
            health_status = event_data.get('status', 'unknown')
            await self._update_tenant_metrics(tenant_id, f'health_{health_status}', 1)
            
            # Store health check result
            health_key = f"health_check:{tenant_id}:{int(time.time())}"
            await self.redis.setex(health_key, 300, json.dumps(event_data))  # 5 minutes TTL
            
            logger.info(
                "System health check recorded",
                tenant_id=tenant_id,
                status=health_status,
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle system health check event",
                error=str(e),
                event=event
            )
    
    async def handle_system_alert(self, event: Dict[str, Any]) -> None:
        """Handle system alert event."""
        try:
            event_data = event['data']
            tenant_id = event['tenant_id']
            alert_type = event_data.get('alert_type', 'unknown')
            
            # Update alert metrics
            await self._update_tenant_metrics(tenant_id, 'system_alerts', 1)
            await self._update_tenant_metrics(tenant_id, f'alert_{alert_type}', 1)
            
            # Store alert
            alert_key = f"system_alert:{tenant_id}:{int(time.time())}"
            await self.redis.setex(alert_key, 86400, json.dumps(event_data))  # 24 hours TTL
            
            logger.warning(
                "System alert received",
                tenant_id=tenant_id,
                alert_type=alert_type,
                message=event_data.get('message'),
                event_id=event['event_id']
            )
            
        except Exception as e:
            logger.error(
                "Failed to handle system alert event",
                error=str(e),
                event=event
            )
    
    async def _update_tenant_metrics(self, tenant_id: str, metric_name: str, value: float) -> None:
        """Update tenant metrics."""
        try:
            metric_key = f"tenant_metrics:{tenant_id}:{metric_name}"
            await self.redis.incrbyfloat(metric_key, value)
            await self.redis.expire(metric_key, 86400)  # 24 hours TTL
        except Exception as e:
            logger.error("Failed to update tenant metrics", error=str(e))
    
    async def _get_misroute_rate(self, tenant_id: str) -> float:
        """Get misroute rate for tenant."""
        try:
            misroutes = await self.redis.get(f"tenant_metrics:{tenant_id}:router_misroutes") or 0
            decisions = await self.redis.get(f"tenant_metrics:{tenant_id}:router_decisions") or 1
            
            return float(misroutes) / float(decisions)
        except Exception as e:
            logger.error("Failed to get misroute rate", error=str(e))
            return 0.0
    
    async def _send_alert(self, tenant_id: str, message: str) -> None:
        """Send alert to tenant."""
        try:
            await self.event_bus.publish_event(
                EventType.SYSTEM_ALERT,
                {
                    'message': message,
                    'alert_type': 'threshold_exceeded',
                    'tenant_id': tenant_id
                },
                tenant_id,
                EventPriority.HIGH
            )
        except Exception as e:
            logger.error("Failed to send alert", error=str(e))
