"""Integration tests for CostGuard features."""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from apps.billing-service.core.budget_manager import BudgetManager, BudgetPeriod, BudgetStatus
from apps.router-service.core.cost_drift_detector import CostDriftDetector, DriftType, DriftSeverity
from apps.router-service.core.safe_mode_router import SafeModeRouter, SafeModeLevel
from apps.billing-service.jobs.drift_detection_job import DriftDetectionJob
from libs.contracts.billing import BudgetConfig, BudgetUsage
from libs.contracts.router import RouterRequest, LLMTier


class TestBudgetManager:
    """Test BudgetManager functionality."""
    
    @pytest.fixture
    async def budget_manager(self):
        """Create BudgetManager instance for testing."""
        db_session = AsyncMock()
        return BudgetManager(db_session)
    
    @pytest.mark.asyncio
    async def test_create_budget_success(self, budget_manager):
        """Test successful budget creation."""
        # Mock database operations
        budget_manager.db.execute.return_value = None
        budget_manager.db.commit.return_value = None
        
        budget_config = BudgetConfig(
            period=BudgetPeriod.MONTHLY,
            amount=Decimal("1000.00"),
            currency="USD",
            warning_threshold=75.0,
            critical_threshold=90.0,
            auto_renew=True
        )
        
        result = await budget_manager.create_budget("test-tenant-1", budget_config)
        
        assert result is True
        budget_manager.db.execute.assert_called_once()
        budget_manager.db.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_check_budget_limit_allowed(self, budget_manager):
        """Test budget limit check when request is allowed."""
        # Mock budget retrieval
        budget_config = BudgetConfig(
            period=BudgetPeriod.MONTHLY,
            amount=Decimal("1000.00"),
            warning_threshold=75.0,
            critical_threshold=90.0
        )
        
        budget_usage = BudgetUsage(
            tenant_id="test-tenant-1",
            period=BudgetPeriod.MONTHLY,
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            request_count=100,
            total_cost=500.0,
            avg_cost=5.0,
            max_cost=10.0,
            last_updated=datetime.now(timezone.utc)
        )
        
        # Mock methods
        budget_manager.get_budget.return_value = budget_config
        budget_manager.get_budget_usage.return_value = budget_usage
        
        # Test budget check
        result = await budget_manager.check_budget_limit("test-tenant-1", 100.0)
        
        assert result["allowed"] is True
        assert result["usage_percent"] == 60.0  # (500 + 100) / 1000 * 100
    
    @pytest.mark.asyncio
    async def test_check_budget_limit_exceeded(self, budget_manager):
        """Test budget limit check when budget would be exceeded."""
        # Mock budget retrieval
        budget_config = BudgetConfig(
            period=BudgetPeriod.MONTHLY,
            amount=Decimal("1000.00"),
            warning_threshold=75.0,
            critical_threshold=90.0
        )
        
        budget_usage = BudgetUsage(
            tenant_id="test-tenant-1",
            period=BudgetPeriod.MONTHLY,
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            request_count=100,
            total_cost=950.0,
            avg_cost=9.5,
            max_cost=10.0,
            last_updated=datetime.now(timezone.utc)
        )
        
        # Mock methods
        budget_manager.get_budget.return_value = budget_config
        budget_manager.get_budget_usage.return_value = budget_usage
        
        # Test budget check
        result = await budget_manager.check_budget_limit("test-tenant-1", 100.0)
        
        assert result["allowed"] is False
        assert result["reason"] == "Budget exceeded"
        assert result["current_usage"] == 950.0
        assert result["budget_limit"] == 1000.0
        assert result["projected_usage"] == 1050.0
    
    @pytest.mark.asyncio
    async def test_check_budget_limit_warning(self, budget_manager):
        """Test budget limit check when warning threshold is reached."""
        # Mock budget retrieval
        budget_config = BudgetConfig(
            period=BudgetPeriod.MONTHLY,
            amount=Decimal("1000.00"),
            warning_threshold=75.0,
            critical_threshold=90.0
        )
        
        budget_usage = BudgetUsage(
            tenant_id="test-tenant-1",
            period=BudgetPeriod.MONTHLY,
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            request_count=100,
            total_cost=700.0,
            avg_cost=7.0,
            max_cost=10.0,
            last_updated=datetime.now(timezone.utc)
        )
        
        # Mock methods
        budget_manager.get_budget.return_value = budget_config
        budget_manager.get_budget_usage.return_value = budget_usage
        
        # Test budget check
        result = await budget_manager.check_budget_limit("test-tenant-1", 100.0)
        
        assert result["allowed"] is True
        assert result["warning"] == "warning"
        assert result["usage_percent"] == 80.0
        assert "warning budget threshold" in result["reason"]


