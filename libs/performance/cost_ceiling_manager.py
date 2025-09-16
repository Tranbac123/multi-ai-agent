"""
Cost Ceiling Manager

Manages cost ceilings and spending limits with real-time monitoring,
budget enforcement, and cost optimization recommendations.
"""

import asyncio
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta
from sqlalchemy import text, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession
from decimal import Decimal, ROUND_HALF_UP

logger = structlog.get_logger(__name__)


class CostType(Enum):
    """Types of costs tracked."""
    LLM_TOKENS = "llm_tokens"
    API_CALLS = "api_calls"
    STORAGE = "storage"
    COMPUTE = "compute"
    NETWORK = "network"
    CUSTOM = "custom"


class CeilingType(Enum):
    """Types of cost ceilings."""
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"
    PER_REQUEST = "per_request"
    PER_TENANT = "per_tenant"


class AlertLevel(Enum):
    """Cost alert levels."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class CostCeiling:
    """Cost ceiling definition."""
    
    ceiling_id: str
    name: str
    description: str
    ceiling_type: CeilingType
    cost_type: CostType
    limit_amount: Decimal
    currency: str = "USD"
    tenant_id: Optional[str] = None
    service: Optional[str] = None
    is_active: bool = True
    alert_thresholds: Dict[AlertLevel, float] = field(default_factory=lambda: {
        AlertLevel.WARNING: 0.8,  # 80% of limit
        AlertLevel.CRITICAL: 0.95,  # 95% of limit
        AlertLevel.EMERGENCY: 1.0  # 100% of limit
    })
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostRecord:
    """Cost record for tracking spending."""
    
    record_id: str
    ceiling_id: str
    tenant_id: str
    service: str
    cost_type: CostType
    amount: Decimal
    currency: str
    timestamp: datetime
    request_id: Optional[str] = None
    operation: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostAlert:
    """Cost ceiling alert."""
    
    alert_id: str
    ceiling_id: str
    alert_level: AlertLevel
    current_spending: Decimal
    limit_amount: Decimal
    usage_percentage: float
    triggered_at: datetime
    resolved_at: Optional[datetime] = None
    is_resolved: bool = False
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CostOptimizationRecommendation:
    """Cost optimization recommendation."""
    
    recommendation_id: str
    ceiling_id: str
    recommendation_type: str
    description: str
    potential_savings: Decimal
    implementation_effort: str  # "low", "medium", "high"
    priority: int  # 1-10, higher is more important
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class CostCeilingManager:
    """Manages cost ceilings and spending limits."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.ceiling_cache: Dict[str, CostCeiling] = {}
        self.spending_cache: Dict[str, Decimal] = {}
        
        logger.info("Cost ceiling manager initialized")
    
    async def create_cost_ceiling(
        self,
        name: str,
        description: str,
        ceiling_type: CeilingType,
        cost_type: CostType,
        limit_amount: Decimal,
        currency: str = "USD",
        tenant_id: Optional[str] = None,
        service: Optional[str] = None,
        alert_thresholds: Optional[Dict[AlertLevel, float]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> CostCeiling:
        """Create a new cost ceiling."""
        
        ceiling_id = f"ceiling_{ceiling_type.value}_{cost_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        ceiling = CostCeiling(
            ceiling_id=ceiling_id,
            name=name,
            description=description,
            ceiling_type=ceiling_type,
            cost_type=cost_type,
            limit_amount=limit_amount,
            currency=currency,
            tenant_id=tenant_id,
            service=service,
            alert_thresholds=alert_thresholds or {
                AlertLevel.WARNING: 0.8,
                AlertLevel.CRITICAL: 0.95,
                AlertLevel.EMERGENCY: 1.0
            },
            metadata=metadata or {}
        )
        
        await self._store_cost_ceiling(ceiling)
        self.ceiling_cache[ceiling_id] = ceiling
        
        logger.info("Cost ceiling created", 
                   ceiling_id=ceiling_id,
                   name=name,
                   ceiling_type=ceiling_type.value,
                   cost_type=cost_type.value,
                   limit_amount=float(limit_amount))
        
        return ceiling
    
    async def _store_cost_ceiling(self, ceiling: CostCeiling):
        """Store cost ceiling in database."""
        
        query = """
        INSERT INTO cost_ceilings (
            ceiling_id, name, description, ceiling_type, cost_type, limit_amount,
            currency, tenant_id, service, is_active, alert_thresholds,
            created_at, updated_at, metadata
        ) VALUES (
            :ceiling_id, :name, :description, :ceiling_type, :cost_type, :limit_amount,
            :currency, :tenant_id, :service, :is_active, :alert_thresholds,
            :created_at, :updated_at, :metadata
        )
        """
        
        # Convert alert thresholds to JSON
        alert_thresholds_json = {
            level.value: threshold for level, threshold in ceiling.alert_thresholds.items()
        }
        
        await self.db_session.execute(text(query), {
            "ceiling_id": ceiling.ceiling_id,
            "name": ceiling.name,
            "description": ceiling.description,
            "ceiling_type": ceiling.ceiling_type.value,
            "cost_type": ceiling.cost_type.value,
            "limit_amount": float(ceiling.limit_amount),
            "currency": ceiling.currency,
            "tenant_id": ceiling.tenant_id,
            "service": ceiling.service,
            "is_active": ceiling.is_active,
            "alert_thresholds": json.dumps(alert_thresholds_json),
            "created_at": ceiling.created_at,
            "updated_at": ceiling.updated_at,
            "metadata": json.dumps(ceiling.metadata)
        })
        
        await self.db_session.commit()
    
    async def record_cost(
        self,
        ceiling_id: str,
        tenant_id: str,
        service: str,
        cost_type: CostType,
        amount: Decimal,
        currency: str = "USD",
        request_id: Optional[str] = None,
        operation: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Record a cost and check against ceiling."""
        
        ceiling = await self.get_cost_ceiling(ceiling_id)
        if not ceiling:
            logger.error("Cost ceiling not found", ceiling_id=ceiling_id)
            return False
        
        # Create cost record
        record_id = f"cost_{ceiling_id}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        
        cost_record = CostRecord(
            record_id=record_id,
            ceiling_id=ceiling_id,
            tenant_id=tenant_id,
            service=service,
            cost_type=cost_type,
            amount=amount,
            currency=currency,
            timestamp=datetime.now(),
            request_id=request_id,
            operation=operation,
            metadata=metadata or {}
        )
        
        # Store cost record
        await self._store_cost_record(cost_record)
        
        # Check spending against ceiling
        current_spending = await self.get_current_spending(ceiling_id)
        
        # Update spending cache
        cache_key = f"{ceiling_id}_{self._get_time_window_key(ceiling.ceiling_type)}"
        if cache_key not in self.spending_cache:
            self.spending_cache[cache_key] = Decimal('0')
        self.spending_cache[cache_key] += amount
        
        # Check for ceiling violations and alerts
        await self._check_ceiling_violations(ceiling, current_spending)
        
        # Check if spending exceeds limit
        if current_spending >= ceiling.limit_amount:
            logger.warning("Cost ceiling exceeded", 
                          ceiling_id=ceiling_id,
                          current_spending=float(current_spending),
                          limit_amount=float(ceiling.limit_amount))
            return False  # Indicate that spending should be blocked
        
        return True
    
    async def _store_cost_record(self, cost_record: CostRecord):
        """Store cost record in database."""
        
        query = """
        INSERT INTO cost_records (
            record_id, ceiling_id, tenant_id, service, cost_type, amount,
            currency, timestamp, request_id, operation, metadata
        ) VALUES (
            :record_id, :ceiling_id, :tenant_id, :service, :cost_type, :amount,
            :currency, :timestamp, :request_id, :operation, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "record_id": cost_record.record_id,
            "ceiling_id": cost_record.ceiling_id,
            "tenant_id": cost_record.tenant_id,
            "service": cost_record.service,
            "cost_type": cost_record.cost_type.value,
            "amount": float(cost_record.amount),
            "currency": cost_record.currency,
            "timestamp": cost_record.timestamp,
            "request_id": cost_record.request_id,
            "operation": cost_record.operation,
            "metadata": json.dumps(cost_record.metadata)
        })
        
        await self.db_session.commit()
    
    def _get_time_window_key(self, ceiling_type: CeilingType) -> str:
        """Get time window key for caching."""
        
        now = datetime.now()
        
        if ceiling_type == CeilingType.DAILY:
            return now.strftime('%Y%m%d')
        elif ceiling_type == CeilingType.WEEKLY:
            return f"{now.year}W{now.isocalendar()[1]}"
        elif ceiling_type == CeilingType.MONTHLY:
            return now.strftime('%Y%m')
        elif ceiling_type == CeilingType.QUARTERLY:
            quarter = (now.month - 1) // 3 + 1
            return f"{now.year}Q{quarter}"
        elif ceiling_type == CeilingType.YEARLY:
            return str(now.year)
        else:
            return "unlimited"
    
    async def get_current_spending(
        self,
        ceiling_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> Decimal:
        """Get current spending for a ceiling."""
        
        ceiling = await self.get_cost_ceiling(ceiling_id)
        if not ceiling:
            return Decimal('0')
        
        # Use cache if available
        cache_key = f"{ceiling_id}_{self._get_time_window_key(ceiling.ceiling_type)}"
        if cache_key in self.spending_cache:
            return self.spending_cache[cache_key]
        
        # Calculate time window
        if not end_time:
            end_time = datetime.now()
        if not start_time:
            start_time = self._get_ceiling_start_time(ceiling.ceiling_type, end_time)
        
        # Query database for spending
        query = """
        SELECT COALESCE(SUM(amount), 0) as total_spending
        FROM cost_records 
        WHERE ceiling_id = :ceiling_id 
        AND timestamp >= :start_time 
        AND timestamp <= :end_time
        """
        
        result = await self.db_session.execute(text(query), {
            "ceiling_id": ceiling_id,
            "start_time": start_time,
            "end_time": end_time
        })
        
        row = result.fetchone()
        total_spending = Decimal(str(row.total_spending)) if row else Decimal('0')
        
        # Update cache
        self.spending_cache[cache_key] = total_spending
        
        return total_spending
    
    def _get_ceiling_start_time(self, ceiling_type: CeilingType, end_time: datetime) -> datetime:
        """Get start time for ceiling type."""
        
        if ceiling_type == CeilingType.DAILY:
            return end_time.replace(hour=0, minute=0, second=0, microsecond=0)
        elif ceiling_type == CeilingType.WEEKLY:
            # Start of the week (Monday)
            days_since_monday = end_time.weekday()
            return (end_time - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        elif ceiling_type == CeilingType.MONTHLY:
            return end_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        elif ceiling_type == CeilingType.QUARTERLY:
            quarter_start_month = ((end_time.month - 1) // 3) * 3 + 1
            return end_time.replace(month=quarter_start_month, day=1, hour=0, minute=0, second=0, microsecond=0)
        elif ceiling_type == CeilingType.YEARLY:
            return end_time.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        else:
            # Unlimited or per-request - use a very old date
            return datetime(2020, 1, 1)
    
    async def _check_ceiling_violations(self, ceiling: CostCeiling, current_spending: Decimal):
        """Check for ceiling violations and trigger alerts."""
        
        usage_percentage = float(current_spending / ceiling.limit_amount)
        
        # Check each alert threshold
        for alert_level, threshold in ceiling.alert_thresholds.items():
            if usage_percentage >= threshold:
                await self._trigger_cost_alert(
                    ceiling, alert_level, current_spending, usage_percentage
                )
    
    async def _trigger_cost_alert(
        self,
        ceiling: CostCeiling,
        alert_level: AlertLevel,
        current_spending: Decimal,
        usage_percentage: float
    ):
        """Trigger cost ceiling alert."""
        
        alert_id = f"alert_{ceiling.ceiling_id}_{alert_level.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        # Create alert message
        if alert_level == AlertLevel.WARNING:
            message = f"Cost ceiling warning: {usage_percentage:.1%} of limit reached"
        elif alert_level == AlertLevel.CRITICAL:
            message = f"Cost ceiling critical: {usage_percentage:.1%} of limit reached"
        elif alert_level == AlertLevel.EMERGENCY:
            message = f"Cost ceiling exceeded: {usage_percentage:.1%} of limit"
        else:
            message = f"Cost ceiling alert: {usage_percentage:.1%} of limit reached"
        
        alert = CostAlert(
            alert_id=alert_id,
            ceiling_id=ceiling.ceiling_id,
            alert_level=alert_level,
            current_spending=current_spending,
            limit_amount=ceiling.limit_amount,
            usage_percentage=usage_percentage,
            triggered_at=datetime.now(),
            message=message
        )
        
        await self._store_cost_alert(alert)
        
        logger.warning("Cost ceiling alert triggered", 
                      ceiling_id=ceiling.ceiling_id,
                      alert_level=alert_level.value,
                      usage_percentage=usage_percentage,
                      current_spending=float(current_spending),
                      limit_amount=float(ceiling.limit_amount))
    
    async def _store_cost_alert(self, alert: CostAlert):
        """Store cost alert in database."""
        
        query = """
        INSERT INTO cost_alerts (
            alert_id, ceiling_id, alert_level, current_spending, limit_amount,
            usage_percentage, triggered_at, resolved_at, is_resolved, message, metadata
        ) VALUES (
            :alert_id, :ceiling_id, :alert_level, :current_spending, :limit_amount,
            :usage_percentage, :triggered_at, :resolved_at, :is_resolved, :message, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "alert_id": alert.alert_id,
            "ceiling_id": alert.ceiling_id,
            "alert_level": alert.alert_level.value,
            "current_spending": float(alert.current_spending),
            "limit_amount": float(alert.limit_amount),
            "usage_percentage": alert.usage_percentage,
            "triggered_at": alert.triggered_at,
            "resolved_at": alert.resolved_at,
            "is_resolved": alert.is_resolved,
            "message": alert.message,
            "metadata": json.dumps(alert.metadata)
        })
        
        await self.db_session.commit()
    
    async def get_cost_ceiling(self, ceiling_id: str) -> Optional[CostCeiling]:
        """Get cost ceiling by ID."""
        
        # Check cache first
        if ceiling_id in self.ceiling_cache:
            return self.ceiling_cache[ceiling_id]
        
        query = """
        SELECT * FROM cost_ceilings 
        WHERE ceiling_id = :ceiling_id AND is_active = true
        """
        
        result = await self.db_session.execute(text(query), {"ceiling_id": ceiling_id})
        row = result.fetchone()
        
        if not row:
            return None
        
        ceiling = self._row_to_cost_ceiling(row)
        self.ceiling_cache[ceiling_id] = ceiling
        
        return ceiling
    
    async def get_cost_ceilings(
        self,
        tenant_id: Optional[str] = None,
        service: Optional[str] = None,
        cost_type: Optional[CostType] = None,
        ceiling_type: Optional[CeilingType] = None,
        is_active: bool = True
    ) -> List[CostCeiling]:
        """Get cost ceilings with filters."""
        
        query = """
        SELECT * FROM cost_ceilings 
        WHERE is_active = :is_active
        """
        
        params = {"is_active": is_active}
        
        if tenant_id:
            query += " AND tenant_id = :tenant_id"
            params["tenant_id"] = tenant_id
        
        if service:
            query += " AND service = :service"
            params["service"] = service
        
        if cost_type:
            query += " AND cost_type = :cost_type"
            params["cost_type"] = cost_type.value
        
        if ceiling_type:
            query += " AND ceiling_type = :ceiling_type"
            params["ceiling_type"] = ceiling_type.value
        
        query += " ORDER BY created_at DESC"
        
        result = await self.db_session.execute(text(query), params)
        rows = result.fetchall()
        
        return [self._row_to_cost_ceiling(row) for row in rows]
    
    async def get_cost_alerts(
        self,
        ceiling_id: Optional[str] = None,
        alert_level: Optional[AlertLevel] = None,
        is_resolved: Optional[bool] = None,
        limit: int = 100
    ) -> List[CostAlert]:
        """Get cost alerts with filters."""
        
        query = """
        SELECT * FROM cost_alerts 
        WHERE 1=1
        """
        
        params = {}
        
        if ceiling_id:
            query += " AND ceiling_id = :ceiling_id"
            params["ceiling_id"] = ceiling_id
        
        if alert_level:
            query += " AND alert_level = :alert_level"
            params["alert_level"] = alert_level.value
        
        if is_resolved is not None:
            query += " AND is_resolved = :is_resolved"
            params["is_resolved"] = is_resolved
        
        query += " ORDER BY triggered_at DESC LIMIT :limit"
        params["limit"] = limit
        
        result = await self.db_session.execute(text(query), params)
        rows = result.fetchall()
        
        return [self._row_to_cost_alert(row) for row in rows]
    
    async def generate_optimization_recommendations(
        self,
        ceiling_id: str,
        analysis_period_days: int = 30
    ) -> List[CostOptimizationRecommendation]:
        """Generate cost optimization recommendations."""
        
        ceiling = await self.get_cost_ceiling(ceiling_id)
        if not ceiling:
            return []
        
        recommendations = []
        
        # Analyze spending patterns
        end_time = datetime.now()
        start_time = end_time - timedelta(days=analysis_period_days)
        
        # Get spending data
        spending_query = """
        SELECT 
            service,
            cost_type,
            SUM(amount) as total_spending,
            COUNT(*) as request_count,
            AVG(amount) as avg_cost_per_request
        FROM cost_records 
        WHERE ceiling_id = :ceiling_id 
        AND timestamp >= :start_time 
        AND timestamp <= :end_time
        GROUP BY service, cost_type
        ORDER BY total_spending DESC
        """
        
        result = await self.db_session.execute(text(spending_query), {
            "ceiling_id": ceiling_id,
            "start_time": start_time,
            "end_time": end_time
        })
        
        rows = result.fetchall()
        
        # Generate recommendations based on spending patterns
        for row in rows:
            if row.total_spending > ceiling.limit_amount * Decimal('0.1'):  # 10% of limit
                # High spending service recommendation
                rec_id = f"rec_{ceiling_id}_high_spending_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                recommendation = CostOptimizationRecommendation(
                    recommendation_id=rec_id,
                    ceiling_id=ceiling_id,
                    recommendation_type="high_spending_service",
                    description=f"Consider optimizing {row.service} service which accounts for {float(row.total_spending):.2f} in spending",
                    potential_savings=row.total_spending * Decimal('0.2'),  # 20% potential savings
                    implementation_effort="medium",
                    priority=8,
                    metadata={
                        "service": row.service,
                        "cost_type": row.cost_type,
                        "total_spending": float(row.total_spending),
                        "request_count": row.request_count,
                        "avg_cost_per_request": float(row.avg_cost_per_request)
                    }
                )
                
                recommendations.append(recommendation)
            
            if row.avg_cost_per_request > ceiling.limit_amount * Decimal('0.01'):  # 1% of limit per request
                # High per-request cost recommendation
                rec_id = f"rec_{ceiling_id}_high_per_request_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                recommendation = CostOptimizationRecommendation(
                    recommendation_id=rec_id,
                    ceiling_id=ceiling_id,
                    recommendation_type="high_per_request_cost",
                    description=f"High per-request cost in {row.service}: {float(row.avg_cost_per_request):.4f} per request",
                    potential_savings=row.total_spending * Decimal('0.15'),  # 15% potential savings
                    implementation_effort="high",
                    priority=9,
                    metadata={
                        "service": row.service,
                        "avg_cost_per_request": float(row.avg_cost_per_request),
                        "request_count": row.request_count
                    }
                )
                
                recommendations.append(recommendation)
        
        # Store recommendations
        for recommendation in recommendations:
            await self._store_optimization_recommendation(recommendation)
        
        return recommendations
    
    async def _store_optimization_recommendation(self, recommendation: CostOptimizationRecommendation):
        """Store optimization recommendation in database."""
        
        query = """
        INSERT INTO cost_optimization_recommendations (
            recommendation_id, ceiling_id, recommendation_type, description,
            potential_savings, implementation_effort, priority, created_at, metadata
        ) VALUES (
            :recommendation_id, :ceiling_id, :recommendation_type, :description,
            :potential_savings, :implementation_effort, :priority, :created_at, :metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "recommendation_id": recommendation.recommendation_id,
            "ceiling_id": recommendation.ceiling_id,
            "recommendation_type": recommendation.recommendation_type,
            "description": recommendation.description,
            "potential_savings": float(recommendation.potential_savings),
            "implementation_effort": recommendation.implementation_effort,
            "priority": recommendation.priority,
            "created_at": recommendation.created_at,
            "metadata": json.dumps(recommendation.metadata)
        })
        
        await self.db_session.commit()
    
    def _row_to_cost_ceiling(self, row) -> CostCeiling:
        """Convert database row to CostCeiling object."""
        
        # Parse alert thresholds
        alert_thresholds = {}
        if row.alert_thresholds:
            thresholds_data = json.loads(row.alert_thresholds)
            for level_str, threshold in thresholds_data.items():
                alert_thresholds[AlertLevel(level_str)] = threshold
        
        return CostCeiling(
            ceiling_id=row.ceiling_id,
            name=row.name,
            description=row.description,
            ceiling_type=CeilingType(row.ceiling_type),
            cost_type=CostType(row.cost_type),
            limit_amount=Decimal(str(row.limit_amount)),
            currency=row.currency,
            tenant_id=row.tenant_id,
            service=row.service,
            is_active=row.is_active,
            alert_thresholds=alert_thresholds,
            created_at=row.created_at,
            updated_at=row.updated_at,
            metadata=json.loads(row.metadata) if row.metadata else {}
        )
    
    def _row_to_cost_alert(self, row) -> CostAlert:
        """Convert database row to CostAlert object."""
        
        return CostAlert(
            alert_id=row.alert_id,
            ceiling_id=row.ceiling_id,
            alert_level=AlertLevel(row.alert_level),
            current_spending=Decimal(str(row.current_spending)),
            limit_amount=Decimal(str(row.limit_amount)),
            usage_percentage=row.usage_percentage,
            triggered_at=row.triggered_at,
            resolved_at=row.resolved_at,
            is_resolved=row.is_resolved,
            message=row.message,
            metadata=json.loads(row.metadata) if row.metadata else {}
        )
    
    async def get_cost_statistics(self) -> Dict[str, Any]:
        """Get cost statistics."""
        
        # Ceiling statistics
        ceiling_query = """
        SELECT 
            COUNT(*) as total_ceilings,
            COUNT(CASE WHEN is_active = true THEN 1 END) as active_ceilings,
            COUNT(DISTINCT tenant_id) as tenants_with_ceilings,
            COUNT(DISTINCT service) as services_with_ceilings,
            SUM(limit_amount) as total_limit_amount
        FROM cost_ceilings
        """
        
        ceiling_result = await self.db_session.execute(text(ceiling_query))
        ceiling_stats = ceiling_result.fetchone()
        
        # Alert statistics
        alert_query = """
        SELECT 
            COUNT(*) as total_alerts,
            COUNT(CASE WHEN is_resolved = false THEN 1 END) as active_alerts,
            COUNT(CASE WHEN alert_level = 'emergency' THEN 1 END) as emergency_alerts,
            COUNT(CASE WHEN alert_level = 'critical' THEN 1 END) as critical_alerts,
            COUNT(CASE WHEN alert_level = 'warning' THEN 1 END) as warning_alerts
        FROM cost_alerts
        """
        
        alert_result = await self.db_session.execute(text(alert_query))
        alert_stats = alert_result.fetchone()
        
        # Spending statistics (last 30 days)
        spending_query = """
        SELECT 
            SUM(amount) as total_spending,
            COUNT(*) as total_requests,
            AVG(amount) as avg_cost_per_request
        FROM cost_records 
        WHERE timestamp >= :start_time
        """
        
        start_time = datetime.now() - timedelta(days=30)
        spending_result = await self.db_session.execute(text(spending_query), {"start_time": start_time})
        spending_stats = spending_result.fetchone()
        
        return {
            "ceiling_statistics": {
                "total_ceilings": ceiling_stats.total_ceilings,
                "active_ceilings": ceiling_stats.active_ceilings,
                "tenants_with_ceilings": ceiling_stats.tenants_with_ceilings,
                "services_with_ceilings": ceiling_stats.services_with_ceilings,
                "total_limit_amount": float(ceiling_stats.total_limit_amount)
            },
            "alert_statistics": {
                "total_alerts": alert_stats.total_alerts,
                "active_alerts": alert_stats.active_alerts,
                "emergency_alerts": alert_stats.emergency_alerts,
                "critical_alerts": alert_stats.critical_alerts,
                "warning_alerts": alert_stats.warning_alerts
            },
            "spending_statistics": {
                "total_spending_30d": float(spending_stats.total_spending) if spending_stats.total_spending else 0.0,
                "total_requests_30d": spending_stats.total_requests,
                "avg_cost_per_request": float(spending_stats.avg_cost_per_request) if spending_stats.avg_cost_per_request else 0.0
            },
            "timestamp": datetime.now().isoformat()
        }
