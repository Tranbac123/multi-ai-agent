#!/usr/bin/env python3
"""
User Experience Monitor for Production

This script monitors user experience metrics in real-time and provides
comprehensive analytics and alerting for production deployments.
"""

import asyncio
import json
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import structlog
import requests
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import psutil

logger = structlog.get_logger(__name__)

# Prometheus metrics
USER_EXPERIENCE_METRICS = {
    "response_time_p50": Histogram('user_experience_response_time_p50_seconds', '50th percentile response time'),
    "response_time_p95": Histogram('user_experience_response_time_p95_seconds', '95th percentile response time'),
    "response_time_p99": Histogram('user_experience_response_time_p99_seconds', '99th percentile response time'),
    "error_rate": Counter('user_experience_error_rate_total', 'Total error rate', ['service', 'endpoint']),
    "throughput": Counter('user_experience_throughput_total', 'Total throughput', ['service']),
    "active_users": Gauge('user_experience_active_users_total', 'Active users'),
    "chat_completion_rate": Gauge('user_experience_chat_completion_rate', 'Chat completion rate'),
    "user_satisfaction": Gauge('user_experience_satisfaction_score', 'User satisfaction score'),
    "session_duration": Histogram('user_experience_session_duration_seconds', 'User session duration'),
    "feature_adoption": Gauge('user_experience_feature_adoption_rate', 'Feature adoption rate', ['feature']),
}


