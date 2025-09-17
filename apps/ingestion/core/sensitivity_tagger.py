"""Sensitivity Tagging System for document classification and protection."""

from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime, timezone
import hashlib

from libs.utils.security.pii_detector import PIIDetector, PIIDetectionResult, PIIType, SensitivityLevel

logger = structlog.get_logger(__name__)


class DocumentSensitivity(Enum):
    """Document sensitivity levels."""
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class DataCategory(Enum):
    """Data categories for classification."""
    PERSONAL_IDENTIFIABLE_INFO = "pii"
    FINANCIAL_DATA = "financial"
    HEALTHCARE_DATA = "healthcare"
    LEGAL_DATA = "legal"
    INTELLECTUAL_PROPERTY = "ip"
    BUSINESS_CONFIDENTIAL = "business_confidential"
    TECHNICAL_DATA = "technical"
    MARKETING_DATA = "marketing"


@dataclass
class SensitivityTag:
    """Sensitivity tag for a document or data field."""
    document_id: str
    sensitivity_level: DocumentSensitivity
    data_categories: List[DataCategory]
    pii_detected: bool
    pii_types: List[PIIType]
    confidence_score: float
    tagged_by: str  # system, user, or policy
    tagged_at: datetime
    expires_at: Optional[datetime] = None
    metadata: Dict[str, Any] = None


@dataclass
class SensitivityPolicy:
    """Sensitivity classification policy."""
    policy_id: str
    name: str
    description: str
    rules: List[Dict[str, Any]]
    sensitivity_level: DocumentSensitivity
    data_categories: List[DataCategory]
    auto_tag: bool = True
    requires_approval: bool = False
    created_by: str = "system"
    created_at: datetime = None


