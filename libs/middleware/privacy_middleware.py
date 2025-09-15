"""Privacy Middleware for PII detection and redaction in API responses."""

from typing import Dict, List, Optional, Any
import structlog
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import json

from libs.utils.security.pii_detector import PIIDetector, PIIType, SensitivityLevel
from libs.utils.security.field_encryption import FieldEncryptionManager
from apps.ingestion.core.sensitivity_tagger import SensitivityTagger, DocumentSensitivity

logger = structlog.get_logger(__name__)


class PrivacyMiddleware:
    """Middleware for privacy protection and PII handling."""
    
    def __init__(self, pii_detector: PIIDetector, 
                 field_encryption: FieldEncryptionManager,
                 sensitivity_tagger: SensitivityTagger):
        self.pii_detector = pii_detector
        self.field_encryption = field_encryption
        self.sensitivity_tagger = sensitivity_tagger
        self.redaction_stats = {
            "total_requests": 0,
            "pii_detected": 0,
            "pii_redacted": 0,
            "encryption_applied": 0
        }
    
    async def __call__(self, request: Request, call_next) -> Response:
        """Process request with privacy protection."""
        try:
            # Extract tenant and user information
            tenant_id = await self._extract_tenant_id(request)
            user_id = await self._extract_user_id(request)
            
            # Process the request
            response = await call_next(request)
            
            # Apply privacy protection to response
            protected_response = await self._apply_privacy_protection(
                response, tenant_id, user_id, request
            )
            
            # Update statistics
            self._update_stats(protected_response)
            
            return protected_response
            
        except Exception as e:
            logger.error("Privacy middleware error", error=str(e))
            # Return original response on error
            return await call_next(request)
    
    async def _extract_tenant_id(self, request: Request) -> Optional[str]:
        """Extract tenant ID from request."""
        try:
            # Try to get from headers
            tenant_id = request.headers.get("X-Tenant-ID")
            if tenant_id:
                return tenant_id
            
            # Try to get from JWT token
            # This would integrate with your auth system
            return None
            
        except Exception as e:
            logger.error("Failed to extract tenant ID", error=str(e))
            return None
    
    async def _extract_user_id(self, request: Request) -> Optional[str]:
        """Extract user ID from request."""
        try:
            # Try to get from headers
            user_id = request.headers.get("X-User-ID")
            if user_id:
                return user_id
            
            # Try to get from JWT token
            # This would integrate with your auth system
            return None
            
        except Exception as e:
            logger.error("Failed to extract user ID", error=str(e))
            return None
    
    async def _apply_privacy_protection(self, response: Response, 
                                      tenant_id: Optional[str], 
                                      user_id: Optional[str],
                                      request: Request) -> Response:
        """Apply privacy protection to response."""
        try:
            # Only process JSON responses
            if not self._is_json_response(response):
                return response
            
            # Get response content
            response_body = await self._get_response_body(response)
            if not response_body:
                return response
            
            # Parse JSON content
            try:
                content = json.loads(response_body)
            except json.JSONDecodeError:
                return response
            
            # Apply privacy protection
            protected_content = await self._protect_content(
                content, tenant_id, user_id, request
            )
            
            # Create new response with protected content
            protected_body = json.dumps(protected_content, ensure_ascii=False)
            
            # Create new response
            protected_response = JSONResponse(
                content=json.loads(protected_body),
                status_code=response.status_code,
                headers=dict(response.headers)
            )
            
            # Add privacy headers
            protected_response.headers["X-Privacy-Protected"] = "true"
            protected_response.headers["X-PII-Redacted"] = str(
                protected_content.get("_privacy_metadata", {}).get("pii_redacted", False)
            )
            
            return protected_response
            
        except Exception as e:
            logger.error("Failed to apply privacy protection", error=str(e))
            return response
    
    def _is_json_response(self, response: Response) -> bool:
        """Check if response is JSON."""
        content_type = response.headers.get("content-type", "").lower()
        return "application/json" in content_type
    
    async def _get_response_body(self, response: Response) -> Optional[str]:
        """Get response body as string."""
        try:
            if hasattr(response, 'body'):
                return response.body.decode('utf-8')
            elif hasattr(response, '_content'):
                return response._content.decode('utf-8')
            else:
                return None
        except Exception as e:
            logger.error("Failed to get response body", error=str(e))
            return None
    
    async def _protect_content(self, content: Any, tenant_id: Optional[str], 
                             user_id: Optional[str], request: Request) -> Any:
        """Recursively protect content for privacy."""
        try:
            if isinstance(content, dict):
                return await self._protect_dict(content, tenant_id, user_id, request)
            elif isinstance(content, list):
                return await self._protect_list(content, tenant_id, user_id, request)
            elif isinstance(content, str):
                return await self._protect_string(content, tenant_id, user_id, request)
            else:
                return content
                
        except Exception as e:
            logger.error("Failed to protect content", error=str(e))
            return content
    
    async def _protect_dict(self, content: Dict[str, Any], tenant_id: Optional[str], 
                          user_id: Optional[str], request: Request) -> Dict[str, Any]:
        """Protect dictionary content."""
        try:
            protected_dict = {}
            privacy_metadata = {
                "pii_detected": False,
                "pii_redacted": False,
                "encryption_applied": False,
                "sensitivity_level": DocumentSensitivity.PUBLIC.value
            }
            
            for key, value in content.items():
                # Skip privacy metadata
                if key.startswith("_privacy_"):
                    continue
                
                # Check if field should be encrypted
                if self._should_encrypt_field(key, value):
                    encrypted_value = await self._encrypt_field_value(
                        value, tenant_id, key
                    )
                    protected_dict[key] = encrypted_value
                    privacy_metadata["encryption_applied"] = True
                else:
                    # Apply PII detection and redaction
                    protected_value = await self._protect_content(
                        value, tenant_id, user_id, request
                    )
                    protected_dict[key] = protected_value
            
            # Add privacy metadata
            protected_dict["_privacy_metadata"] = privacy_metadata
            
            return protected_dict
            
        except Exception as e:
            logger.error("Failed to protect dictionary", error=str(e))
            return content
    
    async def _protect_list(self, content: List[Any], tenant_id: Optional[str], 
                          user_id: Optional[str], request: Request) -> List[Any]:
        """Protect list content."""
        try:
            protected_list = []
            
            for item in content:
                protected_item = await self._protect_content(
                    item, tenant_id, user_id, request
                )
                protected_list.append(protected_item)
            
            return protected_list
            
        except Exception as e:
            logger.error("Failed to protect list", error=str(e))
            return content
    
    async def _protect_string(self, content: str, tenant_id: Optional[str], 
                            user_id: Optional[str], request: Request) -> Any:
        """Protect string content with PII detection."""
        try:
            # Detect PII in string
            pii_result = self.pii_detector.detect_pii(content)
            
            if pii_result.has_pii:
                # Check if PII is allowed for this tenant
                allowed_types = await self._get_allowed_pii_types(tenant_id)
                
                # Filter out non-allowed PII types
                filtered_detections = [
                    detection for detection in pii_result.detections
                    if detection.pii_type in allowed_types
                ]
                
                if filtered_detections:
                    # Apply redaction
                    redacted_content = self._apply_redaction(content, filtered_detections)
                    
                    # Log PII detection
                    logger.warning("PII detected and redacted in response",
                                 tenant_id=tenant_id,
                                 user_id=user_id,
                                 pii_types=[d.pii_type.value for d in filtered_detections],
                                 sensitivity_level=max(d.sensitivity_level.value for d in filtered_detections))
                    
                    return redacted_content
            
            return content
            
        except Exception as e:
            logger.error("Failed to protect string", error=str(e))
            return content
    
    def _should_encrypt_field(self, field_name: str, value: Any) -> bool:
        """Check if field should be encrypted."""
        try:
            # Define fields that should be encrypted
            sensitive_fields = [
                "password", "secret", "token", "key", "credential",
                "ssn", "social_security", "credit_card", "bank_account",
                "private_key", "api_key", "access_token"
            ]
            
            field_name_lower = field_name.lower()
            
            for sensitive_field in sensitive_fields:
                if sensitive_field in field_name_lower:
                    return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to check encryption requirement", error=str(e))
            return False
    
    async def _encrypt_field_value(self, value: Any, tenant_id: Optional[str], 
                                 field_name: str) -> Dict[str, Any]:
        """Encrypt field value."""
        try:
            if not tenant_id:
                # Return masked value if no tenant context
                return {"encrypted": True, "value": "***"}
            
            encrypted_field = await self.field_encryption.encrypt_field(
                value, tenant_id, field_name
            )
            
            return {
                "encrypted": True,
                "key_id": encrypted_field.key_id,
                "algorithm": encrypted_field.algorithm.value,
                "created_at": encrypted_field.created_at.isoformat(),
                "value": encrypted_field.encrypted_data
            }
            
        except Exception as e:
            logger.error("Failed to encrypt field value", error=str(e))
            return {"encrypted": True, "value": "***"}
    
    def _apply_redaction(self, content: str, detections: List) -> str:
        """Apply PII redaction to content."""
        try:
            redacted_content = content
            
            # Sort detections by position (reverse order for redaction)
            sorted_detections = sorted(detections, key=lambda x: x.start_position, reverse=True)
            
            for detection in sorted_detections:
                redacted_content = (
                    redacted_content[:detection.start_position] +
                    detection.redaction_mask +
                    redacted_content[detection.end_position:]
                )
            
            return redacted_content
            
        except Exception as e:
            logger.error("Failed to apply redaction", error=str(e))
            return content
    
    async def _get_allowed_pii_types(self, tenant_id: Optional[str]) -> List[PIIType]:
        """Get allowed PII types for tenant."""
        try:
            if not tenant_id:
                # Default allowlist for no tenant context
                return [PIIType.EMAIL, PIIType.PHONE]
            
            # In production, this would check tenant's privacy policy
            # For now, return a default allowlist
            return [
                PIIType.EMAIL,
                PIIType.PHONE,
                PIIType.IP_ADDRESS,
                PIIType.MAC_ADDRESS
            ]
            
        except Exception as e:
            logger.error("Failed to get allowed PII types", error=str(e))
            return []
    
    def _update_stats(self, response: Response):
        """Update privacy protection statistics."""
        try:
            self.redaction_stats["total_requests"] += 1
            
            # Check if PII was redacted
            pii_redacted = response.headers.get("X-PII-Redacted", "false")
            if pii_redacted.lower() == "true":
                self.redaction_stats["pii_redacted"] += 1
            
            # Check if encryption was applied
            privacy_protected = response.headers.get("X-Privacy-Protected", "false")
            if privacy_protected.lower() == "true":
                self.redaction_stats["encryption_applied"] += 1
            
        except Exception as e:
            logger.error("Failed to update stats", error=str(e))
    
    def get_privacy_stats(self) -> Dict[str, Any]:
        """Get privacy protection statistics."""
        try:
            total = self.redaction_stats["total_requests"]
            
            stats = {
                "total_requests": total,
                "pii_redacted": self.redaction_stats["pii_redacted"],
                "encryption_applied": self.redaction_stats["encryption_applied"],
                "pii_redaction_rate": (
                    self.redaction_stats["pii_redacted"] / total * 100
                ) if total > 0 else 0,
                "encryption_rate": (
                    self.redaction_stats["encryption_applied"] / total * 100
                ) if total > 0 else 0
            }
            
            return stats
            
        except Exception as e:
            logger.error("Failed to get privacy stats", error=str(e))
            return {}


