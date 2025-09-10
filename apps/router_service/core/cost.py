"""Cost calculator for router decisions."""

from typing import Dict, Any
import structlog

from libs.contracts.router import RouterTier, TextFeatures

logger = structlog.get_logger(__name__)


class CostCalculator:
    """Calculate costs for different routing tiers."""
    
    def __init__(self):
        self.base_costs = {
            RouterTier.SLM_A: 0.001,  # $0.001 per request
            RouterTier.SLM_B: 0.005,  # $0.005 per request
            RouterTier.LLM: 0.02      # $0.02 per request
        }
        
        self.domain_multipliers = {
            'finance': 2.0,
            'legal': 2.0,
            'medical': 3.0,
            'ecommerce': 1.5
        }
        
        self.complexity_multipliers = {
            'low': 1.0,
            'medium': 1.5,
            'high': 2.0
        }
    
    def initialize(self):
        """Initialize cost calculator."""
        logger.info("Cost calculator initialized")
    
    async def calculate_cost(self, tier: RouterTier, features: TextFeatures) -> float:
        """Calculate expected cost for tier and features."""
        try:
            # Base cost for tier
            base_cost = self.base_costs[tier]
            
            # Apply domain multipliers
            domain_multiplier = 1.0
            for domain, is_present in features.domain_flags.items():
                if is_present:
                    domain_multiplier *= self.domain_multipliers.get(domain, 1.0)
            
            # Apply complexity multiplier
            complexity = self._get_complexity_level(features)
            complexity_multiplier = self.complexity_multipliers[complexity]
            
            # Apply token count multiplier
            token_multiplier = 1.0 + (features.token_count / 1000) * 0.5
            
            # Calculate final cost
            final_cost = base_cost * domain_multiplier * complexity_multiplier * token_multiplier
            
            return round(final_cost, 4)
            
        except Exception as e:
            logger.error("Cost calculation failed", error=str(e))
            return self.base_costs[tier]
    
    def _get_complexity_level(self, features: TextFeatures) -> str:
        """Determine complexity level based on features."""
        complexity_score = 0
        
        # JSON schema complexity
        if features.json_schema_complexity > 0.7:
            complexity_score += 2
        elif features.json_schema_complexity > 0.4:
            complexity_score += 1
        
        # Format strictness
        if features.format_strictness > 0.7:
            complexity_score += 2
        elif features.format_strictness > 0.4:
            complexity_score += 1
        
        # Reasoning keywords
        if len(features.reasoning_keywords) > 3:
            complexity_score += 2
        elif len(features.reasoning_keywords) > 1:
            complexity_score += 1
        
        # Entity count
        if features.entity_count > 5:
            complexity_score += 1
        
        # Determine level
        if complexity_score >= 4:
            return 'high'
        elif complexity_score >= 2:
            return 'medium'
        else:
            return 'low'
    
    async def calculate_savings(self, original_tier: RouterTier, new_tier: RouterTier, features: TextFeatures) -> float:
        """Calculate cost savings from tier change."""
        original_cost = await self.calculate_cost(original_tier, features)
        new_cost = await self.calculate_cost(new_tier, features)
        
        return max(0, original_cost - new_cost)
    
    async def get_cost_breakdown(self, tier: RouterTier, features: TextFeatures) -> Dict[str, Any]:
        """Get detailed cost breakdown."""
        base_cost = self.base_costs[tier]
        
        # Calculate multipliers
        domain_multiplier = 1.0
        domain_breakdown = {}
        for domain, is_present in features.domain_flags.items():
            if is_present:
                multiplier = self.domain_multipliers.get(domain, 1.0)
                domain_multiplier *= multiplier
                domain_breakdown[domain] = multiplier
        
        complexity = self._get_complexity_level(features)
        complexity_multiplier = self.complexity_multipliers[complexity]
        
        token_multiplier = 1.0 + (features.token_count / 1000) * 0.5
        
        final_cost = base_cost * domain_multiplier * complexity_multiplier * token_multiplier
        
        return {
            "base_cost": base_cost,
            "domain_multiplier": domain_multiplier,
            "domain_breakdown": domain_breakdown,
            "complexity_multiplier": complexity_multiplier,
            "complexity_level": complexity,
            "token_multiplier": token_multiplier,
            "final_cost": final_cost
        }