class SensitivityTagger:
    """Automated sensitivity tagging system for documents and data."""
    
    def __init__(self):
        self.pii_detector = PIIDetector()
        self.sensitivity_policies: Dict[str, SensitivityPolicy] = {}
        self.document_tags: Dict[str, SensitivityTag] = {}
        self._initialize_default_policies()
    
    def _initialize_default_policies(self):
        """Initialize default sensitivity policies."""
        try:
            # PII Policy
            pii_policy = SensitivityPolicy(
                policy_id="pii_detection",
                name="PII Detection Policy",
                description="Automatically tag documents containing PII",
                rules=[
                    {
                        "condition": "pii_detected",
                        "operator": "equals",
                        "value": True,
                        "sensitivity_level": DocumentSensitivity.CONFIDENTIAL
                    }
                ],
                sensitivity_level=DocumentSensitivity.CONFIDENTIAL,
                data_categories=[DataCategory.PERSONAL_IDENTIFIABLE_INFO],
                auto_tag=True,
                requires_approval=False,
                created_by="system",
                created_at=datetime.now(timezone.utc)
            )
            self.sensitivity_policies["pii_detection"] = pii_policy
            
            # Financial Data Policy
            financial_policy = SensitivityPolicy(
                policy_id="financial_data",
                name="Financial Data Policy",
                description="Tag documents containing financial information",
                rules=[
                    {
                        "condition": "contains_financial_data",
                        "operator": "equals",
                        "value": True,
                        "sensitivity_level": DocumentSensitivity.RESTRICTED
                    }
                ],
                sensitivity_level=DocumentSensitivity.RESTRICTED,
                data_categories=[DataCategory.FINANCIAL_DATA],
                auto_tag=True,
                requires_approval=True,
                created_by="system",
                created_at=datetime.now(timezone.utc)
            )
            self.sensitivity_policies["financial_data"] = financial_policy
            
            # Healthcare Data Policy
            healthcare_policy = SensitivityPolicy(
                policy_id="healthcare_data",
                name="Healthcare Data Policy",
                description="Tag documents containing healthcare information",
                rules=[
                    {
                        "condition": "contains_healthcare_data",
                        "operator": "equals",
                        "value": True,
                        "sensitivity_level": DocumentSensitivity.RESTRICTED
                    }
                ],
                sensitivity_level=DocumentSensitivity.RESTRICTED,
                data_categories=[DataCategory.HEALTHCARE_DATA],
                auto_tag=True,
                requires_approval=True,
                created_by="system",
                created_at=datetime.now(timezone.utc)
            )
            self.sensitivity_policies["healthcare_data"] = healthcare_policy
            
            logger.info("Default sensitivity policies initialized",
                       policy_count=len(self.sensitivity_policies))
            
        except Exception as e:
            logger.error("Failed to initialize default policies", error=str(e))
    
    async def tag_document(self, document_id: str, content: str, 
                          tenant_id: str, user_id: str = "system") -> SensitivityTag:
        """Tag document with sensitivity classification."""
        try:
            logger.info("Tagging document for sensitivity",
                       document_id=document_id,
                       tenant_id=tenant_id)
            
            # Detect PII in content
            pii_result = self.pii_detector.detect_pii(content)
            
            # Analyze content for other sensitive data
            content_analysis = await self._analyze_content(content)
            
            # Determine sensitivity level
            sensitivity_level = self._determine_sensitivity_level(
                pii_result, content_analysis
            )
            
            # Determine data categories
            data_categories = self._determine_data_categories(
                pii_result, content_analysis
            )
            
            # Calculate confidence score
            confidence_score = self._calculate_confidence_score(
                pii_result, content_analysis
            )
            
            # Create sensitivity tag
            sensitivity_tag = SensitivityTag(
                document_id=document_id,
                sensitivity_level=sensitivity_level,
                data_categories=data_categories,
                pii_detected=pii_result.has_pii,
                pii_types=[detection.pii_type for detection in pii_result.detections],
                confidence_score=confidence_score,
                tagged_by=user_id,
                tagged_at=datetime.now(timezone.utc),
                metadata={
                    "tenant_id": tenant_id,
                    "content_length": len(content),
                    "pii_count": pii_result.redaction_count,
                    "sensitivity_score": pii_result.sensitivity_score,
                    "content_hash": self._hash_content(content)
                }
            )
            
            # Store tag
            self.document_tags[document_id] = sensitivity_tag
            
            logger.info("Document tagged successfully",
                       document_id=document_id,
                       sensitivity_level=sensitivity_level.value,
                       data_categories=[cat.value for cat in data_categories],
                       pii_detected=pii_result.has_pii,
                       confidence_score=confidence_score)
            
            return sensitivity_tag
            
        except Exception as e:
            logger.error("Failed to tag document",
                        document_id=document_id,
                        tenant_id=tenant_id,
                        error=str(e))
            # Return default tag on error
            return SensitivityTag(
                document_id=document_id,
                sensitivity_level=DocumentSensitivity.INTERNAL,
                data_categories=[],
                pii_detected=False,
                pii_types=[],
                confidence_score=0.5,
                tagged_by="system",
                tagged_at=datetime.now(timezone.utc),
                metadata={"error": str(e)}
            )
    
    async def _analyze_content(self, content: str) -> Dict[str, Any]:
        """Analyze content for sensitive information beyond PII."""
        try:
            analysis = {
                "contains_financial_data": False,
                "contains_healthcare_data": False,
                "contains_legal_data": False,
                "contains_business_confidential": False,
                "contains_technical_data": False,
                "contains_marketing_data": False,
                "financial_indicators": [],
                "healthcare_indicators": [],
                "legal_indicators": [],
                "business_indicators": [],
                "technical_indicators": [],
                "marketing_indicators": []
            }
            
            content_lower = content.lower()
            
            # Financial data indicators
            financial_keywords = [
                "bank account", "credit card", "payment", "invoice", "receipt",
                "financial statement", "balance sheet", "profit", "loss",
                "revenue", "expense", "budget", "salary", "wage", "bonus",
                "tax", "irs", "ssn", "social security", "account number"
            ]
            
            for keyword in financial_keywords:
                if keyword in content_lower:
                    analysis["contains_financial_data"] = True
                    analysis["financial_indicators"].append(keyword)
            
            # Healthcare data indicators
            healthcare_keywords = [
                "medical record", "patient", "diagnosis", "treatment", "prescription",
                "medication", "doctor", "physician", "hospital", "clinic",
                "health insurance", "medical history", "symptoms", "allergy",
                "hipaa", "phi", "protected health information"
            ]
            
            for keyword in healthcare_keywords:
                if keyword in content_lower:
                    analysis["contains_healthcare_data"] = True
                    analysis["healthcare_indicators"].append(keyword)
            
            # Legal data indicators
            legal_keywords = [
                "confidential", "privileged", "attorney-client", "legal advice",
                "court", "lawsuit", "litigation", "contract", "agreement",
                "nda", "non-disclosure", "proprietary", "trade secret"
            ]
            
            for keyword in legal_keywords:
                if keyword in content_lower:
                    analysis["contains_legal_data"] = True
                    analysis["legal_indicators"].append(keyword)
            
            # Business confidential indicators
            business_keywords = [
                "confidential", "proprietary", "trade secret", "internal use",
                "company strategy", "business plan", "customer list",
                "pricing", "cost", "margin", "revenue", "competitor"
            ]
            
            for keyword in business_keywords:
                if keyword in content_lower:
                    analysis["contains_business_confidential"] = True
                    analysis["business_indicators"].append(keyword)
            
            # Technical data indicators
            technical_keywords = [
                "source code", "api key", "password", "secret", "token",
                "database", "server", "endpoint", "configuration",
                "algorithm", "encryption", "security", "vulnerability"
            ]
            
            for keyword in technical_keywords:
                if keyword in content_lower:
                    analysis["contains_technical_data"] = True
                    analysis["technical_indicators"].append(keyword)
            
            # Marketing data indicators
            marketing_keywords = [
                "marketing", "campaign", "promotion", "advertisement",
                "customer", "lead", "prospect", "demographic",
                "survey", "feedback", "review", "rating"
            ]
            
            for keyword in marketing_keywords:
                if keyword in content_lower:
                    analysis["contains_marketing_data"] = True
                    analysis["marketing_indicators"].append(keyword)
            
            return analysis
            
        except Exception as e:
            logger.error("Failed to analyze content", error=str(e))
            return {
                "contains_financial_data": False,
                "contains_healthcare_data": False,
                "contains_legal_data": False,
                "contains_business_confidential": False,
                "contains_technical_data": False,
                "contains_marketing_data": False,
                "financial_indicators": [],
                "healthcare_indicators": [],
                "legal_indicators": [],
                "business_indicators": [],
                "technical_indicators": [],
                "marketing_indicators": []
            }
    
    def _determine_sensitivity_level(self, pii_result: PIIDetectionResult, 
                                   content_analysis: Dict[str, Any]) -> DocumentSensitivity:
        """Determine document sensitivity level based on analysis."""
        try:
            # Start with base sensitivity
            sensitivity_level = DocumentSensitivity.PUBLIC
            
            # Upgrade based on PII detection
            if pii_result.has_pii:
                if pii_result.sensitivity_score >= 0.8:
                    sensitivity_level = DocumentSensitivity.RESTRICTED
                elif pii_result.sensitivity_score >= 0.6:
                    sensitivity_level = DocumentSensitivity.CONFIDENTIAL
                elif pii_result.sensitivity_score >= 0.4:
                    sensitivity_level = DocumentSensitivity.INTERNAL
            
            # Upgrade based on content analysis
            if content_analysis["contains_healthcare_data"]:
                sensitivity_level = max(sensitivity_level, DocumentSensitivity.RESTRICTED)
            
            if content_analysis["contains_financial_data"]:
                sensitivity_level = max(sensitivity_level, DocumentSensitivity.CONFIDENTIAL)
            
            if content_analysis["contains_legal_data"]:
                sensitivity_level = max(sensitivity_level, DocumentSensitivity.RESTRICTED)
            
            if content_analysis["contains_business_confidential"]:
                sensitivity_level = max(sensitivity_level, DocumentSensitivity.CONFIDENTIAL)
            
            if content_analysis["contains_technical_data"]:
                sensitivity_level = max(sensitivity_level, DocumentSensitivity.INTERNAL)
            
            return sensitivity_level
            
        except Exception as e:
            logger.error("Failed to determine sensitivity level", error=str(e))
            return DocumentSensitivity.INTERNAL
    
    def _determine_data_categories(self, pii_result: PIIDetectionResult, 
                                 content_analysis: Dict[str, Any]) -> List[DataCategory]:
        """Determine data categories based on analysis."""
        try:
            categories = []
            
            # Add categories based on PII detection
            if pii_result.has_pii:
                categories.append(DataCategory.PERSONAL_IDENTIFIABLE_INFO)
            
            # Add categories based on content analysis
            if content_analysis["contains_financial_data"]:
                categories.append(DataCategory.FINANCIAL_DATA)
            
            if content_analysis["contains_healthcare_data"]:
                categories.append(DataCategory.HEALTHCARE_DATA)
            
            if content_analysis["contains_legal_data"]:
                categories.append(DataCategory.LEGAL_DATA)
            
            if content_analysis["contains_business_confidential"]:
                categories.append(DataCategory.BUSINESS_CONFIDENTIAL)
            
            if content_analysis["contains_technical_data"]:
                categories.append(DataCategory.TECHNICAL_DATA)
            
            if content_analysis["contains_marketing_data"]:
                categories.append(DataCategory.MARKETING_DATA)
            
            return categories
            
        except Exception as e:
            logger.error("Failed to determine data categories", error=str(e))
            return []
    
    def _calculate_confidence_score(self, pii_result: PIIDetectionResult, 
                                  content_analysis: Dict[str, Any]) -> float:
        """Calculate confidence score for sensitivity classification."""
        try:
            # Start with PII confidence
            base_confidence = pii_result.sensitivity_score if pii_result.has_pii else 0.5
            
            # Adjust based on content analysis
            content_indicators = 0
            total_indicators = 6  # Number of content analysis categories
            
            for key, value in content_analysis.items():
                if key.startswith("contains_") and value:
                    content_indicators += 1
            
            content_confidence = content_indicators / total_indicators
            
            # Combine confidences
            final_confidence = (base_confidence + content_confidence) / 2
            
            return min(max(final_confidence, 0.0), 1.0)
            
        except Exception as e:
            logger.error("Failed to calculate confidence score", error=str(e))
            return 0.5
    
    def _hash_content(self, content: str) -> str:
        """Create hash of content for tracking."""
        try:
            return hashlib.sha256(content.encode('utf-8')).hexdigest()
        except Exception as e:
            logger.error("Failed to hash content", error=str(e))
            return ""
    
    async def get_document_tag(self, document_id: str) -> Optional[SensitivityTag]:
        """Get sensitivity tag for document."""
        try:
            return self.document_tags.get(document_id)
        except Exception as e:
            logger.error("Failed to get document tag", document_id=document_id, error=str(e))
            return None
    
    async def update_sensitivity_policy(self, policy: SensitivityPolicy):
        """Update sensitivity classification policy."""
        try:
            self.sensitivity_policies[policy.policy_id] = policy
            
            logger.info("Sensitivity policy updated",
                       policy_id=policy.policy_id,
                       name=policy.name)
            
        except Exception as e:
            logger.error("Failed to update sensitivity policy",
                        policy_id=policy.policy_id,
                        error=str(e))
    
    async def get_sensitivity_summary(self, tenant_id: str) -> Dict[str, Any]:
        """Get sensitivity classification summary for tenant."""
        try:
            tenant_tags = self._get_tenant_tags(tenant_id)
            
            summary = self._create_base_summary(tenant_id, tenant_tags)
            
            if not tenant_tags:
                return summary
            
            # Calculate distribution statistics
            summary["sensitivity_distribution"] = self._calculate_sensitivity_distribution(tenant_tags)
            summary["data_categories"] = self._calculate_data_categories(tenant_tags)
            summary["pii_detection_stats"] = self._calculate_pii_stats(tenant_tags)
            
            return summary
            
        except Exception as e:
            logger.error("Failed to get sensitivity summary", tenant_id=tenant_id, error=str(e))
            return {"tenant_id": tenant_id, "error": str(e)}
    
    def _get_tenant_tags(self, tenant_id: str) -> List:
        """Get all tags for a specific tenant."""
        return [
            tag for tag in self.document_tags.values()
            if tag.metadata.get("tenant_id") == tenant_id
        ]
    
    def _create_base_summary(self, tenant_id: str, tenant_tags: List) -> Dict[str, Any]:
        """Create base summary structure."""
        return {
            "tenant_id": tenant_id,
            "total_documents": len(tenant_tags),
            "sensitivity_distribution": {},
            "data_categories": {},
            "pii_detection_stats": {
                "documents_with_pii": 0,
                "pii_types_found": set(),
                "average_confidence": 0.0
            }
        }
    
    def _calculate_sensitivity_distribution(self, tenant_tags: List) -> Dict[str, int]:
        """Calculate distribution by sensitivity level."""
        distribution = {}
        for level in DocumentSensitivity:
            count = sum(1 for tag in tenant_tags if tag.sensitivity_level == level)
            distribution[level.value] = count
        return distribution
    
    def _calculate_data_categories(self, tenant_tags: List) -> Dict[str, int]:
        """Calculate distribution by data category."""
        categories = {}
        for category in DataCategory:
            count = sum(1 for tag in tenant_tags if category in tag.data_categories)
            categories[category.value] = count
        return categories
    
    def _calculate_pii_stats(self, tenant_tags: List) -> Dict[str, Any]:
        """Calculate PII detection statistics."""
        pii_tags = [tag for tag in tenant_tags if tag.pii_detected]
        
        stats = {
            "documents_with_pii": len(pii_tags),
            "pii_types_found": [],
            "average_confidence": 0.0
        }
        
        if pii_tags:
            all_pii_types = set()
            for tag in pii_tags:
                all_pii_types.update(tag.pii_types)
            stats["pii_types_found"] = [t.value for t in all_pii_types]
            
            avg_confidence = sum(tag.confidence_score for tag in pii_tags) / len(pii_tags)
            stats["average_confidence"] = avg_confidence
        
        return stats
    
    async def bulk_tag_documents(self, documents: List[Dict[str, Any]], 
                               tenant_id: str, user_id: str = "system") -> List[SensitivityTag]:
        """Bulk tag multiple documents."""
        try:
            tags = []
            
            for doc in documents:
                document_id = doc.get("document_id")
                content = doc.get("content", "")
                
                if document_id and content:
                    tag = await self.tag_document(document_id, content, tenant_id, user_id)
                    tags.append(tag)
            
            logger.info("Bulk document tagging completed",
                       tenant_id=tenant_id,
                       documents_processed=len(tags))
            
            return tags
            
        except Exception as e:
            logger.error("Failed to bulk tag documents", tenant_id=tenant_id, error=str(e))
            return []
    
    async def validate_sensitivity_access(self, document_id: str, user_id: str, 
                                        tenant_id: str) -> bool:
        """Validate if user can access document based on sensitivity level."""
        try:
            tag = await self.get_document_tag(document_id)
            if not tag:
                # No tag found, allow access by default
                return True
            
            # Check tenant isolation
            if tag.metadata.get("tenant_id") != tenant_id:
                return False
            
            # For now, implement basic access control
            # In production, this would integrate with RBAC system
            
            if tag.sensitivity_level == DocumentSensitivity.PUBLIC:
                return True
            elif tag.sensitivity_level == DocumentSensitivity.INTERNAL:
                return True  # Allow internal users
            elif tag.sensitivity_level == DocumentSensitivity.CONFIDENTIAL:
                return True  # Allow with proper authorization
            elif tag.sensitivity_level == DocumentSensitivity.RESTRICTED:
                return False  # Require special authorization
            elif tag.sensitivity_level == DocumentSensitivity.TOP_SECRET:
                return False  # Deny access
            
            return False
            
        except Exception as e:
            logger.error("Failed to validate sensitivity access",
                        document_id=document_id,
                        user_id=user_id,
                        error=str(e))
            return False
