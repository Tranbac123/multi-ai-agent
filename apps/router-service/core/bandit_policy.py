"""Bandit policy minimizing E[cost + λ·error] for router v2."""

import asyncio
import time
import math
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
import structlog
import redis.asyncio as redis

from apps.router-service.core.feature_extractor import RouterFeatures, Tier

logger = structlog.get_logger(__name__)


@dataclass
class BanditArm:
    """Bandit arm representing a tier."""
    tier: Tier
    pulls: int
    rewards: float
    costs: float
    errors: int
    last_updated: float


@dataclass
class BanditConfig:
    """Bandit policy configuration."""
    lambda_error: float  # Error penalty weight
    exploration_rate: float  # Epsilon for epsilon-greedy
    confidence_level: float  # UCB confidence level
    min_pulls: int  # Minimum pulls before using UCB
    cost_weights: Dict[Tier, float]  # Cost weights per tier


class BanditPolicy:
    """Bandit policy minimizing E[cost + λ·error]."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.config = BanditConfig(
            lambda_error=1.0,  # Error penalty weight
            exploration_rate=0.1,  # 10% exploration
            confidence_level=2.0,  # UCB confidence
            min_pulls=10,  # Minimum pulls for UCB
            cost_weights={
                Tier.A: 0.1,  # Cheap
                Tier.B: 0.5,  # Medium
                Tier.C: 1.0   # Expensive
            }
        )
        self.arms = {}
    
    async def select_arm(
        self,
        features: RouterFeatures,
        tenant_id: str
    ) -> Tuple[Tier, float, Dict[str, Any]]:
        """Select arm (tier) using bandit policy."""
        try:
            # Get or initialize arms for tenant
            await self._ensure_arms_initialized(tenant_id)
            
            # Calculate expected values for each arm
            arm_values = await self._calculate_arm_values(tenant_id, features)
            
            # Select arm using epsilon-greedy with UCB
            selected_arm, selection_info = await self._select_arm_strategy(arm_values, tenant_id)
            
            # Update selection metrics
            await self._update_selection_metrics(tenant_id, selected_arm, selection_info)
            
            return selected_arm, arm_values[selected_arm], selection_info
            
        except Exception as e:
            logger.error("Bandit selection failed", error=str(e))
            # Fallback to Tier B
            return Tier.B, 0.5, {'strategy': 'fallback', 'reason': str(e)}
    
    async def update_arm(
        self,
        tenant_id: str,
        tier: Tier,
        reward: float,
        cost: float,
        error: bool = False
    ) -> None:
        """Update arm statistics after receiving feedback."""
        try:
            arm_key = f"bandit_arm:{tenant_id}:{tier.value}"
            
            # Get current arm data
            arm_data = await self.redis.hgetall(arm_key)
            
            if arm_data:
                # Update existing arm
                pulls = int(arm_data['pulls']) + 1
                rewards = float(arm_data['rewards']) + reward
                costs = float(arm_data['costs']) + cost
                errors = int(arm_data['errors']) + (1 if error else 0)
            else:
                # Initialize new arm
                pulls = 1
                rewards = reward
                costs = cost
                errors = 1 if error else 0
            
            # Update arm data
            await self.redis.hset(arm_key, mapping={
                'tier': tier.value,
                'pulls': pulls,
                'rewards': rewards,
                'costs': costs,
                'errors': errors,
                'last_updated': time.time()
            })
            
            # Set TTL
            await self.redis.expire(arm_key, 86400 * 30)  # 30 days
            
            logger.info(
                "Arm updated",
                tenant_id=tenant_id,
                tier=tier.value,
                pulls=pulls,
                reward=reward,
                cost=cost,
                error=error
            )
            
        except Exception as e:
            logger.error("Failed to update arm", error=str(e))
    
    async def _ensure_arms_initialized(self, tenant_id: str) -> None:
        """Ensure all arms are initialized for tenant."""
        try:
            for tier in Tier:
                arm_key = f"bandit_arm:{tenant_id}:{tier.value}"
                arm_exists = await self.redis.exists(arm_key)
                
                if not arm_exists:
                    # Initialize arm with default values
                    await self.redis.hset(arm_key, mapping={
                        'tier': tier.value,
                        'pulls': 0,
                        'rewards': 0.0,
                        'costs': 0.0,
                        'errors': 0,
                        'last_updated': time.time()
                    })
                    await self.redis.expire(arm_key, 86400 * 30)
                    
        except Exception as e:
            logger.error("Failed to initialize arms", error=str(e))
    
    async def _calculate_arm_values(
        self,
        tenant_id: str,
        features: RouterFeatures
    ) -> Dict[Tier, float]:
        """Calculate expected values for each arm."""
        try:
            arm_values = {}
            
            for tier in Tier:
                arm_key = f"bandit_arm:{tenant_id}:{tier.value}"
                arm_data = await self.redis.hgetall(arm_key)
                
                if arm_data and int(arm_data['pulls']) > 0:
                    # Calculate expected value
                    pulls = int(arm_data['pulls'])
                    rewards = float(arm_data['rewards'])
                    costs = float(arm_data['costs'])
                    errors = int(arm_data['errors'])
                    
                    # Expected reward
                    expected_reward = rewards / pulls
                    
                    # Expected cost
                    expected_cost = costs / pulls
                    
                    # Expected error rate
                    expected_error_rate = errors / pulls
                    
                    # Calculate value: reward - cost - λ·error
                    value = expected_reward - expected_cost - (self.config.lambda_error * expected_error_rate)
                    
                    arm_values[tier] = value
                else:
                    # Default value for unexplored arms
                    arm_values[tier] = 0.0
            
            return arm_values
            
        except Exception as e:
            logger.error("Failed to calculate arm values", error=str(e))
            return {tier: 0.0 for tier in Tier}
    
    async def _select_arm_strategy(
        self,
        arm_values: Dict[Tier, float],
        tenant_id: str
    ) -> Tuple[Tier, Dict[str, Any]]:
        """Select arm using epsilon-greedy with UCB."""
        try:
            # Get total pulls across all arms
            total_pulls = await self._get_total_pulls(tenant_id)
            
            # Check if we should explore or exploit
            if total_pulls < self.config.min_pulls:
                # Pure exploration for first few pulls
                selected_arm = await self._select_random_arm()
                selection_info = {
                    'strategy': 'random_exploration',
                    'total_pulls': total_pulls,
                    'reason': 'insufficient_data'
                }
            else:
                # Use epsilon-greedy with UCB
                if await self._should_explore():
                    # Exploration: select arm with highest UCB
                    selected_arm, ucb_value = await self._select_ucb_arm(tenant_id, arm_values)
                    selection_info = {
                        'strategy': 'ucb_exploration',
                        'ucb_value': ucb_value,
                        'total_pulls': total_pulls
                    }
                else:
                    # Exploitation: select arm with highest expected value
                    selected_arm = max(arm_values.keys(), key=lambda t: arm_values[t])
                    selection_info = {
                        'strategy': 'exploitation',
                        'expected_value': arm_values[selected_arm],
                        'total_pulls': total_pulls
                    }
            
            return selected_arm, selection_info
            
        except Exception as e:
            logger.error("Failed to select arm", error=str(e))
            return Tier.B, {'strategy': 'fallback', 'reason': str(e)}
    
    async def _get_total_pulls(self, tenant_id: str) -> int:
        """Get total pulls across all arms for tenant."""
        try:
            total_pulls = 0
            for tier in Tier:
                arm_key = f"bandit_arm:{tenant_id}:{tier.value}"
                arm_data = await self.redis.hgetall(arm_key)
                if arm_data:
                    total_pulls += int(arm_data['pulls'])
            return total_pulls
        except Exception:
            return 0
    
    async def _select_random_arm(self) -> Tier:
        """Select random arm for exploration."""
        import random
        return random.choice(list(Tier))
    
    async def _should_explore(self) -> bool:
        """Determine if we should explore."""
        import random
        return random.random() < self.config.exploration_rate
    
    async def _select_ucb_arm(
        self,
        tenant_id: str,
        arm_values: Dict[Tier, float]
    ) -> Tuple[Tier, float]:
        """Select arm using Upper Confidence Bound."""
        try:
            total_pulls = await self._get_total_pulls(tenant_id)
            best_arm = None
            best_ucb = float('-inf')
            
            for tier in Tier:
                arm_key = f"bandit_arm:{tenant_id}:{tier.value}"
                arm_data = await self.redis.hgetall(arm_key)
                
                if arm_data:
                    pulls = int(arm_data['pulls'])
                    if pulls > 0:
                        # Calculate UCB
                        expected_value = arm_values[tier]
                        confidence_interval = self.config.confidence_level * math.sqrt(
                            math.log(total_pulls) / pulls
                        )
                        ucb_value = expected_value + confidence_interval
                        
                        if ucb_value > best_ucb:
                            best_ucb = ucb_value
                            best_arm = tier
            
            if best_arm is None:
                best_arm = Tier.B
                best_ucb = 0.0
            
            return best_arm, best_ucb
            
        except Exception as e:
            logger.error("Failed to select UCB arm", error=str(e))
            return Tier.B, 0.0
    
    async def _update_selection_metrics(
        self,
        tenant_id: str,
        selected_arm: Tier,
        selection_info: Dict[str, Any]
    ) -> None:
        """Update selection metrics."""
        try:
            metrics_key = f"selection_metrics:{tenant_id}"
            await self.redis.hincrby(metrics_key, 'total_selections', 1)
            await self.redis.hincrby(metrics_key, f'selections_{selected_arm.value}', 1)
            await self.redis.hincrby(metrics_key, f'strategy_{selection_info["strategy"]}', 1)
            await self.redis.expire(metrics_key, 86400 * 7)  # 7 days TTL
            
        except Exception as e:
            logger.error("Failed to update selection metrics", error=str(e))
    
    async def get_arm_statistics(self, tenant_id: str) -> Dict[str, Any]:
        """Get arm statistics for tenant."""
        try:
            stats = {
                'tenant_id': tenant_id,
                'arms': {},
                'total_pulls': 0,
                'config': {
                    'lambda_error': self.config.lambda_error,
                    'exploration_rate': self.config.exploration_rate,
                    'confidence_level': self.config.confidence_level
                }
            }
            
            total_pulls = 0
            for tier in Tier:
                arm_key = f"bandit_arm:{tenant_id}:{tier.value}"
                arm_data = await self.redis.hgetall(arm_key)
                
                if arm_data:
                    pulls = int(arm_data['pulls'])
                    rewards = float(arm_data['rewards'])
                    costs = float(arm_data['costs'])
                    errors = int(arm_data['errors'])
                    
                    stats['arms'][tier.value] = {
                        'pulls': pulls,
                        'rewards': rewards,
                        'costs': costs,
                        'errors': errors,
                        'expected_reward': rewards / pulls if pulls > 0 else 0,
                        'expected_cost': costs / pulls if pulls > 0 else 0,
                        'error_rate': errors / pulls if pulls > 0 else 0
                    }
                    
                    total_pulls += pulls
            
            stats['total_pulls'] = total_pulls
            return stats
            
        except Exception as e:
            logger.error("Failed to get arm statistics", error=str(e))
            return {'error': str(e)}
    
    async def reset_arms(self, tenant_id: str) -> None:
        """Reset all arms for tenant."""
        try:
            for tier in Tier:
                arm_key = f"bandit_arm:{tenant_id}:{tier.value}"
                await self.redis.delete(arm_key)
            
            metrics_key = f"selection_metrics:{tenant_id}"
            await self.redis.delete(metrics_key)
            
            logger.info("Arms reset", tenant_id=tenant_id)
            
        except Exception as e:
            logger.error("Failed to reset arms", error=str(e))