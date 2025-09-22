"""
Integration tests for performance gates.

Tests performance baseline management, Locust profiles, cost ceiling management,
and comprehensive performance validation with gates and thresholds.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta
from decimal import Decimal
import json

from libs.performance.baseline_manager import (
    PerformanceBaselineManager, PerformanceBaseline, BaselineType, MetricAggregation,
    PerformanceMetric, BaselineResult, PerformanceAlert
)
from libs.performance.cost_ceiling_manager import (
    CostCeilingManager, CostCeiling, CeilingType, CostType, AlertLevel,
    CostRecord, CostAlert, CostOptimizationRecommendation
)
from libs.performance.locust_profiles import (
    TestScenario, PerformanceGate, GateThreshold, TestProfile,
    LightUser, ModerateUser, HeavyUser, BurstUser, StressUser,
    PerformanceGateValidator, get_test_profiles
)


class TestPerformanceBaselineManager:
    """Test performance baseline management."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def baseline_manager(self, mock_db_session):
        """Create baseline manager for testing."""
        return PerformanceBaselineManager(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_create_baseline(self, baseline_manager, mock_db_session):
        """Test creating a performance baseline."""
        
        baseline = await baseline_manager.create_baseline(
            name="API Response Time",
            description="95th percentile response time for API endpoints",
            baseline_type=BaselineType.LATENCY,
            service="api_gateway",
            endpoint="/chat/message",
            aggregation_method=MetricAggregation.P95,
            window_size_hours=24,
            sample_size=1000,
            threshold_percentage=10.0
        )
        
        assert baseline.baseline_id is not None
        assert baseline.name == "API Response Time"
        assert baseline.baseline_type == BaselineType.LATENCY
        assert baseline.service == "api_gateway"
        assert baseline.aggregation_method == MetricAggregation.P95
        assert baseline.threshold_percentage == 10.0
        assert baseline.is_active is True
        
        # Verify database call
        mock_db_session.execute.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_record_metric(self, baseline_manager, mock_db_session):
        """Test recording performance metrics."""
        
        # Create baseline first
        baseline = await baseline_manager.create_baseline(
            name="Test Baseline",
            description="Test baseline for metrics",
            baseline_type=BaselineType.LATENCY,
            service="test_service"
        )
        
        # Record metrics
        await baseline_manager.record_metric(
            baseline_id=baseline.baseline_id,
            value=150.0,
            unit="ms",
            tags={"endpoint": "/test"},
            metadata={"test": True}
        )
        
        # Verify metric was recorded
        mock_db_session.execute.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_calculate_baseline(self, baseline_manager, mock_db_session):
        """Test baseline calculation."""
        
        # Create baseline
        baseline = await baseline_manager.create_baseline(
            name="Test Baseline",
            description="Test baseline calculation",
            baseline_type=BaselineType.LATENCY,
            service="test_service",
            aggregation_method=MetricAggregation.P95
        )
        
        # Mock database response for metrics
        mock_metrics = [
            MagicMock(value=100.0, timestamp=datetime.now()),
            MagicMock(value=120.0, timestamp=datetime.now()),
            MagicMock(value=150.0, timestamp=datetime.now()),
            MagicMock(value=200.0, timestamp=datetime.now()),
            MagicMock(value=250.0, timestamp=datetime.now())
        ]
        
        baseline_manager._get_metrics_for_window = AsyncMock(return_value=mock_metrics)
        baseline_manager._get_stored_baseline_value = AsyncMock(return_value=150.0)
        baseline_manager._update_baseline_value = AsyncMock()
        
        # Calculate baseline
        result = await baseline_manager.calculate_baseline(baseline.baseline_id)
        
        assert result.baseline_id == baseline.baseline_id
        assert result.calculated_value > 0.0
        assert result.baseline_value == 150.0
        assert isinstance(result.regression_percentage, float)
        assert isinstance(result.is_regression, bool)
        assert result.confidence_level > 0.0
        assert result.sample_size == len(mock_metrics)
    
    @pytest.mark.asyncio
    async def test_percentile_calculation(self, baseline_manager):
        """Test percentile calculation."""
        
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        
        p50 = baseline_manager._percentile(values, 50)
        p95 = baseline_manager._percentile(values, 95)
        p99 = baseline_manager._percentile(values, 99)
        
        assert p50 == 50  # Median
        assert p95 == 95  # 95th percentile
        assert p99 == 99  # 99th percentile
    
    @pytest.mark.asyncio
    async def test_aggregate_values(self, baseline_manager):
        """Test value aggregation methods."""
        
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        
        mean = baseline_manager._aggregate_values(values, MetricAggregation.MEAN)
        median = baseline_manager._aggregate_values(values, MetricAggregation.MEDIAN)
        min_val = baseline_manager._aggregate_values(values, MetricAggregation.MIN)
        max_val = baseline_manager._aggregate_values(values, MetricAggregation.MAX)
        count = baseline_manager._aggregate_values(values, MetricAggregation.COUNT)
        
        assert mean == 55.0  # Average
        assert median == 50.0  # Median
        assert min_val == 10  # Minimum
        assert max_val == 100  # Maximum
        assert count == 10  # Count
    
    @pytest.mark.asyncio
    async def test_confidence_level_calculation(self, baseline_manager):
        """Test confidence level calculation."""
        
        # Small sample - low confidence
        small_sample = [100, 120, 150]
        confidence_small = baseline_manager._calculate_confidence_level(small_sample, len(small_sample))
        assert confidence_small == 0.5
        
        # Medium sample - medium confidence
        medium_sample = list(range(50))  # 50 values
        confidence_medium = baseline_manager._calculate_confidence_level(medium_sample, len(medium_sample))
        assert confidence_medium == 0.7
        
        # Large sample with low variance - high confidence
        large_sample = [100] * 200  # 200 identical values
        confidence_large = baseline_manager._calculate_confidence_level(large_sample, len(large_sample))
        assert confidence_large == 0.8


class TestCostCeilingManager:
    """Test cost ceiling management."""
    
    @pytest.fixture
    def mock_db_session(self):
        """Create mock database session."""
        return AsyncMock()
    
    @pytest.fixture
    def cost_manager(self, mock_db_session):
        """Create cost ceiling manager for testing."""
        return CostCeilingManager(mock_db_session)
    
    @pytest.mark.asyncio
    async def test_create_cost_ceiling(self, cost_manager, mock_db_session):
        """Test creating a cost ceiling."""
        
        ceiling = await cost_manager.create_cost_ceiling(
            name="Daily API Cost Limit",
            description="Daily spending limit for API calls",
            ceiling_type=CeilingType.DAILY,
            cost_type=CostType.API_CALLS,
            limit_amount=Decimal('100.00'),
            currency="USD",
            tenant_id="tenant-123"
        )
        
        assert ceiling.ceiling_id is not None
        assert ceiling.name == "Daily API Cost Limit"
        assert ceiling.ceiling_type == CeilingType.DAILY
        assert ceiling.cost_type == CostType.API_CALLS
        assert ceiling.limit_amount == Decimal('100.00')
        assert ceiling.currency == "USD"
        assert ceiling.tenant_id == "tenant-123"
        assert ceiling.is_active is True
        
        # Verify database call
        mock_db_session.execute.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_record_cost(self, cost_manager, mock_db_session):
        """Test recording costs."""
        
        # Create ceiling first
        ceiling = await cost_manager.create_cost_ceiling(
            name="Test Ceiling",
            description="Test ceiling for costs",
            ceiling_type=CeilingType.DAILY,
            cost_type=CostType.API_CALLS,
            limit_amount=Decimal('50.00')
        )
        
        # Mock get_cost_ceiling and get_current_spending
        cost_manager.get_cost_ceiling = AsyncMock(return_value=ceiling)
        cost_manager.get_current_spending = AsyncMock(return_value=Decimal('10.00'))
        cost_manager._check_ceiling_violations = AsyncMock()
        
        # Record cost
        success = await cost_manager.record_cost(
            ceiling_id=ceiling.ceiling_id,
            tenant_id="tenant-123",
            service="test_service",
            cost_type=CostType.API_CALLS,
            amount=Decimal('5.00')
        )
        
        assert success is True
        
        # Verify database call
        mock_db_session.execute.assert_called()
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_record_cost_exceeds_limit(self, cost_manager, mock_db_session):
        """Test recording cost that exceeds limit."""
        
        # Create ceiling
        ceiling = await cost_manager.create_cost_ceiling(
            name="Test Ceiling",
            description="Test ceiling for costs",
            ceiling_type=CeilingType.DAILY,
            cost_type=CostType.API_CALLS,
            limit_amount=Decimal('10.00')
        )
        
        # Mock get_cost_ceiling and get_current_spending to return high spending
        cost_manager.get_cost_ceiling = AsyncMock(return_value=ceiling)
        cost_manager.get_current_spending = AsyncMock(return_value=Decimal('15.00'))
        cost_manager._check_ceiling_violations = AsyncMock()
        
        # Record cost
        success = await cost_manager.record_cost(
            ceiling_id=ceiling.ceiling_id,
            tenant_id="tenant-123",
            service="test_service",
            cost_type=CostType.API_CALLS,
            amount=Decimal('5.00')
        )
        
        assert success is False  # Should fail because already over limit
    
    @pytest.mark.asyncio
    async def test_get_current_spending(self, cost_manager, mock_db_session):
        """Test getting current spending."""
        
        # Create ceiling
        ceiling = await cost_manager.create_cost_ceiling(
            name="Test Ceiling",
            description="Test ceiling for spending",
            ceiling_type=CeilingType.DAILY,
            cost_type=CostType.API_CALLS,
            limit_amount=Decimal('100.00')
        )
        
        # Mock database response
        mock_result = MagicMock()
        mock_result.fetchone.return_value = MagicMock(total_spending=25.50)
        mock_db_session.execute.return_value = mock_result
        
        # Get current spending
        spending = await cost_manager.get_current_spending(ceiling.ceiling_id)
        
        assert spending == Decimal('25.50')
    
    @pytest.mark.asyncio
    async def test_time_window_key_generation(self, cost_manager):
        """Test time window key generation."""
        
        test_time = datetime(2024, 3, 15, 14, 30, 0)  # Friday, March 15, 2024, 2:30 PM
        
        daily_key = cost_manager._get_time_window_key(CeilingType.DAILY)
        weekly_key = cost_manager._get_time_window_key(CeilingType.WEEKLY)
        monthly_key = cost_manager._get_time_window_key(CeilingType.MONTHLY)
        yearly_key = cost_manager._get_time_window_key(CeilingType.YEARLY)
        
        assert daily_key == "20240315"
        assert weekly_key == "2024W11"  # Week 11 of 2024
        assert monthly_key == "202403"
        assert yearly_key == "2024"
    
    @pytest.mark.asyncio
    async def test_ceiling_start_time_calculation(self, cost_manager):
        """Test ceiling start time calculation."""
        
        test_time = datetime(2024, 3, 15, 14, 30, 0)  # Friday, March 15, 2024, 2:30 PM
        
        daily_start = cost_manager._get_ceiling_start_time(CeilingType.DAILY, test_time)
        weekly_start = cost_manager._get_ceiling_start_time(CeilingType.WEEKLY, test_time)
        monthly_start = cost_manager._get_ceiling_start_time(CeilingType.MONTHLY, test_time)
        yearly_start = cost_manager._get_ceiling_start_time(CeilingType.YEARLY, test_time)
        
        assert daily_start == datetime(2024, 3, 15, 0, 0, 0)  # Start of day
        assert weekly_start == datetime(2024, 3, 11, 0, 0, 0)  # Start of week (Monday)
        assert monthly_start == datetime(2024, 3, 1, 0, 0, 0)  # Start of month
        assert yearly_start == datetime(2024, 1, 1, 0, 0, 0)  # Start of year


class TestLocustProfiles:
    """Test Locust performance testing profiles."""
    
    def test_test_scenarios_enum(self):
        """Test test scenarios enum."""
        
        scenarios = [TestScenario.LIGHT_USER, TestScenario.MODERATE_USER, 
                    TestScenario.HEAVY_USER, TestScenario.BURST_USER, TestScenario.STRESS_USER]
        
        for scenario in scenarios:
            assert scenario.value in ["light_user", "moderate_user", "heavy_user", "burst_user", "stress_user"]
    
    def test_performance_gates_enum(self):
        """Test performance gates enum."""
        
        gates = [PerformanceGate.LATENCY_P95_MS, PerformanceGate.LATENCY_P99_MS,
                PerformanceGate.ERROR_RATE_PERCENT, PerformanceGate.THROUGHPUT_RPS,
                PerformanceGate.COST_PER_REQUEST]
        
        for gate in gates:
            assert gate.value in ["latency_p95_ms", "latency_p99_ms", "error_rate_percent", 
                                "throughput_rps", "cost_per_request"]
    
    def test_gate_threshold_creation(self):
        """Test gate threshold creation."""
        
        threshold = GateThreshold(
            gate=PerformanceGate.LATENCY_P95_MS,
            threshold_value=500.0,
            unit="ms",
            severity="warning"
        )
        
        assert threshold.gate == PerformanceGate.LATENCY_P95_MS
        assert threshold.threshold_value == 500.0
        assert threshold.unit == "ms"
        assert threshold.severity == "warning"
    
    def test_test_profile_creation(self):
        """Test test profile creation."""
        
        profile = TestProfile(
            name="light_load",
            description="Light load testing",
            scenario=TestScenario.LIGHT_USER,
            user_count=10,
            spawn_rate=2,
            duration_minutes=10,
            gates=[
                GateThreshold(PerformanceGate.LATENCY_P95_MS, 500.0, "ms", "warning")
            ]
        )
        
        assert profile.name == "light_load"
        assert profile.scenario == TestScenario.LIGHT_USER
        assert profile.user_count == 10
        assert len(profile.gates) == 1
    
    def test_get_test_profiles(self):
        """Test getting test profiles."""
        
        profiles = get_test_profiles()
        
        assert len(profiles) == 5
        assert all(isinstance(profile, TestProfile) for profile in profiles)
        
        profile_names = [profile.name for profile in profiles]
        expected_names = ["light_load", "moderate_load", "heavy_load", "burst_load", "stress_load"]
        
        for expected_name in expected_names:
            assert expected_name in profile_names


class TestPerformanceGateValidator:
    """Test performance gate validator."""
    
    def test_performance_gate_validator_creation(self):
        """Test performance gate validator creation."""
        
        validator = PerformanceGateValidator()
        
        assert validator.gates == {}
        assert validator.metrics == {}
    
    def test_add_gate(self):
        """Test adding performance gates."""
        
        validator = PerformanceGateValidator()
        
        validator.add_gate(
            PerformanceGate.LATENCY_P95_MS,
            threshold_value=1000.0,
            unit="ms",
            severity="warning"
        )
        
        assert PerformanceGate.LATENCY_P95_MS.value in validator.gates
        gate = validator.gates[PerformanceGate.LATENCY_P95_MS.value]
        assert gate.threshold_value == 1000.0
        assert gate.severity == "warning"
    
    def test_percentile_calculation(self):
        """Test percentile calculation."""
        
        validator = PerformanceGateValidator()
        
        values = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        
        p50 = validator._percentile(values, 50)
        p95 = validator._percentile(values, 95)
        p99 = validator._percentile(values, 99)
        
        assert p50 == 50  # Median
        assert p95 == 95  # 95th percentile
        assert p99 == 99  # 99th percentile


@pytest.mark.asyncio
async def test_performance_baseline_workflow():
    """Test complete performance baseline workflow."""
    
    # Create mock components
    mock_db_session = AsyncMock()
    baseline_manager = PerformanceBaselineManager(mock_db_session)
    
    # Create baseline
    baseline = await baseline_manager.create_baseline(
        name="API Latency Baseline",
        description="95th percentile latency for API endpoints",
        baseline_type=BaselineType.LATENCY,
        service="api_gateway",
        aggregation_method=MetricAggregation.P95,
        threshold_percentage=15.0
    )
    
    assert baseline.name == "API Latency Baseline"
    assert baseline.threshold_percentage == 15.0
    
    # Record multiple metrics
    for i in range(10):
        await baseline_manager.record_metric(
            baseline_id=baseline.baseline_id,
            value=100.0 + (i * 10),  # 100, 110, 120, ..., 190
            unit="ms",
            tags={"endpoint": f"/api/v{i}"}
        )
    
    # Verify metrics were recorded
    assert mock_db_session.execute.call_count >= 11  # 1 for baseline + 10 for metrics


@pytest.mark.asyncio
async def test_cost_ceiling_workflow():
    """Test complete cost ceiling workflow."""
    
    # Create mock components
    mock_db_session = AsyncMock()
    cost_manager = CostCeilingManager(mock_db_session)
    
    # Create cost ceiling
    ceiling = await cost_manager.create_cost_ceiling(
        name="Monthly API Cost Limit",
        description="Monthly spending limit for API usage",
        ceiling_type=CeilingType.MONTHLY,
        cost_type=CostType.API_CALLS,
        limit_amount=Decimal('1000.00'),
        tenant_id="tenant-123"
    )
    
    assert ceiling.limit_amount == Decimal('1000.00')
    assert ceiling.ceiling_type == CeilingType.MONTHLY
    
    # Mock get_cost_ceiling and get_current_spending
    cost_manager.get_cost_ceiling = AsyncMock(return_value=ceiling)
    cost_manager.get_current_spending = AsyncMock(return_value=Decimal('100.00'))
    cost_manager._check_ceiling_violations = AsyncMock()
    
    # Record multiple costs
    total_recorded = Decimal('0')
    for i in range(5):
        amount = Decimal('50.00')
        success = await cost_manager.record_cost(
            ceiling_id=ceiling.ceiling_id,
            tenant_id="tenant-123",
            service="api_gateway",
            cost_type=CostType.API_CALLS,
            amount=amount
        )
        
        assert success is True
        total_recorded += amount
    
    assert total_recorded == Decimal('250.00')


@pytest.mark.asyncio
async def test_performance_gates_validation():
    """Test performance gates validation with realistic scenarios."""
    
    validator = PerformanceGateValidator()
    
    # Add gates
    validator.add_gate(PerformanceGate.LATENCY_P95_MS, 500.0, "ms", "warning")
    validator.add_gate(PerformanceGate.ERROR_RATE_PERCENT, 2.0, "%", "critical")
    
    # Simulate request metrics
    latencies = [100, 150, 200, 300, 400, 500, 600, 700, 800, 900]  # p95 would be ~850
    errors = [0, 0, 0, 0, 0, 0, 0, 1, 0, 0]  # 10% error rate
    
    # Process metrics
    for latency, error in zip(latencies, errors):
        validator._on_request(
            request_type="POST",
            name="/api/test",
            response_time=latency,
            response_length=100,
            exception=Exception("Test error") if error else None,
            context={}
        )
    
    # Check that metrics were collected
    assert "latency" in validator.metrics
    assert "error_rate" in validator.metrics
    assert len(validator.metrics["latency"]) == 10
    assert len(validator.metrics["error_rate"]) == 10
    
    # Validate gates (this would normally happen at test stop)
    violations = []
    
    # Check latency gate
    if "latency" in validator.gates:
        p95 = validator._percentile(validator.metrics["latency"], 95)
        if p95 > validator.gates["latency"].threshold_value:
            violations.append({
                "gate": "latency_p95_ms",
                "actual": p95,
                "threshold": validator.gates["latency"].threshold_value
            })
    
    # Check error rate gate
    if "error_rate" in validator.gates:
        error_rate = (sum(validator.metrics["error_rate"]) / len(validator.metrics["error_rate"])) * 100
        if error_rate > validator.gates["error_rate"].threshold_value:
            violations.append({
                "gate": "error_rate_percent",
                "actual": error_rate,
                "threshold": validator.gates["error_rate"].threshold_value
            })
    
    # Should have violations for both gates
    assert len(violations) == 2
    assert violations[0]["gate"] == "latency_p95_ms"
    assert violations[1]["gate"] == "error_rate_percent"
