"""Base judge for evaluation."""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class JudgeResult:
    """Result from judge evaluation."""
    score: float  # 0.0 to 1.0
    reasoning: str
    metrics: Dict[str, float]
    recommendations: List[str] = None
    
    def __post_init__(self):
        if self.recommendations is None:
            self.recommendations = []


class BaseJudge(ABC):
    """Base class for evaluation judges."""
    
    @abstractmethod
    async def initialize(self):
        """Initialize the judge."""
        pass
    
    @abstractmethod
    async def judge_router_decision(
        self,
        task_input: Dict[str, Any],
        expected_tier: str,
        actual_tier: str,
        actual_confidence: float,
        actual_cost_usd: float,
        actual_latency_ms: int
    ) -> JudgeResult:
        """Judge router decision quality."""
        pass
    
    @abstractmethod
    async def judge_agent_response(
        self,
        task_input: Dict[str, Any],
        expected_output: Dict[str, Any],
        actual_output: Dict[str, Any]
    ) -> JudgeResult:
        """Judge agent response quality."""
        pass
    
    async def judge_batch(
        self,
        tasks: List[Dict[str, Any]]
    ) -> List[JudgeResult]:
        """Judge multiple tasks in batch."""
        results = []
        for task in tasks:
            if task["type"] == "router":
                result = await self.judge_router_decision(**task["data"])
            elif task["type"] == "agent":
                result = await self.judge_agent_response(**task["data"])
            else:
                result = JudgeResult(
                    score=0.0,
                    reasoning="Unknown task type",
                    metrics={}
                )
            results.append(result)
        return results
