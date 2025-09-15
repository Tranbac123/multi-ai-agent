"""Router evaluation tests for performance and correctness."""

import pytest
import asyncio
from typing import Dict, Any, List
from datetime import datetime

from tests.eval import EvaluationMetric, EvaluationResult, RouterEvaluation
from tests.integration.router import RouterTier, RouterDecision
from tests.contract.schemas import APIRequest, RequestType


class RouterEvaluator:
    """Evaluates router performance against benchmarks."""
    
    def __init__(self):
        self.benchmarks = {
            'accuracy_threshold': 0.95,
            'response_time_threshold': 200.0,  # ms
            'cost_efficiency_threshold': 0.005,  # USD
            'escalation_rate_threshold': 0.1  # 10%
        }
    
    def evaluate_router_performance(self, results: List[Dict[str, Any]]) -> List[RouterEvaluation]:
        """Evaluate router performance against benchmarks."""
        evaluations = []
        
        # Calculate metrics
        total_requests = len(results)
        successful_requests = len([r for r in results if r.get('success', False)])
        avg_response_time = sum(r.get('response_time', 0) for r in results) / total_requests if total_requests > 0 else 0
        avg_cost = sum(r.get('cost', 0) for r in results) / total_requests if total_requests > 0 else 0
        escalation_rate = len([r for r in results if r.get('escalated', False)]) / total_requests if total_requests > 0 else 0
        
        # Evaluate accuracy
        accuracy = successful_requests / total_requests if total_requests > 0 else 0
        evaluations.append(RouterEvaluation(
            metric_name=EvaluationMetric.ACCURACY,
            expected_value=self.benchmarks['accuracy_threshold'],
            actual_value=accuracy,
            threshold=self.benchmarks['accuracy_threshold'],
            result=EvaluationResult.PASSED if accuracy >= self.benchmarks['accuracy_threshold'] else EvaluationResult.FAILED,
            timestamp=datetime.now()
        ))
        
        # Evaluate response time
        evaluations.append(RouterEvaluation(
            metric_name=EvaluationMetric.RESPONSE_TIME,
            expected_value=self.benchmarks['response_time_threshold'],
            actual_value=avg_response_time,
            threshold=self.benchmarks['response_time_threshold'],
            result=EvaluationResult.PASSED if avg_response_time <= self.benchmarks['response_time_threshold'] else EvaluationResult.FAILED,
            timestamp=datetime.now()
        ))
        
        # Evaluate cost efficiency
        evaluations.append(RouterEvaluation(
            metric_name=EvaluationMetric.COST_EFFICIENCY,
            expected_value=self.benchmarks['cost_efficiency_threshold'],
            actual_value=avg_cost,
            threshold=self.benchmarks['cost_efficiency_threshold'],
            result=EvaluationResult.PASSED if avg_cost <= self.benchmarks['cost_efficiency_threshold'] else EvaluationResult.FAILED,
            timestamp=datetime.now()
        ))
        
        return evaluations


class TestRouterEvaluation:
    """Test router evaluation against benchmarks."""
    
    @pytest.fixture
    def router_evaluator(self):
        """Create router evaluator."""
        return RouterEvaluator()
    
    def test_router_accuracy_evaluation(self, router_evaluator):
        """Test router accuracy evaluation."""
        # Create test results
        test_results = [
            {'success': True, 'response_time': 150, 'cost': 0.002, 'escalated': False},
            {'success': True, 'response_time': 180, 'cost': 0.003, 'escalated': False},
            {'success': False, 'response_time': 200, 'cost': 0.004, 'escalated': True},
            {'success': True, 'response_time': 120, 'cost': 0.002, 'escalated': False},
            {'success': True, 'response_time': 160, 'cost': 0.002, 'escalated': False}
        ]
        
        # Evaluate performance
        evaluations = router_evaluator.evaluate_router_performance(test_results)
        
        # Validate evaluations
        assert len(evaluations) == 3
        
        accuracy_eval = next(e for e in evaluations if e.metric_name == EvaluationMetric.ACCURACY)
        assert accuracy_eval.actual_value == 0.8  # 4 out of 5 successful
        assert accuracy_eval.result == EvaluationResult.FAILED  # Below 95% threshold
        
        response_time_eval = next(e for e in evaluations if e.metric_name == EvaluationMetric.RESPONSE_TIME)
        assert response_time_eval.actual_value == 162.0  # Average response time
        assert response_time_eval.result == EvaluationResult.PASSED  # Below 200ms threshold
        
        cost_eval = next(e for e in evaluations if e.metric_name == EvaluationMetric.COST_EFFICIENCY)
        assert abs(cost_eval.actual_value - 0.0026) < 0.0001  # Average cost (with floating point tolerance)
        assert cost_eval.result == EvaluationResult.PASSED  # Below $0.005 threshold
    
    def test_router_performance_benchmarks(self, router_evaluator):
        """Test router performance against benchmarks."""
        # Create high-performance test results
        high_perf_results = [
            {'success': True, 'response_time': 100, 'cost': 0.001, 'escalated': False},
            {'success': True, 'response_time': 120, 'cost': 0.002, 'escalated': False},
            {'success': True, 'response_time': 110, 'cost': 0.001, 'escalated': False},
            {'success': True, 'response_time': 130, 'cost': 0.002, 'escalated': False},
            {'success': True, 'response_time': 115, 'cost': 0.001, 'escalated': False}
        ]
        
        # Evaluate performance
        evaluations = router_evaluator.evaluate_router_performance(high_perf_results)
        
        # All evaluations should pass
        for evaluation in evaluations:
            assert evaluation.result == EvaluationResult.PASSED
    
    def test_router_failure_detection(self, router_evaluator):
        """Test router failure detection."""
        # Create failing test results
        failing_results = [
            {'success': False, 'response_time': 500, 'cost': 0.010, 'escalated': True},
            {'success': False, 'response_time': 600, 'cost': 0.012, 'escalated': True},
            {'success': True, 'response_time': 150, 'cost': 0.002, 'escalated': False},
            {'success': False, 'response_time': 700, 'cost': 0.015, 'escalated': True},
            {'success': False, 'response_time': 400, 'cost': 0.008, 'escalated': True}
        ]
        
        # Evaluate performance
        evaluations = router_evaluator.evaluate_router_performance(failing_results)
        
        # All evaluations should fail
        for evaluation in evaluations:
            assert evaluation.result == EvaluationResult.FAILED
    
    def test_router_evaluation_metrics_structure(self, router_evaluator):
        """Test router evaluation metrics structure."""
        test_results = [
            {'success': True, 'response_time': 150, 'cost': 0.002, 'escalated': False}
        ]
        
        evaluations = router_evaluator.evaluate_router_performance(test_results)
        
        # Validate metric structure
        for evaluation in evaluations:
            assert evaluation.metric_name in [EvaluationMetric.ACCURACY, EvaluationMetric.RESPONSE_TIME, EvaluationMetric.COST_EFFICIENCY]
            assert evaluation.expected_value > 0
            assert evaluation.actual_value >= 0
            assert evaluation.threshold > 0
            assert evaluation.result in [EvaluationResult.PASSED, EvaluationResult.FAILED]
            assert isinstance(evaluation.timestamp, datetime)
