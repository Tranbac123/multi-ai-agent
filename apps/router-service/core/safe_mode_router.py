"""Safe Mode Router for cost-optimized routing during budget constraints."""

from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime, timezone

from libs.contracts.router import RouterDecision, RouterRequest, LLMTier
from libs.contracts.billing import BudgetConfig, BudgetStatus

logger = structlog.get_logger(__name__)


class SafeModeLevel(Enum):
    """Safe mode levels based on budget constraints."""
    NORMAL = "normal"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class SafeModeConfig:
    """Safe mode configuration for cost optimization."""
    enabled: bool = False
    level: SafeModeLevel = SafeModeLevel.NORMAL
    force_slm_a: bool = False
    disable_verbose_critique: bool = False
    disable_debate_mode: bool = False
    reduce_context_size: bool = False
    max_cost_per_request: float = 0.01
    preferred_tiers: List[LLMTier] = None
    
    def __post_init__(self):
        if self.preferred_tiers is None:
            self.preferred_tiers = [LLMTier.SLM_A, LLMTier.SLM_B, LLMTier.PREMIUM]


@dataclass
class CostOptimizedDecision:
    """Cost-optimized routing decision."""
    tier: LLMTier
    reasoning: str
    cost_estimate: float
    latency_estimate: float
    safe_mode_applied: bool
    original_tier: Optional[LLMTier] = None