class UserExperienceMonitor:
    """Real-time user experience monitoring."""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.metrics_history = []
        self.alerts = []
        self.is_running = False
        
    async def start_monitoring(self):
        """Start user experience monitoring."""
        
        logger.info("Starting user experience monitoring")
        self.is_running = True
        
        # Start Prometheus metrics server
        start_http_server(self.config.get("metrics_port", 8000))
        
        # Start monitoring tasks
        tasks = [
            self._monitor_response_times(),
            self._monitor_error_rates(),
            self._monitor_throughput(),
            self._monitor_active_users(),
            self._monitor_chat_completion(),
            self._monitor_user_satisfaction(),
            self._monitor_session_duration(),
            self._monitor_feature_adoption(),
            self._check_alerts(),
            self._generate_reports()
        ]
        
        await asyncio.gather(*tasks)
    
    async def _monitor_response_times(self):
        """Monitor response times across all services."""
        
        while self.is_running:
            try:
                services = self.config.get("services", [])
                
                for service in services:
                    response_times = await self._get_response_times(service)
                    
                    if response_times:
                        USER_EXPERIENCE_METRICS["response_time_p50"].observe(response_times.get("p50", 0))
                        USER_EXPERIENCE_METRICS["response_time_p95"].observe(response_times.get("p95", 0))
                        USER_EXPERIENCE_METRICS["response_time_p99"].observe(response_times.get("p99", 0))
                        
                        logger.debug("Response times updated", 
                                   service=service,
                                   p50=response_times.get("p50", 0),
                                   p95=response_times.get("p95", 0),
                                   p99=response_times.get("p99", 0))
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error("Error monitoring response times", error=str(e))
                await asyncio.sleep(60)
    
    async def _monitor_error_rates(self):
        """Monitor error rates across all services."""
        
        while self.is_running:
            try:
                services = self.config.get("services", [])
                
                for service in services:
                    error_rate = await self._get_error_rate(service)
                    
                    if error_rate is not None:
                        USER_EXPERIENCE_METRICS["error_rate"].labels(
                            service=service, endpoint="all"
                        ).inc(error_rate)
                        
                        logger.debug("Error rate updated", service=service, rate=error_rate)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error("Error monitoring error rates", error=str(e))
                await asyncio.sleep(60)
    
    async def _monitor_throughput(self):
        """Monitor throughput across all services."""
        
        while self.is_running:
            try:
                services = self.config.get("services", [])
                
                for service in services:
                    throughput = await self._get_throughput(service)
                    
                    if throughput is not None:
                        USER_EXPERIENCE_METRICS["throughput"].labels(service=service).inc(throughput)
                        
                        logger.debug("Throughput updated", service=service, rate=throughput)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error("Error monitoring throughput", error=str(e))
                await asyncio.sleep(60)
    
    async def _monitor_active_users(self):
        """Monitor active users."""
        
        while self.is_running:
            try:
                active_users = await self._get_active_users()
                
                if active_users is not None:
                    USER_EXPERIENCE_METRICS["active_users"].set(active_users)
                    
                    logger.debug("Active users updated", count=active_users)
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error("Error monitoring active users", error=str(e))
                await asyncio.sleep(60)
    
    async def _monitor_chat_completion(self):
        """Monitor chat completion rate."""
        
        while self.is_running:
            try:
                completion_rate = await self._get_chat_completion_rate()
                
                if completion_rate is not None:
                    USER_EXPERIENCE_METRICS["chat_completion_rate"].set(completion_rate)
                    
                    logger.debug("Chat completion rate updated", rate=completion_rate)
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error("Error monitoring chat completion", error=str(e))
                await asyncio.sleep(60)
    
    async def _monitor_user_satisfaction(self):
        """Monitor user satisfaction score."""
        
        while self.is_running:
            try:
                satisfaction = await self._get_user_satisfaction()
                
                if satisfaction is not None:
                    USER_EXPERIENCE_METRICS["user_satisfaction"].set(satisfaction)
                    
                    logger.debug("User satisfaction updated", score=satisfaction)
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error("Error monitoring user satisfaction", error=str(e))
                await asyncio.sleep(300)
    
    async def _monitor_session_duration(self):
        """Monitor user session duration."""
        
        while self.is_running:
            try:
                session_durations = await self._get_session_durations()
                
                if session_durations:
                    for duration in session_durations:
                        USER_EXPERIENCE_METRICS["session_duration"].observe(duration)
                    
                    logger.debug("Session durations updated", count=len(session_durations))
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error("Error monitoring session duration", error=str(e))
                await asyncio.sleep(60)
    
    async def _monitor_feature_adoption(self):
        """Monitor feature adoption rates."""
        
        while self.is_running:
            try:
                features = self.config.get("features", [])
                
                for feature in features:
                    adoption_rate = await self._get_feature_adoption(feature)
                    
                    if adoption_rate is not None:
                        USER_EXPERIENCE_METRICS["feature_adoption"].labels(feature=feature).set(adoption_rate)
                        
                        logger.debug("Feature adoption updated", feature=feature, rate=adoption_rate)
                
                await asyncio.sleep(300)  # Check every 5 minutes
                
            except Exception as e:
                logger.error("Error monitoring feature adoption", error=str(e))
                await asyncio.sleep(300)
    
    async def _check_alerts(self):
        """Check for alert conditions."""
        
        while self.is_running:
            try:
                await self._check_response_time_alerts()
                await self._check_error_rate_alerts()
                await self._check_completion_rate_alerts()
                await self._check_satisfaction_alerts()
                
                await asyncio.sleep(60)  # Check every minute
                
            except Exception as e:
                logger.error("Error checking alerts", error=str(e))
                await asyncio.sleep(60)
    
    async def _check_response_time_alerts(self):
        """Check response time alerts."""
        
        # Get current response time metrics
        p95_response_time = USER_EXPERIENCE_METRICS["response_time_p95"]._sum.get()
        
        if p95_response_time > 1.0:  # Alert if p95 > 1 second
            alert = {
                "type": "response_time",
                "severity": "warning",
                "message": f"High response time detected: p95 = {p95_response_time:.2f}s",
                "timestamp": datetime.now(),
                "threshold": 1.0,
                "current_value": p95_response_time
            }
            
            await self._send_alert(alert)
    
    async def _check_error_rate_alerts(self):
        """Check error rate alerts."""
        
        # Get current error rate
        total_errors = USER_EXPERIENCE_METRICS["error_rate"]._sum.get()
        
        if total_errors > 0.01:  # Alert if error rate > 1%
            alert = {
                "type": "error_rate",
                "severity": "critical",
                "message": f"High error rate detected: {total_errors:.2%}",
                "timestamp": datetime.now(),
                "threshold": 0.01,
                "current_value": total_errors
            }
            
            await self._send_alert(alert)
    
    async def _check_completion_rate_alerts(self):
        """Check chat completion rate alerts."""
        
        completion_rate = USER_EXPERIENCE_METRICS["chat_completion_rate"]._value.get()
        
        if completion_rate < 0.9:  # Alert if completion rate < 90%
            alert = {
                "type": "completion_rate",
                "severity": "warning",
                "message": f"Low chat completion rate: {completion_rate:.2%}",
                "timestamp": datetime.now(),
                "threshold": 0.9,
                "current_value": completion_rate
            }
            
            await self._send_alert(alert)
    
    async def _check_satisfaction_alerts(self):
        """Check user satisfaction alerts."""
        
        satisfaction = USER_EXPERIENCE_METRICS["user_satisfaction"]._value.get()
        
        if satisfaction < 4.0:  # Alert if satisfaction < 4.0/5.0
            alert = {
                "type": "satisfaction",
                "severity": "warning",
                "message": f"Low user satisfaction: {satisfaction:.2f}/5.0",
                "timestamp": datetime.now(),
                "threshold": 4.0,
                "current_value": satisfaction
            }
            
            await self._send_alert(alert)
    
    async def _send_alert(self, alert: Dict[str, Any]):
        """Send alert notification."""
        
        # Check if alert already sent recently
        alert_key = f"{alert['type']}_{alert['severity']}"
        recent_alerts = [
            a for a in self.alerts 
            if a['type'] == alert['type'] and 
            a['severity'] == alert['severity'] and 
            (datetime.now() - a['timestamp']).seconds < 300  # 5 minutes
        ]
        
        if recent_alerts:
            return  # Don't send duplicate alerts
        
        self.alerts.append(alert)
        
        # Send alert (in production, this would send to Slack, PagerDuty, etc.)
        logger.warning("Alert triggered", alert=alert)
        
        # Here you would integrate with your alerting system
        # await self._send_to_slack(alert)
        # await self._send_to_pagerduty(alert)
    
    async def _generate_reports(self):
        """Generate periodic reports."""
        
        while self.is_running:
            try:
                # Generate hourly report
                await asyncio.sleep(3600)  # Wait 1 hour
                
                report = await self._generate_hourly_report()
                logger.info("Hourly report generated", report=report)
                
                # Generate daily report at midnight
                now = datetime.now()
                if now.hour == 0 and now.minute < 5:
                    daily_report = await self._generate_daily_report()
                    logger.info("Daily report generated", report=daily_report)
                
            except Exception as e:
                logger.error("Error generating reports", error=str(e))
                await asyncio.sleep(3600)
    
    async def _generate_hourly_report(self) -> Dict[str, Any]:
        """Generate hourly user experience report."""
        
        return {
            "timestamp": datetime.now(),
            "type": "hourly",
            "metrics": {
                "response_time_p95": USER_EXPERIENCE_METRICS["response_time_p95"]._sum.get(),
                "error_rate": USER_EXPERIENCE_METRICS["error_rate"]._sum.get(),
                "active_users": USER_EXPERIENCE_METRICS["active_users"]._value.get(),
                "chat_completion_rate": USER_EXPERIENCE_METRICS["chat_completion_rate"]._value.get(),
                "user_satisfaction": USER_EXPERIENCE_METRICS["user_satisfaction"]._value.get()
            },
            "alerts": len(self.alerts),
            "status": "healthy" if len(self.alerts) == 0 else "degraded"
        }
    
    async def _generate_daily_report(self) -> Dict[str, Any]:
        """Generate daily user experience report."""
        
        return {
            "timestamp": datetime.now(),
            "type": "daily",
            "summary": {
                "total_alerts": len(self.alerts),
                "avg_response_time": USER_EXPERIENCE_METRICS["response_time_p95"]._sum.get(),
                "avg_error_rate": USER_EXPERIENCE_METRICS["error_rate"]._sum.get(),
                "peak_active_users": USER_EXPERIENCE_METRICS["active_users"]._value.get(),
                "avg_completion_rate": USER_EXPERIENCE_METRICS["chat_completion_rate"]._value.get(),
                "avg_satisfaction": USER_EXPERIENCE_METRICS["user_satisfaction"]._value.get()
            },
            "recommendations": await self._generate_recommendations()
        }
    
    async def _generate_recommendations(self) -> List[str]:
        """Generate improvement recommendations."""
        
        recommendations = []
        
        p95_response_time = USER_EXPERIENCE_METRICS["response_time_p95"]._sum.get()
        if p95_response_time > 0.5:
            recommendations.append("Consider optimizing database queries to improve response times")
        
        error_rate = USER_EXPERIENCE_METRICS["error_rate"]._sum.get()
        if error_rate > 0.005:
            recommendations.append("Investigate and fix recurring errors to improve reliability")
        
        completion_rate = USER_EXPERIENCE_METRICS["chat_completion_rate"]._value.get()
        if completion_rate < 0.95:
            recommendations.append("Review chat flow to improve completion rates")
        
        satisfaction = USER_EXPERIENCE_METRICS["user_satisfaction"]._value.get()
        if satisfaction < 4.5:
            recommendations.append("Gather user feedback to identify satisfaction improvement opportunities")
        
        return recommendations
    
    # Mock methods for getting metrics (in production, these would query actual data sources)
    
    async def _get_response_times(self, service: str) -> Optional[Dict[str, float]]:
        """Get response times for a service."""
        # Mock implementation - in production, this would query Prometheus or your metrics system
        return {
            "p50": 0.1 + (hash(service) % 100) / 1000,
            "p95": 0.2 + (hash(service) % 200) / 1000,
            "p99": 0.5 + (hash(service) % 500) / 1000
        }
    
    async def _get_error_rate(self, service: str) -> Optional[float]:
        """Get error rate for a service."""
        # Mock implementation
        return (hash(service) % 100) / 10000  # 0-1% error rate
    
    async def _get_throughput(self, service: str) -> Optional[float]:
        """Get throughput for a service."""
        # Mock implementation
        return 100 + (hash(service) % 1000)  # 100-1100 RPS
    
    async def _get_active_users(self) -> Optional[int]:
        """Get active user count."""
        # Mock implementation
        return 1000 + (hash(str(time.time())) % 5000)  # 1000-6000 users
    
    async def _get_chat_completion_rate(self) -> Optional[float]:
        """Get chat completion rate."""
        # Mock implementation
        return 0.9 + (hash(str(time.time())) % 100) / 1000  # 90-100%
    
    async def _get_user_satisfaction(self) -> Optional[float]:
        """Get user satisfaction score."""
        # Mock implementation
        return 4.0 + (hash(str(time.time())) % 100) / 100  # 4.0-5.0
    
    async def _get_session_durations(self) -> List[float]:
        """Get session durations."""
        # Mock implementation
        return [300 + (hash(str(i)) % 1800) for i in range(100)]  # 5-35 minutes
    
    async def _get_feature_adoption(self, feature: str) -> Optional[float]:
        """Get feature adoption rate."""
        # Mock implementation
        return 0.5 + (hash(feature) % 500) / 1000  # 50-100%
    
    def stop_monitoring(self):
        """Stop monitoring."""
        self.is_running = False
        logger.info("User experience monitoring stopped")


async def main():
    """Main monitoring function."""
    
    # Configure logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    # Load configuration
    config = {
        "services": [
            "api-gateway", "orchestrator", "router-service", "realtime",
            "analytics-service", "billing-service", "ingestion", "chat-adapters",
            "tenant-service", "admin-portal", "eval-service"
        ],
        "features": [
            "chat", "voice", "file_upload", "analytics", "billing", "admin"
        ],
        "metrics_port": 8000,
        "domain": "your-domain.com"
    }
    
    logger.info("Starting user experience monitoring", config=config)
    
    monitor = UserExperienceMonitor(config)
    
    try:
        await monitor.start_monitoring()
    except KeyboardInterrupt:
        logger.info("Monitoring stopped by user")
        monitor.stop_monitoring()
    except Exception as e:
        logger.error("Monitoring failed", error=str(e))
        monitor.stop_monitoring()
        raise


if __name__ == "__main__":
    asyncio.run(main())
