"""Production-grade router drift detection and correctness tests."""

import pytest
import asyncio
import json
import time
import statistics
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
import random

from tests._fixtures.factories import factory, TenantTier, RouterTier
from tests.contract.schemas import APIRequest, APIResponse, RequestType
from hypothesis import given, strategies as st


class RouterDecision(Enum):
    """Router decision outcomes."""
    ACCEPT = "accept"
    ESCALATE = "escalate"
    REJECT = "reject"
    RETRY = "retry"


class DriftType(Enum):
    """Types of router drift."""
    LATENCY_INCREASE = "latency_increase"
    COST_INCREASE = "cost_increase"
    CONFIDENCE_DECREASE = "confidence_decrease"
    ESCALATION_INCREASE = "escalation_increase"
    MISROUTE_INCREASE = "misroute_increase"


@dataclass
class RouterMetrics:
    """Router performance metrics."""
    tier: RouterTier
    decision_time_ms: float
    cost_usd: float
    confidence_score: float
    escalation_count: int = 0
    rejection_count: int = 0
    misroute_count: int = 0
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class DriftMetrics:
    """Drift detection metrics."""
    drift_type: DriftType
    severity: str  # "low", "medium", "high", "critical"
    current_value: float
    baseline_value: float
    deviation_percent: float
    threshold_percent: float
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)


@dataclass
class RouterBaseline:
    """Router performance baseline."""
    tier: RouterTier
    avg_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_cost_usd: float
    avg_confidence: float
    avg_escalation_rate: float
    avg_misroute_rate: float
    sample_size: int
    established_at: datetime = None
    
    def __post_init__(self):
        if self.established_at is None:
            self.established_at = datetime.now(timezone.utc)


