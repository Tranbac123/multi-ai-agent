"""
Integration tests for loop safety mechanisms.

Tests loop cutting, progress tracking, oscillation detection, and budget management.
"""

import pytest
import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

from apps.orchestrator.core.loop_safety import (
    LoopSafetyManager, LoopBudget, LoopStatus, 
    OscillationDetector, BudgetAwareDegradation
)
from apps.orchestrator.core.enhanced_orchestrator import EnhancedOrchestrator


@pytest.fixture
def loop_budget():
    """Create test loop budget with lower limits for faster testing."""
    return LoopBudget(
        max_steps=10,
        max_wall_ms=5000,  # 5 seconds
        max_repair_attempts=3,
        no_progress_window_ms=1000,  # 1 second
        oscillation_threshold=3,
        cost_limit_usd=0.01
    )


@pytest.fixture
def safety_manager(loop_budget):
    """Create safety manager with test budget."""
    return LoopSafetyManager(budget=loop_budget)


@pytest.fixture
def mock_workflow_engine():
    """Mock workflow engine."""
    engine = AsyncMock()
    engine.get_current_plan = AsyncMock(return_value={
        "hash": "test_hash",
        "remaining_goals": ["goal1", "goal2"],
        "next_action": {
            "tool": "test_tool",
            "args": {"param": "value"}
        }
    })
    return engine


@pytest.fixture
def mock_tool_registry():
    """Mock tool registry."""
    registry = AsyncMock()
    mock_tool = AsyncMock()
    mock_tool.execute = AsyncMock(return_value={
        "evidence": ["evidence1"],
        "entities": ["entity1"],
        "cost_usd": 0.001,
        "tokens_used": 100
    })
    registry.get_tool.return_value = mock_tool
    return registry


@pytest.fixture
def enhanced_orchestrator(mock_workflow_engine, mock_tool_registry, loop_budget):
    """Create enhanced orchestrator for testing."""
    return EnhancedOrchestrator(
        workflow_engine=mock_workflow_engine,
        tool_registry=mock_tool_registry,
        budget=loop_budget
    )