class SafeModeRouter:
    """Router that optimizes for cost when in safe mode."""
    
    def __init__(self):
        self.safe_mode_config = SafeModeConfig()
        self.cost_tiers = {
            LLMTier.SLM_A: {"cost_per_1k_tokens": 0.0001, "latency_ms": 50},
            LLMTier.SLM_B: {"cost_per_1k_tokens": 0.0003, "latency_ms": 100},
            LLMTier.STANDARD: {"cost_per_1k_tokens": 0.001, "latency_ms": 200},
            LLMTier.PREMIUM: {"cost_per_1k_tokens": 0.003, "latency_ms": 300},
            LLMTier.ENTERPRISE: {"cost_per_1k_tokens": 0.005, "latency_ms": 400}
        }
        self.task_complexity_estimates = {
            "simple_json": {"tokens": 100, "complexity": 0.1},
            "strict_json": {"tokens": 200, "complexity": 0.3},
            "creative_writing": {"tokens": 1000, "complexity": 0.8},
            "code_generation": {"tokens": 800, "complexity": 0.7},
            "analysis": {"tokens": 600, "complexity": 0.6},
            "translation": {"tokens": 400, "complexity": 0.4}
        }
    
    def update_safe_mode_config(self, config: SafeModeConfig):
        """Update safe mode configuration."""
        self.safe_mode_config = config
        
        logger.info("Safe mode configuration updated",
                   enabled=config.enabled,
                   level=config.level.value,
                   force_slm_a=config.force_slm_a,
                   max_cost_per_request=config.max_cost_per_request)
    
    def determine_safe_mode_level(self, budget_status: BudgetStatus, 
                                 usage_percent: float) -> SafeModeLevel:
        """Determine safe mode level based on budget status and usage."""
        try:
            if usage_percent >= 95:
                return SafeModeLevel.EMERGENCY
            elif usage_percent >= 90:
                return SafeModeLevel.CRITICAL
            elif usage_percent >= 75:
                return SafeModeLevel.WARNING
            else:
                return SafeModeLevel.NORMAL
                
        except Exception as e:
            logger.error("Failed to determine safe mode level", error=str(e))
            return SafeModeLevel.NORMAL
    
    def route_with_safe_mode(self, request: RouterRequest, 
                           budget_config: Optional[BudgetConfig] = None,
                           usage_percent: float = 0.0) -> RouterDecision:
        """Route request with safe mode cost optimization."""
        try:
            # Determine safe mode level
            if budget_config:
                budget_status = self._get_budget_status(usage_percent, budget_config)
                safe_mode_level = self.determine_safe_mode_level(budget_status, usage_percent)
            else:
                safe_mode_level = SafeModeLevel.NORMAL
            
            # Apply safe mode configuration
            safe_mode_config = self._get_safe_mode_config(safe_mode_level)
            
            # Estimate request complexity and cost
            complexity_estimate = self._estimate_request_complexity(request)
            cost_estimate = self._estimate_request_cost(complexity_estimate, LLMTier.PREMIUM)
            
            # Check if we need to apply safe mode
            if (safe_mode_config.enabled and 
                (cost_estimate > safe_mode_config.max_cost_per_request or 
                 usage_percent >= 75)):
                
                # Apply cost optimization
                optimized_decision = self._optimize_for_cost(
                    request, complexity_estimate, safe_mode_config
                )
                
                return RouterDecision(
                    tier=optimized_decision.tier,
                    confidence=0.95,  # High confidence for safe mode
                    reasoning=optimized_decision.reasoning,
                    estimated_cost=optimized_decision.cost_estimate,
                    estimated_latency=optimized_decision.latency_estimate,
                    safe_mode_applied=True,
                    safe_mode_level=safe_mode_level.value,
                    original_tier=optimized_decision.original_tier
                )
            
            # Normal routing without safe mode
            return self._normal_routing(request, complexity_estimate)
            
        except Exception as e:
            logger.error("Failed to route with safe mode", error=str(e))
            # Fallback to safe tier
            return RouterDecision(
                tier=LLMTier.SLM_A,
                confidence=0.5,
                reasoning="Safe mode fallback due to error",
                estimated_cost=0.0001,
                estimated_latency=50,
                safe_mode_applied=True,
                safe_mode_level=SafeModeLevel.EMERGENCY.value
            )
    
    def _get_budget_status(self, usage_percent: float, 
                          budget_config: BudgetConfig) -> BudgetStatus:
        """Get budget status based on usage percentage."""
        if usage_percent >= 100:
            return BudgetStatus.EXCEEDED
        elif usage_percent >= budget_config.critical_threshold:
            return BudgetStatus.CRITICAL
        elif usage_percent >= budget_config.warning_threshold:
            return BudgetStatus.WARNING
        else:
            return BudgetStatus.HEALTHY
    
    def _get_safe_mode_config(self, level: SafeModeLevel) -> SafeModeConfig:
        """Get safe mode configuration based on level."""
        config = SafeModeConfig()
        
        if level == SafeModeLevel.NORMAL:
            config.enabled = False
        elif level == SafeModeLevel.WARNING:
            config.enabled = True
            config.max_cost_per_request = 0.008
            config.preferred_tiers = [LLMTier.SLM_A, LLMTier.SLM_B, LLMTier.STANDARD]
        elif level == SafeModeLevel.CRITICAL:
            config.enabled = True
            config.force_slm_a = False
            config.disable_verbose_critique = True
            config.max_cost_per_request = 0.005
            config.preferred_tiers = [LLMTier.SLM_A, LLMTier.SLM_B]
        else:  # EMERGENCY
            config.enabled = True
            config.force_slm_a = True
            config.disable_verbose_critique = True
            config.disable_debate_mode = True
            config.reduce_context_size = True
            config.max_cost_per_request = 0.002
            config.preferred_tiers = [LLMTier.SLM_A]
        
        return config
    
    def _estimate_request_complexity(self, request: RouterRequest) -> Dict[str, Any]:
        """Estimate request complexity for cost optimization."""
        try:
            # Analyze request content
            content = request.content.lower()
            content_length = len(request.content)
            
            # Determine task type
            task_type = "simple_json"  # Default
            
            if any(keyword in content for keyword in ["write", "create", "generate", "compose"]):
                task_type = "creative_writing"
            elif any(keyword in content for keyword in ["code", "function", "class", "import"]):
                task_type = "code_generation"
            elif any(keyword in content for keyword in ["analyze", "explain", "evaluate", "assess"]):
                task_type = "analysis"
            elif any(keyword in content for keyword in ["translate", "convert", "transform"]):
                task_type = "translation"
            elif any(keyword in content for keyword in ["json", "format", "structure"]):
                task_type = "strict_json"
            
            # Estimate token count
            base_tokens = self.task_complexity_estimates[task_type]["tokens"]
            length_factor = min(content_length / 100, 3.0)  # Cap at 3x
            estimated_tokens = int(base_tokens * length_factor)
            
            return {
                "task_type": task_type,
                "estimated_tokens": estimated_tokens,
                "complexity_score": self.task_complexity_estimates[task_type]["complexity"],
                "content_length": content_length
            }
            
        except Exception as e:
            logger.error("Failed to estimate request complexity", error=str(e))
            return {
                "task_type": "simple_json",
                "estimated_tokens": 100,
                "complexity_score": 0.1,
                "content_length": 0
            }
    
    def _estimate_request_cost(self, complexity: Dict[str, Any], tier: LLMTier) -> float:
        """Estimate request cost based on complexity and tier."""
        try:
            estimated_tokens = complexity["estimated_tokens"]
            cost_per_1k = self.cost_tiers[tier]["cost_per_1k_tokens"]
            
            return (estimated_tokens / 1000) * cost_per_1k
            
        except Exception as e:
            logger.error("Failed to estimate request cost", error=str(e))
            return 0.001  # Default cost estimate
    
    def _optimize_for_cost(self, request: RouterRequest, 
                          complexity: Dict[str, Any],
                          safe_mode_config: SafeModeConfig) -> CostOptimizedDecision:
        """Optimize routing decision for cost under safe mode."""
        try:
            # Start with original tier (if available)
            original_tier = getattr(request, 'original_tier', LLMTier.PREMIUM)
            
            # Try preferred tiers in order
            for tier in safe_mode_config.preferred_tiers:
                cost_estimate = self._estimate_request_cost(complexity, tier)
                
                if cost_estimate <= safe_mode_config.max_cost_per_request:
                    # This tier is acceptable
                    reasoning = f"Safe mode optimization: {tier.value} selected for cost efficiency"
                    
                    if safe_mode_config.force_slm_a:
                        tier = LLMTier.SLM_A
                        cost_estimate = self._estimate_request_cost(complexity, tier)
                        reasoning = f"Safe mode emergency: forced to {tier.value} for maximum cost savings"
                    
                    return CostOptimizedDecision(
                        tier=tier,
                        reasoning=reasoning,
                        cost_estimate=cost_estimate,
                        latency_estimate=self.cost_tiers[tier]["latency_ms"],
                        safe_mode_applied=True,
                        original_tier=original_tier
                    )
            
            # If no tier meets cost requirements, use cheapest available
            cheapest_tier = LLMTier.SLM_A
            cost_estimate = self._estimate_request_cost(complexity, cheapest_tier)
            
            return CostOptimizedDecision(
                tier=cheapest_tier,
                reasoning="Safe mode emergency: using cheapest tier due to cost constraints",
                cost_estimate=cost_estimate,
                latency_estimate=self.cost_tiers[cheapest_tier]["latency_ms"],
                safe_mode_applied=True,
                original_tier=original_tier
            )
            
        except Exception as e:
            logger.error("Failed to optimize for cost", error=str(e))
            # Emergency fallback
            return CostOptimizedDecision(
                tier=LLMTier.SLM_A,
                reasoning="Safe mode emergency fallback",
                cost_estimate=0.0001,
                latency_estimate=50,
                safe_mode_applied=True,
                original_tier=original_tier
            )
    
    def _normal_routing(self, request: RouterRequest, 
                       complexity: Dict[str, Any]) -> RouterDecision:
        """Normal routing without safe mode constraints."""
        try:
            # Use complexity to determine appropriate tier
            complexity_score = complexity["complexity_score"]
            
            if complexity_score <= 0.2:
                tier = LLMTier.SLM_A
                reasoning = "Simple task, using SLM-A for efficiency"
            elif complexity_score <= 0.4:
                tier = LLMTier.SLM_B
                reasoning = "Moderate complexity, using SLM-B"
            elif complexity_score <= 0.6:
                tier = LLMTier.STANDARD
                reasoning = "Standard complexity, using Standard tier"
            elif complexity_score <= 0.8:
                tier = LLMTier.PREMIUM
                reasoning = "High complexity, using Premium tier"
            else:
                tier = LLMTier.ENTERPRISE
                reasoning = "Very high complexity, using Enterprise tier"
            
            cost_estimate = self._estimate_request_cost(complexity, tier)
            
            return RouterDecision(
                tier=tier,
                confidence=0.85,
                reasoning=reasoning,
                estimated_cost=cost_estimate,
                estimated_latency=self.cost_tiers[tier]["latency_ms"],
                safe_mode_applied=False
            )
            
        except Exception as e:
            logger.error("Failed in normal routing", error=str(e))
            # Fallback
            return RouterDecision(
                tier=LLMTier.STANDARD,
                confidence=0.5,
                reasoning="Normal routing fallback",
                estimated_cost=0.001,
                estimated_latency=200,
                safe_mode_applied=False
            )
    
    def get_cost_savings_summary(self, requests_processed: int, 
                               safe_mode_requests: int) -> Dict[str, Any]:
        """Get summary of cost savings from safe mode."""
        try:
            # Calculate estimated savings
            normal_avg_cost = 0.002  # Average cost without safe mode
            safe_mode_avg_cost = 0.0005  # Average cost with safe mode
            
            total_normal_cost = requests_processed * normal_avg_cost
            safe_mode_cost = safe_mode_requests * safe_mode_avg_cost
            normal_cost_for_safe_requests = safe_mode_requests * normal_avg_cost
            
            cost_savings = normal_cost_for_safe_requests - safe_mode_cost
            savings_percent = (cost_savings / normal_cost_for_safe_requests * 100) if normal_cost_for_safe_requests > 0 else 0
            
            return {
                "total_requests": requests_processed,
                "safe_mode_requests": safe_mode_requests,
                "safe_mode_percent": (safe_mode_requests / requests_processed * 100) if requests_processed > 0 else 0,
                "estimated_cost_savings": cost_savings,
                "savings_percent": savings_percent,
                "normal_avg_cost": normal_avg_cost,
                "safe_mode_avg_cost": safe_mode_avg_cost
            }
            
        except Exception as e:
            logger.error("Failed to calculate cost savings summary", error=str(e))
            return {
                "total_requests": requests_processed,
                "safe_mode_requests": safe_mode_requests,
                "safe_mode_percent": 0,
                "estimated_cost_savings": 0,
                "savings_percent": 0,
                "normal_avg_cost": 0,
                "safe_mode_avg_cost": 0
            }