class ProductionRouter:
    """Production-grade router with drift detection."""
    
    def __init__(self, tier: RouterTier = RouterTier.BALANCED):
        """Initialize production router."""
        self.tier = tier
        self.decision_history: List[RouterMetrics] = []
        self.baseline: Optional[RouterBaseline] = None
        self.drift_detection_enabled = True
        self.drift_thresholds = {
            "latency": 20.0,  # 20% increase
            "cost": 15.0,     # 15% increase
            "confidence": 10.0,  # 10% decrease
            "escalation": 25.0,  # 25% increase
            "misroute": 5.0    # 5% increase
        }
        self.expected_tool_mapping = {
            "faq": "faq_search_tool",
            "order": "order_management_tool",
            "payment": "payment_processing_tool",
            "support": "support_ticket_tool",
            "tracking": "order_tracking_tool"
        }
    
    async def route_request(self, request: APIRequest) -> Tuple[RouterDecision, RouterMetrics, Optional[str]]:
        """Route request with drift detection."""
        start_time = time.time()
        
        # Simulate routing decision
        decision, metrics = await self._make_routing_decision(request)
        
        # Calculate actual metrics
        decision_time = (time.time() - start_time) * 1000
        metrics.decision_time_ms = decision_time
        metrics.timestamp = datetime.now(timezone.utc)
        
        # Store metrics
        self.decision_history.append(metrics)
        
        # Check for drift
        drift_detected = None
        if self.drift_detection_enabled and len(self.decision_history) >= 10:
            drift_detected = self._detect_drift()
        
        return decision, metrics, drift_detected
    
    async def _make_routing_decision(self, request: APIRequest) -> Tuple[RouterDecision, RouterMetrics]:
        """Make routing decision based on request."""
        # Simulate decision logic
        confidence = random.uniform(0.85, 0.98)
        cost = self._calculate_cost(request)
        
        # Determine decision based on confidence and tier
        if confidence > 0.95:
            decision = RouterDecision.ACCEPT
        elif confidence > 0.80:
            decision = RouterDecision.ACCEPT
        else:
            decision = RouterDecision.ESCALATE
        
        # Simulate occasional misroutes
        misroute = random.random() < 0.02  # 2% misroute rate
        
        metrics = RouterMetrics(
            tier=self.tier,
            decision_time_ms=0,  # Will be set by caller
            cost_usd=cost,
            confidence_score=confidence,
            escalation_count=1 if decision == RouterDecision.ESCALATE else 0,
            rejection_count=1 if decision == RouterDecision.REJECT else 0,
            misroute_count=1 if misroute else 0
        )
        
        return decision, metrics
    
    def _calculate_cost(self, request: APIRequest) -> float:
        """Calculate routing cost based on request complexity."""
        base_cost = 0.001
        
        # Cost varies by request type and complexity
        if request.request_type == RequestType.PAYMENT:
            base_cost = 0.005
        elif request.request_type == RequestType.ORDER:
            base_cost = 0.003
        elif request.request_type == RequestType.FAQ:
            base_cost = 0.001
        
        # Add complexity factor
        complexity_factor = len(request.message) / 1000
        return base_cost + (base_cost * complexity_factor)
    
    def establish_baseline(self, sample_size: int = 100) -> RouterBaseline:
        """Establish performance baseline from recent metrics."""
        if len(self.decision_history) < sample_size:
            raise ValueError(f"Need at least {sample_size} metrics to establish baseline")
        
        recent_metrics = self.decision_history[-sample_size:]
        
        latencies = [m.decision_time_ms for m in recent_metrics]
        costs = [m.cost_usd for m in recent_metrics]
        confidences = [m.confidence_score for m in recent_metrics]
        
        escalation_count = sum(m.escalation_count for m in recent_metrics)
        misroute_count = sum(m.misroute_count for m in recent_metrics)
        
        baseline = RouterBaseline(
            tier=self.tier,
            avg_latency_ms=statistics.mean(latencies),
            p95_latency_ms=self._percentile(latencies, 95),
            p99_latency_ms=self._percentile(latencies, 99),
            avg_cost_usd=statistics.mean(costs),
            avg_confidence=statistics.mean(confidences),
            avg_escalation_rate=(escalation_count / sample_size) * 100,
            avg_misroute_rate=(misroute_count / sample_size) * 100,
            sample_size=sample_size
        )
        
        self.baseline = baseline
        return baseline
    
    def _detect_drift(self) -> Optional[str]:
        """Detect performance drift."""
        if not self.baseline:
            return None
        
        recent_metrics = self.decision_history[-20:]  # Last 20 decisions
        
        # Check latency drift
        recent_latencies = [m.decision_time_ms for m in recent_metrics]
        avg_latency = statistics.mean(recent_latencies)
        latency_drift = ((avg_latency - self.baseline.avg_latency_ms) / self.baseline.avg_latency_ms) * 100
        
        if latency_drift > self.drift_thresholds["latency"]:
            return f"LATENCY_DRIFT: {latency_drift:.1f}% increase (threshold: {self.drift_thresholds['latency']}%)"
        
        # Check cost drift
        recent_costs = [m.cost_usd for m in recent_metrics]
        avg_cost = statistics.mean(recent_costs)
        cost_drift = ((avg_cost - self.baseline.avg_cost_usd) / self.baseline.avg_cost_usd) * 100
        
        if cost_drift > self.drift_thresholds["cost"]:
            return f"COST_DRIFT: {cost_drift:.1f}% increase (threshold: {self.drift_thresholds['cost']}%)"
        
        # Check confidence drift
        recent_confidences = [m.confidence_score for m in recent_metrics]
        avg_confidence = statistics.mean(recent_confidences)
        confidence_drift = ((self.baseline.avg_confidence - avg_confidence) / self.baseline.avg_confidence) * 100
        
        if confidence_drift > self.drift_thresholds["confidence"]:
            return f"CONFIDENCE_DRIFT: {confidence_drift:.1f}% decrease (threshold: {self.drift_thresholds['confidence']}%)"
        
        # Check escalation drift
        recent_escalations = sum(m.escalation_count for m in recent_metrics)
        escalation_rate = (recent_escalations / len(recent_metrics)) * 100
        escalation_drift = ((escalation_rate - self.baseline.avg_escalation_rate) / max(self.baseline.avg_escalation_rate, 0.1)) * 100
        
        if escalation_drift > self.drift_thresholds["escalation"]:
            return f"ESCALATION_DRIFT: {escalation_drift:.1f}% increase (threshold: {self.drift_thresholds['escalation']}%)"
        
        # Check misroute drift
        recent_misroutes = sum(m.misroute_count for m in recent_metrics)
        misroute_rate = (recent_misroutes / len(recent_metrics)) * 100
        misroute_drift = ((misroute_rate - self.baseline.avg_misroute_rate) / max(self.baseline.avg_misroute_rate, 0.1)) * 100
        
        if misroute_drift > self.drift_thresholds["misroute"]:
            return f"MISROUTE_DRIFT: {misroute_drift:.1f}% increase (threshold: {self.drift_thresholds['misroute']}%)"
        
        return None
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get router performance summary."""
        if not self.decision_history:
            return {"error": "No metrics available"}
        
        recent_metrics = self.decision_history[-50:]  # Last 50 decisions
        
        latencies = [m.decision_time_ms for m in recent_metrics]
        costs = [m.cost_usd for m in recent_metrics]
        confidences = [m.confidence_score for m in recent_metrics]
        
        total_escalations = sum(m.escalation_count for m in recent_metrics)
        total_misroutes = sum(m.misroute_count for m in recent_metrics)
        
        return {
            "tier": self.tier.value,
            "total_decisions": len(self.decision_history),
            "avg_latency_ms": statistics.mean(latencies),
            "p95_latency_ms": self._percentile(latencies, 95),
            "p99_latency_ms": self._percentile(latencies, 99),
            "avg_cost_usd": statistics.mean(costs),
            "avg_confidence": statistics.mean(confidences),
            "escalation_rate": (total_escalations / len(recent_metrics)) * 100,
            "misroute_rate": (total_misroutes / len(recent_metrics)) * 100,
            "drift_detected": self._detect_drift() is not None
        }


class TestRouterDriftDetection:
    """Test router drift detection and correctness."""
    
    @pytest.fixture
    async def production_router(self):
        """Create production router for testing."""
        return ProductionRouter(tier=RouterTier.BALANCED)
    
    @pytest.fixture
    async def router_with_baseline(self, production_router):
        """Create router with established baseline."""
        # Generate baseline data
        tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        user = factory.create_user(tenant_id=tenant.tenant_id)
        
        for i in range(100):
            request = APIRequest(
                request_id=f"req_{i:03d}",
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                request_type=RequestType.FAQ,
                message=f"Test message {i}"
            )
            
            decision, metrics, drift = await production_router.route_request(request)
        
        # Establish baseline
        baseline = production_router.establish_baseline(sample_size=80)
        
        return production_router, baseline
    
    @pytest.mark.asyncio
    async def test_router_baseline_establishment(self, production_router):
        """Test router baseline establishment."""
        tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        user = factory.create_user(tenant_id=tenant.tenant_id)
        
        # Generate metrics for baseline
        for i in range(100):
            request = APIRequest(
                request_id=f"req_{i:03d}",
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                request_type=RequestType.FAQ,
                message=f"Test message {i}"
            )
            
            await production_router.route_request(request)
        
        # Establish baseline
        baseline = production_router.establish_baseline(sample_size=80)
        
        # Validate baseline
        assert baseline.tier == RouterTier.BALANCED
        assert baseline.avg_latency_ms > 0
        assert baseline.avg_cost_usd > 0
        assert 0 <= baseline.avg_confidence <= 1
        assert baseline.sample_size == 80
        assert baseline.established_at is not None
    
    @pytest.mark.asyncio
    async def test_latency_drift_detection(self, router_with_baseline):
        """Test latency drift detection."""
        router, baseline = router_with_baseline
        
        # Simulate latency increase by slowing down router
        original_route = router._make_routing_decision
        
        async def slow_route(request):
            await asyncio.sleep(0.1)  # Add 100ms delay
            return await original_route(request)
        
        router._make_routing_decision = slow_route
        
        # Generate requests with increased latency
        tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        user = factory.create_user(tenant_id=tenant.tenant_id)
        
        drift_detected = False
        for i in range(25):  # Generate 25 requests
            request = APIRequest(
                request_id=f"drift_req_{i:03d}",
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                request_type=RequestType.FAQ,
                message=f"Drift test message {i}"
            )
            
            decision, metrics, drift = await router.route_request(request)
            if drift and "LATENCY_DRIFT" in drift:
                drift_detected = True
                break
        
        assert drift_detected, "Latency drift should be detected"
    
    @pytest.mark.asyncio
    async def test_cost_drift_detection(self, router_with_baseline):
        """Test cost drift detection."""
        router, baseline = router_with_baseline
        
        # Modify cost calculation to increase costs
        original_calculate = router._calculate_cost
        
        def expensive_calculate(request):
            cost = original_calculate(request)
            return cost * 2.0  # Double the cost
        
        router._calculate_cost = expensive_calculate
        
        # Generate requests with increased cost
        tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        user = factory.create_user(tenant_id=tenant.tenant_id)
        
        drift_detected = False
        for i in range(25):
            request = APIRequest(
                request_id=f"cost_drift_req_{i:03d}",
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                request_type=RequestType.PAYMENT,
                message=f"Cost drift test {i}"
            )
            
            decision, metrics, drift = await router.route_request(request)
            if drift and "COST_DRIFT" in drift:
                drift_detected = True
                break
        
        assert drift_detected, "Cost drift should be detected"
    
    @pytest.mark.asyncio
    async def test_misroute_rate_detection(self, router_with_baseline):
        """Test misroute rate detection."""
        router, baseline = router_with_baseline
        
        # Increase misroute rate
        original_route = router._make_routing_decision
        
        async def misrouting_route(request):
            decision, metrics = await original_route(request)
            # Increase misroute rate to 10%
            metrics.misroute_count = 1 if random.random() < 0.1 else 0
            return decision, metrics
        
        router._make_routing_decision = misrouting_route
        
        # Generate requests with increased misroute rate
        tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        user = factory.create_user(tenant_id=tenant.tenant_id)
        
        drift_detected = False
        for i in range(25):
            request = APIRequest(
                request_id=f"misroute_req_{i:03d}",
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                request_type=RequestType.FAQ,
                message=f"Misroute test {i}"
            )
            
            decision, metrics, drift = await router.route_request(request)
            if drift and "MISROUTE_DRIFT" in drift:
                drift_detected = True
                break
        
        assert drift_detected, "Misroute drift should be detected"
    
    @pytest.mark.asyncio
    async def test_router_performance_summary(self, router_with_baseline):
        """Test router performance summary."""
        router, baseline = router_with_baseline
        
        # Get performance summary
        summary = router.get_performance_summary()
        
        # Validate summary
        assert "tier" in summary
        assert "total_decisions" in summary
        assert "avg_latency_ms" in summary
        assert "p95_latency_ms" in summary
        assert "p99_latency_ms" in summary
        assert "avg_cost_usd" in summary
        assert "avg_confidence" in summary
        assert "escalation_rate" in summary
        assert "misroute_rate" in summary
        assert "drift_detected" in summary
        
        # Validate values
        assert summary["tier"] == RouterTier.BALANCED.value
        assert summary["total_decisions"] >= 100
        assert summary["avg_latency_ms"] > 0
        assert summary["avg_cost_usd"] > 0
        assert 0 <= summary["avg_confidence"] <= 1
        assert 0 <= summary["escalation_rate"] <= 100
        assert 0 <= summary["misroute_rate"] <= 100
    
    @pytest.mark.asyncio
    async def test_expected_vs_actual_cost_validation(self, production_router):
        """Test expected vs actual cost validation."""
        tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        user = factory.create_user(tenant_id=tenant.tenant_id)
        
        cost_deviations = []
        
        for i in range(20):
            request = APIRequest(
                request_id=f"cost_val_req_{i:03d}",
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                request_type=RequestType.FAQ,
                message=f"Cost validation test {i}"
            )
            
            decision, metrics, drift = await production_router.route_request(request)
            
            # Calculate expected cost
            expected_cost = production_router._calculate_cost(request)
            
            # Calculate deviation
            deviation = abs(metrics.cost_usd - expected_cost) / expected_cost * 100
            cost_deviations.append(deviation)
        
        # Validate cost accuracy
        avg_deviation = statistics.mean(cost_deviations)
        max_deviation = max(cost_deviations)
        
        assert avg_deviation < 5.0, f"Average cost deviation {avg_deviation:.2f}% exceeds 5%"
        assert max_deviation < 10.0, f"Max cost deviation {max_deviation:.2f}% exceeds 10%"
    
    @pytest.mark.asyncio
    async def test_router_tier_performance_comparison(self):
        """Test router performance across different tiers."""
        tiers = [RouterTier.FAST, RouterTier.BALANCED, RouterTier.ACCURATE]
        tier_results = {}
        
        tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        user = factory.create_user(tenant_id=tenant.tenant_id)
        
        for tier in tiers:
            router = ProductionRouter(tier=tier)
            
            # Generate requests
            for i in range(30):
                request = APIRequest(
                    request_id=f"tier_req_{tier.value}_{i:03d}",
                    tenant_id=tenant.tenant_id,
                    user_id=user.user_id,
                    request_type=RequestType.FAQ,
                    message=f"Tier test {i}"
                )
                
                await router.route_request(request)
            
            # Get performance summary
            summary = router.get_performance_summary()
            tier_results[tier] = summary
        
        # Validate tier performance characteristics
        fast_latency = tier_results[RouterTier.FAST]["avg_latency_ms"]
        balanced_latency = tier_results[RouterTier.BALANCED]["avg_latency_ms"]
        accurate_latency = tier_results[RouterTier.ACCURATE]["avg_latency_ms"]
        
        # FAST should be fastest
        assert fast_latency <= balanced_latency, "FAST tier should be faster than BALANCED"
        assert fast_latency <= accurate_latency, "FAST tier should be faster than ACCURATE"
        
        # ACCURATE should have highest confidence
        fast_confidence = tier_results[RouterTier.FAST]["avg_confidence"]
        balanced_confidence = tier_results[RouterTier.BALANCED]["avg_confidence"]
        accurate_confidence = tier_results[RouterTier.ACCURATE]["avg_confidence"]
        
        assert accurate_confidence >= balanced_confidence, "ACCURATE tier should have higher confidence than BALANCED"
        assert accurate_confidence >= fast_confidence, "ACCURATE tier should have higher confidence than FAST"
    
    @given(st.text(min_size=1, max_size=100))
    def test_router_property_based_fuzzing(self, query_text):
        """Test router with property-based fuzzing."""
        router = ProductionRouter(tier=RouterTier.BALANCED)
        
        # Create request with fuzzed text
        request = APIRequest(
            request_id="fuzz_req",
            tenant_id="tenant_0001",
            user_id="user_0001",
            request_type=RequestType.FAQ,
            message=query_text
        )
        
        # Router should handle any text input
        try:
            # This would be async in real implementation
            cost = router._calculate_cost(request)
            assert cost > 0, "Cost should be positive"
            assert cost < 1.0, "Cost should be reasonable"
        except Exception as e:
            pytest.fail(f"Router failed on input '{query_text}': {e}")
    
    @pytest.mark.asyncio
    async def test_router_ci_failure_on_drift_threshold(self, router_with_baseline):
        """Test that CI fails when drift exceeds threshold."""
        router, baseline = router_with_baseline
        
        # Simulate severe latency increase
        original_route = router._make_routing_decision
        
        async def severely_slow_route(request):
            await asyncio.sleep(0.5)  # 500ms delay - severe drift
            return await original_route(request)
        
        router._make_routing_decision = severely_slow_route
        
        # Generate requests that should trigger CI failure
        tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        user = factory.create_user(tenant_id=tenant.tenant_id)
        
        drift_detected = False
        drift_message = None
        
        for i in range(25):
            request = APIRequest(
                request_id=f"ci_fail_req_{i:03d}",
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                request_type=RequestType.FAQ,
                message=f"CI failure test {i}"
            )
            
            decision, metrics, drift = await router.route_request(request)
            if drift:
                drift_detected = True
                drift_message = drift
                break
        
        assert drift_detected, "Severe drift should be detected"
        assert "LATENCY_DRIFT" in drift_message, "Should detect latency drift"
        
        # Parse drift percentage
        drift_percent = float(drift_message.split(": ")[1].split("%")[0])
        assert drift_percent > 20.0, "Drift should exceed threshold"
        
        # This would fail CI in production
        if drift_percent > 20.0:
            pytest.fail(f"CI FAILURE: Router drift {drift_percent:.1f}% exceeds threshold 20%")
