"""Regional Analytics Engine for multi-region data processing."""

from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import asyncio
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)


@dataclass
class RegionalQuery:
    """Regional analytics query configuration."""
    tenant_id: str
    query: str
    regions: List[str]
    start_time: datetime
    end_time: datetime
    metrics: List[str]


@dataclass
class RegionalResult:
    """Regional analytics query result."""
    region: str
    data: List[Dict[str, Any]]
    processing_time: float
    record_count: int


class RegionalAnalyticsEngine:
    """Engine for processing analytics queries across multiple regions."""
    
    def __init__(self, db_session: AsyncSession):
        self.db = db_session
        self.regional_read_replicas: Dict[str, AsyncSession] = {}
        self.regional_connections = {}
        self._setup_regional_replicas()
    
    def _setup_regional_replicas(self) -> None:
        """Setup read replicas per region."""
        # This would typically connect to actual regional read replicas
        # For now, we'll use the same connection but with region-specific queries
        regions = ["us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1", "ap-northeast-1"]
        
        for region in regions:
            # In production, this would connect to actual read replicas
            self.regional_read_replicas[region] = self.db
            self.regional_connections[region] = {
                "host": f"analytics-{region}.example.com",
                "port": 5432,
                "database": "analytics",
                "status": "healthy"
            }
        
        logger.info("Regional analytics replicas configured", 
                   regions=list(self.regional_read_replicas.keys()))
    
    async def route_analytics_query(self, tenant_id: str, query: str, 
                                  regions: Optional[List[str]] = None) -> Dict[str, Any]:
        """Route analytics queries to appropriate regional replica."""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Determine target regions
            if not regions:
                # Get tenant's allowed regions from database
                regions = await self._get_tenant_allowed_regions(tenant_id)
            
            # Validate regional access
            if not await self._validate_regional_access(tenant_id, regions):
                return {
                    "error": "Regional access denied",
                    "detail": f"Tenant not allowed to query regions: {regions}"
                }
            
            # Execute query in parallel across regions
            regional_queries = []
            for region in regions:
                regional_queries.append(
                    self._execute_regional_query(tenant_id, query, region)
                )
            
            # Wait for all regional queries to complete
            regional_results = await asyncio.gather(*regional_queries, return_exceptions=True)
            
            # Process results
            results = []
            total_records = 0
            total_processing_time = 0
            
            for i, result in enumerate(regional_results):
                if isinstance(result, Exception):
                    logger.error("Regional query failed",
                               region=regions[i],
                               error=str(result))
                    continue
                
                if result:
                    results.append(result)
                    total_records += result.record_count
                    total_processing_time += result.processing_time
            
            # Aggregate results
            aggregated_data = self._aggregate_regional_results(results)
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            logger.info("Analytics query completed",
                       tenant_id=tenant_id,
                       regions=regions,
                       total_records=total_records,
                       processing_time=processing_time)
            
            return {
                "data": aggregated_data,
                "metadata": {
                    "regions_queried": regions,
                    "total_records": total_records,
                    "processing_time": processing_time,
                    "regional_breakdown": [
                        {
                            "region": r.region,
                            "records": r.record_count,
                            "processing_time": r.processing_time
                        }
                        for r in results
                    ]
                }
            }
            
        except Exception as e:
            logger.error("Failed to route analytics query",
                        tenant_id=tenant_id,
                        error=str(e))
            return {
                "error": "Query execution failed",
                "detail": str(e)
            }
    
    async def _execute_regional_query(self, tenant_id: str, query: str, region: str) -> Optional[RegionalResult]:
        """Execute query on regional replica."""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Get regional database connection
            db_connection = self.regional_read_replicas.get(region)
            if not db_connection:
                logger.error("No database connection for region", region=region)
                return None
            
            # Add regional filter to query
            regional_query = self._add_regional_filter(query, region, tenant_id)
            
            # Execute query
            result = await db_connection.execute(text(regional_query))
            rows = result.fetchall()
            
            # Convert rows to dictionaries
            data = []
            for row in rows:
                data.append(dict(row._mapping))
            
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            
            logger.info("Regional query executed",
                       tenant_id=tenant_id,
                       region=region,
                       record_count=len(data),
                       processing_time=processing_time)
            
            return RegionalResult(
                region=region,
                data=data,
                processing_time=processing_time,
                record_count=len(data)
            )
            
        except Exception as e:
            logger.error("Failed to execute regional query",
                        tenant_id=tenant_id,
                        region=region,
                        error=str(e))
            return None
    
    def _add_regional_filter(self, query: str, region: str, tenant_id: str) -> str:
        """Add regional and tenant filters to query."""
        # Add tenant filter (RLS should handle this, but we add it explicitly for safety)
        if "WHERE" in query.upper():
            # Add tenant and region filters to existing WHERE clause
            tenant_filter = f"tenant_id = '{tenant_id}'"
            region_filter = f"data_region = '{region}'"
            
            # Find WHERE clause and add filters
            where_index = query.upper().find("WHERE")
            where_clause = query[where_index:]
            
            if tenant_filter not in where_clause:
                where_clause = where_clause.replace("WHERE", f"WHERE {tenant_filter} AND")
            
            if region_filter not in where_clause:
                where_clause = where_clause.replace("WHERE", f"WHERE {region_filter} AND")
            
            query = query[:where_index] + where_clause
        else:
            # Add WHERE clause with filters
            query = f"{query} WHERE tenant_id = '{tenant_id}' AND data_region = '{region}'"
        
        return query
    
    def _aggregate_regional_results(self, results: List[RegionalResult]) -> List[Dict[str, Any]]:
        """Aggregate results from multiple regions."""
        try:
            if not results:
                return []
            
            # Simple aggregation - combine all data
            aggregated_data = []
            for result in results:
                aggregated_data.extend(result.data)
            
            # Sort by timestamp if available
            if aggregated_data and "timestamp" in aggregated_data[0]:
                aggregated_data.sort(key=lambda x: x["timestamp"], reverse=True)
            
            return aggregated_data
            
        except Exception as e:
            logger.error("Failed to aggregate regional results", error=str(e))
            return []
    
    async def _get_tenant_allowed_regions(self, tenant_id: str) -> List[str]:
        """Get tenant's allowed regions."""
        try:
            result = await self.db.execute(text("""
                SELECT allowed_regions
                FROM tenants
                WHERE id = :tenant_id
            """), {"tenant_id": tenant_id})
            
            row = result.fetchone()
            if row and row[0]:
                return row[0]
            
            # Default to tenant's data region
            result = await self.db.execute(text("""
                SELECT data_region
                FROM tenants
                WHERE id = :tenant_id
            """), {"tenant_id": tenant_id})
            
            row = result.fetchone()
            if row:
                return [row[0]]
            
            return ["us-east-1"]  # Default region
            
        except Exception as e:
            logger.error("Failed to get tenant allowed regions",
                        tenant_id=tenant_id,
                        error=str(e))
            return ["us-east-1"]
    
    async def _validate_regional_access(self, tenant_id: str, regions: List[str]) -> bool:
        """Validate if tenant can access specified regions."""
        try:
            # Get tenant's allowed regions
            allowed_regions = await self._get_tenant_allowed_regions(tenant_id)
            
            # Check if all requested regions are allowed
            for region in regions:
                if region not in allowed_regions:
                    logger.warning("Regional access denied",
                                  tenant_id=tenant_id,
                                  requested_region=region,
                                  allowed_regions=allowed_regions)
                    return False
            
            return True
            
        except Exception as e:
            logger.error("Failed to validate regional access",
                        tenant_id=tenant_id,
                        regions=regions,
                        error=str(e))
            return False
    
    async def get_regional_metrics(self, tenant_id: str, region: str, 
                                 start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get metrics for specific region."""
        try:
            query = """
                SELECT 
                    COUNT(*) as total_events,
                    COUNT(DISTINCT session_id) as unique_sessions,
                    AVG(processing_time_ms) as avg_processing_time,
                    MAX(processing_time_ms) as max_processing_time,
                    MIN(processing_time_ms) as min_processing_time
                FROM analytics_events_regional
                WHERE timestamp BETWEEN :start_time AND :end_time
            """
            
            result = await self._execute_regional_query(tenant_id, query, region)
            if not result or not result.data:
                return {}
            
            return result.data[0]
            
        except Exception as e:
            logger.error("Failed to get regional metrics",
                        tenant_id=tenant_id,
                        region=region,
                        error=str(e))
            return {}
    
    async def get_cross_region_summary(self, tenant_id: str, 
                                     start_time: datetime, end_time: datetime) -> Dict[str, Any]:
        """Get summary across all allowed regions."""
        try:
            allowed_regions = await self._get_tenant_allowed_regions(tenant_id)
            
            regional_summaries = {}
            total_events = 0
            total_sessions = 0
            
            for region in allowed_regions:
                metrics = await self.get_regional_metrics(tenant_id, region, start_time, end_time)
                if metrics:
                    regional_summaries[region] = metrics
                    total_events += metrics.get("total_events", 0)
                    total_sessions += metrics.get("unique_sessions", 0)
            
            return {
                "regional_breakdown": regional_summaries,
                "totals": {
                    "total_events": total_events,
                    "total_sessions": total_sessions,
                    "regions_queried": len(regional_summaries)
                }
            }
            
        except Exception as e:
            logger.error("Failed to get cross-region summary",
                        tenant_id=tenant_id,
                        error=str(e))
            return {}
    
    async def health_check_regional_replicas(self) -> Dict[str, Any]:
        """Check health of regional replicas."""
        try:
            health_status = {}
            
            for region, connection_info in self.regional_connections.items():
                try:
                    # Test connection to regional replica
                    db_connection = self.regional_read_replicas[region]
                    result = await db_connection.execute(text("SELECT 1"))
                    result.fetchone()
                    
                    health_status[region] = {
                        "status": "healthy",
                        "connection": connection_info,
                        "last_check": datetime.now(timezone.utc).isoformat()
                    }
                    
                except Exception as e:
                    health_status[region] = {
                        "status": "unhealthy",
                        "connection": connection_info,
                        "error": str(e),
                        "last_check": datetime.now(timezone.utc).isoformat()
                    }
            
            return health_status
            
        except Exception as e:
            logger.error("Failed to check regional replica health", error=str(e))
            return {}