class TestLoopSafetyManager:
    """Test loop safety manager functionality."""
    
    def test_start_loop(self, safety_manager):
        """Test starting a new loop."""
        run_id = "test_run_123"
        tenant_id = "tenant_123"
        workflow_id = "workflow_123"
        
        loop_state = safety_manager.start_loop(run_id, tenant_id, workflow_id)
        
        assert loop_state.run_id == run_id
        assert loop_state.tenant_id == tenant_id
        assert loop_state.workflow_id == workflow_id
        assert loop_state.status == LoopStatus.RUNNING
        assert run_id in safety_manager.active_loops
    
    def test_step_limit_cut(self, safety_manager):
        """Test loop cutting due to step limit."""
        run_id = "test_run_123"
        tenant_id = "tenant_123"
        workflow_id = "workflow_123"
        
        safety_manager.start_loop(run_id, tenant_id, workflow_id)
        
        # Exceed step limit
        for _ in range(safety_manager.budget.max_steps + 1):
            safety_manager.increment_step(run_id)
        
        should_continue, reason = safety_manager.check_loop_safety(run_id)
        
        assert not should_continue
        assert "max_steps_exceeded" in reason
        assert run_id not in safety_manager.active_loops
    
    def test_wall_time_cut(self, safety_manager):
        """Test loop cutting due to wall time limit."""
        run_id = "test_run_123"
        tenant_id = "tenant_123"
        workflow_id = "workflow_123"
        
        safety_manager.start_loop(run_id, tenant_id, workflow_id)
        
        # Mock time to exceed wall time limit
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 10  # 10 seconds later
            
            should_continue, reason = safety_manager.check_loop_safety(run_id)
            
            assert not should_continue
            assert "max_wall_time_exceeded" in reason
    
    def test_repair_attempts_cut(self, safety_manager):
        """Test loop cutting due to repair attempts limit."""
        run_id = "test_run_123"
        tenant_id = "tenant_123"
        workflow_id = "workflow_123"
        
        safety_manager.start_loop(run_id, tenant_id, workflow_id)
        
        # Exceed repair attempts limit
        for _ in range(safety_manager.budget.max_repair_attempts + 1):
            safety_manager.increment_repair_attempt(run_id)
        
        should_continue, reason = safety_manager.check_loop_safety(run_id)
        
        assert not should_continue
        assert "max_repair_attempts_exceeded" in reason
    
    def test_cost_budget_cut(self, safety_manager):
        """Test loop cutting due to cost budget limit."""
        run_id = "test_run_123"
        tenant_id = "tenant_123"
        workflow_id = "workflow_123"
        
        safety_manager.start_loop(run_id, tenant_id, workflow_id)
        
        # Exceed cost budget
        safety_manager.add_cost(run_id, safety_manager.budget.cost_limit_usd + 0.001)
        
        should_continue, reason = safety_manager.check_loop_safety(run_id)
        
        assert not should_continue
        assert "cost_budget_exceeded" in reason
    
    def test_no_progress_cut(self, safety_manager):
        """Test loop cutting due to no progress."""
        run_id = "test_run_123"
        tenant_id = "tenant_123"
        workflow_id = "workflow_123"
        
        safety_manager.start_loop(run_id, tenant_id, workflow_id)
        
        # Mock time to exceed no progress window
        with patch('time.time') as mock_time:
            mock_time.return_value = time.time() + 2  # 2 seconds later
            
            should_continue, reason = safety_manager.check_loop_safety(run_id)
            
            assert not should_continue
            assert "no_progress" in reason
            assert safety_manager.metrics['no_progress_events_total'] == 1
    
    def test_progress_recording(self, safety_manager):
        """Test progress recording and tracking."""
        run_id = "test_run_123"
        tenant_id = "tenant_123"
        workflow_id = "workflow_123"
        
        safety_manager.start_loop(run_id, tenant_id, workflow_id)
        
        # Record progress
        success = safety_manager.record_progress(
            run_id=run_id,
            plan_hash="hash1",
            goals_left=5,
            evidence_size=10,
            distinct_tools_used=2,
            new_entities=3
        )
        
        assert success
        assert len(safety_manager.active_loops[run_id].progress_history) == 1
        
        progress = safety_manager.active_loops[run_id].progress_history[0]
        assert progress.plan_hash == "hash1"
        assert progress.goals_left == 5
        assert progress.evidence_size == 10
        assert progress.distinct_tools_used == 2
        assert progress.new_entities == 3
    
    def test_oscillation_detection(self, safety_manager):
        """Test oscillation detection."""
        run_id = "test_run_123"
        tenant_id = "tenant_123"
        workflow_id = "workflow_123"
        
        safety_manager.start_loop(run_id, tenant_id, workflow_id)
        
        # Record same progress multiple times (oscillation)
        for _ in range(4):  # Exceed threshold
            success = safety_manager.record_progress(
                run_id=run_id,
                plan_hash="same_hash",
                goals_left=5,
                evidence_size=10,
                distinct_tools_used=2,
                new_entities=3
            )
        
        assert not success  # Should be cut due to oscillation
        assert safety_manager.metrics['oscillation_detected_total'] == 1
    
    def test_loop_completion(self, safety_manager):
        """Test loop completion."""
        run_id = "test_run_123"
        tenant_id = "tenant_123"
        workflow_id = "workflow_123"
        
        safety_manager.start_loop(run_id, tenant_id, workflow_id)
        
        # Add some metrics
        safety_manager.add_cost(run_id, 0.005)
        safety_manager.add_tokens(run_id, 500)
        
        # Complete loop
        safety_manager.complete_loop(run_id, success=True)
        
        assert run_id not in safety_manager.active_loops


class TestOscillationDetector:
    """Test oscillation detection functionality."""
    
    def test_no_oscillation(self):
        """Test normal state progression (no oscillation)."""
        detector = OscillationDetector(threshold=3)
        
        # Different states - no oscillation
        states = ["hash1", "hash2", "hash3", "hash1", "hash2"]
        
        oscillation_detected = False
        for state in states:
            if detector.add_state(state):
                oscillation_detected = True
                break
        
        assert not oscillation_detected
    
    def test_oscillation_detected(self):
        """Test oscillation detection."""
        detector = OscillationDetector(threshold=3)
        
        # Same state repeated - oscillation
        oscillation_detected = False
        for _ in range(4):
            if detector.add_state("same_hash"):
                oscillation_detected = True
                break
        
        assert oscillation_detected
    
    def test_state_history_limit(self):
        """Test state history is limited."""
        detector = OscillationDetector(threshold=3)
        
        # Add many states
        for i in range(10):
            detector.add_state(f"hash{i}")
        
        # Should only keep recent history
        assert len(detector.state_history) <= 6  # threshold * 2


