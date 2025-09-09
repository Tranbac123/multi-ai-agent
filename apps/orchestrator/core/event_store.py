"""Event store for event sourcing."""

import asyncio
import json
from typing import Dict, Any, Optional, List
from uuid import UUID
from datetime import datetime
import structlog
from opentelemetry import trace

from libs.contracts.agent import AgentRun
from libs.contracts.tool import ToolCall, ToolResult
from libs.contracts.message import MessageSpec, MessageRole

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class EventStore:
    """Event store for storing and retrieving events."""
    
    def __init__(self):
        self.events: Dict[UUID, List[Dict[str, Any]]] = {}
        self._ready = False
    
    def initialize(self):
        """Initialize event store."""
        try:
            self._ready = True
            logger.info("Event store initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize event store", error=str(e))
            self._ready = False
    
    def is_ready(self) -> bool:
        """Check if event store is ready."""
        return self._ready
    
    async def store_event(
        self,
        run_id: UUID,
        event_type: str,
        data: Dict[str, Any]
    ) -> None:
        """Store event in event store."""
        with tracer.start_as_current_span("store_event") as span:
            span.set_attribute("run_id", str(run_id))
            span.set_attribute("event_type", event_type)
            
            try:
                # Create event
                event = {
                    "event_id": str(uuid4()),
                    "run_id": str(run_id),
                    "event_type": event_type,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat(),
                    "version": 1
                }
                
                # Store event
                if run_id not in self.events:
                    self.events[run_id] = []
                
                self.events[run_id].append(event)
                
                logger.debug(
                    "Event stored",
                    run_id=str(run_id),
                    event_type=event_type,
                    event_id=event["event_id"]
                )
                
            except Exception as e:
                logger.error(
                    "Failed to store event",
                    run_id=str(run_id),
                    event_type=event_type,
                    error=str(e)
                )
                raise
    
    async def get_events(self, run_id: UUID) -> List[Dict[str, Any]]:
        """Get events for run."""
        with tracer.start_as_current_span("get_events") as span:
            span.set_attribute("run_id", str(run_id))
            
            try:
                events = self.events.get(run_id, [])
                
                logger.debug(
                    "Events retrieved",
                    run_id=str(run_id),
                    event_count=len(events)
                )
                
                return events
                
            except Exception as e:
                logger.error(
                    "Failed to get events",
                    run_id=str(run_id),
                    error=str(e)
                )
                raise
    
    async def get_events_by_type(
        self,
        run_id: UUID,
        event_type: str
    ) -> List[Dict[str, Any]]:
        """Get events by type for run."""
        with tracer.start_as_current_span("get_events_by_type") as span:
            span.set_attribute("run_id", str(run_id))
            span.set_attribute("event_type", event_type)
            
            try:
                events = self.events.get(run_id, [])
                filtered_events = [
                    event for event in events
                    if event["event_type"] == event_type
                ]
                
                logger.debug(
                    "Events retrieved by type",
                    run_id=str(run_id),
                    event_type=event_type,
                    event_count=len(filtered_events)
                )
                
                return filtered_events
                
            except Exception as e:
                logger.error(
                    "Failed to get events by type",
                    run_id=str(run_id),
                    event_type=event_type,
                    error=str(e)
                )
                raise
    
    async def get_latest_event(
        self,
        run_id: UUID,
        event_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Get latest event for run."""
        with tracer.start_as_current_span("get_latest_event") as span:
            span.set_attribute("run_id", str(run_id))
            span.set_attribute("event_type", event_type or "any")
            
            try:
                events = self.events.get(run_id, [])
                
                if event_type:
                    events = [
                        event for event in events
                        if event["event_type"] == event_type
                    ]
                
                if not events:
                    return None
                
                # Sort by timestamp and get latest
                latest_event = max(events, key=lambda x: x["timestamp"])
                
                logger.debug(
                    "Latest event retrieved",
                    run_id=str(run_id),
                    event_type=event_type or "any",
                    event_id=latest_event["event_id"]
                )
                
                return latest_event
                
            except Exception as e:
                logger.error(
                    "Failed to get latest event",
                    run_id=str(run_id),
                    event_type=event_type,
                    error=str(e)
                )
                raise
    
    async def replay_events(self, run_id: UUID) -> AgentRun:
        """Replay events to reconstruct run state."""
        with tracer.start_as_current_span("replay_events") as span:
            span.set_attribute("run_id", str(run_id))
            
            try:
                # Get all events for run
                events = await self.get_events(run_id)
                
                if not events:
                    raise ValueError(f"No events found for run {run_id}")
                
                # Sort events by timestamp
                events.sort(key=lambda x: x["timestamp"])
                
                # Reconstruct run state from events
                run_state = await self._reconstruct_run_state(events)
                
                logger.info(
                    "Events replayed successfully",
                    run_id=str(run_id),
                    event_count=len(events)
                )
                
                return run_state
                
            except Exception as e:
                logger.error(
                    "Failed to replay events",
                    run_id=str(run_id),
                    error=str(e)
                )
                raise
    
    async def _reconstruct_run_state(self, events: List[Dict[str, Any]]) -> AgentRun:
        """Reconstruct run state from events."""
        try:
            # Initialize run state
            run_state = {
                "run_id": None,
                "tenant_id": None,
                "workflow": "default",
                "status": "pending",
                "agent_spec": None,
                "context": {},
                "plan": [],
                "artifacts": {},
                "tokens_in": 0,
                "tokens_out": 0,
                "cost_usd": 0.0,
                "created_at": None,
                "finished_at": None,
                "error": None
            }
            
            # Process events in order
            for event in events:
                await self._apply_event(run_state, event)
            
            # Create AgentRun from state
            run = AgentRun(
                run_id=UUID(run_state["run_id"]),
                tenant_id=UUID(run_state["tenant_id"]),
                workflow=run_state["workflow"],
                status=run_state["status"],
                agent_spec=run_state["agent_spec"],
                context=run_state["context"],
                plan=run_state["plan"],
                artifacts=run_state["artifacts"],
                tokens_in=run_state["tokens_in"],
                tokens_out=run_state["tokens_out"],
                cost_usd=run_state["cost_usd"],
                created_at=datetime.fromisoformat(run_state["created_at"]),
                finished_at=datetime.fromisoformat(run_state["finished_at"]) if run_state["finished_at"] else None,
                error=run_state["error"]
            )
            
            return run
            
        except Exception as e:
            logger.error("Failed to reconstruct run state", error=str(e))
            raise
    
    async def _apply_event(self, run_state: Dict[str, Any], event: Dict[str, Any]) -> None:
        """Apply event to run state."""
        event_type = event["event_type"]
        data = event["data"]
        
        if event_type == "run_requested":
            run_state["run_id"] = str(event["run_id"])
            run_state["tenant_id"] = data.get("tenant_id")
            run_state["agent_spec"] = data.get("agent_spec")
            run_state["context"] = data.get("context", {})
            run_state["created_at"] = event["timestamp"]
        
        elif event_type == "run_started":
            run_state["status"] = "running"
        
        elif event_type == "run_completed":
            run_state["status"] = "completed"
            run_state["tokens_in"] = data.get("tokens_in", 0)
            run_state["tokens_out"] = data.get("tokens_out", 0)
            run_state["cost_usd"] = data.get("cost_usd", 0.0)
            run_state["artifacts"] = data.get("artifacts", {})
            run_state["finished_at"] = event["timestamp"]
        
        elif event_type == "run_failed":
            run_state["status"] = "failed"
            run_state["error"] = data.get("error")
            run_state["finished_at"] = event["timestamp"]
        
        elif event_type == "run_cancelled":
            run_state["status"] = "cancelled"
            run_state["finished_at"] = event["timestamp"]
        
        elif event_type == "step_completed":
            # Update tokens and cost
            run_state["tokens_in"] += data.get("tokens_in", 0)
            run_state["tokens_out"] += data.get("tokens_out", 0)
            run_state["cost_usd"] += data.get("cost_usd", 0.0)
            
            # Update artifacts
            if "artifacts" in data:
                run_state["artifacts"].update(data["artifacts"])
        
        elif event_type == "tool_call_succeeded":
            # Update tokens and cost
            run_state["tokens_in"] += data.get("tokens_used", 0)
            run_state["cost_usd"] += data.get("cost_usd", 0.0)
        
        # Add more event types as needed
    
    async def get_event_statistics(self, run_id: UUID) -> Dict[str, Any]:
        """Get event statistics for run."""
        try:
            events = await self.get_events(run_id)
            
            if not events:
                return {
                    "total_events": 0,
                    "event_types": {},
                    "first_event": None,
                    "last_event": None
                }
            
            # Count event types
            event_types = {}
            for event in events:
                event_type = event["event_type"]
                event_types[event_type] = event_types.get(event_type, 0) + 1
            
            # Get first and last event timestamps
            first_event = min(events, key=lambda x: x["timestamp"])
            last_event = max(events, key=lambda x: x["timestamp"])
            
            return {
                "total_events": len(events),
                "event_types": event_types,
                "first_event": first_event["timestamp"],
                "last_event": last_event["timestamp"]
            }
            
        except Exception as e:
            logger.error(
                "Failed to get event statistics",
                run_id=str(run_id),
                error=str(e)
            )
            raise