class PrivacyValidator:
    """Validator for privacy policy compliance."""
    
    def __init__(self, pii_detector: PIIDetector, sensitivity_tagger: SensitivityTagger):
        self.pii_detector = pii_detector
        self.sensitivity_tagger = sensitivity_tagger
    
    async def validate_request_privacy(self, request: Request, tenant_id: str) -> Dict[str, Any]:
        """Validate request for privacy policy compliance."""
        try:
            # Get request content
            request_body = await request.body()
            
            if not request_body:
                return {"compliant": True, "violations": []}
            
            # Parse request content
            try:
                content = json.loads(request_body.decode('utf-8'))
            except json.JSONDecodeError:
                return {"compliant": True, "violations": []}
            
            # Check for PII in request
            content_str = json.dumps(content)
            pii_result = self.pii_detector.detect_pii(content_str)
            
            violations = []
            
            if pii_result.has_pii:
                # Check if PII is allowed
                allowed_types = await self._get_allowed_pii_types(tenant_id)
                
                for detection in pii_result.detections:
                    if detection.pii_type not in allowed_types:
                        violations.append({
                            "type": "pii_not_allowed",
                            "pii_type": detection.pii_type.value,
                            "sensitivity_level": detection.sensitivity_level.value,
                            "confidence": detection.confidence
                        })
            
            return {
                "compliant": len(violations) == 0,
                "violations": violations,
                "pii_detected": pii_result.has_pii,
                "sensitivity_score": pii_result.sensitivity_score
            }
            
        except Exception as e:
            logger.error("Failed to validate request privacy", error=str(e))
            return {"compliant": False, "violations": [{"type": "validation_error", "error": str(e)}]}
    
    async def _get_allowed_pii_types(self, tenant_id: str) -> List[PIIType]:
        """Get allowed PII types for tenant."""
        # In production, this would check tenant's privacy policy
        return [PIIType.EMAIL, PIIType.PHONE]