class TestBudgetAwareDegradation:
    """Test budget-aware degradation."""
    
    def test_no_degradation_early(self, safety_manager):
        """Test no degradation when budget is low."""
        degradation_manager = BudgetAwareDegradation(safety_manager)
        
        run_id = "test_run_123"
        safety_manager.start_loop(run_id, "tenant_123", "workflow_123")
        
        # Low budget consumption
        safety_manager.add_cost(run_id, 0.001)  # 1% of budget
        
        assert not degradation_manager.should_degrade(run_id, "disable_critique")
        assert not degradation_manager.should_degrade(run_id, "disable_debate")
        assert not degradation_manager.should_degrade(run_id, "shrink_context")
        assert not degradation_manager.should_degrade(run_id, "prefer_slm")
    
    def test_degradation_thresholds(self, safety_manager):
        """Test degradation at different thresholds."""
        degradation_manager = BudgetAwareDegradation(safety_manager)
        
        run_id = "test_run_123"
        safety_manager.start_loop(run_id, "tenant_123", "workflow_123")
        
        # High cost consumption (70% of budget)
        safety_manager.add_cost(run_id, 0.007)
        
        # Should trigger some degradations
        assert degradation_manager.should_degrade(run_id, "disable_critique")
        assert degradation_manager.should_degrade(run_id, "disable_debate")
        assert not degradation_manager.should_degrade(run_id, "shrink_context")
        assert not degradation_manager.should_degrade(run_id, "prefer_slm")
    
    def test_degradation_strategies(self, safety_manager):
        """Test getting degradation strategies."""
        degradation_manager = BudgetAwareDegradation(safety_manager)
        
        run_id = "test_run_123"
        safety_manager.start_loop(run_id, "tenant_123", "workflow_123")
        
        # Very high cost consumption (90% of budget)
        safety_manager.add_cost(run_id, 0.009)
        
        strategies = degradation_manager.get_degradation_strategy(run_id)
        
        assert "disable_critique" in strategies
        assert "disable_debate" in strategies
        assert "shrink_context" in strategies
        assert "prefer_slm" in strategies


