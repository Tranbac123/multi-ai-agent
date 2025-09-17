"""
Early Exit Manager for Router v2

Implements early exit logic for strict JSON validation in SLM_A tier
to prevent unnecessary escalation.
"""

import json
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import structlog
from datetime import datetime

logger = structlog.get_logger(__name__)


@dataclass
class EarlyExitResult:
    """Result of early exit evaluation."""
    
    should_exit: bool
    confidence: float
    reason: str
    validated_json: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None


class JSONValidator:
    """Validates JSON structure and content."""
    
    def __init__(self):
        self.strict_mode = True
        self.allowed_schemas = self._initialize_allowed_schemas()
    
    def _initialize_allowed_schemas(self) -> Dict[str, Dict[str, Any]]:
        """Initialize allowed JSON schemas for early exit."""
        return {
            "simple_response": {
                "type": "object",
                "properties": {
                    "answer": {"type": "string"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["answer", "confidence"],
                "additionalProperties": False
            },
            "classification": {
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "probability": {"type": "number", "minimum": 0, "maximum": 1},
                    "reasoning": {"type": "string"}
                },
                "required": ["category", "probability"],
                "additionalProperties": False
            },
            "extraction": {
                "type": "object",
                "properties": {
                    "entities": {
                        "type": "array",
                        "items": {"type": "string"}
                    },
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1}
                },
                "required": ["entities"],
                "additionalProperties": False
            },
            "boolean_response": {
                "type": "object",
                "properties": {
                    "result": {"type": "boolean"},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "reasoning": {"type": "string"}
                },
                "required": ["result", "confidence"],
                "additionalProperties": False
            }
        }
    
    def validate_json_structure(self, json_str: str) -> Tuple[bool, Optional[Dict[str, Any]], Optional[str]]:
        """Validate JSON structure and parse."""
        try:
            parsed_json = json.loads(json_str)
            return True, parsed_json, None
        except json.JSONDecodeError as e:
            return False, None, f"JSON decode error: {str(e)}"
        except Exception as e:
            return False, None, f"JSON parsing error: {str(e)}"
    
    def validate_against_schema(self, data: Dict[str, Any], schema_name: str) -> Tuple[bool, Optional[str]]:
        """Validate data against a specific schema."""
        if schema_name not in self.allowed_schemas:
            return False, f"Unknown schema: {schema_name}"
        
        schema = self.allowed_schemas[schema_name]
        return self._validate_schema(data, schema)
    
    def _validate_schema(self, data: Any, schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate data against schema (simplified implementation)."""
        schema_type = schema.get("type")
        
        if schema_type == "object":
            return self._validate_object(data, schema)
        elif schema_type == "array":
            return self._validate_array(data, schema)
        elif schema_type == "string":
            return self._validate_string(data, schema)
        elif schema_type == "number":
            return self._validate_number(data, schema)
        elif schema_type == "boolean":
            return self._validate_boolean(data, schema)
        else:
            return True, None  # Unknown type, assume valid
    
    def _validate_object(self, data: Any, schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate object type data."""
        if not isinstance(data, dict):
            return False, "Expected object"
        
        # Check required properties
        required_error = self._check_required_properties(data, schema)
        if required_error:
            return False, required_error
        
        # Check properties
        properties_error = self._check_object_properties(data, schema)
        if properties_error:
            return False, properties_error
        
        return True, None
    
    def _check_required_properties(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
        """Check that all required properties are present."""
        required = schema.get("required", [])
        for prop in required:
            if prop not in data:
                return f"Missing required property: {prop}"
        return None
    
    def _check_object_properties(self, data: Dict[str, Any], schema: Dict[str, Any]) -> Optional[str]:
        """Check object properties against schema."""
        properties = schema.get("properties", {})
        for prop, value in data.items():
            if prop in properties:
                prop_schema = properties[prop]
                is_valid, error = self._validate_schema(value, prop_schema)
                if not is_valid:
                    return f"Property '{prop}' validation failed: {error}"
            elif not schema.get("additionalProperties", True):
                return f"Additional property '{prop}' not allowed"
        return None
    
    def _validate_array(self, data: Any, schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate array type data."""
        if not isinstance(data, list):
            return False, "Expected array"
        
        items_schema = schema.get("items", {})
        for i, item in enumerate(data):
            is_valid, error = self._validate_schema(item, items_schema)
            if not is_valid:
                return False, f"Array item {i} validation failed: {error}"
        
        return True, None
    
    def _validate_string(self, data: Any, schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate string type data."""
        if not isinstance(data, str):
            return False, "Expected string"
        
        # Check minimum/maximum length
        min_length = schema.get("minLength")
        max_length = schema.get("maxLength")
        if min_length is not None and len(data) < min_length:
            return False, f"String too short (minimum {min_length})"
        if max_length is not None and len(data) > max_length:
            return False, f"String too long (maximum {max_length})"
        
        return True, None
    
    def _validate_number(self, data: Any, schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate number type data."""
        if not isinstance(data, (int, float)):
            return False, "Expected number"
        
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and data < minimum:
            return False, f"Number below minimum {minimum}"
        if maximum is not None and data > maximum:
            return False, f"Number above maximum {maximum}"
        
        return True, None
    
    def _validate_boolean(self, data: Any, schema: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate boolean type data."""
        if not isinstance(data, bool):
            return False, "Expected boolean"
        return True, None


class ConfidenceEstimator:
    """Estimates confidence in SLM_A responses."""
    
    def __init__(self):
        self.confidence_factors = {
            "json_validity": 0.4,
            "schema_compliance": 0.3,
            "content_quality": 0.2,
            "response_completeness": 0.1
        }
    
    def estimate_confidence(
        self, 
        response_text: str, 
        validated_json: Optional[Dict[str, Any]] = None,
        schema_name: Optional[str] = None
    ) -> float:
        """Estimate confidence in the response."""
        
        scores = {}
        
        # JSON validity score
        if validated_json is not None:
            scores["json_validity"] = 1.0
        else:
            scores["json_validity"] = 0.0
        
        # Schema compliance score
        if schema_name and validated_json:
            validator = JSONValidator()
            is_valid, _ = validator.validate_against_schema(validated_json, schema_name)
            scores["schema_compliance"] = 1.0 if is_valid else 0.0
        else:
            scores["schema_compliance"] = 0.0
        
        # Content quality score
        scores["content_quality"] = self._assess_content_quality(response_text, validated_json)
        
        # Response completeness score
        scores["response_completeness"] = self._assess_completeness(response_text, validated_json)
        
        # Calculate weighted confidence
        confidence = sum(
            scores[factor] * weight 
            for factor, weight in self.confidence_factors.items()
        )
        
        return min(1.0, confidence)
    
    def _assess_content_quality(self, text: str, json_data: Optional[Dict[str, Any]]) -> float:
        """Assess content quality of the response."""
        score = 0.0
        
        # Check for reasonable length
        if 10 <= len(text) <= 1000:
            score += 0.3
        
        # Check for proper formatting
        if not re.search(r'[.!?]$', text.strip()):
            score += 0.2
        
        # Check for clear language
        if not re.search(r'\b(um|uh|er|like)\b', text.lower()):
            score += 0.2
        
        # Check JSON content quality if available
        if json_data:
            if isinstance(json_data.get("confidence"), (int, float)):
                if 0 <= json_data["confidence"] <= 1:
                    score += 0.2
            elif isinstance(json_data.get("result"), bool):
                score += 0.1
        
        return min(1.0, score)
    
    def _assess_completeness(self, text: str, json_data: Optional[Dict[str, Any]]) -> float:
        """Assess completeness of the response."""
        score = 0.0
        
        # Check if response addresses the question
        if len(text.strip()) > 5:
            score += 0.4
        
        # Check for required fields in JSON
        if json_data:
            required_fields = ["answer", "confidence", "result", "category"]
            present_fields = sum(1 for field in required_fields if field in json_data)
            score += (present_fields / len(required_fields)) * 0.4
        
        # Check for reasoning if present
        if json_data and "reasoning" in json_data:
            if json_data["reasoning"] and len(json_data["reasoning"]) > 10:
                score += 0.2
        
        return min(1.0, score)


class EarlyExitManager:
    """Manages early exit decisions for router."""
    
    def __init__(self, confidence_threshold: float = 0.85):
        self.confidence_threshold = confidence_threshold
        self.json_validator = JSONValidator()
        self.confidence_estimator = ConfidenceEstimator()
        
        # Statistics
        self.total_evaluations = 0
        self.early_exits = 0
        self.successful_exits = 0
        
        logger.info("Early exit manager initialized", 
                   confidence_threshold=confidence_threshold)
    
    def evaluate_early_exit(
        self, 
        response_text: str, 
        expected_schema: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> EarlyExitResult:
        """Evaluate if early exit should be triggered."""
        
        self.total_evaluations += 1
        
        # Validate JSON structure
        is_valid_json, validated_json, json_error = self.json_validator.validate_json_structure(response_text)
        
        if not is_valid_json:
            return EarlyExitResult(
                should_exit=False,
                confidence=0.0,
                reason="Invalid JSON structure",
                error_message=json_error
            )
        
        # Validate against schema if provided
        if expected_schema and validated_json:
            is_valid_schema, schema_error = self.json_validator.validate_against_schema(
                validated_json, expected_schema
            )
            
            if not is_valid_schema:
                return EarlyExitResult(
                    should_exit=False,
                    confidence=0.0,
                    reason="Schema validation failed",
                    error_message=schema_error
                )
        
        # Estimate confidence
        confidence = self.confidence_estimator.estimate_confidence(
            response_text, validated_json, expected_schema
        )
        
        # Make early exit decision
        should_exit = confidence >= self.confidence_threshold
        
        if should_exit:
            self.early_exits += 1
        
        # Generate reason
        reason = self._generate_reason(should_exit, confidence, validated_json)
        
        return EarlyExitResult(
            should_exit=should_exit,
            confidence=confidence,
            reason=reason,
            validated_json=validated_json
        )
    
    def _generate_reason(
        self, 
        should_exit: bool, 
        confidence: float, 
        validated_json: Optional[Dict[str, Any]]
    ) -> str:
        """Generate human-readable reason for the decision."""
        
        if should_exit:
            reason_parts = [f"High confidence ({confidence:.2f}) response from SLM_A"]
            
            if validated_json:
                reason_parts.append("Valid JSON structure")
                
                # Check for specific quality indicators
                if isinstance(validated_json.get("confidence"), (int, float)):
                    if validated_json["confidence"] >= 0.8:
                        reason_parts.append("High model confidence")
                
                if "reasoning" in validated_json and validated_json["reasoning"]:
                    reason_parts.append("Includes reasoning")
            
            return ". ".join(reason_parts) + "."
        
        else:
            reason_parts = [f"Low confidence ({confidence:.2f}) response from SLM_A"]
            
            if confidence < 0.5:
                reason_parts.append("Response quality insufficient")
            elif confidence < 0.7:
                reason_parts.append("Response needs validation")
            else:
                reason_parts.append("Below confidence threshold")
            
            return ". ".join(reason_parts) + "."
    
    def record_outcome(self, success: bool):
        """Record the outcome of an early exit decision."""
        if success:
            self.successful_exits += 1
        
        success_rate = self.successful_exits / max(1, self.early_exits)
        
        logger.info("Early exit outcome recorded", 
                   success=success, 
                   success_rate=success_rate,
                   total_exits=self.early_exits)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get early exit statistics."""
        return {
            "total_evaluations": self.total_evaluations,
            "early_exits": self.early_exits,
            "successful_exits": self.successful_exits,
            "exit_rate": self.early_exits / max(1, self.total_evaluations),
            "success_rate": self.successful_exits / max(1, self.early_exits),
            "confidence_threshold": self.confidence_threshold
        }
    
    def update_threshold(self, new_threshold: float):
        """Update confidence threshold based on performance."""
        old_threshold = self.confidence_threshold
        self.confidence_threshold = new_threshold
        
        logger.info("Confidence threshold updated", 
                   old_threshold=old_threshold, 
                   new_threshold=new_threshold)
    
    def should_adjust_threshold(self) -> Tuple[bool, float]:
        """Determine if threshold should be adjusted and by how much."""
        
        if self.early_exits < 10:  # Not enough data
            return False, self.confidence_threshold
        
        success_rate = self.successful_exits / self.early_exits
        
        # If success rate is too low, increase threshold
        if success_rate < 0.8:
            new_threshold = min(0.95, self.confidence_threshold + 0.05)
            return True, new_threshold
        
        # If success rate is very high and exit rate is low, decrease threshold
        elif success_rate > 0.95 and self.early_exits / self.total_evaluations < 0.3:
            new_threshold = max(0.7, self.confidence_threshold - 0.05)
            return True, new_threshold
        
        return False, self.confidence_threshold