class TestCostDriftDetector:
    """Test CostDriftDetector functionality."""
    
    @pytest.fixture
    async def drift_detector(self):
        """Create CostDriftDetector instance for testing."""
        db_session = AsyncMock()
        return CostDriftDetector(db_session)
    
    @pytest.mark.asyncio
    async def test_analyze_drift_no_drift(self, drift_detector):
        """Test drift analysis when no significant drift is detected."""
        # Mock actual metrics (similar to expected)
        actual_metrics = {
            "request_count": 100,
            "avg_cost_usd": 0.001,
            "total_cost_usd": 0.1,
            "avg_latency_ms": 100.0,
            "p95_latency_ms": 200.0
        }
        
        expected_metrics = {
            "request_count": 95,
            "avg_cost_usd": 0.001,
            "total_cost_usd": 0.095,
            "avg_latency_ms": 105.0,
            "p95_latency_ms": 210.0
        }
        
        # Mock methods
        drift_detector._get_actual_metrics.return_value = actual_metrics
        drift_detector._get_expected_metrics.return_value = expected_metrics
        
        # Test drift analysis
        result = await drift_detector.analyze_drift("test-tenant-1", "llm")
        
        assert result["drift_detected"] is False
        assert "cost_drift" in result
        assert "latency_drift" in result
    
    @pytest.mark.asyncio
    async def test_analyze_drift_significant_cost_increase(self, drift_detector):
        """Test drift analysis when significant cost increase is detected."""
        # Mock actual metrics (higher cost)
        actual_metrics = {
            "request_count": 100,
            "avg_cost_usd": 0.002,  # 100% increase
            "total_cost_usd": 0.2,
            "avg_latency_ms": 100.0,
            "p95_latency_ms": 200.0
        }
        
        expected_metrics = {
            "request_count": 100,
            "avg_cost_usd": 0.001,
            "total_cost_usd": 0.1,
            "avg_latency_ms": 100.0,
            "p95_latency_ms": 200.0
        }
        
        # Mock methods
        drift_detector._get_actual_metrics.return_value = actual_metrics
        drift_detector._get_expected_metrics.return_value = expected_metrics
        
        # Test drift analysis
        result = await drift_detector.analyze_drift("test-tenant-1", "llm")
        
        assert result["drift_detected"] is True
        assert result["cost_drift"]["drift_percent"] == 100.0
        assert result["cost_drift"]["severity"] == "critical"
        assert result["cost_drift"]["threshold_exceeded"] is True
    
    @pytest.mark.asyncio
    async def test_analyze_drift_significant_latency_increase(self, drift_detector):
        """Test drift analysis when significant latency increase is detected."""
        # Mock actual metrics (higher latency)
        actual_metrics = {
            "request_count": 100,
            "avg_cost_usd": 0.001,
            "total_cost_usd": 0.1,
            "avg_latency_ms": 150.0,
            "p95_latency_ms": 300.0  # 50% increase
        }
        
        expected_metrics = {
            "request_count": 100,
            "avg_cost_usd": 0.001,
            "total_cost_usd": 0.1,
            "avg_latency_ms": 150.0,
            "p95_latency_ms": 200.0
        }
        
        # Mock methods
        drift_detector._get_actual_metrics.return_value = actual_metrics
        drift_detector._get_expected_metrics.return_value = expected_metrics
        
        # Test drift analysis
        result = await drift_detector.analyze_drift("test-tenant-1", "llm")
        
        assert result["drift_detected"] is True
        assert result["latency_drift"]["drift_percent"] == 50.0
        assert result["latency_drift"]["severity"] == "critical"
        assert result["latency_drift"]["threshold_exceeded"] is True
    
    def test_determine_drift_severity(self, drift_detector):
        """Test drift severity determination."""
        # Test cost drift severity
        assert drift_detector._determine_drift_severity(5.0, "cost") == DriftSeverity.LOW
        assert drift_detector._determine_drift_severity(15.0, "cost") == DriftSeverity.HIGH
        assert drift_detector._determine_drift_severity(35.0, "cost") == DriftSeverity.CRITICAL
        
        # Test latency drift severity
        assert drift_detector._determine_drift_severity(10.0, "latency") == DriftSeverity.LOW
        assert drift_detector._determine_drift_severity(30.0, "latency") == DriftSeverity.HIGH
        assert drift_detector._determine_drift_severity(60.0, "latency") == DriftSeverity.CRITICAL


