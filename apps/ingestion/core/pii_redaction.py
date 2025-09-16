"""
PII Redaction System

Implements PII detection and redaction at system boundaries with configurable
patterns, sensitivity tagging, and comprehensive logging.
"""

import re
import hashlib
from typing import Dict, List, Optional, Any, Set, Tuple, Pattern
from dataclasses import dataclass, field
from enum import Enum
import structlog
from datetime import datetime
import json

logger = structlog.get_logger(__name__)


class PIIType(Enum):
    """Types of PII that can be detected."""
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    NAME = "name"
    ADDRESS = "address"
    DATE_OF_BIRTH = "date_of_birth"
    IP_ADDRESS = "ip_address"
    MAC_ADDRESS = "mac_address"
    PASSPORT = "passport"
    DRIVER_LICENSE = "driver_license"
    BANK_ACCOUNT = "bank_account"
    API_KEY = "api_key"
    TOKEN = "token"
    PASSWORD = "password"


class RedactionMethod(Enum):
    """Methods for redacting PII."""
    MASK = "mask"  # Replace with asterisks
    HASH = "hash"  # Replace with hash
    REMOVE = "remove"  # Remove completely
    PLACEHOLDER = "placeholder"  # Replace with placeholder text


@dataclass
class PIIDetectionRule:
    """PII detection rule configuration."""
    
    pii_type: PIIType
    pattern: Pattern[str]
    confidence: float
    redaction_method: RedactionMethod
    placeholder: str = "[REDACTED]"
    case_sensitive: bool = False
    min_length: int = 1
    max_length: int = 1000


@dataclass
class PIIDetectionResult:
    """Result of PII detection."""
    
    pii_type: PIIType
    original_text: str
    redacted_text: str
    start_position: int
    end_position: int
    confidence: float
    redaction_method: RedactionMethod
    matched_pattern: str
    detection_time: datetime


@dataclass
class RedactionConfig:
    """Configuration for PII redaction."""
    
    enabled: bool = True
    rules: Dict[PIIType, PIIDetectionRule] = field(default_factory=dict)
    global_placeholder: str = "[REDACTED]"
    preserve_format: bool = True
    log_detections: bool = True
    hash_salt: str = "default_salt"


