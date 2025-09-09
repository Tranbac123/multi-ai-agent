"""Document processor for ingestion pipeline."""

import hashlib
import mimetypes
from datetime import datetime
from typing import Dict, Any, List, Optional, Union
from uuid import UUID
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, insert, update, delete
import aiohttp
import aiofiles
from pathlib import Path

logger = structlog.get_logger(__name__)


class DocumentProcessor:
    """Processes documents for ingestion pipeline."""
    
    def __init__(self):
        self.supported_types = {
            'text/plain': self._process_text,
            'text/html': self._process_html,
            'application/pdf': self._process_pdf,
            'application/json': self._process_json,
            'text/markdown': self._process_markdown,
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document': self._process_docx,
        }
        self.max_file_size = 10 * 1024 * 1024  # 10MB
    
    async def process_document(
        self,
        doc_id: str,
        filename: str,
        content: bytes,
        tenant_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Process uploaded document."""
        try:
            # Calculate content hash for idempotency
            content_hash = hashlib.sha256(content).hexdigest()
            
            # Check if document already exists
            existing_doc = await self._get_document_by_hash(content_hash, tenant_id, db)
            if existing_doc:
                logger.info("Document already exists", doc_id=doc_id, hash=content_hash)
                return existing_doc
            
            # Detect content type
            content_type = self._detect_content_type(filename, content)
            
            # Process content based on type
            if content_type in self.supported_types:
                processed_content = await self.supported_types[content_type](content)
            else:
                raise ValueError(f"Unsupported content type: {content_type}")
            
            # Extract metadata
            metadata = await self._extract_metadata(filename, content, processed_content)
            
            # Store document
            doc_data = {
                "id": doc_id,
                "tenant_id": tenant_id,
                "filename": filename,
                "content_type": content_type,
                "content_hash": content_hash,
                "size_bytes": len(content),
                "metadata": metadata,
                "status": "processed",
                "created_at": datetime.utcnow()
            }
            
            await self._store_document(doc_data, db)
            
            # Publish indexing event
            await self._publish_indexing_event(doc_id, tenant_id, processed_content, metadata)
            
            logger.info("Document processed successfully", 
                       doc_id=doc_id, 
                       filename=filename,
                       content_type=content_type)
            
            return {
                "doc_id": doc_id,
                "filename": filename,
                "content_type": content_type,
                "size_bytes": len(content),
                "status": "processed",
                "metadata": metadata
            }
            
        except Exception as e:
            logger.error("Document processing failed", 
                        doc_id=doc_id, 
                        filename=filename, 
                        error=str(e))
            raise
    
    async def process_url(
        self,
        doc_id: str,
        url: str,
        tenant_id: UUID,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Process document from URL."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ValueError(f"Failed to fetch URL: {response.status}")
                    
                    content = await response.read()
                    filename = url.split('/')[-1] or 'webpage.html'
                    
                    return await self.process_document(
                        doc_id, filename, content, tenant_id, db
                    )
                    
        except Exception as e:
            logger.error("URL processing failed", doc_id=doc_id, url=url, error=str(e))
            raise
    
    async def get_documents(
        self,
        tenant_id: UUID,
        limit: int,
        offset: int,
        db: AsyncSession
    ) -> List[Dict[str, Any]]:
        """Get documents for tenant."""
        try:
            stmt = select("documents").where(
                "documents.tenant_id == tenant_id"
            ).order_by("documents.created_at.desc()).limit(limit).offset(offset)
            
            result = await db.execute(stmt)
            rows = result.fetchall()
            
            documents = []
            for row in rows:
                documents.append({
                    "id": row.id,
                    "filename": row.filename,
                    "content_type": row.content_type,
                    "size_bytes": row.size_bytes,
                    "status": row.status,
                    "created_at": row.created_at.isoformat(),
                    "metadata": row.metadata
                })
            
            return documents
            
        except Exception as e:
            logger.error("Failed to get documents", tenant_id=tenant_id, error=str(e))
            return []
    
    async def delete_document(
        self,
        doc_id: str,
        tenant_id: UUID,
        db: AsyncSession
    ):
        """Delete document."""
        try:
            stmt = delete("documents").where(
                "documents.id == doc_id",
                "documents.tenant_id == tenant_id"
            )
            await db.execute(stmt)
            await db.commit()
            
            logger.info("Document deleted", doc_id=doc_id, tenant_id=tenant_id)
            
        except Exception as e:
            logger.error("Failed to delete document", doc_id=doc_id, error=str(e))
            raise
    
    def _detect_content_type(self, filename: str, content: bytes) -> str:
        """Detect content type from filename and content."""
        # Try MIME type detection from filename
        content_type, _ = mimetypes.guess_type(filename)
        
        if content_type:
            return content_type
        
        # Fallback to content-based detection
        if content.startswith(b'%PDF'):
            return 'application/pdf'
        elif content.startswith(b'<!DOCTYPE html') or content.startswith(b'<html'):
            return 'text/html'
        elif content.startswith(b'{') or content.startswith(b'['):
            return 'application/json'
        else:
            return 'text/plain'
    
    async def _process_text(self, content: bytes) -> str:
        """Process plain text content."""
        return content.decode('utf-8', errors='ignore')
    
    async def _process_html(self, content: bytes) -> str:
        """Process HTML content."""
        # Simple HTML processing - in production, use BeautifulSoup
        text = content.decode('utf-8', errors='ignore')
        # Remove HTML tags (basic implementation)
        import re
        clean_text = re.sub(r'<[^>]+>', '', text)
        return clean_text
    
    async def _process_pdf(self, content: bytes) -> str:
        """Process PDF content."""
        # In production, use PyPDF2 or pdfplumber
        # For now, return placeholder
        return f"PDF content ({len(content)} bytes)"
    
    async def _process_json(self, content: bytes) -> str:
        """Process JSON content."""
        import json
        data = json.loads(content.decode('utf-8'))
        return json.dumps(data, indent=2)
    
    async def _process_markdown(self, content: bytes) -> str:
        """Process Markdown content."""
        return content.decode('utf-8', errors='ignore')
    
    async def _process_docx(self, content: bytes) -> str:
        """Process DOCX content."""
        # In production, use python-docx
        return f"DOCX content ({len(content)} bytes)"
    
    async def _extract_metadata(
        self, 
        filename: str, 
        content: bytes, 
        processed_content: str
    ) -> Dict[str, Any]:
        """Extract metadata from document."""
        return {
            "filename": filename,
            "size_bytes": len(content),
            "word_count": len(processed_content.split()),
            "line_count": len(processed_content.splitlines()),
            "language": "en",  # In production, use language detection
            "extracted_at": datetime.utcnow().isoformat()
        }
    
    async def _get_document_by_hash(
        self, 
        content_hash: str, 
        tenant_id: UUID, 
        db: AsyncSession
    ) -> Optional[Dict[str, Any]]:
        """Check if document exists by content hash."""
        try:
            stmt = select("documents").where(
                "documents.content_hash == content_hash",
                "documents.tenant_id == tenant_id"
            )
            result = await db.execute(stmt)
            row = result.first()
            
            if row:
                return {
                    "doc_id": row.id,
                    "filename": row.filename,
                    "content_type": row.content_type,
                    "status": row.status
                }
            
            return None
            
        except Exception as e:
            logger.error("Failed to check document hash", error=str(e))
            return None
    
    async def _store_document(self, doc_data: Dict[str, Any], db: AsyncSession):
        """Store document in database."""
        stmt = insert("documents").values(**doc_data)
        await db.execute(stmt)
        await db.commit()
    
    async def _publish_indexing_event(
        self, 
        doc_id: str, 
        tenant_id: UUID, 
        content: str, 
        metadata: Dict[str, Any]
    ):
        """Publish document indexing event."""
        # This would publish to NATS event bus
        # For now, just log
        logger.info("Indexing event published", 
                   doc_id=doc_id, 
                   tenant_id=tenant_id,
                   content_length=len(content))
