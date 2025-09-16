"""
Permissioned Retrieval System

Implements tenant-isolated document retrieval with role-based access control,
sensitivity filtering, and comprehensive permission validation.
"""

import asyncio
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime, timedelta
import hashlib

from .rag_metadata import (
    RAGMetadataManager, DocumentMetadata, RetrievalContext, 
    SensitivityLevel, DocumentStatus
)

logger = structlog.get_logger(__name__)


class AccessLevel(Enum):
    """User access levels for document retrieval."""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"
    OWNER = "owner"


@dataclass
class DocumentAccess:
    """Document access permissions."""
    
    doc_id: str
    tenant_id: str
    required_roles: Set[str]
    sensitivity: SensitivityLevel
    access_level: AccessLevel
    expires_at: Optional[datetime] = None
    created_by: Optional[str] = None


@dataclass
class RetrievalResult:
    """Result of document retrieval."""
    
    doc_id: str
    content: str
    metadata: DocumentMetadata
    relevance_score: float
    access_granted: bool
    access_reason: str
    retrieved_at: datetime


class PermissionValidator:
    """Validates document access permissions."""
    
    def __init__(self):
        self.sensitivity_access_map = {
            SensitivityLevel.PUBLIC: [AccessLevel.READ, AccessLevel.WRITE, AccessLevel.ADMIN, AccessLevel.OWNER],
            SensitivityLevel.INTERNAL: [AccessLevel.READ, AccessLevel.WRITE, AccessLevel.ADMIN, AccessLevel.OWNER],
            SensitivityLevel.CONFIDENTIAL: [AccessLevel.WRITE, AccessLevel.ADMIN, AccessLevel.OWNER],
            SensitivityLevel.RESTRICTED: [AccessLevel.ADMIN, AccessLevel.OWNER]
        }
        
        logger.info("Permission validator initialized")
    
    def validate_access(
        self,
        user_roles: Set[str],
        user_access_level: AccessLevel,
        document_access: DocumentAccess,
        include_expired: bool = False
    ) -> Tuple[bool, str]:
        """Validate if user has access to document."""
        
        # Check if document is expired
        if not include_expired and document_access.expires_at:
            if datetime.now() > document_access.expires_at:
                return False, "document_expired"
        
        # Check tenant isolation
        if not user_roles or not any(role in document_access.required_roles for role in user_roles):
            return False, "insufficient_roles"
        
        # Check sensitivity level access
        allowed_access_levels = self.sensitivity_access_map.get(
            document_access.sensitivity, []
        )
        
        if user_access_level not in allowed_access_levels:
            return False, f"insufficient_access_level_for_{document_access.sensitivity.value}"
        
        # Check access level hierarchy
        access_level_hierarchy = {
            AccessLevel.READ: 1,
            AccessLevel.WRITE: 2,
            AccessLevel.ADMIN: 3,
            AccessLevel.OWNER: 4
        }
        
        user_level = access_level_hierarchy.get(user_access_level, 0)
        required_level = access_level_hierarchy.get(document_access.access_level, 0)
        
        if user_level < required_level:
            return False, "insufficient_access_level"
        
        return True, "access_granted"
    
    def get_accessible_sensitivity_levels(self, user_access_level: AccessLevel) -> List[SensitivityLevel]:
        """Get sensitivity levels accessible to user."""
        
        accessible_levels = []
        
        for sensitivity, access_levels in self.sensitivity_access_map.items():
            if user_access_level in access_levels:
                accessible_levels.append(sensitivity)
        
        return accessible_levels


