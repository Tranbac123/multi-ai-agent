"""
LLM Judge for Evaluation

Implements LLM-based evaluation with structured scoring, criteria-based assessment,
and comprehensive evaluation metrics for golden task validation.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta
from openai import AsyncOpenAI
import re

from src.golden_tasks import GoldenTask, TaskExecution, EvaluationResult

logger = structlog.get_logger(__name__)


class EvaluationMethod(Enum):
    """Evaluation methods for LLM judge."""
    EXACT_MATCH = "exact_match"
    SEMANTIC_SIMILARITY = "semantic_similarity"
    CRITERIA_BASED = "criteria_based"
    LLM_JUDGE = "llm_judge"
    HYBRID = "hybrid"


class ScoringScale(Enum):
    """Scoring scales for evaluation."""
    BINARY = "binary"  # 0 or 1
    FIVE_POINT = "five_point"  # 1-5
    TEN_POINT = "ten_point"  # 1-10
    PERCENTAGE = "percentage"  # 0-100
    CUSTOM = "custom"


@dataclass
class EvaluationCriteria:
    """Evaluation criteria definition."""
    
    name: str
    description: str
    weight: float  # Weight in overall score (0.0 to 1.0)
    scoring_scale: ScoringScale
    min_score: float
    max_score: float
    evaluation_prompt: str
    expected_format: str = "json"


@dataclass
class LLMJudgeConfig:
    """Configuration for LLM judge."""
    
    model: str = "gpt-4"
    temperature: float = 0.1
    max_tokens: int = 1000
    timeout_seconds: int = 60
    retry_attempts: int = 3
    evaluation_prompt_template: str = ""
    system_prompt: str = ""
    criteria: List[EvaluationCriteria] = field(default_factory=list)


@dataclass
class JudgeResponse:
    """Response from LLM judge."""
    
    overall_score: float
    criteria_scores: Dict[str, float]
    reasoning: str
    passed: bool
    confidence: float
    raw_response: str
    evaluation_time_ms: int
    model_used: str


class LLMJudge:
    """LLM-based judge for task evaluation."""
    
    def __init__(self, config: LLMJudgeConfig, openai_client: Optional[AsyncOpenAI] = None):
        self.config = config
        self.openai_client = openai_client or AsyncOpenAI()
        
        # Default evaluation prompt template
        if not self.config.evaluation_prompt_template:
            self.config.evaluation_prompt_template = self._get_default_evaluation_template()
        
        # Default system prompt
        if not self.config.system_prompt:
            self.config.system_prompt = self._get_default_system_prompt()
        
        logger.info("LLM judge initialized", 
                   model=config.model,
                   criteria_count=len(config.criteria))
    
    def _get_default_system_prompt(self) -> str:
        """Get default system prompt for LLM judge."""
        
        return """You are an expert evaluator for AI agent performance. Your task is to objectively evaluate the quality of AI agent responses against specific criteria.

Guidelines:
1. Be objective and unbiased in your evaluation
2. Consider the context and requirements carefully
3. Provide detailed reasoning for your scores
4. Use the specified scoring scale consistently
5. If the response is incomplete or unclear, score accordingly
6. Focus on accuracy, relevance, and quality

You must respond with a valid JSON object containing your evaluation."""
    
    def _get_default_evaluation_template(self) -> str:
        """Get default evaluation prompt template."""
        
        return """Please evaluate the following AI agent response against the given criteria.

TASK DESCRIPTION:
{task_description}

INPUT DATA:
{input_data}

EXPECTED OUTPUT:
{expected_output}

ACTUAL OUTPUT:
{actual_output}

EVALUATION CRITERIA:
{evaluation_criteria}

Please provide your evaluation as a JSON object with the following structure:
{{
    "overall_score": <float between 0 and 100>,
    "criteria_scores": {{
        <criterion_name>: <float between 0 and 100>
    }},
    "reasoning": "<detailed explanation of your evaluation>",
    "passed": <boolean indicating if the response meets minimum requirements>,
    "confidence": <float between 0 and 1 indicating your confidence in this evaluation>
}}

