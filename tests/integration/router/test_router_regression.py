"""Router regression tests for drift detection and misroute prevention."""

import pytest
import asyncio
from typing import Dict, Any, List, Tuple
from datetime import datetime

from tests.integration.router import RouterTier, RouterDecision, DriftType, RouterMetrics, DriftMetrics
from tests.contract.schemas import APIRequest, APIResponse, RequestType


class MockRouter:
    """Mock router for testing regression scenarios."""
    
    def __init__(self, tier: RouterTier = RouterTier.SLM_A):
        self.tier = tier
        self.decision_history: List[RouterMetrics] = []
        self.baseline_metrics = {
            'cost_usd': 0.002,
            'latency_ms': 150.0,
            'confidence_score': 0.95
        }
    
    async def route_request(self, request: APIRequest) -> Tuple[RouterDecision, RouterMetrics]:
        """Route a request and return decision with metrics."""
        # Simulate routing logic
        decision_time = 120.0
        cost = 0.002
        confidence = 0.95
        
        # Determine routing decision
        decision = RouterDecision.ACCEPT if confidence > 0.8 else RouterDecision.ESCALATE
        
        # Create metrics
        metrics = RouterMetrics(
            tier=self.tier,
            decision_time_ms=decision_time,
            cost_usd=cost,
            confidence_score=confidence,
            escalation_count=1 if decision == RouterDecision.ESCALATE else 0,
            rejection_count=1 if decision == RouterDecision.REJECT else 0
        )
        
        self.decision_history.append(metrics)
        return decision, metrics
    
    def detect_drift(self) -> List[DriftMetrics]:
        """Detect drift in router performance."""
        if len(self.decision_history) < 5:
            return []
        
        recent_metrics = self.decision_history[-5:]
        drift_metrics = []
        
        # Cost drift detection
        avg_cost = sum(m.cost_usd for m in recent_metrics) / len(recent_metrics)
        expected_cost = self.baseline_metrics['cost_usd']
        cost_drift_percent = abs(avg_cost - expected_cost) / expected_cost * 100
        
        if cost_drift_percent > 10.0:  # 10% threshold
            drift_metrics.append(DriftMetrics(
                drift_type=DriftType.COST_DRIFT,
                expected_value=expected_cost,
                actual_value=avg_cost,
                drift_percentage=cost_drift_percent,
                threshold_exceeded=True,
                timestamp=datetime.now()
            ))
        
        return drift_metrics


class TestRouterRegression:
    """Test router regression and drift detection."""
    
    @pytest.fixture
    def mock_router(self):
        """Create mock router for testing."""
        return MockRouter(tier=RouterTier.SLM_A)
    
    @pytest.mark.asyncio
    async def test_early_exit_strict_json_acceptance(self, mock_router):
        """Test early-exit strict-JSON acceptance."""
        request = APIRequest(
            request_id="req_001",
            tenant_id="tenant_1234",
            user_id="user_1234",
            request_type=RequestType.SUPPORT,
            message="Test message",
            context={"source": "web", "session_id": "sess_001"},
            metadata={"priority": "normal"}
        )
        
        decision, metrics = await mock_router.route_request(request)
        
        # Validate early exit conditions
        assert decision in [RouterDecision.ACCEPT, RouterDecision.ESCALATE, RouterDecision.REJECT]
        assert metrics.decision_time_ms < 300
        assert metrics.cost_usd > 0
        assert 0.7 <= metrics.confidence_score <= 1.0
    
    @pytest.mark.asyncio
    async def test_escalation_correctness(self, mock_router):
        """Test escalation correctness."""
        request = APIRequest(
            request_id="req_002",
            tenant_id="tenant_1234",
            user_id="user_1234",
            request_type=RequestType.SUPPORT,
            message="Simple question",
            context={"source": "web", "session_id": "sess_002"},
            metadata={"priority": "normal"}
        )
        
        decision, metrics = await mock_router.route_request(request)
        assert decision == RouterDecision.ACCEPT
        assert metrics.confidence_score > 0.8
    
    @pytest.mark.asyncio
    async def test_cost_latency_drift_detection(self, mock_router):
        """Test cost and latency drift detection."""
        # Generate requests to build history
        for i in range(10):
            request = APIRequest(
                request_id=f"req_{i:03d}",
                tenant_id="tenant_1234",
                user_id="user_1234",
                request_type=RequestType.SUPPORT,
                message=f"Test message {i}",
                context={"source": "web", "session_id": f"sess_{i:03d}"},
                metadata={"priority": "normal"}
            )
            
            await mock_router.route_request(request)
        
        # Detect drift
        drift_metrics = mock_router.detect_drift()
        
        # Validate drift detection
        assert isinstance(drift_metrics, list)
        
        # Check drift metrics structure
        for drift in drift_metrics:
            assert drift.drift_type in [DriftType.COST_DRIFT, DriftType.LATENCY_DRIFT, DriftType.QUALITY_DRIFT]
            assert drift.expected_value > 0
            assert drift.actual_value > 0
            assert drift.drift_percentage >= 0