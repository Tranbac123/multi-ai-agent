"""PII Detection Engine for identifying and classifying sensitive data."""

import re
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
import structlog
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)


class PIIType(Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    PHONE = "phone"
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    BANK_ACCOUNT = "bank_account"
    IP_ADDRESS = "ip_address"
    MAC_ADDRESS = "mac_address"
    PERSONAL_NAME = "personal_name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    NATIONAL_ID = "national_id"


class SensitivityLevel(Enum):
    """Sensitivity levels for detected PII."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class PIIDetection:
    """Represents a detected PII instance."""
    pii_type: PIIType
    value: str
    confidence: float
    sensitivity_level: SensitivityLevel
    start_position: int
    end_position: int
    context: str
    redaction_mask: str
    detected_at: datetime


@dataclass
class PIIDetectionResult:
    """Result of PII detection analysis."""
    text: str
    detections: List[PIIDetection]
    has_pii: bool
    sensitivity_score: float
    redacted_text: str
    redaction_count: int


class PIIDetector:
    """Advanced PII detection engine with multiple detection strategies."""
    
    def __init__(self):
        self.detection_patterns = self._initialize_detection_patterns()
        self.sensitivity_mapping = self._initialize_sensitivity_mapping()
        self.redaction_masks = self._initialize_redaction_masks()
    
    def _initialize_detection_patterns(self) -> Dict[PIIType, List[re.Pattern]]:
        """Initialize regex patterns for PII detection."""
        return {
            PIIType.EMAIL: [
                re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', re.IGNORECASE)
            ],
            PIIType.PHONE: [
                re.compile(r'(\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})'),
                re.compile(r'(\+?[1-9]\d{1,14})'),  # International format
            ],
            PIIType.CREDIT_CARD: [
                re.compile(r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|3[0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b'),
                re.compile(r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b'),
            ],
            PIIType.SSN: [
                re.compile(r'\b\d{3}-?\d{2}-?\d{4}\b'),
                re.compile(r'\b\d{9}\b'),
            ],
            PIIType.PASSPORT: [
                re.compile(r'\b[A-Z]{1,2}\d{6,9}\b'),
                re.compile(r'\b\d{9}\b'),
            ],
            PIIType.DRIVER_LICENSE: [
                re.compile(r'\b[A-Z]\d{7,8}\b'),
                re.compile(r'\b\d{8,9}\b'),
            ],
            PIIType.BANK_ACCOUNT: [
                re.compile(r'\b\d{8,17}\b'),  # Most bank accounts are 8-17 digits
            ],
            PIIType.IP_ADDRESS: [
                re.compile(r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'),
                re.compile(r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b'),  # IPv6
            ],
            PIIType.MAC_ADDRESS: [
                re.compile(r'\b(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}\b'),
            ],
            PIIType.DATE_OF_BIRTH: [
                re.compile(r'\b(?:0[1-9]|1[0-2])[-\/](?:0[1-9]|[12][0-9]|3[01])[-\/](?:19|20)\d{2}\b'),
                re.compile(r'\b(?:19|20)\d{2}[-\/](?:0[1-9]|1[0-2])[-\/](?:0[1-9]|[12][0-9]|3[01])\b'),
            ],
            PIIType.NATIONAL_ID: [
                re.compile(r'\b[A-Z]{2}\d{6,12}[A-Z0-9]?\b'),  # Various national ID formats
            ],
        }
    
    def _initialize_sensitivity_mapping(self) -> Dict[PIIType, SensitivityLevel]:
        """Initialize sensitivity level mapping for PII types."""
        return {
            PIIType.EMAIL: SensitivityLevel.MEDIUM,
            PIIType.PHONE: SensitivityLevel.MEDIUM,
            PIIType.CREDIT_CARD: SensitivityLevel.CRITICAL,
            PIIType.SSN: SensitivityLevel.CRITICAL,
            PIIType.PASSPORT: SensitivityLevel.CRITICAL,
            PIIType.DRIVER_LICENSE: SensitivityLevel.HIGH,
            PIIType.BANK_ACCOUNT: SensitivityLevel.CRITICAL,
            PIIType.IP_ADDRESS: SensitivityLevel.LOW,
            PIIType.MAC_ADDRESS: SensitivityLevel.LOW,
            PIIType.PERSONAL_NAME: SensitivityLevel.MEDIUM,
            PIIType.ADDRESS: SensitivityLevel.HIGH,
            PIIType.DATE_OF_BIRTH: SensitivityLevel.HIGH,
            PIIType.NATIONAL_ID: SensitivityLevel.CRITICAL,
        }
    
    def _initialize_redaction_masks(self) -> Dict[PIIType, str]:
        """Initialize redaction masks for different PII types."""
        return {
            PIIType.EMAIL: "***@***.***",
            PIIType.PHONE: "***-***-****",
            PIIType.CREDIT_CARD: "****-****-****-****",
            PIIType.SSN: "***-**-****",
            PIIType.PASSPORT: "********",
            PIIType.DRIVER_LICENSE: "********",
            PIIType.BANK_ACCOUNT: "****-****-****-****",
            PIIType.IP_ADDRESS: "***.***.***.***",
            PIIType.MAC_ADDRESS: "**:**:**:**:**:**",
            PIIType.PERSONAL_NAME: "****",
            PIIType.ADDRESS: "*** ********",
            PIIType.DATE_OF_BIRTH: "**/**/****",
            PIIType.NATIONAL_ID: "********",
        }
    
    def detect_pii(self, text: str, allowed_types: Optional[List[PIIType]] = None) -> PIIDetectionResult:
        """Detect PII in the given text."""
        try:
            detections = []
            redacted_text = text
            
            # Detect each type of PII
            for pii_type, patterns in self.detection_patterns.items():
                if allowed_types and pii_type not in allowed_types:
                    continue
                
                for pattern in patterns:
                    matches = pattern.finditer(text)
                    for match in matches:
                        detection = self._create_pii_detection(
                            pii_type, match.group(), match.start(), match.end(), text
                        )
                        detections.append(detection)
            
            # Sort detections by position (reverse order for redaction)
            detections.sort(key=lambda x: x.start_position, reverse=True)
            
            # Apply redactions
            for detection in detections:
                redacted_text = (
                    redacted_text[:detection.start_position] +
                    detection.redaction_mask +
                    redacted_text[detection.end_position:]
                )
            
            # Calculate sensitivity score
            sensitivity_score = self._calculate_sensitivity_score(detections)
            
            return PIIDetectionResult(
                text=text,
                detections=detections,
                has_pii=len(detections) > 0,
                sensitivity_score=sensitivity_score,
                redacted_text=redacted_text,
                redaction_count=len(detections)
            )
            
        except Exception as e:
            logger.error("Failed to detect PII", error=str(e))
            return PIIDetectionResult(
                text=text,
                detections=[],
                has_pii=False,
                sensitivity_score=0.0,
                redacted_text=text,
                redaction_count=0
            )
    
    def _create_pii_detection(self, pii_type: PIIType, value: str, 
                            start_pos: int, end_pos: int, context: str) -> PIIDetection:
        """Create a PII detection instance."""
        try:
            # Calculate confidence based on pattern match quality
            confidence = self._calculate_confidence(pii_type, value)
            
            # Get sensitivity level
            sensitivity_level = self.sensitivity_mapping.get(pii_type, SensitivityLevel.MEDIUM)
            
            # Get redaction mask
            redaction_mask = self.redaction_masks.get(pii_type, "****")
            
            # Get context around the detection
            context_start = max(0, start_pos - 20)
            context_end = min(len(context), end_pos + 20)
            context_snippet = context[context_start:context_end]
            
            return PIIDetection(
                pii_type=pii_type,
                value=value,
                confidence=confidence,
                sensitivity_level=sensitivity_level,
                start_position=start_pos,
                end_position=end_pos,
                context=context_snippet,
                redaction_mask=redaction_mask,
                detected_at=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            logger.error("Failed to create PII detection", error=str(e))
            # Return minimal detection
            return PIIDetection(
                pii_type=pii_type,
                value=value,
                confidence=0.5,
                sensitivity_level=SensitivityLevel.MEDIUM,
                start_position=start_pos,
                end_position=end_pos,
                context="",
                redaction_mask="****",
                detected_at=datetime.now(timezone.utc)
            )
    
    def _calculate_confidence(self, pii_type: PIIType, value: str) -> float:
        """Calculate confidence score for PII detection."""
        try:
            base_confidence = 0.8
            
            # Apply type-specific confidence adjustments
            if pii_type == PIIType.EMAIL:
                # Validate email format more strictly
                if '@' in value and '.' in value.split('@')[1]:
                    base_confidence = 0.95
                else:
                    base_confidence = 0.7
            
            elif pii_type == PIIType.PHONE:
                # Check for valid phone number patterns
                digits = re.sub(r'[^\d]', '', value)
                if len(digits) == 10 or len(digits) == 11:
                    base_confidence = 0.9
                else:
                    base_confidence = 0.6
            
            elif pii_type == PIIType.CREDIT_CARD:
                # Luhn algorithm validation
                if self._validate_credit_card(value):
                    base_confidence = 0.95
                else:
                    base_confidence = 0.7
            
            elif pii_type == PIIType.SSN:
                # SSN format validation
                digits = re.sub(r'[^\d]', '', value)
                if len(digits) == 9:
                    # Check for invalid SSN patterns
                    if not self._is_invalid_ssn(digits):
                        base_confidence = 0.9
                    else:
                        base_confidence = 0.3
                else:
                    base_confidence = 0.5
            
            return min(base_confidence, 1.0)
            
        except Exception as e:
            logger.error("Failed to calculate confidence", error=str(e))
            return 0.5
    
    def _validate_credit_card(self, card_number: str) -> bool:
        """Validate credit card number using Luhn algorithm."""
        try:
            # Remove non-digits
            digits = re.sub(r'[^\d]', '', card_number)
            
            if len(digits) < 13 or len(digits) > 19:
                return False
            
            # Luhn algorithm
            total = 0
            is_odd = False
            
            for digit in reversed(digits):
                digit = int(digit)
                if is_odd:
                    digit *= 2
                    if digit > 9:
                        digit -= 9
                total += digit
                is_odd = not is_odd
            
            return total % 10 == 0
            
        except Exception as e:
            logger.error("Failed to validate credit card", error=str(e))
            return False
    
    def _is_invalid_ssn(self, ssn: str) -> bool:
        """Check if SSN matches known invalid patterns."""
        try:
            # Invalid SSN patterns
            invalid_patterns = [
                "000000000",
                "111111111",
                "222222222",
                "333333333",
                "444444444",
                "555555555",
                "666666666",
                "777777777",
                "888888888",
                "999999999",
                "123456789",
                "000000001",
                "123456789",
            ]
            
            return ssn in invalid_patterns or ssn.startswith("000") or ssn.startswith("666")
            
        except Exception as e:
            logger.error("Failed to check invalid SSN", error=str(e))
            return False
    
    def _calculate_sensitivity_score(self, detections: List[PIIDetection]) -> float:
        """Calculate overall sensitivity score for the text."""
        try:
            if not detections:
                return 0.0
            
            # Weight by sensitivity level
            level_weights = {
                SensitivityLevel.LOW: 1.0,
                SensitivityLevel.MEDIUM: 2.0,
                SensitivityLevel.HIGH: 3.0,
                SensitivityLevel.CRITICAL: 4.0,
            }
            
            total_weight = 0.0
            weighted_sum = 0.0
            
            for detection in detections:
                weight = level_weights.get(detection.sensitivity_level, 1.0)
                weighted_sum += detection.confidence * weight
                total_weight += weight
            
            if total_weight == 0:
                return 0.0
            
            # Normalize to 0-1 scale
            return min(weighted_sum / total_weight, 1.0)
            
        except Exception as e:
            logger.error("Failed to calculate sensitivity score", error=str(e))
            return 0.0
    
    def get_pii_summary(self, detections: List[PIIDetection]) -> Dict[str, Any]:
        """Get summary of PII detections."""
        try:
            summary = {
                "total_detections": len(detections),
                "pii_types_found": list(set(detection.pii_type.value for detection in detections)),
                "sensitivity_levels": {},
                "confidence_stats": {
                    "min": 0.0,
                    "max": 0.0,
                    "avg": 0.0
                }
            }
            
            if not detections:
                return summary
            
            # Count by sensitivity level
            for level in SensitivityLevel:
                count = sum(1 for d in detections if d.sensitivity_level == level)
                summary["sensitivity_levels"][level.value] = count
            
            # Confidence statistics
            confidences = [d.confidence for d in detections]
            summary["confidence_stats"] = {
                "min": min(confidences),
                "max": max(confidences),
                "avg": sum(confidences) / len(confidences)
            }
            
            return summary
            
        except Exception as e:
            logger.error("Failed to get PII summary", error=str(e))
            return {"total_detections": 0, "pii_types_found": [], "sensitivity_levels": {}}
    
    def create_pii_hash(self, value: str, salt: str = "") -> str:
        """Create a hash of PII value for tracking without storing the actual value."""
        try:
            # Combine value with salt for additional security
            combined = f"{value}{salt}"
            
            # Use SHA-256 for hashing
            hash_obj = hashlib.sha256()
            hash_obj.update(combined.encode('utf-8'))
            
            return hash_obj.hexdigest()
            
        except Exception as e:
            logger.error("Failed to create PII hash", error=str(e))
            return ""
    
    def is_pii_allowed(self, pii_type: PIIType, tenant_id: str, 
                      allowlist: Dict[PIIType, List[str]]) -> bool:
        """Check if specific PII type is allowed for tenant."""
        try:
            # Check if PII type is in tenant's allowlist
            if pii_type in allowlist:
                return True
            
            # Default deny for sensitive PII types
            critical_types = {
                PIIType.CREDIT_CARD,
                PIIType.SSN,
                PIIType.BANK_ACCOUNT,
                PIIType.NATIONAL_ID
            }
            
            if pii_type in critical_types:
                return False
            
            # Allow other types by default
            return True
            
        except Exception as e:
            logger.error("Failed to check PII allowlist", error=str(e))
            return False
