"""LLM judge for borderline routing decisions."""

import asyncio
from typing import Dict, Any, List, Optional
from uuid import UUID
import structlog
import openai
from openai import AsyncOpenAI

logger = structlog.get_logger(__name__)


class LLMJudge:
    """LLM-powered judge for complex routing decisions."""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.max_tokens = 1000
        self.temperature = 0.1  # Low temperature for consistent decisions
    
    async def judge_routing_decision(
        self,
        request_text: str,
        features: Dict[str, Any],
        suggested_tier: str,
        confidence: float,
        tenant_id: UUID
    ) -> Dict[str, Any]:
        """Judge routing decision and provide reasoning."""
        try:
            # Prepare context for LLM
            context = self._prepare_judgment_context(
                request_text, features, suggested_tier, confidence
            )
            
            # Get LLM judgment
            judgment = await self._get_llm_judgment(context)
            
            # Parse and validate judgment
            parsed_judgment = self._parse_judgment(judgment)
            
            # Add metadata
            parsed_judgment.update({
                "request_text": request_text,
                "suggested_tier": suggested_tier,
                "confidence": confidence,
                "tenant_id": str(tenant_id),
                "judge_model": self.model
            })
            
            logger.info("LLM judgment completed", 
                       suggested_tier=suggested_tier, 
                       final_tier=parsed_judgment.get("final_tier"),
                       tenant_id=tenant_id)
            
            return parsed_judgment
            
        except Exception as e:
            logger.error("LLM judgment failed", 
                        tenant_id=tenant_id, 
                        error=str(e))
            # Fallback to original suggestion
            return {
                "final_tier": suggested_tier,
                "confidence": confidence,
                "reasoning": "LLM judge unavailable, using original suggestion",
                "escalation_recommended": confidence < 0.7,
                "error": str(e)
            }
    
    def _prepare_judgment_context(
        self,
        request_text: str,
        features: Dict[str, Any],
        suggested_tier: str,
        confidence: float
    ) -> str:
        """Prepare context for LLM judgment."""
        context = f"""
You are an expert AI routing judge. Analyze the following request and routing decision:

REQUEST TEXT:
{request_text}

REQUEST FEATURES:
- Text Length: {features.get('text_length', 0)} characters
- Word Count: {features.get('word_count', 0)} words
- Has Question: {features.get('has_question', False)}
- Has Technical Terms: {features.get('has_technical_terms', False)}
- Has Urgency: {features.get('has_urgency', False)}
- Complexity Score: {features.get('avg_word_length', 0):.2f}

SUGGESTED ROUTING:
- Tier: {suggested_tier}
- Confidence: {confidence:.2f}

AVAILABLE TIERS:
- SLM_A: Fast, cheap, good for simple questions and classifications
- SLM_B: Medium speed/cost, good for complex questions and reasoning
- LLM: Slow, expensive, best for advanced reasoning and creative tasks

Please provide your judgment in the following JSON format:
{{
    "final_tier": "SLM_A|SLM_B|LLM",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of decision",
    "escalation_recommended": true/false,
    "alternative_tier": "Alternative if different from final_tier",
    "risk_factors": ["List of potential issues"]
}}
"""
        return context
    
    async def _get_llm_judgment(self, context: str) -> str:
        """Get judgment from LLM."""
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert AI routing judge. Analyze requests and provide routing decisions in the specified JSON format."
                    },
                    {
                        "role": "user",
                        "content": context
                    }
                ],
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("LLM API call failed", error=str(e))
            raise
    
    def _parse_judgment(self, judgment: str) -> Dict[str, Any]:
        """Parse LLM judgment response."""
        try:
            import json
            import re
            
            # Extract JSON from response
            json_match = re.search(r'\{.*\}', judgment, re.DOTALL)
            if json_match:
                judgment_json = json.loads(json_match.group())
            else:
                # Fallback parsing
                judgment_json = self._fallback_parse(judgment)
            
            # Validate required fields
            required_fields = ["final_tier", "confidence", "reasoning"]
            for field in required_fields:
                if field not in judgment_json:
                    judgment_json[field] = self._get_default_value(field)
            
            # Validate tier
            valid_tiers = ["SLM_A", "SLM_B", "LLM"]
            if judgment_json["final_tier"] not in valid_tiers:
                judgment_json["final_tier"] = "LLM"  # Safe fallback
            
            # Validate confidence
            confidence = judgment_json.get("confidence", 0.5)
            if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
                judgment_json["confidence"] = 0.5
            
            return judgment_json
            
        except Exception as e:
            logger.error("Failed to parse judgment", error=str(e))
            return self._get_default_judgment()
    
    def _fallback_parse(self, judgment: str) -> Dict[str, Any]:
        """Fallback parsing for non-JSON responses."""
        result = {}
        
        # Look for tier mentions
        if "SLM_A" in judgment.upper():
            result["final_tier"] = "SLM_A"
        elif "SLM_B" in judgment.upper():
            result["final_tier"] = "SLM_B"
        elif "LLM" in judgment.upper():
            result["final_tier"] = "LLM"
        else:
            result["final_tier"] = "LLM"
        
        # Look for confidence mentions
        import re
        confidence_match = re.search(r'confidence[:\s]*(\d+\.?\d*)', judgment, re.IGNORECASE)
        if confidence_match:
            try:
                result["confidence"] = float(confidence_match.group(1))
            except ValueError:
                result["confidence"] = 0.5
        else:
            result["confidence"] = 0.5
        
        # Extract reasoning
        reasoning_match = re.search(r'reasoning[:\s]*([^.]+)', judgment, re.IGNORECASE)
        if reasoning_match:
            result["reasoning"] = reasoning_match.group(1).strip()
        else:
            result["reasoning"] = "Parsed from LLM response"
        
        return result
    
    def _get_default_value(self, field: str) -> Any:
        """Get default value for missing field."""
        defaults = {
            "final_tier": "LLM",
            "confidence": 0.5,
            "reasoning": "Default judgment",
            "escalation_recommended": False,
            "alternative_tier": None,
            "risk_factors": []
        }
        return defaults.get(field, None)
    
    def _get_default_judgment(self) -> Dict[str, Any]:
        """Get default judgment when parsing fails."""
        return {
            "final_tier": "LLM",
            "confidence": 0.5,
            "reasoning": "Default judgment due to parsing error",
            "escalation_recommended": True,
            "alternative_tier": None,
            "risk_factors": ["Judgment parsing failed"]
        }
    
    async def batch_judge(
        self,
        requests: List[Dict[str, Any]],
        tenant_id: UUID
    ) -> List[Dict[str, Any]]:
        """Judge multiple requests in batch."""
        try:
            judgments = []
            
            # Process requests in parallel
            tasks = []
            for request in requests:
                task = self.judge_routing_decision(
                    request["text"],
                    request["features"],
                    request["suggested_tier"],
                    request["confidence"],
                    tenant_id
                )
                tasks.append(task)
            
            judgments = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Handle exceptions
            processed_judgments = []
            for i, judgment in enumerate(judgments):
                if isinstance(judgment, Exception):
                    logger.error("Batch judgment failed for request", 
                                index=i, 
                                error=str(judgment))
                    processed_judgments.append(self._get_default_judgment())
                else:
                    processed_judgments.append(judgment)
            
            logger.info("Batch judgment completed", 
                       request_count=len(requests), 
                       tenant_id=tenant_id)
            
            return processed_judgments
            
        except Exception as e:
            logger.error("Batch judgment failed", 
                        tenant_id=tenant_id, 
                        error=str(e))
            return [self._get_default_judgment() for _ in requests]
    
    async def get_judgment_stats(self, tenant_id: UUID) -> Dict[str, Any]:
        """Get judgment statistics for tenant."""
        try:
            # This would typically query a database or cache
            # For now, return mock stats
            return {
                "total_judgments": 0,
                "tier_distribution": {
                    "SLM_A": 0,
                    "SLM_B": 0,
                    "LLM": 0
                },
                "avg_confidence": 0.0,
                "escalation_rate": 0.0
            }
            
        except Exception as e:
            logger.error("Failed to get judgment stats", 
                        tenant_id=tenant_id, 
                        error=str(e))
            return {}