Focus on:
1. Accuracy and correctness of the response
2. Completeness of the answer
3. Relevance to the task requirements
4. Quality and clarity of the response
5. Adherence to expected format/structure"""
    
    async def evaluate_task_execution(
        self, 
        task: GoldenTask, 
        execution: TaskExecution
    ) -> JudgeResponse:
        """Evaluate a task execution using LLM judge."""
        
        if not execution.actual_output:
            raise ValueError("Task execution has no actual output to evaluate")
        
        start_time = datetime.now()
        
        # Prepare evaluation prompt
        prompt = self._prepare_evaluation_prompt(task, execution)
        
        # Get LLM evaluation
        raw_response = await self._get_llm_evaluation(prompt)
        
        # Parse and validate response
        judge_response = self._parse_judge_response(raw_response, start_time)
        
        logger.info("LLM judge evaluation completed", 
                   execution_id=execution.execution_id,
                   task_id=task.task_id,
                   overall_score=judge_response.overall_score,
                   passed=judge_response.passed,
                   evaluation_time_ms=judge_response.evaluation_time_ms)
        
        return judge_response
    
    def _prepare_evaluation_prompt(
        self, 
        task: GoldenTask, 
        execution: TaskExecution
    ) -> str:
        """Prepare evaluation prompt for LLM."""
        
        # Format evaluation criteria
        criteria_text = "\n".join([
            f"- {criterion.name}: {criterion.description} (Weight: {criterion.weight})"
            for criterion in self.config.criteria
        ])
        
        # Prepare prompt
        prompt = self.config.evaluation_prompt_template.format(
            task_description=task.description,
            input_data=json.dumps(task.input_data, indent=2),
            expected_output=json.dumps(task.expected_output, indent=2),
            actual_output=json.dumps(execution.actual_output, indent=2),
            evaluation_criteria=criteria_text
        )
        
        return prompt
    
    async def _get_llm_evaluation(self, prompt: str) -> str:
        """Get evaluation from LLM with retries."""
        
        for attempt in range(self.config.retry_attempts):
            try:
                response = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model=self.config.model,
                        messages=[
                            {"role": "system", "content": self.config.system_prompt},
                            {"role": "user", "content": prompt}
                        ],
                        temperature=self.config.temperature,
                        max_tokens=self.config.max_tokens
                    ),
                    timeout=self.config.timeout_seconds
                )
                
                return response.choices[0].message.content
                
            except asyncio.TimeoutError:
                logger.warning("LLM evaluation timeout", attempt=attempt + 1)
                if attempt == self.config.retry_attempts - 1:
                    raise
            except Exception as e:
                logger.error("LLM evaluation error", attempt=attempt + 1, error=str(e))
                if attempt == self.config.retry_attempts - 1:
                    raise
        
        raise RuntimeError("All LLM evaluation attempts failed")
    
    def _parse_judge_response(self, raw_response: str, start_time: datetime) -> JudgeResponse:
        """Parse and validate LLM judge response."""
        
        evaluation_time_ms = int((datetime.now() - start_time).total_seconds() * 1000)
        
        try:
            # Extract JSON from response (handle cases where LLM adds extra text)
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON found in LLM response")
            
            response_data = json.loads(json_match.group())
            
            # Validate required fields
            required_fields = ["overall_score", "criteria_scores", "reasoning", "passed", "confidence"]
            for field in required_fields:
                if field not in response_data:
                    raise ValueError(f"Missing required field: {field}")
            
            # Validate score ranges
            overall_score = float(response_data["overall_score"])
            if not (0 <= overall_score <= 100):
                raise ValueError(f"Overall score out of range: {overall_score}")
            
            # Validate criteria scores
            criteria_scores = {}
            for criterion in self.config.criteria:
                if criterion.name in response_data["criteria_scores"]:
                    score = float(response_data["criteria_scores"][criterion.name])
                    if not (0 <= score <= 100):
                        logger.warning(f"Criteria score out of range: {criterion.name}={score}")
                    criteria_scores[criterion.name] = score
                else:
                    criteria_scores[criterion.name] = 0.0
            
            # Validate confidence
            confidence = float(response_data["confidence"])
            if not (0 <= confidence <= 1):
                logger.warning(f"Confidence out of range: {confidence}")
                confidence = max(0.0, min(1.0, confidence))
            
            return JudgeResponse(
                overall_score=overall_score,
                criteria_scores=criteria_scores,
                reasoning=response_data["reasoning"],
                passed=bool(response_data["passed"]),
                confidence=confidence,
                raw_response=raw_response,
                evaluation_time_ms=evaluation_time_ms,
                model_used=self.config.model
            )
            
        except Exception as e:
            logger.error("Failed to parse LLM judge response", error=str(e))
            
            # Return default response for failed parsing
            return JudgeResponse(
                overall_score=0.0,
                criteria_scores={criterion.name: 0.0 for criterion in self.config.criteria},
                reasoning=f"Failed to parse LLM response: {str(e)}",
                passed=False,
                confidence=0.0,
                raw_response=raw_response,
                evaluation_time_ms=evaluation_time_ms,
                model_used=self.config.model
            )
    
    def create_evaluation_result(
        self, 
        execution: TaskExecution, 
        judge_response: JudgeResponse
    ) -> EvaluationResult:
        """Create evaluation result from judge response."""
        
        return EvaluationResult(
            execution_id=execution.execution_id,
            task_id=execution.task_id,
            overall_score=judge_response.overall_score,
            criteria_scores=judge_response.criteria_scores,
            passed=judge_response.passed,
            evaluation_method=EvaluationMethod.LLM_JUDGE.value,
            evaluated_at=datetime.now(),
            evaluator_metadata={
                "model": judge_response.model_used,
                "confidence": judge_response.confidence,
                "evaluation_time_ms": judge_response.evaluation_time_ms,
                "reasoning": judge_response.reasoning
            }
        )


class EvaluationEngine:
    """Engine for comprehensive task evaluation."""
    
    def __init__(self, llm_judge: LLMJudge):
        self.llm_judge = llm_judge
        
        logger.info("Evaluation engine initialized")
    
    async def evaluate_execution(
        self, 
        task: GoldenTask, 
        execution: TaskExecution,
        methods: List[EvaluationMethod] = None
    ) -> List[EvaluationResult]:
        """Evaluate task execution using multiple methods."""
        
        if methods is None:
            methods = [EvaluationMethod.LLM_JUDGE]
        
        results = []
        
        for method in methods:
            try:
                if method == EvaluationMethod.EXACT_MATCH:
                    result = await self._evaluate_exact_match(task, execution)
                elif method == EvaluationMethod.SEMANTIC_SIMILARITY:
                    result = await self._evaluate_semantic_similarity(task, execution)
                elif method == EvaluationMethod.CRITERIA_BASED:
                    result = await self._evaluate_criteria_based(task, execution)
                elif method == EvaluationMethod.LLM_JUDGE:
                    judge_response = await self.llm_judge.evaluate_task_execution(task, execution)
                    result = self.llm_judge.create_evaluation_result(execution, judge_response)
                else:
                    logger.warning("Unknown evaluation method", method=method.value)
                    continue
                
                results.append(result)
                
            except Exception as e:
                logger.error("Evaluation method failed", 
                           method=method.value,
                           execution_id=execution.execution_id,
                           error=str(e))
        
        return results
    
    async def _evaluate_exact_match(
        self, 
        task: GoldenTask, 
        execution: TaskExecution
    ) -> EvaluationResult:
        """Evaluate using exact string matching."""
        
        if not execution.actual_output:
            return EvaluationResult(
                execution_id=execution.execution_id,
                task_id=execution.task_id,
                overall_score=0.0,
                criteria_scores={"exact_match": 0.0},
                passed=False,
                evaluation_method=EvaluationMethod.EXACT_MATCH.value,
                evaluated_at=datetime.now()
            )
        
        # Simple string comparison
        expected_str = json.dumps(task.expected_output, sort_keys=True)
        actual_str = json.dumps(execution.actual_output, sort_keys=True)
        
        score = 100.0 if expected_str == actual_str else 0.0
        
        return EvaluationResult(
            execution_id=execution.execution_id,
            task_id=execution.task_id,
            overall_score=score,
            criteria_scores={"exact_match": score},
            passed=score > 0.0,
            evaluation_method=EvaluationMethod.EXACT_MATCH.value,
            evaluated_at=datetime.now()
        )
    
    async def _evaluate_semantic_similarity(
        self, 
        task: GoldenTask, 
        execution: TaskExecution
    ) -> EvaluationResult:
        """Evaluate using semantic similarity (placeholder implementation)."""
        
        # In a real implementation, this would use embeddings or other semantic similarity measures
        # For now, return a placeholder score
        
        score = 75.0  # Placeholder score
        
        return EvaluationResult(
            execution_id=execution.execution_id,
            task_id=execution.task_id,
            overall_score=score,
            criteria_scores={"semantic_similarity": score},
            passed=score >= 70.0,
            evaluation_method=EvaluationMethod.SEMANTIC_SIMILARITY.value,
            evaluated_at=datetime.now()
        )
    
    async def _evaluate_criteria_based(
        self, 
        task: GoldenTask, 
        execution: TaskExecution
    ) -> EvaluationResult:
        """Evaluate using predefined criteria."""
        
        if not execution.actual_output:
            return EvaluationResult(
                execution_id=execution.execution_id,
                task_id=execution.task_id,
                overall_score=0.0,
                criteria_scores={},
                passed=False,
                evaluation_method=EvaluationMethod.CRITERIA_BASED.value,
                evaluated_at=datetime.now()
            )
        
        # Simple criteria-based evaluation (placeholder)
        criteria_scores = {
            "completeness": 80.0,
            "accuracy": 85.0,
            "relevance": 90.0
        }
        
        # Calculate weighted overall score
        weights = {"completeness": 0.3, "accuracy": 0.4, "relevance": 0.3}
        overall_score = sum(score * weights[criterion] for criterion, score in criteria_scores.items())
        
        return EvaluationResult(
            execution_id=execution.execution_id,
            task_id=execution.task_id,
            overall_score=overall_score,
            criteria_scores=criteria_scores,
            passed=overall_score >= 70.0,
            evaluation_method=EvaluationMethod.CRITERIA_BASED.value,
            evaluated_at=datetime.now()
        )
    
    def calculate_composite_score(self, results: List[EvaluationResult]) -> float:
        """Calculate composite score from multiple evaluation results."""
        
        if not results:
            return 0.0
        
        # Simple average (in production, could use weighted average based on method confidence)
        total_score = sum(result.overall_score for result in results)
        return total_score / len(results)
    
    def determine_overall_pass(self, results: List[EvaluationResult]) -> bool:
        """Determine if execution passes based on multiple evaluation results."""
        
        if not results:
            return False
        
        # Pass if majority of methods indicate pass
        pass_count = sum(1 for result in results if result.passed)
        return pass_count > len(results) / 2