class TestEnhancedOrchestrator:
    """Test enhanced orchestrator integration."""
    
    @pytest.mark.asyncio
    async def test_workflow_execution_success(self, enhanced_orchestrator):
        """Test successful workflow execution."""
        # Mock workflow to complete quickly
        enhanced_orchestrator.workflow_engine.get_current_plan = AsyncMock(
            side_effect=[
                {"hash": "hash1", "remaining_goals": ["goal1"], "next_action": {"tool": "test_tool", "args": {}}},
                {"hash": "hash2", "remaining_goals": [], "next_action": None}
            ]
        )
        
        result = await enhanced_orchestrator.execute_workflow(
            tenant_id="tenant_123",
            workflow_id="workflow_123",
            input_data={"input": "test"},
            context={}
        )
        
        assert result["status"] == "completed"
        assert result["steps_taken"] == 2
        assert "run_id" in result
    
    @pytest.mark.asyncio
    async def test_workflow_execution_step_limit(self, enhanced_orchestrator):
        """Test workflow execution cut due to step limit."""
        # Mock workflow that never completes
        enhanced_orchestrator.workflow_engine.get_current_plan = AsyncMock(
            return_value={
                "hash": "hash1", 
                "remaining_goals": ["goal1"], 
                "next_action": {"tool": "test_tool", "args": {}}
            }
        )
        
        result = await enhanced_orchestrator.execute_workflow(
            tenant_id="tenant_123",
            workflow_id="workflow_123",
            input_data={"input": "test"},
            context={}
        )
        
        # Should be cut due to step limit
        assert result["steps_taken"] >= enhanced_orchestrator.safety_manager.budget.max_steps
    
    @pytest.mark.asyncio
    async def test_workflow_execution_cost_limit(self, enhanced_orchestrator):
        """Test workflow execution cut due to cost limit."""
        # Mock tool that returns high cost
        mock_tool = AsyncMock()
        mock_tool.execute = AsyncMock(return_value={
            "evidence": [],
            "entities": [],
            "cost_usd": 0.02,  # Exceeds budget
            "tokens_used": 100
        })
        enhanced_orchestrator.tool_registry.get_tool.return_value = mock_tool
        
        # Mock workflow that never completes
        enhanced_orchestrator.workflow_engine.get_current_plan = AsyncMock(
            return_value={
                "hash": "hash1", 
                "remaining_goals": ["goal1"], 
                "next_action": {"tool": "test_tool", "args": {}}
            }
        )
        
        result = await enhanced_orchestrator.execute_workflow(
            tenant_id="tenant_123",
            workflow_id="workflow_123",
            input_data={"input": "test"},
            context={}
        )
        
        # Should be cut due to cost limit
        assert result["total_cost_usd"] >= enhanced_orchestrator.safety_manager.budget.cost_limit_usd
    
    def test_safety_metrics(self, enhanced_orchestrator):
        """Test safety metrics collection."""
        metrics = enhanced_orchestrator.get_safety_metrics()
        
        assert "loop_cut_total" in metrics
        assert "no_progress_events_total" in metrics
        assert "oscillation_detected_total" in metrics
        assert "budget_exceeded_total" in metrics
        assert "active_loops" in metrics
    
    def test_active_loops_info(self, enhanced_orchestrator):
        """Test active loops information."""
        # Start a loop
        run_id = enhanced_orchestrator.safety_manager.start_loop("run_123", "tenant_123", "workflow_123")
        
        active_info = enhanced_orchestrator.get_active_loops()
        
        assert "run_123" in active_info
        assert active_info["run_123"]["tenant_id"] == "tenant_123"
        assert active_info["run_123"]["workflow_id"] == "workflow_123"
        assert active_info["run_123"]["status"] == "running"


@pytest.mark.asyncio
async def test_synthetic_loop_fixture():
    """Test synthetic loop that triggers safety cuts."""
    budget = LoopBudget(
        max_steps=5,
        max_wall_ms=1000,
        max_repair_attempts=2,
        no_progress_window_ms=500,
        oscillation_threshold=2,
        cost_limit_usd=0.005
    )
    
    safety_manager = LoopSafetyManager(budget=budget)
    
    # Create synthetic loop that exceeds limits
    run_id = "synthetic_run"
    safety_manager.start_loop(run_id, "tenant_123", "workflow_123")
    
    # Exceed step limit
    for _ in range(6):
        safety_manager.increment_step(run_id)
    
    should_continue, reason = safety_manager.check_loop_safety(run_id)
    
    assert not should_continue
    assert "max_steps_exceeded" in reason
    assert safety_manager.metrics['loop_cut_total'] == 1


@pytest.mark.asyncio
async def test_budgets_respected():
    """Test that all budget limits are respected."""
    budget = LoopBudget(
        max_steps=3,
        max_wall_ms=500,
        max_repair_attempts=2,
        no_progress_window_ms=200,
        oscillation_threshold=2,
        cost_limit_usd=0.002
    )
    
    safety_manager = LoopSafetyManager(budget=budget)
    
    # Test step budget
    run_id = "step_test"
    safety_manager.start_loop(run_id, "tenant_123", "workflow_123")
    for _ in range(4):
        safety_manager.increment_step(run_id)
    
    should_continue, _ = safety_manager.check_loop_safety(run_id)
    assert not should_continue
    
    # Test cost budget
    run_id = "cost_test"
    safety_manager.start_loop(run_id, "tenant_123", "workflow_123")
    safety_manager.add_cost(run_id, 0.003)
    
    should_continue, _ = safety_manager.check_loop_safety(run_id)
    assert not should_continue
    
    # Test repair attempts budget
    run_id = "repair_test"
    safety_manager.start_loop(run_id, "tenant_123", "workflow_123")
    for _ in range(3):
        safety_manager.increment_repair_attempt(run_id)
    
    should_continue, _ = safety_manager.check_loop_safety(run_id)
    assert not should_continue
