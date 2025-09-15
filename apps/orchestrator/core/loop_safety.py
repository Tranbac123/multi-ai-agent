"""
Loop Safety Manager for Orchestrator

Implements comprehensive loop safety mechanisms:
- MAX_STEPS, MAX_WALL_MS, MAX_REPAIR_ATTEMPTS limits
- Progress tracking with oscillation detection
- Budget-aware degradation
- Metrics collection for loop monitoring
"""

import asyncio
import hashlib
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Any, Set, Tuple
import structlog
from opentelemetry import trace

logger = structlog.get_logger(__name__)
tracer = trace.get_tracer(__name__)


class LoopStatus(Enum):
    """Loop execution status."""
    RUNNING = "running"
    COMPLETED = "completed"
    CUT_SAFETY = "cut_safety"
    CUT_BUDGET = "cut_budget"
    CUT_NO_PROGRESS = "cut_no_progress"
    CUT_OSCILLATION = "cut_oscillation"
    CUT_TIMEOUT = "cut_timeout"


@dataclass
class ProgressMetrics:
    """Progress tracking metrics."""
    plan_hash: str = ""
    goals_left: int = 0
    evidence_size: int = 0
    distinct_tools_used: int = 0
    new_entities: int = 0
    timestamp: float = field(default_factory=time.time)


@dataclass
class LoopBudget:
    """Loop execution budget."""
    max_steps: int = 100
    max_wall_ms: int = 30000  # 30 seconds
    max_repair_attempts: int = 5
    no_progress_window_ms: int = 5000  # 5 seconds
    oscillation_threshold: int = 3
    cost_limit_usd: float = 0.10


@dataclass
class LoopState:
    """Current loop execution state."""
    run_id: str
    tenant_id: str
    workflow_id: str
    
    # Execution counters
    steps_taken: int = 0
    repair_attempts: int = 0
    start_time: float = field(default_factory=time.time)
    
    # Progress tracking
    progress_history: List[ProgressMetrics] = field(default_factory=list)
    state_hashes: Set[str] = field(default_factory=set)
    last_progress_time: float = field(default_factory=time.time)
    
    # Current status
    status: LoopStatus = LoopStatus.RUNNING
    cut_reason: Optional[str] = None
    
    # Metrics
    total_cost_usd: float = 0.0
    tokens_used: int = 0


class OscillationDetector:
    """Detects oscillation patterns in loop execution."""
    
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self.state_history: List[str] = []
    
    def add_state(self, state_hash: str) -> bool:
        """Add state hash and check for oscillation."""
        self.state_history.append(state_hash)
        
        # Keep only recent history
        if len(self.state_history) > self.threshold * 2:
            self.state_history = self.state_history[-self.threshold * 2:]
        
        # Check for oscillation pattern
        if len(self.state_history) >= self.threshold:
            recent_states = self.state_history[-self.threshold:]
            if len(set(recent_states)) == 1:
                logger.warning("Oscillation detected", 
                             state_hash=state_hash, 
                             threshold=self.threshold)
                return True
        
        return False


