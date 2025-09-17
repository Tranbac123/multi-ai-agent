"""
RAG Metadata Management

Manages ingestion metadata with tenant isolation, role-based access control,
document lifecycle management, and TTL-based reindexing.
"""

import asyncio
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime, timedelta
from sqlalchemy import text, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger(__name__)


class DocumentStatus(Enum):
    """Document processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
    EXPIRED = "expired"
    DELETED = "deleted"


class SensitivityLevel(Enum):
    """Document sensitivity levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


@dataclass
class DocumentMetadata:
    """Document metadata for RAG ingestion."""
    
    doc_id: str
    tenant_id: str
    roles: List[str]
    source: str
    hash: str
    ttl: Optional[datetime] = None
    sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL
    status: DocumentStatus = DocumentStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    indexed_at: Optional[datetime] = None
    failed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    file_size: Optional[int] = None
    content_type: Optional[str] = None
    language: Optional[str] = None
    tags: Set[str] = field(default_factory=set)
    custom_metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalContext:
    """Context for document retrieval."""
    
    tenant_id: str
    user_roles: List[str]
    query: str
    max_results: int = 10
    sensitivity_filter: Optional[SensitivityLevel] = None
    include_expired: bool = False
    date_range: Optional[Tuple[datetime, datetime]] = None
    tags_filter: Optional[Set[str]] = None
    source_filter: Optional[Set[str]] = None


