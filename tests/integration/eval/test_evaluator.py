"""Test evaluator functionality."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from uuid import uuid4, UUID

from eval.evaluator import Evaluator
from eval.judges.llm_judge import LLMJudgeConfig
from eval.golden_tasks.customer_support import GoldenTask
from libs.contracts.router import RouterDecisionRequest, RouterDecision, RouterTier


class TestEvaluator:
    """Test Evaluator functionality."""

    @pytest.fixture
    def evaluator(self):
        """Create Evaluator instance."""
        judge_config = LLMJudgeConfig(
            model_name="gpt-4",
            api_key="test-key",
            temperature=0.0
        )
        return Evaluator(judge_config)

    @pytest.fixture
    def mock_router_engine(self):
        """Create mock router engine."""
        router_engine = Mock()
        router_engine.route = AsyncMock()
        return router_engine

    @pytest.fixture
    def mock_orchestrator_engine(self):
        """Create mock orchestrator engine."""
        orchestrator_engine = Mock()
        orchestrator_engine.create_run = AsyncMock()
        orchestrator_engine.start_run = AsyncMock()
        orchestrator_engine.get_run = AsyncMock()
        return orchestrator_engine

    @pytest.fixture
    def sample_golden_task(self):
        """Create sample golden task."""
        return GoldenTask(
            task_id="test_task_1",
            name="Customer Support Task",
            description="Help customer with order issue",
            difficulty="medium",
            domain="customer_support",
            category="order_management",
            input_data={
                "user_message": "I need help with my order #12345",
                "customer_id": "cust_123"
            },
            expected_output={
                "response": "I'll help you with your order",
                "actions": ["lookup_order", "resolve_issue"]
            },
            expected_tier=RouterTier.SLM_B,
            expected_confidence=0.8,
            expected_cost_usd=0.005,
            expected_latency_ms=800
        )

    @pytest.mark.asyncio
    async def test_evaluator_initialization(self, evaluator):
        """Test evaluator initialization."""
        assert not evaluator.is_ready()
        
        with patch.object(evaluator.judge, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_init.return_value = None
            
            await evaluator.initialize()
            
            assert evaluator.is_ready()
            mock_init.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluator_initialization_failure(self, evaluator):
        """Test evaluator initialization failure."""
        with patch.object(evaluator.judge, 'initialize', new_callable=AsyncMock) as mock_init:
            mock_init.side_effect = Exception("Judge initialization failed")
            
            await evaluator.initialize()
            
            assert not evaluator.is_ready()

    @pytest.mark.asyncio
    async def test_evaluate_router_not_ready(self, evaluator):
        """Test router evaluation when not ready."""
        with pytest.raises(RuntimeError, match="Evaluator not initialized"):
            await evaluator.evaluate_router(Mock())

    @pytest.mark.asyncio
    async def test_evaluate_router_success(self, evaluator, mock_router_engine, sample_golden_task):
        """Test successful router evaluation."""
        # Initialize evaluator
        with patch.object(evaluator.judge, 'initialize', new_callable=AsyncMock):
            await evaluator.initialize()
        
        # Mock golden tasks
        with patch.object(evaluator.golden_tasks, 'get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = [sample_golden_task]
            
            # Mock router decision
            mock_decision = RouterDecision(
                tier=RouterTier.SLM_B,
                confidence=0.85,
                expected_cost_usd=0.005,
                expected_latency_ms=750,
                reasoning="Task complexity matches SLM_B tier"
            )
            mock_router_engine.route.return_value = mock_decision
            
            # Mock judge result
            mock_judge_result = Mock()
            mock_judge_result.score = 0.9
            mock_judge_result.reasoning = "Good tier selection"
            mock_judge_result.metrics = {"accuracy": 0.9}
            
            with patch.object(evaluator.judge, 'judge_router_decision', new_callable=AsyncMock) as mock_judge:
                mock_judge.return_value = mock_judge_result
                
                report = await evaluator.evaluate_router(mock_router_engine)
        
        # Verify results
        assert report.evaluation_type == "router"
        assert report.total_tasks == 1
        assert report.successful_tasks == 1
        assert report.metrics.average_score == 0.9
        assert report.metrics.tier_accuracy == 1.0  # Expected and actual tier match
        
        # Verify router was called
        mock_router_engine.route.assert_called_once()
        call_args = mock_router_engine.route.call_args[0][0]
        assert isinstance(call_args, RouterDecisionRequest)
        assert call_args.tenant_id == UUID("123e4567-e89b-12d3-a456-426614174000")

    @pytest.mark.asyncio
    async def test_evaluate_router_with_task_filter(self, evaluator, mock_router_engine):
        """Test router evaluation with task filter."""
        # Initialize evaluator
        with patch.object(evaluator.judge, 'initialize', new_callable=AsyncMock):
            await evaluator.initialize()
        
        # Create multiple tasks with different difficulties
        tasks = [
            GoldenTask(
                task_id="task_1", name="Task 1", description="Easy task",
                difficulty="easy", domain="support", category="general",
                input_data={"message": "Hello"}, expected_output={"response": "Hi"},
                expected_tier=RouterTier.SLM_A, expected_confidence=0.9,
                expected_cost_usd=0.001, expected_latency_ms=200
            ),
            GoldenTask(
                task_id="task_2", name="Task 2", description="Hard task",
                difficulty="hard", domain="support", category="general",
                input_data={"message": "Complex query"}, expected_output={"response": "Complex answer"},
                expected_tier=RouterTier.LLM, expected_confidence=0.7,
                expected_cost_usd=0.01, expected_latency_ms=2000
            )
        ]
        
        with patch.object(evaluator.golden_tasks, 'get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = tasks
            
            # Mock router and judge
            mock_decision = RouterDecision(
                tier=RouterTier.SLM_A, confidence=0.8,
                expected_cost_usd=0.001, expected_latency_ms=200,
                reasoning="Simple task"
            )
            mock_router_engine.route.return_value = mock_decision
            
            mock_judge_result = Mock()
            mock_judge_result.score = 0.8
            mock_judge_result.reasoning = "Good"
            mock_judge_result.metrics = {}
            
            with patch.object(evaluator.judge, 'judge_router_decision', new_callable=AsyncMock) as mock_judge:
                mock_judge.return_value = mock_judge_result
                
                # Filter for easy tasks only
                task_filter = {"difficulty": "easy"}
                report = await evaluator.evaluate_router(mock_router_engine, task_filter)
        
        # Should only evaluate easy tasks
        assert report.total_tasks == 1
        mock_router_engine.route.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_router_task_failure(self, evaluator, mock_router_engine, sample_golden_task):
        """Test router evaluation with task failure."""
        # Initialize evaluator
        with patch.object(evaluator.judge, 'initialize', new_callable=AsyncMock):
            await evaluator.initialize()
        
        with patch.object(evaluator.golden_tasks, 'get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = [sample_golden_task]
            
            # Mock router failure
            mock_router_engine.route.side_effect = Exception("Router error")
            
            report = await evaluator.evaluate_router(mock_router_engine)
        
        # Verify failure handling
        assert report.total_tasks == 1
        assert report.successful_tasks == 0
        assert report.metrics.average_score == 0.0
        
        # Check result contains error
        assert len(report.results) == 1
        result = report.results[0]
        assert result["task_id"] == sample_golden_task.task_id
        assert result["success"] is False
        assert "Router error" in result["error"]

    @pytest.mark.asyncio
    async def test_evaluate_agent_success(self, evaluator, mock_orchestrator_engine, sample_golden_task):
        """Test successful agent evaluation."""
        # Initialize evaluator
        with patch.object(evaluator.judge, 'initialize', new_callable=AsyncMock):
            await evaluator.initialize()
        
        with patch.object(evaluator.golden_tasks, 'get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = [sample_golden_task]
            
            # Mock orchestrator run
            mock_run = Mock()
            mock_run.run_id = uuid4()
            mock_run.tenant_id = UUID("123e4567-e89b-12d3-a456-426614174000")
            mock_run.status = "completed"
            mock_run.tokens_in = 100
            mock_run.tokens_out = 50
            mock_run.cost_usd = 0.005
            
            mock_orchestrator_engine.create_run.return_value = mock_run
            mock_orchestrator_engine.get_run.return_value = mock_run
            
            # Mock judge result
            mock_judge_result = Mock()
            mock_judge_result.score = 0.85
            mock_judge_result.reasoning = "Good response"
            mock_judge_result.metrics = {"quality": 0.85}
            
            with patch.object(evaluator.judge, 'judge_agent_response', new_callable=AsyncMock) as mock_judge:
                mock_judge.return_value = mock_judge_result
                
                report = await evaluator.evaluate_agent(mock_orchestrator_engine)
        
        # Verify results
        assert report.evaluation_type == "agent"
        assert report.total_tasks == 1
        assert report.successful_tasks == 1
        assert report.metrics.average_score == 0.85
        
        # Verify orchestrator was called
        mock_orchestrator_engine.create_run.assert_called_once()
        mock_orchestrator_engine.start_run.assert_called_once()
        mock_orchestrator_engine.get_run.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_end_to_end_success(self, evaluator, mock_router_engine, mock_orchestrator_engine, sample_golden_task):
        """Test successful end-to-end evaluation."""
        # Initialize evaluator
        with patch.object(evaluator.judge, 'initialize', new_callable=AsyncMock):
            await evaluator.initialize()
        
        with patch.object(evaluator.golden_tasks, 'get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = [sample_golden_task]
            
            # Mock router decision
            mock_decision = RouterDecision(
                tier=RouterTier.SLM_B, confidence=0.85,
                expected_cost_usd=0.005, expected_latency_ms=750,
                reasoning="Good tier selection"
            )
            mock_router_engine.route.return_value = mock_decision
            
            # Mock orchestrator run
            mock_run = Mock()
            mock_run.run_id = uuid4()
            mock_run.tenant_id = UUID("123e4567-e89b-12d3-a456-426614174000")
            mock_run.status = "completed"
            mock_run.tokens_in = 100
            mock_run.tokens_out = 50
            mock_run.cost_usd = 0.005
            
            mock_orchestrator_engine.create_run.return_value = mock_run
            mock_orchestrator_engine.get_run.return_value = mock_run
            
            # Mock judge results
            mock_router_judge_result = Mock()
            mock_router_judge_result.score = 0.9
            mock_router_judge_result.reasoning = "Good router decision"
            mock_router_judge_result.metrics = {}
            
            mock_agent_judge_result = Mock()
            mock_agent_judge_result.score = 0.8
            mock_agent_judge_result.reasoning = "Good agent response"
            mock_agent_judge_result.metrics = {}
            
            with patch.object(evaluator.judge, 'judge_router_decision', new_callable=AsyncMock) as mock_router_judge, \
                 patch.object(evaluator.judge, 'judge_agent_response', new_callable=AsyncMock) as mock_agent_judge:
                
                mock_router_judge.return_value = mock_router_judge_result
                mock_agent_judge.return_value = mock_agent_judge_result
                
                report = await evaluator.evaluate_end_to_end(mock_router_engine, mock_orchestrator_engine)
        
        # Verify results
        assert report.evaluation_type == "end_to_end"
        assert report.total_tasks == 1
        assert report.successful_tasks == 1
        assert report.metrics.average_score == 0.85  # (0.9 + 0.8) / 2
        
        # Verify both engines were called
        mock_router_engine.route.assert_called_once()
        mock_orchestrator_engine.create_run.assert_called_once()

    def test_filter_tasks_no_filter(self, evaluator, sample_golden_task):
        """Test task filtering with no filter."""
        with patch.object(evaluator.golden_tasks, 'get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = [sample_golden_task]
            
            filtered_tasks = evaluator._filter_tasks(None)
            
            assert len(filtered_tasks) == 1
            assert filtered_tasks[0] == sample_golden_task

    def test_filter_tasks_by_difficulty(self, evaluator):
        """Test task filtering by difficulty."""
        tasks = [
            GoldenTask(
                task_id="task_1", name="Easy Task", description="Easy task",
                difficulty="easy", domain="support", category="general",
                input_data={}, expected_output={},
                expected_tier=RouterTier.SLM_A, expected_confidence=0.9,
                expected_cost_usd=0.001, expected_latency_ms=200
            ),
            GoldenTask(
                task_id="task_2", name="Hard Task", description="Hard task",
                difficulty="hard", domain="support", category="general",
                input_data={}, expected_output={},
                expected_tier=RouterTier.LLM, expected_confidence=0.7,
                expected_cost_usd=0.01, expected_latency_ms=2000
            )
        ]
        
        with patch.object(evaluator.golden_tasks, 'get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = tasks
            
            # Filter for easy tasks
            task_filter = {"difficulty": "easy"}
            filtered_tasks = evaluator._filter_tasks(task_filter)
            
            assert len(filtered_tasks) == 1
            assert filtered_tasks[0].difficulty == "easy"
            assert filtered_tasks[0].task_id == "task_1"

    def test_filter_tasks_by_domain(self, evaluator):
        """Test task filtering by domain."""
        tasks = [
            GoldenTask(
                task_id="task_1", name="Support Task", description="Support task",
                difficulty="medium", domain="customer_support", category="general",
                input_data={}, expected_output={},
                expected_tier=RouterTier.SLM_B, expected_confidence=0.8,
                expected_cost_usd=0.005, expected_latency_ms=800
            ),
            GoldenTask(
                task_id="task_2", name="Sales Task", description="Sales task",
                difficulty="medium", domain="sales", category="general",
                input_data={}, expected_output={},
                expected_tier=RouterTier.SLM_B, expected_confidence=0.8,
                expected_cost_usd=0.005, expected_latency_ms=800
            )
        ]
        
        with patch.object(evaluator.golden_tasks, 'get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = tasks
            
            # Filter for customer support tasks
            task_filter = {"domain": "customer_support"}
            filtered_tasks = evaluator._filter_tasks(task_filter)
            
            assert len(filtered_tasks) == 1
            assert filtered_tasks[0].domain == "customer_support"
            assert filtered_tasks[0].task_id == "task_1"

    def test_filter_tasks_by_category(self, evaluator):
        """Test task filtering by category."""
        tasks = [
            GoldenTask(
                task_id="task_1", name="Order Task", description="Order task",
                difficulty="medium", domain="support", category="order_management",
                input_data={}, expected_output={},
                expected_tier=RouterTier.SLM_B, expected_confidence=0.8,
                expected_cost_usd=0.005, expected_latency_ms=800
            ),
            GoldenTask(
                task_id="task_2", name="General Task", description="General task",
                difficulty="medium", domain="support", category="general",
                input_data={}, expected_output={},
                expected_tier=RouterTier.SLM_B, expected_confidence=0.8,
                expected_cost_usd=0.005, expected_latency_ms=800
            )
        ]
        
        with patch.object(evaluator.golden_tasks, 'get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = tasks
            
            # Filter for order management tasks
            task_filter = {"category": "order_management"}
            filtered_tasks = evaluator._filter_tasks(task_filter)
            
            assert len(filtered_tasks) == 1
            assert filtered_tasks[0].category == "order_management"
            assert filtered_tasks[0].task_id == "task_1"

    def test_filter_tasks_multiple_criteria(self, evaluator):
        """Test task filtering with multiple criteria."""
        tasks = [
            GoldenTask(
                task_id="task_1", name="Easy Support", description="Easy support task",
                difficulty="easy", domain="customer_support", category="general",
                input_data={}, expected_output={},
                expected_tier=RouterTier.SLM_A, expected_confidence=0.9,
                expected_cost_usd=0.001, expected_latency_ms=200
            ),
            GoldenTask(
                task_id="task_2", name="Easy Sales", description="Easy sales task",
                difficulty="easy", domain="sales", category="general",
                input_data={}, expected_output={},
                expected_tier=RouterTier.SLM_A, expected_confidence=0.9,
                expected_cost_usd=0.001, expected_latency_ms=200
            ),
            GoldenTask(
                task_id="task_3", name="Hard Support", description="Hard support task",
                difficulty="hard", domain="customer_support", category="general",
                input_data={}, expected_output={},
                expected_tier=RouterTier.LLM, expected_confidence=0.7,
                expected_cost_usd=0.01, expected_latency_ms=2000
            )
        ]
        
        with patch.object(evaluator.golden_tasks, 'get_tasks') as mock_get_tasks:
            mock_get_tasks.return_value = tasks
            
            # Filter for easy customer support tasks
            task_filter = {"difficulty": "easy", "domain": "customer_support"}
            filtered_tasks = evaluator._filter_tasks(task_filter)
            
            assert len(filtered_tasks) == 1
            assert filtered_tasks[0].task_id == "task_1"
            assert filtered_tasks[0].difficulty == "easy"
            assert filtered_tasks[0].domain == "customer_support"

    def test_calculate_score_distribution(self, evaluator):
        """Test score distribution calculation."""
        scores = [0.1, 0.3, 0.5, 0.7, 0.9, 0.95]
        distribution = evaluator._calculate_score_distribution(scores)
        
        expected = {
            "0.0-0.2": 1,
            "0.2-0.4": 1,
            "0.4-0.6": 1,
            "0.6-0.8": 1,
            "0.8-1.0": 2
        }
        
        assert distribution == expected

    def test_calculate_score_distribution_empty(self, evaluator):
        """Test score distribution calculation with empty scores."""
        scores = []
        distribution = evaluator._calculate_score_distribution(scores)
        
        expected = {
            "0.0-0.2": 0,
            "0.2-0.4": 0,
            "0.4-0.6": 0,
            "0.6-0.8": 0,
            "0.8-1.0": 0
        }
        
        assert distribution == expected

    def test_generate_router_report_no_successful_tasks(self, evaluator):
        """Test router report generation with no successful tasks."""
        results = [
            {"task_id": "task_1", "success": False, "error": "Router failed"}
        ]
        
        report = evaluator._generate_router_report(results)
        
        assert report.evaluation_type == "router"
        assert report.total_tasks == 1
        assert report.successful_tasks == 0
        assert report.metrics.average_score == 0.0
        assert report.metrics.tier_accuracy == 0.0
        assert report.metrics.cost_efficiency == 0.0
        assert report.metrics.latency_performance == 0.0

    def test_generate_router_report_cost_efficiency(self, evaluator):
        """Test router report generation with cost efficiency calculation."""
        results = [
            {
                "task_id": "task_1", "success": True, "judge_score": 0.8,
                "expected_tier": "SLM_A", "actual_tier": "SLM_A",
                "expected_cost": 0.001, "actual_cost": 0.0008,
                "expected_latency": 200, "actual_latency": 180
            },
            {
                "task_id": "task_2", "success": True, "judge_score": 0.9,
                "expected_tier": "SLM_B", "actual_tier": "SLM_B",
                "expected_cost": 0.005, "actual_cost": 0.004,
                "expected_latency": 800, "actual_latency": 750
            }
        ]
        
        report = evaluator._generate_router_report(results)
        
        assert report.successful_tasks == 2
        assert report.metrics.tier_accuracy == 1.0  # Both tiers correct
        
        # Cost efficiency should be positive (actual < expected)
        assert report.metrics.cost_efficiency > 0.0
        
        # Latency performance should be positive (actual < expected)
        assert report.metrics.latency_performance > 0.0

    def test_generate_agent_report_no_successful_tasks(self, evaluator):
        """Test agent report generation with no successful tasks."""
        results = [
            {"task_id": "task_1", "success": False, "error": "Agent failed"}
        ]
        
        report = evaluator._generate_agent_report(results)
        
        assert report.evaluation_type == "agent"
        assert report.total_tasks == 1
        assert report.successful_tasks == 0
        assert report.metrics.average_score == 0.0

    def test_generate_e2e_report_no_successful_tasks(self, evaluator):
        """Test E2E report generation with no successful tasks."""
        results = [
            {"task_id": "task_1", "success": False, "error": "E2E failed"}
        ]
        
        report = evaluator._generate_e2e_report(results)
        
        assert report.evaluation_type == "end_to_end"
        assert report.total_tasks == 1
        assert report.successful_tasks == 0
        assert report.metrics.average_score == 0.0

    def test_generate_e2e_report_with_results(self, evaluator):
        """Test E2E report generation with successful results."""
        results = [
            {
                "task_id": "task_1", "success": True,
                "router_result": {"judge_score": 0.8},
                "agent_result": {"judge_score": 0.9},
                "overall_score": 0.85
            },
            {
                "task_id": "task_2", "success": True,
                "router_result": {"judge_score": 0.7},
                "agent_result": {"judge_score": 0.8},
                "overall_score": 0.75
            }
        ]
        
        report = evaluator._generate_e2e_report(results)
        
        assert report.successful_tasks == 2
        assert report.metrics.average_score == 0.8  # (0.85 + 0.75) / 2
