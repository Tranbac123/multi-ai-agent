"""LLM-based judge for evaluation quality assessment."""

import asyncio
import json
from typing import Dict, Any, List, Optional
from uuid import UUID
import structlog
import openai
from openai import AsyncOpenAI

logger = structlog.get_logger(__name__)


class LLMJudge:
    """LLM-based judge for evaluating response quality."""

    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.temperature = 0.1  # Low temperature for consistent evaluation

    async def evaluate_response(
        self,
        task: Dict[str, Any],
        actual_response: str,
        actual_intent: str,
        actual_confidence: float,
        actual_tools_used: List[str],
        tenant_id: UUID,
    ) -> Dict[str, Any]:
        """Evaluate response against golden task."""
        try:
            # Prepare evaluation context
            context = self._prepare_evaluation_context(
                task,
                actual_response,
                actual_intent,
                actual_confidence,
                actual_tools_used,
            )

            # Get LLM evaluation
            evaluation = await self._get_llm_evaluation(context)

            # Parse and validate evaluation
            parsed_evaluation = self._parse_evaluation(evaluation)

            # Add metadata
            parsed_evaluation.update(
                {
                    "task_id": task["task_id"],
                    "tenant_id": str(tenant_id),
                    "judge_model": self.model,
                    "evaluation_timestamp": asyncio.get_event_loop().time(),
                }
            )

            logger.info(
                "LLM evaluation completed", task_id=task["task_id"], tenant_id=tenant_id
            )

            return parsed_evaluation

        except Exception as e:
            logger.error("LLM evaluation failed", task_id=task["task_id"], error=str(e))
            return self._get_default_evaluation(task["task_id"])

    def _prepare_evaluation_context(
        self,
        task: Dict[str, Any],
        actual_response: str,
        actual_intent: str,
        actual_confidence: float,
        actual_tools_used: List[str],
    ) -> str:
        """Prepare context for LLM evaluation."""
        context = f"""
You are an expert AI evaluation judge. Evaluate the following response against the golden task.

GOLDEN TASK:
- Task ID: {task['task_id']}
- Category: {task['category']}
- Input: {task['input_text']}
- Expected Response: {task['expected_response']}
- Expected Intent: {task['expected_intent']}
- Expected Confidence: {task['expected_confidence']}
- Expected Tools: {', '.join(task['expected_tools'])}
- Difficulty: {task['metadata'].get('difficulty', 'unknown')}
- Domain: {task['metadata'].get('domain', 'unknown')}

ACTUAL RESPONSE:
- Response: {actual_response}
- Intent: {actual_intent}
- Confidence: {actual_confidence}
- Tools Used: {', '.join(actual_tools_used)}

Please provide your evaluation in the following JSON format:
{{
    "overall_score": 0.0-1.0,
    "response_quality": 0.0-1.0,
    "intent_accuracy": 0.0-1.0,
    "confidence_appropriateness": 0.0-1.0,
    "tool_usage_correctness": 0.0-1.0,
    "reasoning": "Brief explanation of evaluation",
    "strengths": ["List of strengths"],
    "weaknesses": ["List of weaknesses"],
    "improvement_suggestions": ["List of suggestions"],
    "passes_threshold": true/false
}}
"""
        return context

    async def _get_llm_evaluation(self, context: str) -> str:
        """Get evaluation from LLM."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert AI evaluation judge. Evaluate responses against golden tasks and provide detailed assessments in the specified JSON format.",
                    },
                    {"role": "user", "content": context},
                ],
                max_tokens=1000,
                temperature=self.temperature,
            )

            return response.choices[0].message.content

        except Exception as e:
            logger.error("LLM API call failed", error=str(e))
            raise

    def _parse_evaluation(self, evaluation: str) -> Dict[str, Any]:
        """Parse LLM evaluation response."""
        try:
            import re

            # Extract JSON from response
            json_match = re.search(r"\{.*\}", evaluation, re.DOTALL)
            if json_match:
                evaluation_json = json.loads(json_match.group())
            else:
                # Fallback parsing
                evaluation_json = self._fallback_parse(evaluation)

            # Validate required fields
            required_fields = [
                "overall_score",
                "response_quality",
                "intent_accuracy",
                "confidence_appropriateness",
                "tool_usage_correctness",
                "reasoning",
                "strengths",
                "weaknesses",
                "improvement_suggestions",
                "passes_threshold",
            ]

            for field in required_fields:
                if field not in evaluation_json:
                    evaluation_json[field] = self._get_default_value(field)

            # Validate scores (0.0-1.0)
            score_fields = [
                "overall_score",
                "response_quality",
                "intent_accuracy",
                "confidence_appropriateness",
                "tool_usage_correctness",
            ]

            for field in score_fields:
                score = evaluation_json.get(field, 0.0)
                if not isinstance(score, (int, float)) or not 0 <= score <= 1:
                    evaluation_json[field] = 0.0

            return evaluation_json

        except Exception as e:
            logger.error("Failed to parse evaluation", error=str(e))
            return self._get_default_evaluation("unknown")

    def _fallback_parse(self, evaluation: str) -> Dict[str, Any]:
        """Fallback parsing for non-JSON responses."""
        result = {}

        # Look for score mentions
        import re

        score_patterns = {
            "overall_score": r"overall[:\s]*(\d+\.?\d*)",
            "response_quality": r"response[:\s]*(\d+\.?\d*)",
            "intent_accuracy": r"intent[:\s]*(\d+\.?\d*)",
            "confidence_appropriateness": r"confidence[:\s]*(\d+\.?\d*)",
            "tool_usage_correctness": r"tool[:\s]*(\d+\.?\d*)",
        }

        for field, pattern in score_patterns.items():
            match = re.search(pattern, evaluation, re.IGNORECASE)
            if match:
                try:
                    result[field] = float(match.group(1))
                except ValueError:
                    result[field] = 0.0
            else:
                result[field] = 0.0

        # Look for pass/fail
        if "pass" in evaluation.lower() and "fail" not in evaluation.lower():
            result["passes_threshold"] = True
        else:
            result["passes_threshold"] = False

        # Default values for other fields
        result.update(
            {
                "reasoning": "Parsed from LLM response",
                "strengths": [],
                "weaknesses": [],
                "improvement_suggestions": [],
            }
        )

        return result

    def _get_default_value(self, field: str) -> Any:
        """Get default value for missing field."""
        defaults = {
            "overall_score": 0.0,
            "response_quality": 0.0,
            "intent_accuracy": 0.0,
            "confidence_appropriateness": 0.0,
            "tool_usage_correctness": 0.0,
            "reasoning": "Default evaluation",
            "strengths": [],
            "weaknesses": [],
            "improvement_suggestions": [],
            "passes_threshold": False,
        }
        return defaults.get(field, None)

    def _get_default_evaluation(self, task_id: str) -> Dict[str, Any]:
        """Get default evaluation when parsing fails."""
        return {
            "task_id": task_id,
            "overall_score": 0.0,
            "response_quality": 0.0,
            "intent_accuracy": 0.0,
            "confidence_appropriateness": 0.0,
            "tool_usage_correctness": 0.0,
            "reasoning": "Default evaluation due to parsing error",
            "strengths": [],
            "weaknesses": ["Evaluation parsing failed"],
            "improvement_suggestions": ["Fix evaluation parsing"],
            "passes_threshold": False,
        }

    async def batch_evaluate(
        self,
        tasks: List[Dict[str, Any]],
        responses: List[Dict[str, Any]],
        tenant_id: UUID,
    ) -> List[Dict[str, Any]]:
        """Evaluate multiple responses in batch."""
        try:
            evaluations = []

            # Process evaluations in parallel
            tasks_list = []
            for task, response in zip(tasks, responses):
                task_eval = self.evaluate_response(
                    task,
                    response["actual_response"],
                    response["actual_intent"],
                    response["actual_confidence"],
                    response["actual_tools_used"],
                    tenant_id,
                )
                tasks_list.append(task_eval)

            evaluations = await asyncio.gather(*tasks_list, return_exceptions=True)

            # Handle exceptions
            processed_evaluations = []
            for i, evaluation in enumerate(evaluations):
                if isinstance(evaluation, Exception):
                    logger.error(
                        "Batch evaluation failed for task",
                        index=i,
                        error=str(evaluation),
                    )
                    processed_evaluations.append(
                        self._get_default_evaluation(tasks[i]["task_id"])
                    )
                else:
                    processed_evaluations.append(evaluation)

            logger.info(
                "Batch evaluation completed", task_count=len(tasks), tenant_id=tenant_id
            )

            return processed_evaluations

        except Exception as e:
            logger.error("Batch evaluation failed", tenant_id=tenant_id, error=str(e))
            return [self._get_default_evaluation(task["task_id"]) for task in tasks]

    async def get_evaluation_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get evaluation statistics for tenant."""
        try:
            # This would typically query a database or cache
            # For now, return mock stats
            return {
                "total_evaluations": 0,
                "average_score": 0.0,
                "pass_rate": 0.0,
                "evaluation_distribution": {
                    "excellent": 0,
                    "good": 0,
                    "fair": 0,
                    "poor": 0,
                },
            }

        except Exception as e:
            logger.error(
                "Failed to get evaluation stats", tenant_id=tenant_id, error=str(e)
            )
            return {}
