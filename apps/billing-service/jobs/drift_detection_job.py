"""Nightly drift detection job for cost and latency monitoring."""

import asyncio
import structlog
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy import text

from apps.billing-service.core.budget_manager import BudgetManager, BudgetPeriod
from apps.router-service.core.cost_drift_detector import CostDriftDetector
from apps.router-service.core.safe_mode_router import SafeModeRouter, SafeModeLevel
from libs.clients.notification import NotificationClient
from libs.contracts.billing import BudgetAlert, BudgetConfig

logger = structlog.get_logger(__name__)


class DriftDetectionJob:
    """Nightly job to detect cost and latency drift."""
    
    def __init__(self, db_url: str):
        self.db_url = db_url
        self.engine = create_async_engine(db_url, echo=False)
        self.session_factory = async_sessionmaker(self.engine, expire_on_commit=False)
        self.notification_client = NotificationClient()
        self.drift_thresholds = {
            "cost_warning": 15.0,    # 15% cost increase
            "cost_critical": 30.0,   # 30% cost increase
            "latency_warning": 25.0, # 25% latency increase
            "latency_critical": 50.0 # 50% latency increase
        }
    
    async def run_drift_detection(self) -> Dict[str, Any]:
        """Run the nightly drift detection analysis."""
        try:
            logger.info("Starting nightly drift detection job")
            start_time = datetime.now(timezone.utc)
            
            async with self.session_factory() as session:
                # Initialize components
                budget_manager = BudgetManager(session)
                drift_detector = CostDriftDetector(session)
                safe_mode_router = SafeModeRouter()
                
                # Get all active tenants
                active_tenants = await self._get_active_tenants(session)
                
                drift_results = {
                    "analysis_start": start_time.isoformat(),
                    "total_tenants_analyzed": len(active_tenants),
                    "drift_detected": [],
                    "budget_alerts": [],
                    "safe_mode_recommendations": [],
                    "cost_savings": [],
                    "errors": []
                }
                
                # Analyze each tenant
                for tenant_id in active_tenants:
                    try:
                        await self._analyze_tenant_drift(
                            tenant_id, budget_manager, drift_detector, 
                            safe_mode_router, drift_results
                        )
                    except Exception as e:
                        logger.error("Failed to analyze tenant drift",
                                   tenant_id=tenant_id,
                                   error=str(e))
                        drift_results["errors"].append({
                            "tenant_id": tenant_id,
                            "error": str(e)
                        })
                
                # Generate summary and send notifications
                await self._generate_summary_and_notify(drift_results)
                
                end_time = datetime.now(timezone.utc)
                drift_results["analysis_end"] = end_time.isoformat()
                drift_results["analysis_duration_seconds"] = (end_time - start_time).total_seconds()
                
                logger.info("Drift detection job completed",
                           duration_seconds=drift_results["analysis_duration_seconds"],
                           tenants_analyzed=drift_results["total_tenants_analyzed"],
                           drift_detected_count=len(drift_results["drift_detected"]),
                           budget_alerts_count=len(drift_results["budget_alerts"]))
                
                return drift_results
                
        except Exception as e:
            logger.error("Failed to run drift detection job", error=str(e))
            return {
                "error": str(e),
                "analysis_start": datetime.now(timezone.utc).isoformat(),
                "analysis_end": datetime.now(timezone.utc).isoformat()
            }
    
    async def _get_active_tenants(self, session) -> List[str]:
        """Get list of active tenants for analysis."""
        try:
            # Get tenants with activity in the last 7 days
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(days=7)
            
            query = text("""
                SELECT DISTINCT tenant_id
                FROM billing_events 
                WHERE created_at >= :start_time 
                AND created_at < :end_time
            """)
            
            result = await session.execute(query, {
                "start_time": start_time,
                "end_time": end_time
            })
            
            return [row[0] for row in result.fetchall()]
            
        except Exception as e:
            logger.error("Failed to get active tenants", error=str(e))
            return []
    
    async def _analyze_tenant_drift(self, tenant_id: str, budget_manager: BudgetManager,
                                  drift_detector: CostDriftDetector, safe_mode_router: SafeModeRouter,
                                  drift_results: Dict[str, Any]):
        """Analyze drift for a specific tenant."""
        try:
            logger.info("Analyzing drift for tenant", tenant_id=tenant_id)
            
            # Get tenant's budget configuration
            budget_config = await budget_manager.get_budget(tenant_id, BudgetPeriod.MONTHLY)
            
            if not budget_config:
                logger.debug("No budget configured for tenant", tenant_id=tenant_id)
                return
            
            # Get current budget usage
            budget_usage = await budget_manager.get_budget_usage(tenant_id, BudgetPeriod.MONTHLY)
            usage_percent = (budget_usage.total_cost / budget_config.amount) * 100
            
            # Analyze cost and latency drift
            drift_analysis = await drift_detector.analyze_drift(tenant_id, "llm", 24)
            
            # Check for significant drift
            if drift_analysis.get("drift_detected", False):
                drift_data = {
                    "tenant_id": tenant_id,
                    "usage_percent": usage_percent,
                    "cost_drift": drift_analysis.get("cost_drift", {}),
                    "latency_drift": drift_analysis.get("latency_drift", {}),
                    "analysis_period": drift_analysis.get("analysis_period", {})
                }
                drift_results["drift_detected"].append(drift_data)
                
                # Create budget alert if needed
                if usage_percent >= budget_config.warning_threshold:
                    alert_data = {
                        "tenant_id": tenant_id,
                        "usage_percent": usage_percent,
                        "budget_amount": budget_config.amount,
                        "current_usage": budget_usage.total_cost,
                        "drift_percent": drift_analysis.get("cost_drift", {}).get("drift_percent", 0),
                        "alert_type": "budget_warning" if usage_percent < budget_config.critical_threshold else "budget_critical"
                    }
                    drift_results["budget_alerts"].append(alert_data)
                
                # Generate safe mode recommendation
                safe_mode_level = safe_mode_router.determine_safe_mode_level(
                    budget_config, usage_percent
                )
                
                if safe_mode_level != SafeModeLevel.NORMAL:
                    recommendation = {
                        "tenant_id": tenant_id,
                        "current_level": safe_mode_level.value,
                        "usage_percent": usage_percent,
                        "cost_drift_percent": drift_analysis.get("cost_drift", {}).get("drift_percent", 0),
                        "recommended_actions": self._get_safe_mode_recommendations(safe_mode_level, drift_analysis)
                    }
                    drift_results["safe_mode_recommendations"].append(recommendation)
            
            # Calculate potential cost savings
            if usage_percent >= 75:  # Only for tenants approaching budget limits
                cost_savings = await self._calculate_cost_savings(
                    tenant_id, budget_usage, safe_mode_router
                )
                if cost_savings["potential_savings"] > 0:
                    drift_results["cost_savings"].append(cost_savings)
            
        except Exception as e:
            logger.error("Failed to analyze tenant drift",
                        tenant_id=tenant_id,
                        error=str(e))
            raise
    
    def _get_safe_mode_recommendations(self, safe_mode_level: SafeModeLevel, 
                                     drift_analysis: Dict[str, Any]) -> List[str]:
        """Get recommendations based on safe mode level and drift analysis."""
        recommendations = []
        
        if safe_mode_level == SafeModeLevel.WARNING:
            recommendations.extend([
                "Consider enabling safe mode for cost optimization",
                "Monitor usage more closely",
                "Review recent cost increases"
            ])
        elif safe_mode_level == SafeModeLevel.CRITICAL:
            recommendations.extend([
                "Enable safe mode immediately",
                "Force SLM-A for simple tasks",
                "Disable verbose critique mode",
                "Consider reducing context size"
            ])
        elif safe_mode_level == SafeModeLevel.EMERGENCY:
            recommendations.extend([
                "Emergency safe mode required",
                "Force all requests to SLM-A",
                "Disable debate mode and verbose critique",
                "Minimize context size",
                "Consider temporary service restrictions"
            ])
        
        # Add drift-specific recommendations
        cost_drift = drift_analysis.get("cost_drift", {})
        if cost_drift.get("drift_percent", 0) > 20:
            recommendations.append("Significant cost increase detected - review usage patterns")
        
        latency_drift = drift_analysis.get("latency_drift", {})
        if latency_drift.get("drift_percent", 0) > 30:
            recommendations.append("High latency increase - check system performance")
        
        return recommendations
    
    async def _calculate_cost_savings(self, tenant_id: str, budget_usage, 
                                    safe_mode_router: SafeModeRouter) -> Dict[str, Any]:
        """Calculate potential cost savings from safe mode."""
        try:
            # Estimate current average cost per request
            if budget_usage.request_count > 0:
                current_avg_cost = budget_usage.total_cost / budget_usage.request_count
            else:
                current_avg_cost = 0.002  # Default estimate
            
            # Estimate safe mode average cost
            safe_mode_avg_cost = 0.0005  # Conservative estimate
            
            # Calculate potential savings
            potential_savings = (current_avg_cost - safe_mode_avg_cost) * budget_usage.request_count
            savings_percent = (potential_savings / budget_usage.total_cost * 100) if budget_usage.total_cost > 0 else 0
            
            return {
                "tenant_id": tenant_id,
                "current_total_cost": budget_usage.total_cost,
                "current_avg_cost": current_avg_cost,
                "safe_mode_avg_cost": safe_mode_avg_cost,
                "potential_savings": potential_savings,
                "savings_percent": savings_percent,
                "request_count": budget_usage.request_count
            }
            
        except Exception as e:
            logger.error("Failed to calculate cost savings",
                        tenant_id=tenant_id,
                        error=str(e))
            return {
                "tenant_id": tenant_id,
                "current_total_cost": 0,
                "current_avg_cost": 0,
                "safe_mode_avg_cost": 0,
                "potential_savings": 0,
                "savings_percent": 0,
                "request_count": 0
            }
    
    async def _generate_summary_and_notify(self, drift_results: Dict[str, Any]):
        """Generate summary and send notifications."""
        try:
            # Generate summary
            summary = {
                "analysis_date": datetime.now(timezone.utc).isoformat(),
                "total_tenants": drift_results["total_tenants_analyzed"],
                "tenants_with_drift": len(drift_results["drift_detected"]),
                "budget_alerts": len(drift_results["budget_alerts"]),
                "safe_mode_recommendations": len(drift_results["safe_mode_recommendations"]),
                "total_potential_savings": sum(s.get("potential_savings", 0) for s in drift_results["cost_savings"]),
                "errors": len(drift_results["errors"])
            }
            
            # Send notifications for critical issues
            await self._send_critical_notifications(drift_results)
            
            # Store summary in database
            await self._store_analysis_summary(summary, drift_results)
            
            logger.info("Drift analysis summary generated",
                       summary=summary)
            
        except Exception as e:
            logger.error("Failed to generate summary and notify", error=str(e))
    
    async def _send_critical_notifications(self, drift_results: Dict[str, Any]):
        """Send notifications for critical drift and budget issues."""
        try:
            # Send notifications for budget alerts
            for alert in drift_results["budget_alerts"]:
                if alert["alert_type"] == "budget_critical":
                    await self.notification_client.send_budget_alert(
                        tenant_id=alert["tenant_id"],
                        usage_percent=alert["usage_percent"],
                        budget_amount=alert["budget_amount"],
                        drift_percent=alert["drift_percent"]
                    )
            
            # Send notifications for high drift
            for drift in drift_results["drift_detected"]:
                cost_drift = drift.get("cost_drift", {})
                if cost_drift.get("drift_percent", 0) > 50:  # Very high drift
                    await self.notification_client.send_drift_alert(
                        tenant_id=drift["tenant_id"],
                        cost_drift_percent=cost_drift.get("drift_percent", 0),
                        latency_drift_percent=drift.get("latency_drift", {}).get("drift_percent", 0)
                    )
            
        except Exception as e:
            logger.error("Failed to send critical notifications", error=str(e))
    
    async def _store_analysis_summary(self, summary: Dict[str, Any], 
                                    drift_results: Dict[str, Any]):
        """Store analysis summary in database."""
        try:
            async with self.session_factory() as session:
                # Store summary
                summary_data = {
                    "analysis_date": summary["analysis_date"],
                    "total_tenants": summary["total_tenants"],
                    "tenants_with_drift": summary["tenants_with_drift"],
                    "budget_alerts": summary["budget_alerts"],
                    "safe_mode_recommendations": summary["safe_mode_recommendations"],
                    "total_potential_savings": summary["total_potential_savings"],
                    "errors": summary["errors"],
                    "created_at": datetime.now(timezone.utc)
                }
                
                query = text("""
                    INSERT INTO drift_analysis_summaries 
                    (analysis_date, total_tenants, tenants_with_drift, budget_alerts,
                     safe_mode_recommendations, total_potential_savings, errors, created_at)
                    VALUES (:analysis_date, :total_tenants, :tenants_with_drift, :budget_alerts,
                           :safe_mode_recommendations, :total_potential_savings, :errors, :created_at)
                """)
                
                await session.execute(query, summary_data)
                await session.commit()
                
                logger.info("Analysis summary stored in database")
                
        except Exception as e:
            logger.error("Failed to store analysis summary", error=str(e))


async def main():
    """Main function to run drift detection job."""
    # This would typically be called by a scheduler (e.g., cron, Kubernetes CronJob)
    db_url = "postgresql+asyncpg://user:password@localhost:5432/multitenant"
    
    job = DriftDetectionJob(db_url)
    results = await job.run_drift_detection()
    
    print(f"Drift detection completed: {results}")


if __name__ == "__main__":
    asyncio.run(main())
