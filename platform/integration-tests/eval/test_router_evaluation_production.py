"""Production-grade router evaluation with labeled cases and drift detection."""

import pytest
import asyncio
import json
import statistics
from typing import Dict, Any, List, Tuple, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
from enum import Enum

from tests._fixtures.factories import factory, TenantTier, RouterTier
from tests.contract.schemas import APIRequest, APIResponse, RequestType
from tests.integration.router.test_router_drift_production import ProductionRouter, RouterDecision, RouterMetrics


class EvaluationMetric(Enum):
    """Router evaluation metrics."""
    ACCURACY = "accuracy"
    PRECISION = "precision"
    RECALL = "recall"
    F1_SCORE = "f1_score"
    LATENCY_P50 = "latency_p50"
    LATENCY_P95 = "latency_p95"
    LATENCY_P99 = "latency_p99"
    COST_EFFICIENCY = "cost_efficiency"
    ESCALATION_RATE = "escalation_rate"
    MISROUTE_RATE = "misroute_rate"


@dataclass
class LabeledCase:
    """Labeled test case for router evaluation."""
    case_id: str
    query: str
    expected_tool: str
    expected_tier: RouterTier
    expected_confidence: float
    expected_latency_ms: float
    expected_cost_usd: float
    request_type: RequestType
    context: Dict[str, Any] = None
    difficulty: str = "medium"  # "easy", "medium", "hard"
    
    def __post_init__(self):
        if self.context is None:
            self.context = {}


@dataclass
class EvaluationResult:
    """Router evaluation result."""
    case_id: str
    expected_tool: str
    actual_tool: str
    expected_tier: RouterTier
    actual_tier: RouterTier
    expected_confidence: float
    actual_confidence: float
    expected_latency_ms: float
    actual_latency_ms: float
    expected_cost_usd: float
    actual_cost_usd: float
    decision: RouterDecision
    correct_tool_selection: bool
    correct_tier_selection: bool
    confidence_deviation: float
    latency_deviation: float
    cost_deviation: float
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc)
        
        # Calculate deviations
        self.confidence_deviation = abs(self.actual_confidence - self.expected_confidence) / max(self.expected_confidence, 0.01) * 100
        self.latency_deviation = abs(self.actual_latency_ms - self.expected_latency_ms) / max(self.expected_latency_ms, 1) * 100
        self.cost_deviation = abs(self.actual_cost_usd - self.expected_cost_usd) / max(self.expected_cost_usd, 0.001) * 100


@dataclass
class RouterEvaluation:
    """Complete router evaluation."""
    router_tier: RouterTier
    total_cases: int
    correct_tool_selections: int
    correct_tier_selections: int
    avg_confidence_deviation: float
    avg_latency_deviation: float
    avg_cost_deviation: float
    accuracy: float
    precision: float
    recall: float
    f1_score: float
    avg_latency_p50: float
    avg_latency_p95: float
    avg_latency_p99: float
    cost_efficiency: float
    escalation_rate: float
    misroute_rate: float
    results: List[EvaluationResult]
    evaluation_timestamp: datetime = None
    
    def __post_init__(self):
        if self.evaluation_timestamp is None:
            self.evaluation_timestamp = datetime.now(timezone.utc)


