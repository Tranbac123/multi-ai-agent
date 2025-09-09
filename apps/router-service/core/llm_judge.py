"""LLM judge for borderline cases and misroute detection."""

import asyncio
import time
import json
from typing import Dict, List, Any, Optional, Tuple
import structlog
import openai
import redis.asyncio as redis

logger = structlog.get_logger(__name__)


class LLMJudge:
    """LLM judge for evaluating router decisions and detecting misroutes."""
    
    def __init__(
        self,
        openai_api_key: str,
        redis_client: redis.Redis,
        model_name: str = "gpt-4",
        temperature: float = 0.1
    ):
        self.openai_api_key = openai_api_key
        self.redis_client = redis_client
        self.model_name = model_name
        self.temperature = temperature
        
        # Initialize OpenAI client
        openai.api_key = openai_api_key
    
    async def judge_decision(
        self,
        message: str,
        features: Dict[str, Any],
        predicted_tier: str,
        confidence: float,
        tenant_id: str,
        user_id: Optional[str] = None
    ) -> Tuple[str, float, str, bool]:
        """
        Judge a router decision for borderline cases.
        
        Returns:
            (corrected_tier, judge_confidence, reasoning, is_misroute)
        """
        try:
            # Check if this is a borderline case
            if confidence > 0.8:
                # High confidence, no need for LLM judge
                return predicted_tier, confidence, "High confidence decision", False
            
            # Prepare context for LLM judge
            context = await self._prepare_judge_context(
                message, features, predicted_tier, confidence, tenant_id
            )
            
            # Get LLM judgment
            judgment = await self._get_llm_judgment(context)
            
            # Parse judgment
            corrected_tier, judge_confidence, reasoning = self._parse_judgment(judgment)
            
            # Determine if this was a misroute
            is_misroute = corrected_tier != predicted_tier
            
            # Record judgment for learning
            await self._record_judgment(
                tenant_id, user_id, message, predicted_tier, corrected_tier,
                confidence, judge_confidence, reasoning, is_misroute
            )
            
            logger.info(
                "LLM judgment completed",
                tenant_id=tenant_id,
                user_id=user_id,
                predicted_tier=predicted_tier,
                corrected_tier=corrected_tier,
                is_misroute=is_misroute,
                judge_confidence=judge_confidence
            )
            
            return corrected_tier, judge_confidence, reasoning, is_misroute
            
        except Exception as e:
            logger.error(
                "LLM judgment failed",
                error=str(e),
                tenant_id=tenant_id,
                user_id=user_id
            )
            # Return original decision on error
            return predicted_tier, confidence, "LLM judgment failed", False
    
    async def _prepare_judge_context(
        self,
        message: str,
        features: Dict[str, Any],
        predicted_tier: str,
        confidence: float,
        tenant_id: str
    ) -> Dict[str, Any]:
        """Prepare context for LLM judge."""
        # Get tenant-specific context
        tenant_context = await self._get_tenant_context(tenant_id)
        
        # Get historical performance
        historical_performance = await self._get_historical_performance(tenant_id)
        
        context = {
            'message': message,
            'features': {
                'text_length': features.get('text_length', 0),
                'word_count': features.get('word_count', 0),
                'intent_order': features.get('intent_order', False),
                'intent_support': features.get('intent_support', False),
                'sentiment_negative': features.get('sentiment_negative', False),
                'urgency_high': features.get('urgency_high', False),
                'technical_complexity': features.get('technical_complexity', False)
            },
            'predicted_tier': predicted_tier,
            'confidence': confidence,
            'tenant_context': tenant_context,
            'historical_performance': historical_performance,
            'tier_descriptions': {
                'A': 'Fast, cheap agent for simple queries (FAQ, basic support)',
                'B': 'Medium agent for moderate complexity (order management, account issues)',
                'C': 'Slow, expensive but accurate agent for complex problems (technical support, escalations)'
            }
        }
        
        return context
    
    async def _get_tenant_context(self, tenant_id: str) -> Dict[str, Any]:
        """Get tenant-specific context."""
        try:
            context_key = f"tenant_context:{tenant_id}"
            context_data = await self.redis_client.hgetall(context_key)
            
            if context_data:
                return {
                    'domain': context_data.get('domain', 'unknown'),
                    'industry': context_data.get('industry', 'unknown'),
                    'typical_queries': context_data.get('typical_queries', ''),
                    'escalation_rate': float(context_data.get('escalation_rate', 0.1))
                }
            else:
                return {
                    'domain': 'unknown',
                    'industry': 'unknown',
                    'typical_queries': '',
                    'escalation_rate': 0.1
                }
                
        except Exception as e:
            logger.error("Failed to get tenant context", error=str(e))
            return {}
    
    async def _get_historical_performance(self, tenant_id: str) -> Dict[str, Any]:
        """Get historical performance data."""
        try:
            performance_key = f"tier_performance:{tenant_id}"
            performance_data = await self.redis_client.hgetall(performance_key)
            
            historical_performance = {}
            for tier in ['A', 'B', 'C']:
                tier_key = f"{tier}_performance"
                if tier_key in performance_data:
                    import json
                    historical_performance[tier] = json.loads(performance_data[tier_key])
                else:
                    historical_performance[tier] = {
                        'success_rate': 0.5,
                        'sample_count': 0,
                        'avg_latency': 0.0
                    }
            
            return historical_performance
            
        except Exception as e:
            logger.error("Failed to get historical performance", error=str(e))
            return {}
    
    async def _get_llm_judgment(self, context: Dict[str, Any]) -> str:
        """Get judgment from LLM."""
        try:
            prompt = self._build_judge_prompt(context)
            
            response = await openai.ChatCompletion.acreate(
                model=self.model_name,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert AI routing judge. Analyze the given message and routing decision, then provide your judgment on the correct agent tier."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=self.temperature,
                max_tokens=500
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error("LLM judgment request failed", error=str(e))
            raise
    
    def _build_judge_prompt(self, context: Dict[str, Any]) -> str:
        """Build prompt for LLM judge."""
        prompt = f"""
Analyze this customer message and routing decision:

MESSAGE: "{context['message']}"

FEATURES:
- Text length: {context['features']['text_length']} characters
- Word count: {context['features']['word_count']} words
- Intent: Order={context['features']['intent_order']}, Support={context['features']['intent_support']}
- Sentiment: Negative={context['features']['sentiment_negative']}
- Urgency: High={context['features']['urgency_high']}
- Technical complexity: {context['features']['technical_complexity']}

PREDICTED TIER: {context['predicted_tier']} (Confidence: {context['confidence']:.2f})

TIER DESCRIPTIONS:
- Tier A: {context['tier_descriptions']['A']}
- Tier B: {context['tier_descriptions']['B']}
- Tier C: {context['tier_descriptions']['C']}

TENANT CONTEXT:
- Domain: {context['tenant_context'].get('domain', 'unknown')}
- Industry: {context['tenant_context'].get('industry', 'unknown')}
- Escalation rate: {context['tenant_context'].get('escalation_rate', 0.1):.2f}

HISTORICAL PERFORMANCE:
- Tier A: Success rate {context['historical_performance'].get('A', {}).get('success_rate', 0.5):.2f}
- Tier B: Success rate {context['historical_performance'].get('B', {}).get('success_rate', 0.5):.2f}
- Tier C: Success rate {context['historical_performance'].get('C', {}).get('success_rate', 0.5):.2f}

Please provide your judgment in the following JSON format:
{{
    "corrected_tier": "A|B|C",
    "confidence": 0.0-1.0,
    "reasoning": "Brief explanation of your decision",
    "is_misroute": true/false
}}

Consider:
1. Message complexity and intent
2. Customer urgency and sentiment
3. Historical performance of each tier
4. Cost vs accuracy trade-offs
5. Tenant-specific context
"""
        return prompt
    
    def _parse_judgment(self, judgment: str) -> Tuple[str, float, str]:
        """Parse LLM judgment response."""
        try:
            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', judgment, re.DOTALL)
            if json_match:
                judgment_data = json.loads(json_match.group())
                
                corrected_tier = judgment_data.get('corrected_tier', 'A')
                confidence = float(judgment_data.get('confidence', 0.5))
                reasoning = judgment_data.get('reasoning', 'No reasoning provided')
                
                return corrected_tier, confidence, reasoning
            else:
                # Fallback parsing
                lines = judgment.split('\n')
                corrected_tier = 'A'
                confidence = 0.5
                reasoning = judgment
                
                for line in lines:
                    if 'tier' in line.lower():
                        if 'B' in line:
                            corrected_tier = 'B'
                        elif 'C' in line:
                            corrected_tier = 'C'
                    elif 'confidence' in line.lower():
                        try:
                            confidence = float(re.search(r'[\d.]+', line).group())
                        except:
                            pass
                
                return corrected_tier, confidence, reasoning
                
        except Exception as e:
            logger.error("Failed to parse judgment", error=str(e))
            return 'A', 0.5, "Failed to parse judgment"
    
    async def _record_judgment(
        self,
        tenant_id: str,
        user_id: Optional[str],
        message: str,
        predicted_tier: str,
        corrected_tier: str,
        predicted_confidence: float,
        judge_confidence: float,
        reasoning: str,
        is_misroute: bool
    ) -> None:
        """Record judgment for learning and analysis."""
        try:
            judgment_data = {
                'tenant_id': tenant_id,
                'user_id': user_id,
                'message': message,
                'predicted_tier': predicted_tier,
                'corrected_tier': corrected_tier,
                'predicted_confidence': predicted_confidence,
                'judge_confidence': judge_confidence,
                'reasoning': reasoning,
                'is_misroute': is_misroute,
                'timestamp': time.time()
            }
            
            # Store judgment
            judgment_key = f"llm_judgments:{tenant_id}"
            await self.redis_client.lpush(judgment_key, json.dumps(judgment_data))
            await self.redis_client.ltrim(judgment_key, 0, 9999)  # Keep last 10k judgments
            
            # Update misroute statistics
            if is_misroute:
                misroute_key = f"misroute_stats:{tenant_id}"
                await self.redis_client.hincrby(misroute_key, 'total_misroutes', 1)
                await self.redis_client.hincrby(misroute_key, f'{predicted_tier}_to_{corrected_tier}', 1)
                await self.redis_client.expire(misroute_key, 86400)  # 24 hours TTL
            
        except Exception as e:
            logger.error("Failed to record judgment", error=str(e))
    
    async def get_misroute_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Get misroute statistics for tenant."""
        try:
            misroute_key = f"misroute_stats:{tenant_id}"
            stats_data = await self.redis_client.hgetall(misroute_key)
            
            total_misroutes = int(stats_data.get('total_misroutes', 0))
            total_decisions = await self._get_total_decisions(tenant_id)
            
            misroute_rate = total_misroutes / max(total_decisions, 1)
            
            return {
                'tenant_id': tenant_id,
                'total_misroutes': total_misroutes,
                'total_decisions': total_decisions,
                'misroute_rate': misroute_rate,
                'misroute_breakdown': {
                    k.decode(): int(v) for k, v in stats_data.items() 
                    if k != b'total_misroutes'
                }
            }
            
        except Exception as e:
            logger.error("Failed to get misroute stats", error=str(e))
            return {'tenant_id': tenant_id, 'error': str(e)}
    
    async def _get_total_decisions(self, tenant_id: str) -> int:
        """Get total number of decisions for tenant."""
        try:
            decisions_key = f"bandit_decisions:{tenant_id}"
            return await self.redis_client.llen(decisions_key)
        except Exception as e:
            logger.error("Failed to get total decisions", error=str(e))
            return 0
    
    async def get_judge_performance(self, tenant_id: str) -> Dict[str, Any]:
        """Get LLM judge performance metrics."""
        try:
            judgments_key = f"llm_judgments:{tenant_id}"
            judgments = await self.redis_client.lrange(judgments_key, 0, 99)  # Last 100 judgments
            
            if not judgments:
                return {'tenant_id': tenant_id, 'judge_performance': {}}
            
            # Analyze recent judgments
            total_judgments = len(judgments)
            misroutes_detected = 0
            avg_confidence = 0.0
            
            for judgment_json in judgments:
                try:
                    judgment = json.loads(judgment_json)
                    if judgment.get('is_misroute', False):
                        misroutes_detected += 1
                    avg_confidence += judgment.get('judge_confidence', 0.0)
                except:
                    continue
            
            avg_confidence = avg_confidence / max(total_judgments, 1)
            misroute_detection_rate = misroutes_detected / max(total_judgments, 1)
            
            return {
                'tenant_id': tenant_id,
                'total_judgments': total_judgments,
                'misroutes_detected': misroutes_detected,
                'misroute_detection_rate': misroute_detection_rate,
                'avg_judge_confidence': avg_confidence
            }
            
        except Exception as e:
            logger.error("Failed to get judge performance", error=str(e))
            return {'tenant_id': tenant_id, 'error': str(e)}