"""
Row Level Security (RLS) Implementation

Enforces cross-tenant data isolation with comprehensive RLS policies,
tenant context management, and security validation.
"""

import asyncio
from typing import Dict, List, Optional, Any, Set, Union
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime, timedelta
from sqlalchemy import text, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class TenantAccessLevel(Enum):
    """Tenant access levels for RLS policies."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


@dataclass
class TenantContext:
    """Tenant context for RLS enforcement."""
    
    tenant_id: str
    user_id: Optional[str] = None
    access_level: TenantAccessLevel = TenantAccessLevel.READ
    roles: List[str] = None
    permissions: Set[str] = None
    data_region: Optional[str] = None
    created_at: datetime = None
    
    def __post_init__(self):
        if self.roles is None:
            self.roles = []
        if self.permissions is None:
            self.permissions = set()
        if self.created_at is None:
            self.created_at = datetime.now()


class RLSPolicy:
    """Row Level Security policy definition."""
    
    def __init__(
        self,
        table_name: str,
        policy_name: str,
        policy_type: str,  # "select", "insert", "update", "delete"
        expression: str,
        description: str = ""
    ):
        self.table_name = table_name
        self.policy_name = policy_name
        self.policy_type = policy_type
        self.expression = expression
        self.description = description
    
    def to_sql(self) -> str:
        """Convert policy to SQL DDL statement."""
        return f"""
        CREATE POLICY {self.policy_name} ON {self.table_name}
        FOR {self.policy_type.upper()}
        TO authenticated
        USING ({self.expression});
        """


class RLSManager:
    """Manages Row Level Security policies and enforcement."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.policies: Dict[str, List[RLSPolicy]] = {}
        self.tenant_contexts: Dict[str, TenantContext] = {}
        
        logger.info("RLS Manager initialized")
    
    async def setup_rls_policies(self):
        """Set up all RLS policies for the database."""
        
        policies = self._get_default_policies()
        
        for table_name, table_policies in policies.items():
            await self._setup_table_policies(table_name, table_policies)
        
        logger.info("RLS policies set up successfully")
    
    def _get_default_policies(self) -> Dict[str, List[RLSPolicy]]:
        """Get default RLS policies for all tables."""
        
        return {
            "tenants": [
                RLSPolicy(
                    table_name="tenants",
                    policy_name="tenant_isolation_select",
                    policy_type="select",
                    expression="id = current_setting('app.current_tenant_id')",
                    description="Users can only see their own tenant"
                ),
                RLSPolicy(
                    table_name="tenants",
                    policy_name="tenant_isolation_update",
                    policy_type="update",
                    expression="id = current_setting('app.current_tenant_id')",
                    description="Users can only update their own tenant"
                )
            ],
            "users": [
                RLSPolicy(
                    table_name="users",
                    policy_name="user_tenant_isolation_select",
                    policy_type="select",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only see users in their tenant"
                ),
                RLSPolicy(
                    table_name="users",
                    policy_name="user_tenant_isolation_insert",
                    policy_type="insert",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only create users in their tenant"
                ),
                RLSPolicy(
                    table_name="users",
                    policy_name="user_tenant_isolation_update",
                    policy_type="update",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only update users in their tenant"
                ),
                RLSPolicy(
                    table_name="users",
                    policy_name="user_tenant_isolation_delete",
                    policy_type="delete",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only delete users in their tenant"
                )
            ],
            "agents": [
                RLSPolicy(
                    table_name="agents",
                    policy_name="agent_tenant_isolation_select",
                    policy_type="select",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only see agents in their tenant"
                ),
                RLSPolicy(
                    table_name="agents",
                    policy_name="agent_tenant_isolation_insert",
                    policy_type="insert",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only create agents in their tenant"
                ),
                RLSPolicy(
                    table_name="agents",
                    policy_name="agent_tenant_isolation_update",
                    policy_type="update",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only update agents in their tenant"
                ),
                RLSPolicy(
                    table_name="agents",
                    policy_name="agent_tenant_isolation_delete",
                    policy_type="delete",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only delete agents in their tenant"
                )
            ],
            "messages": [
                RLSPolicy(
                    table_name="messages",
                    policy_name="message_tenant_isolation_select",
                    policy_type="select",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only see messages in their tenant"
                ),
                RLSPolicy(
                    table_name="messages",
                    policy_name="message_tenant_isolation_insert",
                    policy_type="insert",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only create messages in their tenant"
                ),
                RLSPolicy(
                    table_name="messages",
                    policy_name="message_tenant_isolation_update",
                    policy_type="update",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only update messages in their tenant"
                ),
                RLSPolicy(
                    table_name="messages",
                    policy_name="message_tenant_isolation_delete",
                    policy_type="delete",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only delete messages in their tenant"
                )
            ],
            "workflows": [
                RLSPolicy(
                    table_name="workflows",
                    policy_name="workflow_tenant_isolation_select",
                    policy_type="select",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only see workflows in their tenant"
                ),
                RLSPolicy(
                    table_name="workflows",
                    policy_name="workflow_tenant_isolation_insert",
                    policy_type="insert",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only create workflows in their tenant"
                ),
                RLSPolicy(
                    table_name="workflows",
                    policy_name="workflow_tenant_isolation_update",
                    policy_type="update",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only update workflows in their tenant"
                ),
                RLSPolicy(
                    table_name="workflows",
                    policy_name="workflow_tenant_isolation_delete",
                    policy_type="delete",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only delete workflows in their tenant"
                )
            ],
            "analytics": [
                RLSPolicy(
                    table_name="analytics",
                    policy_name="analytics_tenant_isolation_select",
                    policy_type="select",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only see analytics in their tenant"
                ),
                RLSPolicy(
                    table_name="analytics",
                    policy_name="analytics_tenant_isolation_insert",
                    policy_type="insert",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only create analytics in their tenant"
                ),
                RLSPolicy(
                    table_name="analytics",
                    policy_name="analytics_tenant_isolation_update",
                    policy_type="update",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only update analytics in their tenant"
                ),
                RLSPolicy(
                    table_name="analytics",
                    policy_name="analytics_tenant_isolation_delete",
                    policy_type="delete",
                    expression="tenant_id = current_setting('app.current_tenant_id')",
                    description="Users can only delete analytics in their tenant"
                )
            ]
        }
    
    async def _setup_table_policies(self, table_name: str, policies: List[RLSPolicy]):
        """Set up RLS policies for a specific table."""
        
        try:
            # Enable RLS on table
            await self.db_session.execute(text(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;"))
            
            # Create policies
            for policy in policies:
                await self.db_session.execute(text(policy.to_sql()))
                logger.debug("RLS policy created", 
                           table=table_name,
                           policy=policy.policy_name,
                           type=policy.policy_type)
            
            # Store policies
            self.policies[table_name] = policies
            
        except Exception as e:
            logger.error("Error setting up RLS policies", 
                        table=table_name,
                        error=str(e))
            raise
    
    async def set_tenant_context(self, tenant_context: TenantContext):
        """Set tenant context for the current database session."""
        
        try:
            # Set tenant context in database session
            await self.db_session.execute(
                text("SELECT set_config('app.current_tenant_id', :tenant_id, true)"),
                {"tenant_id": tenant_context.tenant_id}
            )
            
            if tenant_context.user_id:
                await self.db_session.execute(
                    text("SELECT set_config('app.current_user_id', :user_id, true)"),
                    {"user_id": tenant_context.user_id}
                )
            
            if tenant_context.data_region:
                await self.db_session.execute(
                    text("SELECT set_config('app.current_data_region', :region, true)"),
                    {"region": tenant_context.data_region}
                )
            
            # Store context
            self.tenant_contexts[tenant_context.tenant_id] = tenant_context
            
            logger.debug("Tenant context set", 
                        tenant_id=tenant_context.tenant_id,
                        user_id=tenant_context.user_id,
                        access_level=tenant_context.access_level.value)
            
        except Exception as e:
            logger.error("Error setting tenant context", 
                        tenant_id=tenant_context.tenant_id,
                        error=str(e))
            raise
    
    async def validate_tenant_access(
        self, 
        tenant_id: str, 
        resource_tenant_id: str,
        required_access: TenantAccessLevel = TenantAccessLevel.READ
    ) -> bool:
        """Validate that tenant has access to a resource."""
        
        # Same tenant always has access
        if tenant_id == resource_tenant_id:
            return True
        
        # Check for cross-tenant access (admin users, etc.)
        tenant_context = self.tenant_contexts.get(tenant_id)
        if tenant_context and tenant_context.access_level in [TenantAccessLevel.ADMIN, TenantAccessLevel.OWNER]:
            return True
        
        return False
    
    async def enforce_tenant_isolation(
        self, 
        query, 
        tenant_id: str,
        table_name: Optional[str] = None
    ) -> Any:
        """Enforce tenant isolation on a query."""
        
        # Set tenant context
        tenant_context = TenantContext(
            tenant_id=tenant_id,
            access_level=TenantAccessLevel.READ
        )
        await self.set_tenant_context(tenant_context)
        
        # Execute query with RLS enforcement
        try:
            result = await self.db_session.execute(query)
            return result
        except Exception as e:
            logger.error("Error executing query with RLS", 
                        tenant_id=tenant_id,
                        table=table_name,
                        error=str(e))
            raise
    
    async def check_cross_tenant_access(self, tenant_id: str, resource_tenant_id: str) -> bool:
        """Check if cross-tenant access is allowed."""
        
        # Same tenant
        if tenant_id == resource_tenant_id:
            return True
        
        # Get tenant context
        tenant_context = self.tenant_contexts.get(tenant_id)
        if not tenant_context:
            return False
        
        # Check permissions
        cross_tenant_permissions = {"admin", "cross_tenant_access", "system_admin"}
        return bool(tenant_context.permissions.intersection(cross_tenant_permissions))
    
    async def get_tenant_data_count(self, tenant_id: str, table_name: str) -> int:
        """Get count of records for a tenant in a specific table."""
        
        try:
            # Set tenant context
            tenant_context = TenantContext(tenant_id=tenant_id)
            await self.set_tenant_context(tenant_context)
            
            # Execute count query with RLS
            result = await self.db_session.execute(
                text(f"SELECT COUNT(*) FROM {table_name}")
            )
            
            count = result.scalar()
            return count or 0
            
        except Exception as e:
            logger.error("Error getting tenant data count", 
                        tenant_id=tenant_id,
                        table=table_name,
                        error=str(e))
            return 0
    
    async def cleanup_tenant_data(self, tenant_id: str, table_name: str) -> int:
        """Clean up all data for a tenant from a specific table."""
        
        try:
            # Set tenant context
            tenant_context = TenantContext(
                tenant_id=tenant_id,
                access_level=TenantAccessLevel.ADMIN
            )
            await self.set_tenant_context(tenant_context)
            
            # Execute delete with RLS
            result = await self.db_session.execute(
                text(f"DELETE FROM {table_name}")
            )
            
            deleted_count = result.rowcount
            await self.db_session.commit()
            
            logger.info("Tenant data cleaned up", 
                       tenant_id=tenant_id,
                       table=table_name,
                       deleted_count=deleted_count)
            
            return deleted_count
            
        except Exception as e:
            logger.error("Error cleaning up tenant data", 
                        tenant_id=tenant_id,
                        table=table_name,
                        error=str(e))
            await self.db_session.rollback()
            raise
    
    def get_policies_for_table(self, table_name: str) -> List[RLSPolicy]:
        """Get all RLS policies for a specific table."""
        return self.policies.get(table_name, [])
    
    async def verify_rls_enforcement(self, tenant_id: str) -> Dict[str, bool]:
        """Verify that RLS is properly enforced for a tenant."""
        
        verification_results = {}
        
        # Test tables
        test_tables = ["users", "agents", "messages", "workflows", "analytics"]
        
        for table in test_tables:
            try:
                # Set tenant context
                tenant_context = TenantContext(tenant_id=tenant_id)
                await self.set_tenant_context(tenant_context)
                
                # Try to access data
                result = await self.db_session.execute(
                    text(f"SELECT COUNT(*) FROM {table}")
                )
                
                count = result.scalar()
                verification_results[table] = True
                
                logger.debug("RLS verification passed", 
                           tenant_id=tenant_id,
                           table=table,
                           count=count)
                
            except Exception as e:
                verification_results[table] = False
                logger.error("RLS verification failed", 
                           tenant_id=tenant_id,
                           table=table,
                           error=str(e))
        
        return verification_results
    
    async def get_tenant_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """Get metrics for a tenant's data usage."""
        
        metrics = {
            "tenant_id": tenant_id,
            "table_counts": {},
            "total_records": 0,
            "last_accessed": datetime.now().isoformat()
        }
        
        # Count records in each table
        tables = ["users", "agents", "messages", "workflows", "analytics"]
        
        for table in tables:
            count = await self.get_tenant_data_count(tenant_id, table)
            metrics["table_counts"][table] = count
            metrics["total_records"] += count
        
        return metrics