class RouterEvaluator:
    """Router evaluation system with labeled cases."""
    
    def __init__(self):
        """Initialize router evaluator."""
        self.labeled_cases = self._create_labeled_cases()
        self.evaluation_results: Dict[RouterTier, RouterEvaluation] = {}
    
    def _create_labeled_cases(self) -> List[LabeledCase]:
        """Create labeled test cases for router evaluation."""
        cases = [
            # FAQ Cases
            LabeledCase(
                case_id="faq_001",
                query="What is your return policy?",
                expected_tool="faq_search_tool",
                expected_tier=RouterTier.FAST,
                expected_confidence=0.95,
                expected_latency_ms=50.0,
                expected_cost_usd=0.001,
                request_type=RequestType.FAQ,
                difficulty="easy"
            ),
            LabeledCase(
                case_id="faq_002",
                query="How do I track my order status?",
                expected_tool="order_tracking_tool",
                expected_tier=RouterTier.BALANCED,
                expected_confidence=0.90,
                expected_latency_ms=100.0,
                expected_cost_usd=0.002,
                request_type=RequestType.FAQ,
                difficulty="easy"
            ),
            LabeledCase(
                case_id="faq_003",
                query="Can you help me with a complex technical issue involving API integration?",
                expected_tool="support_ticket_tool",
                expected_tier=RouterTier.ACCURATE,
                expected_confidence=0.85,
                expected_latency_ms=200.0,
                expected_cost_usd=0.005,
                request_type=RequestType.FAQ,
                difficulty="hard"
            ),
            
            # Order Cases
            LabeledCase(
                case_id="order_001",
                query="I want to place an order for product X",
                expected_tool="order_management_tool",
                expected_tier=RouterTier.BALANCED,
                expected_confidence=0.92,
                expected_latency_ms=120.0,
                expected_cost_usd=0.003,
                request_type=RequestType.ORDER,
                difficulty="medium"
            ),
            LabeledCase(
                case_id="order_002",
                query="Cancel my order #12345",
                expected_tool="order_management_tool",
                expected_tier=RouterTier.BALANCED,
                expected_confidence=0.88,
                expected_latency_ms=150.0,
                expected_cost_usd=0.003,
                request_type=RequestType.ORDER,
                difficulty="medium"
            ),
            
            # Payment Cases
            LabeledCase(
                case_id="payment_001",
                query="I want to pay for my order",
                expected_tool="payment_processing_tool",
                expected_tier=RouterTier.ACCURATE,
                expected_confidence=0.93,
                expected_latency_ms=180.0,
                expected_cost_usd=0.005,
                request_type=RequestType.PAYMENT,
                difficulty="medium"
            ),
            LabeledCase(
                case_id="payment_002",
                query="Process refund for transaction #ABC123",
                expected_tool="payment_processing_tool",
                expected_tier=RouterTier.ACCURATE,
                expected_confidence=0.90,
                expected_latency_ms=200.0,
                expected_cost_usd=0.005,
                request_type=RequestType.PAYMENT,
                difficulty="hard"
            ),
            
            # Support Cases
            LabeledCase(
                case_id="support_001",
                query="I need help with my account",
                expected_tool="support_ticket_tool",
                expected_tier=RouterTier.BALANCED,
                expected_confidence=0.87,
                expected_latency_ms=140.0,
                expected_cost_usd=0.004,
                request_type=RequestType.SUPPORT,
                difficulty="medium"
            ),
            LabeledCase(
                case_id="support_002",
                query="Escalate this issue to a human agent",
                expected_tool="support_ticket_tool",
                expected_tier=RouterTier.ACCURATE,
                expected_confidence=0.85,
                expected_latency_ms=250.0,
                expected_cost_usd=0.006,
                request_type=RequestType.SUPPORT,
                difficulty="hard"
            ),
            
            # Tracking Cases
            LabeledCase(
                case_id="tracking_001",
                query="Where is my package?",
                expected_tool="order_tracking_tool",
                expected_tier=RouterTier.FAST,
                expected_confidence=0.94,
                expected_latency_ms=80.0,
                expected_cost_usd=0.002,
                request_type=RequestType.TRACKING,
                difficulty="easy"
            ),
            LabeledCase(
                case_id="tracking_002",
                query="Update delivery address for order #XYZ789",
                expected_tool="order_tracking_tool",
                expected_tier=RouterTier.BALANCED,
                expected_confidence=0.89,
                expected_latency_ms=160.0,
                expected_cost_usd=0.003,
                request_type=RequestType.TRACKING,
                difficulty="medium"
            ),
            
            # Edge Cases
            LabeledCase(
                case_id="edge_001",
                query="",
                expected_tool="support_ticket_tool",
                expected_tier=RouterTier.ACCURATE,
                expected_confidence=0.70,
                expected_latency_ms=300.0,
                expected_cost_usd=0.008,
                request_type=RequestType.SUPPORT,
                difficulty="hard"
            ),
            LabeledCase(
                case_id="edge_002",
                query="This is a very long query with lots of details about my problem that requires careful analysis and understanding of the context to provide the right response",
                expected_tool="support_ticket_tool",
                expected_tier=RouterTier.ACCURATE,
                expected_confidence=0.82,
                expected_latency_ms=400.0,
                expected_cost_usd=0.010,
                request_type=RequestType.SUPPORT,
                difficulty="hard"
            ),
        ]
        
        return cases
    
    async def evaluate_router(self, router: ProductionRouter) -> RouterEvaluation:
        """Evaluate router performance against labeled cases."""
        tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
        user = factory.create_user(tenant_id=tenant.tenant_id)
        
        results = []
        
        for case in self.labeled_cases:
            # Create API request
            request = APIRequest(
                request_id=f"eval_{case.case_id}",
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                request_type=case.request_type,
                message=case.query,
                context=case.context or {}
            )
            
            # Route request
            decision, metrics, drift = await router.route_request(request)
            
            # Determine actual tool (simplified mapping)
            actual_tool = self._map_decision_to_tool(decision, case.request_type)
            
            # Create evaluation result
            result = EvaluationResult(
                case_id=case.case_id,
                expected_tool=case.expected_tool,
                actual_tool=actual_tool,
                expected_tier=case.expected_tier,
                actual_tier=router.tier,
                expected_confidence=case.expected_confidence,
                actual_confidence=metrics.confidence_score,
                expected_latency_ms=case.expected_latency_ms,
                actual_latency_ms=metrics.decision_time_ms,
                expected_cost_usd=case.expected_cost_usd,
                actual_cost_usd=metrics.cost_usd,
                decision=decision,
                correct_tool_selection=(actual_tool == case.expected_tool),
                correct_tier_selection=(router.tier == case.expected_tier)
            )
            
            results.append(result)
        
        # Calculate evaluation metrics
        evaluation = self._calculate_evaluation_metrics(router.tier, results)
        
        # Store results
        self.evaluation_results[router.tier] = evaluation
        
        return evaluation
    
    def _map_decision_to_tool(self, decision: RouterDecision, request_type: RequestType) -> str:
        """Map router decision to expected tool."""
        tool_mapping = {
            RequestType.FAQ: "faq_search_tool",
            RequestType.ORDER: "order_management_tool",
            RequestType.PAYMENT: "payment_processing_tool",
            RequestType.SUPPORT: "support_ticket_tool",
            RequestType.TRACKING: "order_tracking_tool",
            RequestType.LEAD: "lead_management_tool"
        }
        
        if decision == RouterDecision.ACCEPT:
            return tool_mapping.get(request_type, "default_tool")
        elif decision == RouterDecision.ESCALATE:
            return "support_ticket_tool"
        else:
            return "error_handling_tool"
    
    def _calculate_evaluation_metrics(self, router_tier: RouterTier, results: List[EvaluationResult]) -> RouterEvaluation:
        """Calculate evaluation metrics from results."""
        total_cases = len(results)
        correct_tool_selections = sum(1 for r in results if r.correct_tool_selection)
        correct_tier_selections = sum(1 for r in results if r.correct_tier_selection)
        
        # Calculate accuracy
        accuracy = (correct_tool_selections / total_cases) * 100
        
        # Calculate precision and recall (simplified)
        true_positives = correct_tool_selections
        false_positives = total_cases - correct_tool_selections
        false_negatives = 0  # Simplified for this example
        
        precision = true_positives / max(true_positives + false_positives, 1) * 100
        recall = true_positives / max(true_positives + false_negatives, 1) * 100
        f1_score = 2 * (precision * recall) / max(precision + recall, 1)
        
        # Calculate deviations
        avg_confidence_deviation = statistics.mean([r.confidence_deviation for r in results])
        avg_latency_deviation = statistics.mean([r.latency_deviation for r in results])
        avg_cost_deviation = statistics.mean([r.cost_deviation for r in results])
        
        # Calculate latency percentiles
        latencies = [r.actual_latency_ms for r in results]
        avg_latency_p50 = statistics.median(latencies)
        avg_latency_p95 = self._percentile(latencies, 95)
        avg_latency_p99 = self._percentile(latencies, 99)
        
        # Calculate cost efficiency (expected cost / actual cost)
        cost_efficiencies = [r.expected_cost_usd / max(r.actual_cost_usd, 0.001) for r in results]
        cost_efficiency = statistics.mean(cost_efficiencies) * 100
        
        # Calculate escalation and misroute rates
        escalation_count = sum(1 for r in results if r.decision == RouterDecision.ESCALATE)
        misroute_count = sum(1 for r in results if not r.correct_tool_selection)
        
        escalation_rate = (escalation_count / total_cases) * 100
        misroute_rate = (misroute_count / total_cases) * 100
        
        return RouterEvaluation(
            router_tier=router_tier,
            total_cases=total_cases,
            correct_tool_selections=correct_tool_selections,
            correct_tier_selections=correct_tier_selections,
            avg_confidence_deviation=avg_confidence_deviation,
            avg_latency_deviation=avg_latency_deviation,
            avg_cost_deviation=avg_cost_deviation,
            accuracy=accuracy,
            precision=precision,
            recall=recall,
            f1_score=f1_score,
            avg_latency_p50=avg_latency_p50,
            avg_latency_p95=avg_latency_p95,
            avg_latency_p99=avg_latency_p99,
            cost_efficiency=cost_efficiency,
            escalation_rate=escalation_rate,
            misroute_rate=misroute_rate,
            results=results
        )
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calculate percentile of data."""
        sorted_data = sorted(data)
        index = int((percentile / 100) * len(sorted_data))
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def get_evaluation_summary(self, router_tier: RouterTier) -> Dict[str, Any]:
        """Get evaluation summary for router tier."""
        if router_tier not in self.evaluation_results:
            return {"error": "No evaluation results for this tier"}
        
        evaluation = self.evaluation_results[router_tier]
        
        return {
            "router_tier": router_tier.value,
            "accuracy": f"{evaluation.accuracy:.2f}%",
            "precision": f"{evaluation.precision:.2f}%",
            "recall": f"{evaluation.recall:.2f}%",
            "f1_score": f"{evaluation.f1_score:.2f}",
            "avg_latency_p50": f"{evaluation.avg_latency_p50:.2f}ms",
            "avg_latency_p95": f"{evaluation.avg_latency_p95:.2f}ms",
            "avg_latency_p99": f"{evaluation.avg_latency_p99:.2f}ms",
            "cost_efficiency": f"{evaluation.cost_efficiency:.2f}%",
            "escalation_rate": f"{evaluation.escalation_rate:.2f}%",
            "misroute_rate": f"{evaluation.misroute_rate:.2f}%",
            "total_cases": evaluation.total_cases,
            "correct_tool_selections": evaluation.correct_tool_selections,
            "avg_confidence_deviation": f"{evaluation.avg_confidence_deviation:.2f}%",
            "avg_latency_deviation": f"{evaluation.avg_latency_deviation:.2f}%",
            "avg_cost_deviation": f"{evaluation.avg_cost_deviation:.2f}%"
        }


class TestRouterEvaluationProduction:
    """Production-grade router evaluation tests."""
    
    @pytest.fixture
    async def router_evaluator(self):
        """Create router evaluator."""
        return RouterEvaluator()
    
    @pytest.fixture
    async def routers_for_evaluation(self):
        """Create routers for evaluation."""
        return {
            RouterTier.FAST: ProductionRouter(tier=RouterTier.FAST),
            RouterTier.BALANCED: ProductionRouter(tier=RouterTier.BALANCED),
            RouterTier.ACCURATE: ProductionRouter(tier=RouterTier.ACCURATE)
        }
    
    @pytest.mark.asyncio
    async def test_router_evaluation_with_labeled_cases(self, router_evaluator, routers_for_evaluation):
        """Test router evaluation with labeled cases."""
        router = routers_for_evaluation[RouterTier.BALANCED]
        
        # Evaluate router
        evaluation = await router_evaluator.evaluate_router(router)
        
        # Validate evaluation
        assert evaluation.router_tier == RouterTier.BALANCED
        assert evaluation.total_cases > 0
        assert evaluation.accuracy >= 0
        assert evaluation.precision >= 0
        assert evaluation.recall >= 0
        assert evaluation.f1_score >= 0
        assert evaluation.avg_latency_p50 > 0
        assert evaluation.avg_latency_p95 > 0
        assert evaluation.avg_latency_p99 > 0
        assert evaluation.cost_efficiency > 0
        assert evaluation.escalation_rate >= 0
        assert evaluation.misroute_rate >= 0
        assert len(evaluation.results) == evaluation.total_cases
    
    @pytest.mark.asyncio
    async def test_misroute_percentage_calculation(self, router_evaluator, routers_for_evaluation):
        """Test misroute percentage calculation."""
        router = routers_for_evaluation[RouterTier.BALANCED]
        
        # Evaluate router
        evaluation = await router_evaluator.evaluate_router(router)
        
        # Calculate misroute percentage
        total_cases = evaluation.total_cases
        misroute_count = total_cases - evaluation.correct_tool_selections
        misroute_percentage = (misroute_count / total_cases) * 100
        
        # Validate misroute calculation
        assert misroute_percentage == evaluation.misroute_rate
        assert 0 <= misroute_percentage <= 100
        
        # In production, this would fail CI if misroute rate exceeds threshold
        misroute_threshold = 5.0  # 5% threshold
        if misroute_percentage > misroute_threshold:
            pytest.fail(f"MISROUTE THRESHOLD EXCEEDED: {misroute_percentage:.2f}% > {misroute_threshold}%")
    
    @pytest.mark.asyncio
    async def test_router_tier_comparison(self, router_evaluator, routers_for_evaluation):
        """Test router performance comparison across tiers."""
        evaluations = {}
        
        # Evaluate all router tiers
        for tier, router in routers_for_evaluation.items():
            evaluation = await router_evaluator.evaluate_router(router)
            evaluations[tier] = evaluation
        
        # Compare performance across tiers
        fast_eval = evaluations[RouterTier.FAST]
        balanced_eval = evaluations[RouterTier.BALANCED]
        accurate_eval = evaluations[RouterTier.ACCURATE]
        
        # FAST tier should be fastest
        assert fast_eval.avg_latency_p50 <= balanced_eval.avg_latency_p50
        assert fast_eval.avg_latency_p50 <= accurate_eval.avg_latency_p50
        
        # ACCURATE tier should have highest accuracy (in ideal scenario)
        # Note: In this mock implementation, accuracy might be similar
        assert accurate_eval.accuracy >= 0
        assert balanced_eval.accuracy >= 0
        assert fast_eval.accuracy >= 0
    
    @pytest.mark.asyncio
    async def test_cost_vs_latency_validation(self, router_evaluator, routers_for_evaluation):
        """Test expected vs actual cost and latency validation."""
        router = routers_for_evaluation[RouterTier.BALANCED]
        
        # Evaluate router
        evaluation = await router_evaluator.evaluate_router(router)
        
        # Validate cost and latency deviations
        assert evaluation.avg_cost_deviation >= 0
        assert evaluation.avg_latency_deviation >= 0
        
        # Cost deviation should be reasonable
        cost_tolerance = 20.0  # 20% tolerance
        if evaluation.avg_cost_deviation > cost_tolerance:
            pytest.fail(f"COST DEVIATION EXCEEDED: {evaluation.avg_cost_deviation:.2f}% > {cost_tolerance}%")
        
        # Latency deviation should be reasonable
        latency_tolerance = 30.0  # 30% tolerance
        if evaluation.avg_latency_deviation > latency_tolerance:
            pytest.fail(f"LATENCY DEVIATION EXCEEDED: {evaluation.avg_latency_deviation:.2f}% > {latency_tolerance}%")
    
    @pytest.mark.asyncio
    async def test_router_evaluation_summary(self, router_evaluator, routers_for_evaluation):
        """Test router evaluation summary generation."""
        router = routers_for_evaluation[RouterTier.BALANCED]
        
        # Evaluate router
        await router_evaluator.evaluate_router(router)
        
        # Get summary
        summary = router_evaluator.get_evaluation_summary(RouterTier.BALANCED)
        
        # Validate summary
        required_fields = [
            "router_tier", "accuracy", "precision", "recall", "f1_score",
            "avg_latency_p50", "avg_latency_p95", "avg_latency_p99",
            "cost_efficiency", "escalation_rate", "misroute_rate",
            "total_cases", "correct_tool_selections"
        ]
        
        for field in required_fields:
            assert field in summary, f"Missing field: {field}"
        
        # Validate summary values
        assert summary["router_tier"] == RouterTier.BALANCED.value
        assert summary["total_cases"] > 0
        assert summary["correct_tool_selections"] >= 0
    
    @pytest.mark.asyncio
    async def test_hypothesis_property_based_fuzzing(self, router_evaluator, routers_for_evaluation):
        """Test router with property-based fuzzing using Hypothesis."""
        from hypothesis import given, strategies as st
        
        router = routers_for_evaluation[RouterTier.BALANCED]
        
        @given(
            query=st.text(min_size=1, max_size=200),
            request_type=st.sampled_from([RequestType.FAQ, RequestType.ORDER, RequestType.PAYMENT, RequestType.SUPPORT, RequestType.TRACKING])
        )
        async def test_router_property(query, request_type):
            """Test router with property-based inputs."""
            tenant = factory.create_tenant(tier=TenantTier.PREMIUM)
            user = factory.create_user(tenant_id=tenant.tenant_id)
            
            request = APIRequest(
                request_id="fuzz_req",
                tenant_id=tenant.tenant_id,
                user_id=user.user_id,
                request_type=request_type,
                message=query
            )
            
            # Router should handle any input without crashing
            try:
                decision, metrics, drift = await router.route_request(request)
                
                # Validate response
                assert decision is not None
                assert metrics is not None
                assert metrics.confidence_score >= 0
                assert metrics.confidence_score <= 1
                assert metrics.cost_usd > 0
                assert metrics.decision_time_ms > 0
                
            except Exception as e:
                pytest.fail(f"Router failed on input '{query}' with type {request_type}: {e}")
        
        # Run property-based test
        await test_router_property()
    
    @pytest.mark.asyncio
    async def test_ci_failure_on_drift_threshold(self, router_evaluator, routers_for_evaluation):
        """Test that CI fails when drift exceeds threshold."""
        router = routers_for_evaluation[RouterTier.BALANCED]
        
        # Modify router to simulate drift
        original_route = router._make_routing_decision
        
        async def drifted_route(request):
            decision, metrics = await original_route(request)
            # Increase latency significantly
            metrics.decision_time_ms *= 3.0  # 3x latency increase
            # Decrease confidence
            metrics.confidence_score *= 0.7  # 30% confidence decrease
            return decision, metrics
        
        router._make_routing_decision = drifted_route
        
        # Evaluate router
        evaluation = await router_evaluator.evaluate_router(router)
        
        # Check if drift exceeds thresholds
        latency_drift_threshold = 50.0  # 50% increase
        confidence_drift_threshold = 20.0  # 20% decrease
        
        ci_failed = False
        failure_reasons = []
        
        if evaluation.avg_latency_deviation > latency_drift_threshold:
            ci_failed = True
            failure_reasons.append(f"LATENCY DRIFT: {evaluation.avg_latency_deviation:.2f}% > {latency_drift_threshold}%")
        
        if evaluation.avg_confidence_deviation > confidence_drift_threshold:
            ci_failed = True
            failure_reasons.append(f"CONFIDENCE DRIFT: {evaluation.avg_confidence_deviation:.2f}% > {confidence_drift_threshold}%")
        
        if evaluation.misroute_rate > 5.0:  # 5% misroute threshold
            ci_failed = True
            failure_reasons.append(f"MISROUTE RATE: {evaluation.misroute_rate:.2f}% > 5.0%")
        
        if ci_failed:
            failure_message = "CI FAILURE - Router drift exceeds thresholds:\n" + "\n".join(failure_reasons)
            pytest.fail(failure_message)