class PIIDetector:
    """PII detection engine with configurable rules."""
    
    def __init__(self, config: RedactionConfig):
        self.config = config
        self.detection_rules = self._initialize_detection_rules()
        
        logger.info("PII detector initialized", 
                   enabled=config.enabled,
                   rules_count=len(self.detection_rules))
    
    def _initialize_detection_rules(self) -> Dict[PIIType, PIIDetectionRule]:
        """Initialize default PII detection rules."""
        
        rules = {}
        
        # Email detection
        email_pattern = re.compile(
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            re.IGNORECASE
        )
        rules[PIIType.EMAIL] = PIIDetectionRule(
            pii_type=PIIType.EMAIL,
            pattern=email_pattern,
            confidence=0.95,
            redaction_method=RedactionMethod.MASK,
            placeholder="[EMAIL]"
        )
        
        # Phone number detection (US format)
        phone_pattern = re.compile(
            r'\b(?:\+?1[-.\s]?)?\(?([0-9]{3})\)?[-.\s]?([0-9]{3})[-.\s]?([0-9]{4})\b'
        )
        rules[PIIType.PHONE] = PIIDetectionRule(
            pii_type=PIIType.PHONE,
            pattern=phone_pattern,
            confidence=0.90,
            redaction_method=RedactionMethod.MASK,
            placeholder="[PHONE]"
        )
        
        # SSN detection (US format)
        ssn_pattern = re.compile(
            r'\b(?!000|666|9\d{2})\d{3}[-.]?(?!00)\d{2}[-.]?(?!0000)\d{4}\b'
        )
        rules[PIIType.SSN] = PIIDetectionRule(
            pii_type=PIIType.SSN,
            pattern=ssn_pattern,
            confidence=0.98,
            redaction_method=RedactionMethod.MASK,
            placeholder="[SSN]"
        )
        
        # Credit card detection
        cc_pattern = re.compile(
            r'\b(?:\d{4}[-\s]?){3}\d{4}\b'
        )
        rules[PIIType.CREDIT_CARD] = PIIDetectionRule(
            pii_type=PIIType.CREDIT_CARD,
            pattern=cc_pattern,
            confidence=0.85,
            redaction_method=RedactionMethod.MASK,
            placeholder="[CARD]"
        )
        
        # IP address detection
        ip_pattern = re.compile(
            r'\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b'
        )
        rules[PIIType.IP_ADDRESS] = PIIDetectionRule(
            pii_type=PIIType.IP_ADDRESS,
            pattern=ip_pattern,
            confidence=0.90,
            redaction_method=RedactionMethod.MASK,
            placeholder="[IP]"
        )
        
        # MAC address detection
        mac_pattern = re.compile(
            r'\b(?:[0-9A-Fa-f]{2}[:-]){5}(?:[0-9A-Fa-f]{2})\b'
        )
        rules[PIIType.MAC_ADDRESS] = PIIDetectionRule(
            pii_type=PIIType.MAC_ADDRESS,
            pattern=mac_pattern,
            confidence=0.95,
            redaction_method=RedactionMethod.MASK,
            placeholder="[MAC]"
        )
        
        # API key detection (common patterns)
        api_key_pattern = re.compile(
            r'\b(?:sk-|pk-|ak-|key-)[A-Za-z0-9]{20,}\b'
        )
        rules[PIIType.API_KEY] = PIIDetectionRule(
            pii_type=PIIType.API_KEY,
            pattern=api_key_pattern,
            confidence=0.95,
            redaction_method=RedactionMethod.MASK,
            placeholder="[API_KEY]"
        )
        
        # Token detection (JWT, session tokens, etc.)
        token_pattern = re.compile(
            r'\b[A-Za-z0-9+/]{40,}={0,2}\b'
        )
        rules[PIIType.TOKEN] = PIIDetectionRule(
            pii_type=PIIType.TOKEN,
            pattern=token_pattern,
            confidence=0.80,
            redaction_method=RedactionMethod.MASK,
            placeholder="[TOKEN]"
        )
        
        # Password detection (common patterns)
        password_pattern = re.compile(
            r'\b(?:password|pwd|pass)\s*[:=]\s*["\']?[^"\'\s]{6,}["\']?',
            re.IGNORECASE
        )
        rules[PIIType.PASSWORD] = PIIDetectionRule(
            pii_type=PIIType.PASSWORD,
            pattern=password_pattern,
            confidence=0.85,
            redaction_method=RedactionMethod.MASK,
            placeholder="[PASSWORD]"
        )
        
        # Date of birth detection
        dob_pattern = re.compile(
            r'\b(?:0?[1-9]|1[0-2])[-/](?:0?[1-9]|[12][0-9]|3[01])[-/](?:19|20)\d{2}\b'
        )
        rules[PIIType.DATE_OF_BIRTH] = PIIDetectionRule(
            pii_type=PIIType.DATE_OF_BIRTH,
            pattern=dob_pattern,
            confidence=0.70,
            redaction_method=RedactionMethod.MASK,
            placeholder="[DOB]"
        )
        
        # Apply custom rules from config
        for pii_type, rule in self.config.rules.items():
            rules[pii_type] = rule
        
        return rules
    
    def detect_pii(self, text: str) -> List[PIIDetectionResult]:
        """Detect PII in text."""
        
        if not self.config.enabled or not text:
            return []
        
        detections = []
        
        for pii_type, rule in self.detection_rules.items():
            matches = rule.pattern.finditer(text)
            
            for match in matches:
                original_text = match.group()
                start_pos = match.start()
                end_pos = match.end()
                
                # Apply length filters
                if len(original_text) < rule.min_length or len(original_text) > rule.max_length:
                    continue
                
                # Apply case sensitivity
                if rule.case_sensitive and original_text != original_text:
                    continue
                
                # Create detection result
                detection = PIIDetectionResult(
                    pii_type=pii_type,
                    original_text=original_text,
                    redacted_text=self._redact_text(original_text, rule),
                    start_position=start_pos,
                    end_position=end_pos,
                    confidence=rule.confidence,
                    redaction_method=rule.redaction_method,
                    matched_pattern=match.pattern if hasattr(match, 'pattern') else str(rule.pattern),
                    detection_time=datetime.now()
                )
                
                detections.append(detection)
        
        # Sort by position to maintain order
        detections.sort(key=lambda x: x.start_position)
        
        # Log detections if enabled
        if self.config.log_detections and detections:
            self._log_detections(detections)
        
        return detections
    
    def _redact_text(self, text: str, rule: PIIDetectionRule) -> str:
        """Redact text based on rule configuration."""
        
        if rule.redaction_method == RedactionMethod.MASK:
            if self.config.preserve_format:
                # Preserve format with asterisks
                return re.sub(r'[A-Za-z0-9]', '*', text)
            else:
                return rule.placeholder
        
        elif rule.redaction_method == RedactionMethod.HASH:
            # Create hash of the text
            hash_input = text + self.config.hash_salt
            hash_value = hashlib.sha256(hash_input.encode()).hexdigest()[:8]
            return f"[HASH:{hash_value}]"
        
        elif rule.redaction_method == RedactionMethod.REMOVE:
            return ""
        
        elif rule.redaction_method == RedactionMethod.PLACEHOLDER:
            return rule.placeholder
        
        else:
            return self.config.global_placeholder
    
    def _log_detections(self, detections: List[PIIDetectionResult]):
        """Log PII detections."""
        
        for detection in detections:
            logger.warning("PII detected", 
                          pii_type=detection.pii_type.value,
                          confidence=detection.confidence,
                          method=detection.redaction_method.value,
                          position=f"{detection.start_position}-{detection.end_position}")
    
    def redact_text(self, text: str) -> Tuple[str, List[PIIDetectionResult]]:
        """Redact PII from text and return redacted text with detection results."""
        
        if not self.config.enabled or not text:
            return text, []
        
        detections = self.detect_pii(text)
        
        if not detections:
            return text, []
        
        # Redact from end to beginning to maintain positions
        redacted_text = text
        
        for detection in reversed(detections):
            redacted_text = (
                redacted_text[:detection.start_position] + 
                detection.redacted_text + 
                redacted_text[detection.end_position:]
            )
        
        return redacted_text, detections
    
    def get_detection_summary(self, detections: List[PIIDetectionResult]) -> Dict[str, Any]:
        """Get summary of PII detections."""
        
        if not detections:
            return {"total_detections": 0}
        
        summary = {
            "total_detections": len(detections),
            "by_type": {},
            "by_confidence": {"high": 0, "medium": 0, "low": 0},
            "by_method": {},
            "detection_time": detections[0].detection_time.isoformat()
        }
        
        for detection in detections:
            # By type
            pii_type = detection.pii_type.value
            summary["by_type"][pii_type] = summary["by_type"].get(pii_type, 0) + 1
            
            # By confidence
            if detection.confidence >= 0.9:
                summary["by_confidence"]["high"] += 1
            elif detection.confidence >= 0.7:
                summary["by_confidence"]["medium"] += 1
            else:
                summary["by_confidence"]["low"] += 1
            
            # By method
            method = detection.redaction_method.value
            summary["by_method"][method] = summary["by_method"].get(method, 0) + 1
        
        return summary