class LoopSafetyManager:
    """Manages loop safety and progress tracking."""
    
    def __init__(self, budget: LoopBudget = None):
        self.budget = budget or LoopBudget()
        self.oscillation_detector = OscillationDetector(self.budget.oscillation_threshold)
        self.active_loops: Dict[str, LoopState] = {}
        
        # Metrics (would be connected to Prometheus in production)
        self.metrics = {
            'loop_cut_total': 0,
            'no_progress_events_total': 0,
            'oscillation_detected_total': 0,
            'budget_exceeded_total': 0
        }
    
    def start_loop(self, run_id: str, tenant_id: str, workflow_id: str) -> LoopState:
        """Start tracking a new loop execution."""
        loop_state = LoopState(
            run_id=run_id,
            tenant_id=tenant_id,
            workflow_id=workflow_id
        )
        
        self.active_loops[run_id] = loop_state
        
        logger.info("Loop started", 
                   run_id=run_id, 
                   tenant_id=tenant_id, 
                   workflow_id=workflow_id)
        
        return loop_state
    
    def check_loop_safety(self, run_id: str) -> Tuple[bool, str]:
        """
        Check if loop should continue or be cut.
        
        Returns:
            (should_continue, reason_if_cut)
        """
        if run_id not in self.active_loops:
            return False, "loop_not_found"
        
        loop_state = self.active_loops[run_id]
        current_time = time.time()
        
        # Check step limit
        if loop_state.steps_taken >= self.budget.max_steps:
            loop_state.status = LoopStatus.CUT_SAFETY
            loop_state.cut_reason = f"max_steps_exceeded_{loop_state.steps_taken}"
            self._cut_loop(loop_state, "max_steps")
            return False, loop_state.cut_reason
        
        # Check wall time limit
        elapsed_ms = (current_time - loop_state.start_time) * 1000
        if elapsed_ms >= self.budget.max_wall_ms:
            loop_state.status = LoopStatus.CUT_TIMEOUT
            loop_state.cut_reason = f"max_wall_time_exceeded_{elapsed_ms}ms"
            self._cut_loop(loop_state, "max_wall_time")
            return False, loop_state.cut_reason
        
        # Check repair attempts
        if loop_state.repair_attempts >= self.budget.max_repair_attempts:
            loop_state.status = LoopStatus.CUT_SAFETY
            loop_state.cut_reason = f"max_repair_attempts_exceeded_{loop_state.repair_attempts}"
            self._cut_loop(loop_state, "max_repair_attempts")
            return False, loop_state.cut_reason
        
        # Check cost budget
        if loop_state.total_cost_usd >= self.budget.cost_limit_usd:
            loop_state.status = LoopStatus.CUT_BUDGET
            loop_state.cut_reason = f"cost_budget_exceeded_{loop_state.total_cost_usd}usd"
            self._cut_loop(loop_state, "cost_budget")
            return False, loop_state.cut_reason
        
        # Check for no progress
        no_progress_elapsed_ms = (current_time - loop_state.last_progress_time) * 1000
        if no_progress_elapsed_ms >= self.budget.no_progress_window_ms:
            loop_state.status = LoopStatus.CUT_NO_PROGRESS
            loop_state.cut_reason = f"no_progress_{no_progress_elapsed_ms}ms"
            self._cut_loop(loop_state, "no_progress")
            self.metrics['no_progress_events_total'] += 1
            return False, loop_state.cut_reason
        
        return True, ""
    
    def record_progress(self, run_id: str, plan_hash: str, goals_left: int, 
                       evidence_size: int, distinct_tools_used: int, 
                       new_entities: int) -> bool:
        """
        Record progress metrics and detect oscillation.
        
        Returns:
            True if progress was recorded, False if oscillation detected
        """
        if run_id not in self.active_loops:
            return False
        
        loop_state = self.active_loops[run_id]
        current_time = time.time()
        
        # Create progress metrics
        progress = ProgressMetrics(
            plan_hash=plan_hash,
            goals_left=goals_left,
            evidence_size=evidence_size,
            distinct_tools_used=distinct_tools_used,
            new_entities=new_entities,
            timestamp=current_time
        )
        
        # Generate state hash for oscillation detection
        state_hash = self._generate_state_hash(progress)
        
        # Check for oscillation
        if self.oscillation_detector.add_state(state_hash):
            loop_state.status = LoopStatus.CUT_OSCILLATION
            loop_state.cut_reason = "oscillation_detected"
            self._cut_loop(loop_state, "oscillation")
            self.metrics['oscillation_detected_total'] += 1
            return False
        
        # Record progress
        loop_state.progress_history.append(progress)
        loop_state.state_hashes.add(state_hash)
        loop_state.last_progress_time = current_time
        
        # Keep only recent progress history
        if len(loop_state.progress_history) > 20:
            loop_state.progress_history = loop_state.progress_history[-20:]
        
        logger.debug("Progress recorded", 
                    run_id=run_id,
                    goals_left=goals_left,
                    evidence_size=evidence_size,
                    distinct_tools_used=distinct_tools_used,
                    new_entities=new_entities)
        
        return True
    
    def increment_step(self, run_id: str):
        """Increment step counter."""
        if run_id in self.active_loops:
            self.active_loops[run_id].steps_taken += 1
    
    def increment_repair_attempt(self, run_id: str):
        """Increment repair attempt counter."""
        if run_id in self.active_loops:
            self.active_loops[run_id].repair_attempts += 1
    
    def add_cost(self, run_id: str, cost_usd: float):
        """Add cost to loop budget."""
        if run_id in self.active_loops:
            self.active_loops[run_id].total_cost_usd += cost_usd
    
    def add_tokens(self, run_id: str, tokens: int):
        """Add token usage to loop."""
        if run_id in self.active_loops:
            self.active_loops[run_id].tokens_used += tokens
    
    def complete_loop(self, run_id: str, success: bool = True):
        """Mark loop as completed."""
        if run_id in self.active_loops:
            loop_state = self.active_loops[run_id]
            loop_state.status = LoopStatus.COMPLETED if success else LoopStatus.CUT_SAFETY
            
            elapsed_ms = (time.time() - loop_state.start_time) * 1000
            
            logger.info("Loop completed", 
                       run_id=run_id,
                       status=loop_state.status.value,
                       steps_taken=loop_state.steps_taken,
                       elapsed_ms=elapsed_ms,
                       total_cost_usd=loop_state.total_cost_usd,
                       tokens_used=loop_state.tokens_used)
            
            # Remove from active loops
            del self.active_loops[run_id]
    
    def get_loop_state(self, run_id: str) -> Optional[LoopState]:
        """Get current loop state."""
        return self.active_loops.get(run_id)
    
    def _generate_state_hash(self, progress: ProgressMetrics) -> str:
        """Generate hash for state comparison."""
        state_str = f"{progress.plan_hash}:{progress.goals_left}:{progress.evidence_size}:{progress.distinct_tools_used}:{progress.new_entities}"
        return hashlib.md5(state_str.encode()).hexdigest()
    
    def _cut_loop(self, loop_state: LoopState, reason: str):
        """Cut loop execution."""
        elapsed_ms = (time.time() - loop_state.start_time) * 1000
        
        logger.warning("Loop cut", 
                      run_id=loop_state.run_id,
                      reason=reason,
                      steps_taken=loop_state.steps_taken,
                      elapsed_ms=elapsed_ms,
                      total_cost_usd=loop_state.total_cost_usd)
        
        self.metrics['loop_cut_total'] += 1
        
        # Remove from active loops
        if loop_state.run_id in self.active_loops:
            del self.active_loops[loop_state.run_id]
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current metrics."""
        return {
            **self.metrics,
            'active_loops': len(self.active_loops),
            'total_loops_tracked': sum(1 for _ in self.active_loops.values())
        }


class BudgetAwareDegradation:
    """Manages degradation based on budget consumption."""
    
    def __init__(self, safety_manager: LoopSafetyManager):
        self.safety_manager = safety_manager
    
    def should_degrade(self, run_id: str, degradation_type: str) -> bool:
        """Check if degradation should be applied."""
        loop_state = self.safety_manager.get_loop_state(run_id)
        if not loop_state:
            return False
        
        # Calculate budget consumption percentage
        cost_ratio = loop_state.total_cost_usd / self.safety_manager.budget.cost_limit_usd
        time_ratio = ((time.time() - loop_state.start_time) * 1000) / self.safety_manager.budget.max_wall_ms
        step_ratio = loop_state.steps_taken / self.safety_manager.budget.max_steps
        
        max_ratio = max(cost_ratio, time_ratio, step_ratio)
        
        # Apply degradation thresholds
        if degradation_type == "disable_critique" and max_ratio > 0.6:
            return True
        elif degradation_type == "disable_debate" and max_ratio > 0.7:
            return True
        elif degradation_type == "shrink_context" and max_ratio > 0.8:
            return True
        elif degradation_type == "prefer_slm" and max_ratio > 0.9:
            return True
        
        return False
    
    def get_degradation_strategy(self, run_id: str) -> List[str]:
        """Get list of degradation strategies to apply."""
        strategies = []
        
        if self.should_degrade(run_id, "disable_critique"):
            strategies.append("disable_critique")
        if self.should_degrade(run_id, "disable_debate"):
            strategies.append("disable_debate")
        if self.should_degrade(run_id, "shrink_context"):
            strategies.append("shrink_context")
        if self.should_degrade(run_id, "prefer_slm"):
            strategies.append("prefer_slm")
        
        return strategies


# Global safety manager instance
_safety_manager: Optional[LoopSafetyManager] = None


def get_safety_manager() -> LoopSafetyManager:
    """Get global safety manager instance."""
    global _safety_manager
    if _safety_manager is None:
        _safety_manager = LoopSafetyManager()
    return _safety_manager


def get_degradation_manager() -> BudgetAwareDegradation:
    """Get degradation manager."""
    return BudgetAwareDegradation(get_safety_manager())