class RAGMetadataManager:
    """Manages RAG metadata with tenant isolation and access control."""
    
    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        
        logger.info("RAG metadata manager initialized")
    
    async def create_document_metadata(
        self,
        tenant_id: str,
        content: str,
        source: str,
        roles: List[str],
        sensitivity: SensitivityLevel = SensitivityLevel.INTERNAL,
        ttl_days: Optional[int] = None,
        tags: Optional[Set[str]] = None,
        custom_metadata: Optional[Dict[str, Any]] = None
    ) -> DocumentMetadata:
        """Create document metadata for ingestion."""
        
        # Generate document ID and hash
        doc_id = str(uuid.uuid4())
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        # Calculate TTL if provided
        ttl = None
        if ttl_days:
            ttl = datetime.now() + timedelta(days=ttl_days)
        
        # Create metadata
        metadata = DocumentMetadata(
            doc_id=doc_id,
            tenant_id=tenant_id,
            roles=roles,
            source=source,
            hash=content_hash,
            ttl=ttl,
            sensitivity=sensitivity,
            tags=tags or set(),
            custom_metadata=custom_metadata or {}
        )
        
        # Store in database
        await self._store_metadata(metadata)
        
        logger.info("Document metadata created", 
                   doc_id=doc_id,
                   tenant_id=tenant_id,
                   source=source,
                   sensitivity=sensitivity.value,
                   ttl_days=ttl_days)
        
        return metadata
    
    async def _store_metadata(self, metadata: DocumentMetadata):
        """Store document metadata in database."""
        
        query = """
        INSERT INTO document_metadata (
            doc_id, tenant_id, roles, source, hash, ttl, sensitivity,
            status, created_at, updated_at, file_size, content_type,
            language, tags, custom_metadata
        ) VALUES (
            :doc_id, :tenant_id, :roles, :source, :hash, :ttl, :sensitivity,
            :status, :created_at, :updated_at, :file_size, :content_type,
            :language, :tags, :custom_metadata
        )
        """
        
        await self.db_session.execute(text(query), {
            "doc_id": metadata.doc_id,
            "tenant_id": metadata.tenant_id,
            "roles": metadata.roles,
            "source": metadata.source,
            "hash": metadata.hash,
            "ttl": metadata.ttl,
            "sensitivity": metadata.sensitivity.value,
            "status": metadata.status.value,
            "created_at": metadata.created_at,
            "updated_at": metadata.updated_at,
            "file_size": metadata.file_size,
            "content_type": metadata.content_type,
            "language": metadata.language,
            "tags": list(metadata.tags),
            "custom_metadata": metadata.custom_metadata
        })
        
        await self.db_session.commit()
    
    async def update_document_status(
        self, 
        doc_id: str, 
        status: DocumentStatus,
        error_message: Optional[str] = None
    ):
        """Update document processing status."""
        
        query = """
        UPDATE document_metadata 
        SET status = :status, updated_at = :updated_at
        """
        
        params = {
            "doc_id": doc_id,
            "status": status.value,
            "updated_at": datetime.now()
        }
        
        if status == DocumentStatus.INDEXED:
            query += ", indexed_at = :indexed_at"
            params["indexed_at"] = datetime.now()
        elif status == DocumentStatus.FAILED:
            query += ", failed_at = :failed_at, error_message = :error_message"
            params["failed_at"] = datetime.now()
            params["error_message"] = error_message
        
        query += " WHERE doc_id = :doc_id"
        
        await self.db_session.execute(text(query), params)
        await self.db_session.commit()
        
        logger.debug("Document status updated", 
                    doc_id=doc_id,
                    status=status.value)
    
    async def get_document_metadata(self, doc_id: str) -> Optional[DocumentMetadata]:
        """Get document metadata by ID."""
        
        query = """
        SELECT * FROM document_metadata 
        WHERE doc_id = :doc_id
        """
        
        result = await self.db_session.execute(text(query), {"doc_id": doc_id})
        row = result.fetchone()
        
        if not row:
            return None
        
        return self._row_to_metadata(row)
    
    async def get_tenant_documents(
        self, 
        tenant_id: str,
        status: Optional[DocumentStatus] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[DocumentMetadata]:
        """Get documents for a tenant."""
        
        query = """
        SELECT * FROM document_metadata 
        WHERE tenant_id = :tenant_id
        """
        
        params = {"tenant_id": tenant_id}
        
        if status:
            query += " AND status = :status"
            params["status"] = status.value
        
        query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset
        
        result = await self.db_session.execute(text(query), params)
        rows = result.fetchall()
        
        return [self._row_to_metadata(row) for row in rows]
    
    async def check_document_permissions(
        self, 
        doc_id: str, 
        tenant_id: str, 
        user_roles: List[str]
    ) -> bool:
        """Check if user has permission to access document."""
        
        metadata = await self.get_document_metadata(doc_id)
        
        if not metadata:
            return False
        
        # Check tenant isolation
        if metadata.tenant_id != tenant_id:
            return False
        
        # Check role-based access
        if not any(role in metadata.roles for role in user_roles):
            return False
        
        # Check if document is expired
        if metadata.ttl and datetime.now() > metadata.ttl:
            return False
        
        return True
    
    async def get_expired_documents(self, limit: int = 100) -> List[DocumentMetadata]:
        """Get documents that have expired."""
        
        query = """
        SELECT * FROM document_metadata 
        WHERE ttl IS NOT NULL AND ttl < :now
        AND status != :deleted_status
        ORDER BY ttl ASC
        LIMIT :limit
        """
        
        result = await self.db_session.execute(text(query), {
            "now": datetime.now(),
            "deleted_status": DocumentStatus.DELETED.value,
            "limit": limit
        })
        
        rows = result.fetchall()
        return [self._row_to_metadata(row) for row in rows]
    
    async def mark_documents_expired(self, doc_ids: List[str]):
        """Mark documents as expired."""
        
        if not doc_ids:
            return
        
        query = """
        UPDATE document_metadata 
        SET status = :status, updated_at = :updated_at
        WHERE doc_id = ANY(:doc_ids)
        """
        
        await self.db_session.execute(text(query), {
            "status": DocumentStatus.EXPIRED.value,
            "updated_at": datetime.now(),
            "doc_ids": doc_ids
        })
        
        await self.db_session.commit()
        
        logger.info("Documents marked as expired", count=len(doc_ids))
    
    async def delete_document_metadata(self, doc_id: str):
        """Delete document metadata."""
        
        query = """
        UPDATE document_metadata 
        SET status = :status, updated_at = :updated_at
        WHERE doc_id = :doc_id
        """
        
        await self.db_session.execute(text(query), {
            "doc_id": doc_id,
            "status": DocumentStatus.DELETED.value,
            "updated_at": datetime.now()
        })
        
        await self.db_session.commit()
        
        logger.info("Document metadata deleted", doc_id=doc_id)
    
    async def get_tenant_metrics(self, tenant_id: str) -> Dict[str, Any]:
        """Get metrics for a tenant's documents."""
        
        query = """
        SELECT 
            status,
            sensitivity,
            COUNT(*) as count,
            AVG(file_size) as avg_file_size,
            MIN(created_at) as oldest_document,
            MAX(created_at) as newest_document
        FROM document_metadata 
        WHERE tenant_id = :tenant_id
        GROUP BY status, sensitivity
        """
        
        result = await self.db_session.execute(text(query), {"tenant_id": tenant_id})
        rows = result.fetchall()
        
        metrics = {
            "tenant_id": tenant_id,
            "total_documents": 0,
            "by_status": {},
            "by_sensitivity": {},
            "file_size_stats": {},
            "date_range": {}
        }
        
        total_documents = 0
        file_sizes = []
        dates = []
        
        for row in rows:
            status = row.status
            sensitivity = row.sensitivity
            count = row.count
            avg_file_size = row.avg_file_size
            oldest = row.oldest_document
            newest = row.newest_document
            
            total_documents += count
            
            # By status
            if status not in metrics["by_status"]:
                metrics["by_status"][status] = 0
            metrics["by_status"][status] += count
            
            # By sensitivity
            if sensitivity not in metrics["by_sensitivity"]:
                metrics["by_sensitivity"][sensitivity] = 0
            metrics["by_sensitivity"][sensitivity] += count
            
            # File size stats
            if avg_file_size:
                file_sizes.append(avg_file_size)
            
            # Date range
            if oldest:
                dates.append(oldest)
            if newest:
                dates.append(newest)
        
        metrics["total_documents"] = total_documents
        
        if file_sizes:
            metrics["file_size_stats"] = {
                "average": sum(file_sizes) / len(file_sizes),
                "min": min(file_sizes),
                "max": max(file_sizes)
            }
        
        if dates:
            metrics["date_range"] = {
                "oldest": min(dates),
                "newest": max(dates)
            }
        
        return metrics
    
    def _row_to_metadata(self, row) -> DocumentMetadata:
        """Convert database row to DocumentMetadata object."""
        
        return DocumentMetadata(
            doc_id=row.doc_id,
            tenant_id=row.tenant_id,
            roles=row.roles,
            source=row.source,
            hash=row.hash,
            ttl=row.ttl,
            sensitivity=SensitivityLevel(row.sensitivity),
            status=DocumentStatus(row.status),
            created_at=row.created_at,
            updated_at=row.updated_at,
            indexed_at=row.indexed_at,
            failed_at=row.failed_at,
            error_message=row.error_message,
            file_size=row.file_size,
            content_type=row.content_type,
            language=row.language,
            tags=set(row.tags) if row.tags else set(),
            custom_metadata=row.custom_metadata or {}
        )


class TTLReindexManager:
    """Manages TTL-based reindexing of documents."""
    
    def __init__(self, metadata_manager: RAGMetadataManager):
        self.metadata_manager = metadata_manager
        self.reindex_threshold_days = 7  # Reindex documents expiring within 7 days
        
        logger.info("TTL reindex manager initialized")
    
    async def find_documents_for_reindex(self) -> List[DocumentMetadata]:
        """Find documents that need reindexing based on TTL."""
        
        threshold_date = datetime.now() + timedelta(days=self.reindex_threshold_days)
        
        query = """
        SELECT * FROM document_metadata 
        WHERE ttl IS NOT NULL 
        AND ttl <= :threshold_date
        AND status = :indexed_status
        ORDER BY ttl ASC
        """
        
        result = await self.metadata_manager.db_session.execute(text(query), {
            "threshold_date": threshold_date,
            "indexed_status": DocumentStatus.INDEXED.value
        })
        
        rows = result.fetchall()
        return [self.metadata_manager._row_to_metadata(row) for row in rows]
    
    async def schedule_reindex(self, doc_ids: List[str]):
        """Schedule documents for reindexing."""
        
        if not doc_ids:
            return
        
        query = """
        UPDATE document_metadata 
        SET status = :status, updated_at = :updated_at
        WHERE doc_id = ANY(:doc_ids)
        """
        
        await self.metadata_manager.db_session.execute(text(query), {
            "status": DocumentStatus.PENDING.value,
            "updated_at": datetime.now(),
            "doc_ids": doc_ids
        })
        
        await self.metadata_manager.db_session.commit()
        
        logger.info("Documents scheduled for reindexing", count=len(doc_ids))
    
    async def run_ttl_reindex_job(self):
        """Run the TTL-based reindexing job."""
        
        # Find documents that need reindexing
        documents = await self.find_documents_for_reindex()
        
        if not documents:
            logger.debug("No documents found for TTL reindexing")
            return
        
        # Schedule for reindexing
        doc_ids = [doc.doc_id for doc in documents]
        await self.schedule_reindex(doc_ids)
        
        logger.info("TTL reindex job completed", 
                   documents_found=len(documents),
                   documents_scheduled=len(doc_ids))