class PermissionedRetrievalEngine:
    """Engine for permissioned document retrieval."""
    
    def __init__(
        self, 
        metadata_manager: RAGMetadataManager,
        vector_store_client=None  # Placeholder for vector store client
    ):
        self.metadata_manager = metadata_manager
        self.vector_store_client = vector_store_client
        self.permission_validator = PermissionValidator()
        
        # Cache for access permissions
        self.access_cache: Dict[str, DocumentAccess] = {}
        self.cache_ttl = 300  # 5 minutes
        
        logger.info("Permissioned retrieval engine initialized")
    
    async def retrieve_documents(
        self, 
        context: RetrievalContext,
        user_access_level: AccessLevel = AccessLevel.READ
    ) -> List[RetrievalResult]:
        """Retrieve documents with permission validation."""
        
        logger.info("Starting permissioned retrieval", 
                   tenant_id=context.tenant_id,
                   query_length=len(context.query),
                   max_results=context.max_results)
        
        # Get accessible sensitivity levels
        accessible_sensitivity_levels = self.permission_validator.get_accessible_sensitivity_levels(
            user_access_level
        )
        
        # Build permission filter
        permission_filter = await self._build_permission_filter(
            context, accessible_sensitivity_levels
        )
        
        # Retrieve documents from vector store with permission filter
        vector_results = await self._retrieve_from_vector_store(
            context, permission_filter
        )
        
        # Validate access for each document
        validated_results = []
        
        for result in vector_results:
            doc_id = result.get("doc_id")
            content = result.get("content", "")
            relevance_score = result.get("score", 0.0)
            
            # Get document metadata
            metadata = await self.metadata_manager.get_document_metadata(doc_id)
            
            if not metadata:
                logger.warning("Document metadata not found", doc_id=doc_id)
                continue
            
            # Validate access
            document_access = await self._get_document_access(doc_id, metadata)
            access_granted, access_reason = self.permission_validator.validate_access(
                user_roles=set(context.user_roles),
                user_access_level=user_access_level,
                document_access=document_access,
                include_expired=context.include_expired
            )
            
            # Create retrieval result
            retrieval_result = RetrievalResult(
                doc_id=doc_id,
                content=content,
                metadata=metadata,
                relevance_score=relevance_score,
                access_granted=access_granted,
                access_reason=access_reason,
                retrieved_at=datetime.now()
            )
            
            validated_results.append(retrieval_result)
            
            # Stop if we have enough results
            if len(validated_results) >= context.max_results:
                break
        
        # Filter results based on access
        accessible_results = [
            result for result in validated_results 
            if result.access_granted
        ]
        
        logger.info("Permissioned retrieval completed", 
                   total_retrieved=len(validated_results),
                   accessible_results=len(accessible_results),
                   denied_count=len(validated_results) - len(accessible_results))
        
        return accessible_results
    
    async def _build_permission_filter(
        self, 
        context: RetrievalContext,
        accessible_sensitivity_levels: List[SensitivityLevel]
    ) -> Dict[str, Any]:
        """Build permission filter for vector store query."""
        
        filter_conditions = {
            "tenant_id": context.tenant_id,
            "status": DocumentStatus.INDEXED.value
        }
        
        # Add sensitivity filter
        if context.sensitivity_filter:
            if context.sensitivity_filter in accessible_sensitivity_levels:
                filter_conditions["sensitivity"] = context.sensitivity_filter.value
        else:
            # Filter by accessible sensitivity levels
            filter_conditions["sensitivity"] = [
                level.value for level in accessible_sensitivity_levels
            ]
        
        # Add date range filter
        if context.date_range:
            start_date, end_date = context.date_range
            filter_conditions["created_at"] = {
                "$gte": start_date.isoformat(),
                "$lte": end_date.isoformat()
            }
        
        # Add tags filter
        if context.tags_filter:
            filter_conditions["tags"] = {"$in": list(context.tags_filter)}
        
        # Add source filter
        if context.source_filter:
            filter_conditions["source"] = {"$in": list(context.source_filter)}
        
        # Add TTL filter (exclude expired unless explicitly requested)
        if not context.include_expired:
            filter_conditions["$or"] = [
                {"ttl": None},
                {"ttl": {"$gt": datetime.now().isoformat()}}
            ]
        
        return filter_conditions
    
    async def _retrieve_from_vector_store(
        self, 
        context: RetrievalContext,
        permission_filter: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Retrieve documents from vector store with permission filter."""
        
        if not self.vector_store_client:
            # Mock implementation for testing
            return await self._mock_vector_retrieval(context, permission_filter)
        
        try:
            # Use vector store client to search with filters
            results = await self.vector_store_client.search(
                query=context.query,
                filter=permission_filter,
                limit=context.max_results * 2  # Get more to account for filtering
            )
            
            return results
            
        except Exception as e:
            logger.error("Error retrieving from vector store", error=str(e))
            return []
    
    async def _mock_vector_retrieval(
        self, 
        context: RetrievalContext,
        permission_filter: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Mock vector retrieval for testing."""
        
        # Simulate vector store retrieval
        mock_results = []
        
        # Create mock documents based on filter
        for i in range(min(5, context.max_results)):
            doc_id = f"mock_doc_{i}"
            mock_results.append({
                "doc_id": doc_id,
                "content": f"Mock content for query: {context.query}",
                "score": 0.9 - (i * 0.1)
            })
        
        return mock_results
    
    async def _get_document_access(
        self, 
        doc_id: str, 
        metadata: DocumentMetadata
    ) -> DocumentAccess:
        """Get document access information."""
        
        # Check cache first
        cache_key = f"{doc_id}:{metadata.tenant_id}"
        if cache_key in self.access_cache:
            return self.access_cache[cache_key]
        
        # Create document access
        document_access = DocumentAccess(
            doc_id=doc_id,
            tenant_id=metadata.tenant_id,
            required_roles=set(metadata.roles),
            sensitivity=metadata.sensitivity,
            access_level=self._determine_access_level(metadata),
            expires_at=metadata.ttl,
            created_by=getattr(metadata, 'created_by', None)
        )
        
        # Cache the access information
        self.access_cache[cache_key] = document_access
        
        # Schedule cache cleanup
        asyncio.create_task(self._cleanup_cache_entry(cache_key))
        
        return document_access
    
    def _determine_access_level(self, metadata: DocumentMetadata) -> AccessLevel:
        """Determine required access level for document."""
        
        # Map sensitivity to access level
        sensitivity_access = {
            SensitivityLevel.PUBLIC: AccessLevel.READ,
            SensitivityLevel.INTERNAL: AccessLevel.READ,
            SensitivityLevel.CONFIDENTIAL: AccessLevel.WRITE,
            SensitivityLevel.RESTRICTED: AccessLevel.ADMIN
        }
        
        return sensitivity_access.get(metadata.sensitivity, AccessLevel.READ)
    
    async def _cleanup_cache_entry(self, cache_key: str):
        """Clean up cache entry after TTL."""
        
        await asyncio.sleep(self.cache_ttl)
        self.access_cache.pop(cache_key, None)
    
    async def validate_document_access(
        self, 
        doc_id: str,
        tenant_id: str,
        user_roles: List[str],
        user_access_level: AccessLevel = AccessLevel.READ,
        include_expired: bool = False
    ) -> Tuple[bool, str]:
        """Validate access to a specific document."""
        
        # Get document metadata
        metadata = await self.metadata_manager.get_document_metadata(doc_id)
        
        if not metadata:
            return False, "document_not_found"
        
        # Check tenant isolation
        if metadata.tenant_id != tenant_id:
            return False, "tenant_isolation_violation"
        
        # Get document access
        document_access = await self._get_document_access(doc_id, metadata)
        
        # Validate access
        return self.permission_validator.validate_access(
            user_roles=set(user_roles),
            user_access_level=user_access_level,
            document_access=document_access,
            include_expired=include_expired
        )
    
    async def get_accessible_documents(
        self,
        tenant_id: str,
        user_roles: List[str],
        user_access_level: AccessLevel = AccessLevel.READ,
        limit: int = 100
    ) -> List[DocumentMetadata]:
        """Get all documents accessible to user."""
        
        # Get accessible sensitivity levels
        accessible_sensitivity_levels = self.permission_validator.get_accessible_sensitivity_levels(
            user_access_level
        )
        
        # Get documents from metadata manager
        all_documents = await self.metadata_manager.get_tenant_documents(tenant_id)
        
        # Filter by accessibility
        accessible_documents = []
        
        for document in all_documents:
            # Check sensitivity level access
            if document.sensitivity not in accessible_sensitivity_levels:
                continue
            
            # Check role-based access
            if not any(role in document.roles for role in user_roles):
                continue
            
            # Check TTL
            if document.ttl and datetime.now() > document.ttl:
                continue
            
            accessible_documents.append(document)
            
            if len(accessible_documents) >= limit:
                break
        
        return accessible_documents
    
    async def get_retrieval_metrics(
        self, 
        tenant_id: str,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Get retrieval metrics for a tenant."""
        
        # This would typically query a metrics store
        # For now, return mock metrics
        
        return {
            "tenant_id": tenant_id,
            "total_retrievals": 1000,
            "successful_retrievals": 950,
            "access_denied": 50,
            "success_rate": 0.95,
            "average_relevance_score": 0.85,
            "by_sensitivity_level": {
                "public": 800,
                "internal": 100,
                "confidential": 40,
                "restricted": 10
            },
            "by_access_level": {
                "read": 900,
                "write": 80,
                "admin": 15,
                "owner": 5
            },
            "date_range": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            }
        }
    
    def clear_cache(self):
        """Clear the access cache."""
        
        self.access_cache.clear()
        logger.info("Access cache cleared")