class PIIRedactionMiddleware:
    """Middleware for PII redaction at system boundaries."""
    
    def __init__(self, config: RedactionConfig):
        self.config = config
        self.pii_detector = PIIDetector(config)
        self.redaction_stats = {
            "total_requests": 0,
            "requests_with_pii": 0,
            "total_detections": 0,
            "by_pii_type": {},
            "by_endpoint": {}
        }
        
        logger.info("PII redaction middleware initialized")
    
    async def redact_request_data(
        self, 
        data: Any, 
        endpoint: str = "unknown"
    ) -> Tuple[Any, List[PIIDetectionResult]]:
        """Redact PII from request data."""
        
        self.redaction_stats["total_requests"] += 1
        
        if isinstance(data, str):
            redacted_data, detections = self.pii_detector.redact_text(data)
        elif isinstance(data, dict):
            redacted_data, detections = await self._redact_dict(data)
        elif isinstance(data, list):
            redacted_data, detections = await self._redact_list(data)
        else:
            # For other types, convert to string and redact
            redacted_data, detections = self.pii_detector.redact_text(str(data))
        
        # Update statistics
        if detections:
            self.redaction_stats["requests_with_pii"] += 1
            self.redaction_stats["total_detections"] += len(detections)
            
            # By endpoint
            if endpoint not in self.redaction_stats["by_endpoint"]:
                self.redaction_stats["by_endpoint"][endpoint] = 0
            self.redaction_stats["by_endpoint"][endpoint] += len(detections)
            
            # By PII type
            for detection in detections:
                pii_type = detection.pii_type.value
                self.redaction_stats["by_pii_type"][pii_type] = (
                    self.redaction_stats["by_pii_type"].get(pii_type, 0) + 1
                )
        
        return redacted_data, detections
    
    async def _redact_dict(self, data: Dict[str, Any]) -> Tuple[Dict[str, Any], List[PIIDetectionResult]]:
        """Redact PII from dictionary data."""
        
        redacted_data = {}
        all_detections = []
        
        for key, value in data.items():
            if isinstance(value, str):
                redacted_value, detections = self.pii_detector.redact_text(value)
                redacted_data[key] = redacted_value
                all_detections.extend(detections)
            elif isinstance(value, dict):
                redacted_value, detections = await self._redact_dict(value)
                redacted_data[key] = redacted_value
                all_detections.extend(detections)
            elif isinstance(value, list):
                redacted_value, detections = await self._redact_list(value)
                redacted_data[key] = redacted_value
                all_detections.extend(detections)
            else:
                redacted_data[key] = value
        
        return redacted_data, all_detections
    
    async def _redact_list(self, data: List[Any]) -> Tuple[List[Any], List[PIIDetectionResult]]:
        """Redact PII from list data."""
        
        redacted_data = []
        all_detections = []
        
        for item in data:
            if isinstance(item, str):
                redacted_item, detections = self.pii_detector.redact_text(item)
                redacted_data.append(redacted_item)
                all_detections.extend(detections)
            elif isinstance(item, dict):
                redacted_item, detections = await self._redact_dict(item)
                redacted_data.append(redacted_item)
                all_detections.extend(detections)
            elif isinstance(item, list):
                redacted_item, detections = await self._redact_list(item)
                redacted_data.append(redacted_item)
                all_detections.extend(detections)
            else:
                redacted_data.append(item)
        
        return redacted_data, all_detections
    
    def get_redaction_stats(self) -> Dict[str, Any]:
        """Get redaction statistics."""
        
        stats = self.redaction_stats.copy()
        
        if stats["total_requests"] > 0:
            stats["pii_detection_rate"] = stats["requests_with_pii"] / stats["total_requests"]
        else:
            stats["pii_detection_rate"] = 0.0
        
        return stats
    
    def reset_stats(self):
        """Reset redaction statistics."""
        
        self.redaction_stats = {
            "total_requests": 0,
            "requests_with_pii": 0,
            "total_detections": 0,
            "by_pii_type": {},
            "by_endpoint": {}
        }
        
        logger.info("PII redaction statistics reset")


