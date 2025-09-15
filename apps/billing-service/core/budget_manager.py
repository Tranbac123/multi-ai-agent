"""Budget Manager for per-tenant budget enforcement and monitoring."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
import asyncio
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, text

from libs.contracts.billing import BudgetConfig, BudgetAlert, BudgetUsage
from libs.utils.exceptions import BudgetExceededError, BudgetConfigurationError

logger = structlog.get_logger(__name__)


class BudgetPeriod(Enum):
    """Budget period types."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    YEARLY = "yearly"


class BudgetStatus(Enum):
    """Budget status levels."""
    HEALTHY = "healthy"
    WARNING = "warning"
    CRITICAL = "critical"
    EXCEEDED = "exceeded"


@dataclass
class BudgetThresholds:
    """Budget threshold configuration."""
    warning_percent: float = 75.0
    critical_percent: float = 90.0
    exceeded_percent: float = 100.0


class BudgetManager:
    """Manages tenant budgets, monitoring, and enforcement."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.budget_thresholds = BudgetThresholds()
        self.alerts: List[BudgetAlert] = []
        self.monitoring_task: Optional[asyncio.Task] = None
        self._start_budget_monitoring()
    
    def _start_budget_monitoring(self):
        """Start background budget monitoring task."""
        self.monitoring_task = asyncio.create_task(self._monitor_budgets())
    
    async def create_budget(self, tenant_id: str, budget_config: BudgetConfig) -> bool:
        """Create or update tenant budget configuration."""
        try:
            # Validate budget configuration
            await self._validate_budget_config(budget_config)
            
            # Create budget record
            budget_data = {
                "tenant_id": tenant_id,
                "period": budget_config.period.value,
                "amount": budget_config.amount,
                "currency": budget_config.currency,
                "warning_threshold": budget_config.warning_threshold,
                "critical_threshold": budget_config.critical_threshold,
                "auto_renew": budget_config.auto_renew,
                "created_at": datetime.now(timezone.utc),
                "updated_at": datetime.now(timezone.utc)
            }
            
            # Insert or update budget
            query = text("""
                INSERT INTO tenant_budgets (tenant_id, period, amount, currency, 
                                         warning_threshold, critical_threshold, auto_renew, 
                                         created_at, updated_at)
                VALUES (:tenant_id, :period, :amount, :currency, :warning_threshold, 
                       :critical_threshold, :auto_renew, :created_at, :updated_at)
                ON CONFLICT (tenant_id, period) 
                DO UPDATE SET
                    amount = EXCLUDED.amount,
                    currency = EXCLUDED.currency,
                    warning_threshold = EXCLUDED.warning_threshold,
                    critical_threshold = EXCLUDED.critical_threshold,
                    auto_renew = EXCLUDED.auto_renew,
                    updated_at = EXCLUDED.updated_at
            """)
            
            await self.db.execute(query, budget_data)
            await self.db.commit()
            
            logger.info("Budget created/updated successfully",
                       tenant_id=tenant_id,
                       period=budget_config.period.value,
                       amount=budget_config.amount)
            
            return True
            
        except Exception as e:
            logger.error("Failed to create/update budget",
                        tenant_id=tenant_id,
                        error=str(e))
            await self.db.rollback()
            return False
    
    async def get_budget(self, tenant_id: str, period: BudgetPeriod) -> Optional[BudgetConfig]:
        """Get tenant budget configuration."""
        try:
            query = text("""
                SELECT tenant_id, period, amount, currency, warning_threshold, 
                       critical_threshold, auto_renew, created_at, updated_at
                FROM tenant_budgets 
                WHERE tenant_id = :tenant_id AND period = :period
            """)
            
            result = await self.db.execute(query, {
                "tenant_id": tenant_id,
                "period": period.value
            })
            
            row = result.fetchone()
            if not row:
                return None
            
            return BudgetConfig(
                period=BudgetPeriod(row.period),
                amount=row.amount,
                currency=row.currency,
                warning_threshold=row.warning_threshold,
                critical_threshold=row.critical_threshold,
                auto_renew=row.auto_renew
            )
            
        except Exception as e:
            logger.error("Failed to get budget",
                        tenant_id=tenant_id,
                        period=period.value,
                        error=str(e))
            return None
    
    async def check_budget_limit(self, tenant_id: str, cost_usd: float, 
                                period: BudgetPeriod = BudgetPeriod.MONTHLY) -> Dict[str, Any]:
        """Check if request cost would exceed budget limits."""
        try:
            # Get current budget
            budget = await self.get_budget(tenant_id, period)
            if not budget:
                # No budget configured, allow request
                return {"allowed": True, "reason": "No budget configured"}
            
            # Get current usage for period
            current_usage = await self.get_budget_usage(tenant_id, period)
            
            # Check if adding this cost would exceed budget
            projected_usage = current_usage.total_cost + cost_usd
            
            if projected_usage > budget.amount:
                return {
                    "allowed": False,
                    "reason": "Budget exceeded",
                    "current_usage": current_usage.total_cost,
                    "budget_limit": budget.amount,
                    "projected_usage": projected_usage
                }
            
            # Check warning and critical thresholds
            usage_percent = (projected_usage / budget.amount) * 100
            
            if usage_percent >= budget.critical_threshold:
                return {
                    "allowed": True,
                    "warning": "critical",
                    "usage_percent": usage_percent,
                    "reason": "Approaching critical budget threshold"
                }
            elif usage_percent >= budget.warning_threshold:
                return {
                    "allowed": True,
                    "warning": "warning",
                    "usage_percent": usage_percent,
                    "reason": "Approaching warning budget threshold"
                }
            
            return {"allowed": True, "usage_percent": usage_percent}
            
        except Exception as e:
            logger.error("Failed to check budget limit",
                        tenant_id=tenant_id,
                        cost_usd=cost_usd,
                        error=str(e))
            return {"allowed": True, "reason": "Budget check failed"}
    
    async def get_budget_usage(self, tenant_id: str, period: BudgetPeriod) -> BudgetUsage:
        """Get current budget usage for tenant."""
        try:
            # Calculate period start and end dates
            now = datetime.now(timezone.utc)
            period_start = self._get_period_start(now, period)
            period_end = self._get_period_end(now, period)
            
            # Get usage data from billing events
            query = text("""
                SELECT 
                    COUNT(*) as request_count,
                    SUM(cost_usd) as total_cost,
                    AVG(cost_usd) as avg_cost,
                    MAX(cost_usd) as max_cost
                FROM billing_events 
                WHERE tenant_id = :tenant_id 
                AND created_at >= :period_start 
                AND created_at < :period_end
            """)
            
            result = await self.db.execute(query, {
                "tenant_id": tenant_id,
                "period_start": period_start,
                "period_end": period_end
            })
            
            row = result.fetchone()
            
            return BudgetUsage(
                tenant_id=tenant_id,
                period=period,
                period_start=period_start,
                period_end=period_end,
                request_count=row.request_count or 0,
                total_cost=row.total_cost or 0.0,
                avg_cost=row.avg_cost or 0.0,
                max_cost=row.max_cost or 0.0,
                last_updated=now
            )
            
        except Exception as e:
            logger.error("Failed to get budget usage",
                        tenant_id=tenant_id,
                        period=period.value,
                        error=str(e))
            return BudgetUsage(
                tenant_id=tenant_id,
                period=period,
                period_start=datetime.now(timezone.utc),
                period_end=datetime.now(timezone.utc),
                request_count=0,
                total_cost=0.0,
                avg_cost=0.0,
                max_cost=0.0,
                last_updated=datetime.now(timezone.utc)
            )
    
    async def record_usage(self, tenant_id: str, cost_usd: float, 
                          service_type: str, request_id: str) -> bool:
        """Record usage and cost for budget tracking."""
        try:
            usage_data = {
                "tenant_id": tenant_id,
                "request_id": request_id,
                "service_type": service_type,
                "cost_usd": cost_usd,
                "created_at": datetime.now(timezone.utc)
            }
            
            query = text("""
                INSERT INTO billing_events (tenant_id, request_id, service_type, 
                                          cost_usd, created_at)
                VALUES (:tenant_id, :request_id, :service_type, :cost_usd, :created_at)
            """)
            
            await self.db.execute(query, usage_data)
            await self.db.commit()
            
            logger.info("Usage recorded successfully",
                       tenant_id=tenant_id,
                       cost_usd=cost_usd,
                       service_type=service_type)
            
            return True
            
        except Exception as e:
            logger.error("Failed to record usage",
                        tenant_id=tenant_id,
                        cost_usd=cost_usd,
                        error=str(e))
            await self.db.rollback()
            return False
    
    async def _validate_budget_config(self, budget_config: BudgetConfig):
        """Validate budget configuration."""
        if budget_config.amount <= 0:
            raise BudgetConfigurationError("Budget amount must be positive")
        
        if budget_config.warning_threshold < 0 or budget_config.warning_threshold > 100:
            raise BudgetConfigurationError("Warning threshold must be between 0 and 100")
        
        if budget_config.critical_threshold < budget_config.warning_threshold:
            raise BudgetConfigurationError("Critical threshold must be >= warning threshold")
        
        if budget_config.critical_threshold > 100:
            raise BudgetConfigurationError("Critical threshold must be <= 100")
    
    def _get_period_start(self, now: datetime, period: BudgetPeriod) -> datetime:
        """Get period start date based on period type."""
        if period == BudgetPeriod.DAILY:
            return now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.WEEKLY:
            days_since_monday = now.weekday()
            return (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.MONTHLY:
            return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif period == BudgetPeriod.YEARLY:
            return now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            return now
    
    def _get_period_end(self, now: datetime, period: BudgetPeriod) -> datetime:
        """Get period end date based on period type."""
        if period == BudgetPeriod.DAILY:
            return now.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == BudgetPeriod.WEEKLY:
            days_since_monday = now.weekday()
            end_date = now + timedelta(days=6-days_since_monday)
            return end_date.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif period == BudgetPeriod.MONTHLY:
            if now.month == 12:
                next_month = now.replace(year=now.year + 1, month=1, day=1)
            else:
                next_month = now.replace(month=now.month + 1, day=1)
            return next_month - timedelta(microseconds=1)
        elif period == BudgetPeriod.YEARLY:
            next_year = now.replace(year=now.year + 1, month=1, day=1)
            return next_year - timedelta(microseconds=1)
        else:
            return now
    
    async def _monitor_budgets(self):
        """Background task to monitor budgets and send alerts."""
        while True:
            try:
                await asyncio.sleep(300)  # Check every 5 minutes
                
                # Get all active budgets
                budgets = await self._get_all_active_budgets()
                
                for budget in budgets:
                    await self._check_budget_status(budget)
                
            except Exception as e:
                logger.error("Error in budget monitoring", error=str(e))
                await asyncio.sleep(60)  # Wait longer on error
    
    async def _get_all_active_budgets(self) -> List[Dict[str, Any]]:
        """Get all active budget configurations."""
        try:
            query = text("""
                SELECT tenant_id, period, amount, warning_threshold, critical_threshold
                FROM tenant_budgets
                WHERE auto_renew = true
            """)
            
            result = await self.db.execute(query)
            return [dict(row._mapping) for row in result.fetchall()]
            
        except Exception as e:
            logger.error("Failed to get active budgets", error=str(e))
            return []
    
    async def _check_budget_status(self, budget: Dict[str, Any]):
        """Check budget status and send alerts if needed."""
        try:
            tenant_id = budget["tenant_id"]
            period = BudgetPeriod(budget["period"])
            
            # Get current usage
            usage = await self.get_budget_usage(tenant_id, period)
            
            # Calculate usage percentage
            usage_percent = (usage.total_cost / budget["amount"]) * 100
            
            # Check thresholds and send alerts
            if usage_percent >= budget["critical_threshold"]:
                await self._send_budget_alert(tenant_id, period, usage_percent, "critical")
            elif usage_percent >= budget["warning_threshold"]:
                await self._send_budget_alert(tenant_id, period, usage_percent, "warning")
            
        except Exception as e:
            logger.error("Failed to check budget status",
                        tenant_id=budget.get("tenant_id"),
                        error=str(e))
    
    async def _send_budget_alert(self, tenant_id: str, period: BudgetPeriod, 
                                usage_percent: float, alert_type: str):
        """Send budget alert to tenant."""
        try:
            alert = BudgetAlert(
                tenant_id=tenant_id,
                period=period,
                usage_percent=usage_percent,
                alert_type=alert_type,
                message=f"Budget {alert_type}: {usage_percent:.1f}% of {period.value} budget used",
                created_at=datetime.now(timezone.utc)
            )
            
            # Store alert
            self.alerts.append(alert)
            
            # Here you would typically send the alert via email, webhook, etc.
            logger.warning("Budget alert sent",
                          tenant_id=tenant_id,
                          period=period.value,
                          usage_percent=usage_percent,
                          alert_type=alert_type)
            
        except Exception as e:
            logger.error("Failed to send budget alert",
                        tenant_id=tenant_id,
                        error=str(e))
    
    async def get_budget_alerts(self, tenant_id: str, limit: int = 50) -> List[BudgetAlert]:
        """Get recent budget alerts for tenant."""
        try:
            # Filter alerts for tenant and sort by creation time
            tenant_alerts = [alert for alert in self.alerts if alert.tenant_id == tenant_id]
            tenant_alerts.sort(key=lambda x: x.created_at, reverse=True)
            
            return tenant_alerts[:limit]
            
        except Exception as e:
            logger.error("Failed to get budget alerts", tenant_id=tenant_id, error=str(e))
            return []
    
    async def shutdown(self):
        """Shutdown budget manager gracefully."""
        try:
            if self.monitoring_task:
                self.monitoring_task.cancel()
                try:
                    await self.monitoring_task
                except asyncio.CancelledError:
                    pass
            
            logger.info("Budget manager shutdown complete")
            
        except Exception as e:
            logger.error("Error during budget manager shutdown", error=str(e))