class TestSafeModeRouter:
    """Test SafeModeRouter functionality."""
    
    @pytest.fixture
    async def safe_mode_router(self):
        """Create SafeModeRouter instance for testing."""
        return SafeModeRouter()
    
    def test_determine_safe_mode_level(self, safe_mode_router):
        """Test safe mode level determination."""
        # Test different usage percentages
        assert safe_mode_router.determine_safe_mode_level(BudgetStatus.HEALTHY, 50.0) == SafeModeLevel.NORMAL
        assert safe_mode_router.determine_safe_mode_level(BudgetStatus.WARNING, 80.0) == SafeModeLevel.WARNING
        assert safe_mode_router.determine_safe_mode_level(BudgetStatus.CRITICAL, 92.0) == SafeModeLevel.CRITICAL
        assert safe_mode_router.determine_safe_mode_level(BudgetStatus.EXCEEDED, 98.0) == SafeModeLevel.EMERGENCY
    
    def test_estimate_request_complexity(self, safe_mode_router):
        """Test request complexity estimation."""
        # Test simple JSON request
        request = RouterRequest(
            content="Format this as JSON: {name: 'test', value: 123}",
            user_id="user-1",
            tenant_id="tenant-1"
        )
        
        complexity = safe_mode_router._estimate_request_complexity(request)
        
        assert complexity["task_type"] == "strict_json"
        assert complexity["estimated_tokens"] > 0
        assert complexity["complexity_score"] > 0
    
    def test_estimate_request_cost(self, safe_mode_router):
        """Test request cost estimation."""
        complexity = {
            "estimated_tokens": 1000,
            "complexity_score": 0.5
        }
        
        cost = safe_mode_router._estimate_request_cost(complexity, LLMTier.PREMIUM)
        
        assert cost > 0
        assert cost < 0.01  # Should be reasonable cost
    
    @pytest.mark.asyncio
    async def test_route_with_safe_mode_normal(self, safe_mode_router):
        """Test routing with safe mode when usage is normal."""
        request = RouterRequest(
            content="Simple request",
            user_id="user-1",
            tenant_id="tenant-1"
        )
        
        decision = safe_mode_router.route_with_safe_mode(request)
        
        assert decision.safe_mode_applied is False
        assert decision.tier in [LLMTier.SLM_A, LLMTier.SLM_B, LLMTier.STANDARD, LLMTier.PREMIUM, LLMTier.ENTERPRISE]
    
    @pytest.mark.asyncio
    async def test_route_with_safe_mode_warning(self, safe_mode_router):
        """Test routing with safe mode when usage is high."""
        request = RouterRequest(
            content="Complex creative writing request",
            user_id="user-1",
            tenant_id="tenant-1"
        )
        
        budget_config = BudgetConfig(
            period=BudgetPeriod.MONTHLY,
            amount=Decimal("1000.00"),
            warning_threshold=75.0,
            critical_threshold=90.0
        )
        
        decision = safe_mode_router.route_with_safe_mode(request, budget_config, 80.0)
        
        assert decision.safe_mode_applied is True
        assert decision.safe_mode_level == SafeModeLevel.WARNING.value
        assert decision.tier in [LLMTier.SLM_A, LLMTier.SLM_B, LLMTier.STANDARD]
    
    @pytest.mark.asyncio
    async def test_route_with_safe_mode_emergency(self, safe_mode_router):
        """Test routing with safe mode when usage is critical."""
        request = RouterRequest(
            content="Very complex request",
            user_id="user-1",
            tenant_id="tenant-1"
        )
        
        budget_config = BudgetConfig(
            period=BudgetPeriod.MONTHLY,
            amount=Decimal("1000.00"),
            warning_threshold=75.0,
            critical_threshold=90.0
        )
        
        decision = safe_mode_router.route_with_safe_mode(request, budget_config, 95.0)
        
        assert decision.safe_mode_applied is True
        assert decision.safe_mode_level == SafeModeLevel.EMERGENCY.value
        assert decision.tier == LLMTier.SLM_A  # Should force to cheapest tier
    
    def test_get_cost_savings_summary(self, safe_mode_router):
        """Test cost savings summary calculation."""
        summary = safe_mode_router.get_cost_savings_summary(1000, 200)
        
        assert summary["total_requests"] == 1000
        assert summary["safe_mode_requests"] == 200
        assert summary["safe_mode_percent"] == 20.0
        assert summary["estimated_cost_savings"] > 0
        assert summary["savings_percent"] > 0