class SensitivityTagger:
    """Tags documents with sensitivity levels based on PII detection."""
    
    def __init__(self, pii_detector: PIIDetector):
        self.pii_detector = pii_detector
        
        # Sensitivity mapping based on PII types
        self.pii_sensitivity_map = {
            PIIType.EMAIL: 1,  # Low sensitivity
            PIIType.PHONE: 2,  # Medium sensitivity
            PIIType.NAME: 2,   # Medium sensitivity
            PIIType.ADDRESS: 3,  # High sensitivity
            PIIType.DATE_OF_BIRTH: 3,  # High sensitivity
            PIIType.SSN: 4,    # Very high sensitivity
            PIIType.CREDIT_CARD: 4,  # Very high sensitivity
            PIIType.API_KEY: 4,  # Very high sensitivity
            PIIType.PASSWORD: 4,  # Very high sensitivity
        }
        
        logger.info("Sensitivity tagger initialized")
    
    def tag_document_sensitivity(self, content: str) -> Tuple[SensitivityLevel, Dict[str, Any]]:
        """Tag document with sensitivity level based on PII detection."""
        
        detections = self.pii_detector.detect_pii(content)
        
        if not detections:
            return SensitivityLevel.PUBLIC, {"reason": "no_pii_detected"}
        
        # Calculate sensitivity score
        max_sensitivity_score = 0
        detected_types = set()
        
        for detection in detections:
            sensitivity_score = self.pii_sensitivity_map.get(
                detection.pii_type, 1
            )
            max_sensitivity_score = max(max_sensitivity_score, sensitivity_score)
            detected_types.add(detection.pii_type.value)
        
        # Map score to sensitivity level
        if max_sensitivity_score >= 4:
            sensitivity_level = SensitivityLevel.RESTRICTED
        elif max_sensitivity_score >= 3:
            sensitivity_level = SensitivityLevel.CONFIDENTIAL
        elif max_sensitivity_score >= 2:
            sensitivity_level = SensitivityLevel.INTERNAL
        else:
            sensitivity_level = SensitivityLevel.PUBLIC
        
        metadata = {
            "reason": "pii_detected",
            "max_sensitivity_score": max_sensitivity_score,
            "detected_pii_types": list(detected_types),
            "total_detections": len(detections),
            "confidence_scores": [d.confidence for d in detections]
        }
        
        logger.info("Document sensitivity tagged", 
                   sensitivity=sensitivity_level.value,
                   max_score=max_sensitivity_score,
                   detected_types=detected_types)
        
        return sensitivity_level, metadata