class TestDriftDetectionJob:
    """Test DriftDetectionJob functionality."""
    
    @pytest.fixture
    async def drift_job(self):
        """Create DriftDetectionJob instance for testing."""
        db_url = "sqlite+aiosqlite:///:memory:"
        return DriftDetectionJob(db_url)
    
    @pytest.mark.asyncio
    async def test_run_drift_detection(self, drift_job):
        """Test running drift detection job."""
        # Mock the database session and components
        with patch.object(drift_job, '_get_active_tenants') as mock_get_tenants, \
             patch.object(drift_job, '_analyze_tenant_drift') as mock_analyze:
            
            mock_get_tenants.return_value = ["tenant-1", "tenant-2"]
            mock_analyze.return_value = None
            
            # Mock session factory
            mock_session = AsyncMock()
            drift_job.session_factory.return_value.__aenter__.return_value = mock_session
            
            result = await drift_job.run_drift_detection()
            
            assert result["total_tenants_analyzed"] == 2
            assert "analysis_start" in result
            assert "analysis_end" in result
            assert "drift_detected" in result
            assert "budget_alerts" in result
            assert "safe_mode_recommendations" in result
    
    def test_get_safe_mode_recommendations(self, drift_job):
        """Test safe mode recommendations generation."""
        drift_analysis = {
            "cost_drift": {"drift_percent": 25.0},
            "latency_drift": {"drift_percent": 15.0}
        }
        
        # Test warning level recommendations
        recommendations = drift_job._get_safe_mode_recommendations(
            SafeModeLevel.WARNING, drift_analysis
        )
        
        assert len(recommendations) > 0
        assert any("safe mode" in rec.lower() for rec in recommendations)
        
        # Test critical level recommendations
        recommendations = drift_job._get_safe_mode_recommendations(
            SafeModeLevel.CRITICAL, drift_analysis
        )
        
        assert len(recommendations) > 0
        assert any("SLM-A" in rec for rec in recommendations)
        
        # Test emergency level recommendations
        recommendations = drift_job._get_safe_mode_recommendations(
            SafeModeLevel.EMERGENCY, drift_analysis
        )
        
        assert len(recommendations) > 0
        assert any("emergency" in rec.lower() for rec in recommendations)


class TestCostGuardIntegration:
    """Integration tests for CostGuard features."""
    
    @pytest.mark.asyncio
    async def test_budget_enforcement_workflow(self):
        """Test complete budget enforcement workflow."""
        # This would test the full integration scenario
        # where budget limits are enforced end-to-end
        
        # Setup budget configuration
        # Generate requests that would exceed budget
        # Verify budget enforcement works correctly
        # Verify safe mode is activated when needed
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_drift_detection_and_alerting(self):
        """Test drift detection and alerting workflow."""
        # This would test the complete drift detection scenario
        # where cost/latency drift is detected and alerts are sent
        
        # Simulate cost drift
        # Run drift detection job
        # Verify alerts are generated
        # Verify safe mode recommendations are created
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_safe_mode_cost_optimization(self):
        """Test safe mode cost optimization effectiveness."""
        # This would test that safe mode reduces costs without breaking SLAs
        
        # Generate high-cost requests
        # Enable safe mode
        # Verify cost reduction
        # Verify service quality is maintained
        
        pass  # Implementation would require full integration setup
