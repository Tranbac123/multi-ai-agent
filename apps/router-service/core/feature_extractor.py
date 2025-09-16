"""
Feature Extractor for Router v2

Extracts features for routing decisions including token count, JSON schema strictness,
domain flags, novelty, and historical failure rate.
"""

import re
import json
import hashlib
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import structlog
from datetime import datetime, timedelta

logger = structlog.get_logger(__name__)


@dataclass
class FeatureVector:
    """Feature vector for routing decisions."""
    
    token_count: int
    json_schema_strictness: float
    domain_flags: List[str]
    novelty: float
    historical_failure_rate: float
    complexity_score: float
    urgency_score: float
    cost_sensitivity: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "token_count": self.token_count,
            "json_schema_strictness": self.json_schema_strictness,
            "domain_flags": self.domain_flags,
            "novelty": self.novelty,
            "historical_failure_rate": self.historical_failure_rate,
            "complexity_score": self.complexity_score,
            "urgency_score": self.urgency_score,
            "cost_sensitivity": self.cost_sensitivity
        }


class TokenCounter:
    """Token counting utilities."""
    
    def __init__(self):
        # Simple token estimation (in production, use actual tokenizer)
        self.avg_chars_per_token = 4.0
    
    def count_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        if not text:
            return 0
        
        # Simple estimation: characters / avg_chars_per_token
        return max(1, int(len(text) / self.avg_chars_per_token))
    
    def count_json_tokens(self, data: Any) -> int:
        """Count tokens in JSON data."""
        try:
            json_str = json.dumps(data, separators=(',', ':'))
            return self.count_tokens(json_str)
        except (TypeError, ValueError):
            return 0


class JSONSchemaAnalyzer:
    """Analyzes JSON schema strictness."""
    
    def __init__(self):
        self.strictness_indicators = {
            'required': 0.3,
            'type': 0.2,
            'enum': 0.4,
            'pattern': 0.3,
            'minLength': 0.2,
            'maxLength': 0.2,
            'minimum': 0.2,
            'maximum': 0.2,
            'format': 0.3,
            'additionalProperties': 0.5,
            'items': 0.2,
            'properties': 0.1
        }
    
    def analyze_schema_strictness(self, schema: Dict[str, Any]) -> float:
        """Calculate schema strictness score (0-1)."""
        if not isinstance(schema, dict):
            return 0.0
        
        total_score = 0.0
        total_weight = 0.0
        
        for indicator, weight in self.strictness_indicators.items():
            if indicator in schema:
                total_score += weight
                total_weight += weight
                
                # Additional scoring for nested schemas
                if indicator == 'properties' and isinstance(schema['properties'], dict):
                    for prop_schema in schema['properties'].values():
                        nested_score = self.analyze_schema_strictness(prop_schema)
                        total_score += nested_score * 0.5
                        total_weight += 0.5
        
        return total_score / total_weight if total_weight > 0 else 0.0
    
    def extract_schema_from_data(self, data: Any) -> Dict[str, Any]:
        """Extract schema from data structure."""
        if isinstance(data, dict):
            schema = {"type": "object", "properties": {}}
            for key, value in data.items():
                schema["properties"][key] = self._get_value_schema(value)
            return schema
        elif isinstance(data, list) and data:
            schema = {"type": "array", "items": self._get_value_schema(data[0])}
            return schema
        else:
            return self._get_value_schema(data)
    
    def _get_value_schema(self, value: Any) -> Dict[str, Any]:
        """Get schema for a single value."""
        if isinstance(value, str):
            return {"type": "string"}
        elif isinstance(value, int):
            return {"type": "integer"}
        elif isinstance(value, float):
            return {"type": "number"}
        elif isinstance(value, bool):
            return {"type": "boolean"}
        elif isinstance(value, list):
            return {"type": "array", "items": self._get_value_schema(value[0]) if value else {}}
        elif isinstance(value, dict):
            return {"type": "object", "properties": {k: self._get_value_schema(v) for k, v in value.items()}}
        else:
            return {"type": "null"}


class DomainClassifier:
    """Classifies requests into domain categories."""
    
    def __init__(self):
        self.domain_patterns = {
            'customer_service': [
                r'\b(help|support|issue|problem|complaint|question|assistance)\b',
                r'\b(how to|how do|can you|could you)\b',
                r'\b(not working|broken|error|fail)\b'
            ],
            'billing': [
                r'\b(bill|invoice|payment|charge|cost|price|subscription)\b',
                r'\b(refund|credit|discount|promotion)\b',
                r'\b(upgrade|downgrade|plan|tier)\b'
            ],
            'technical': [
                r'\b(api|integration|webhook|endpoint|authentication)\b',
                r'\b(code|programming|development|technical)\b',
                r'\b(error|exception|bug|debug)\b'
            ],
            'data_analysis': [
                r'\b(analyze|report|dashboard|metrics|statistics)\b',
                r'\b(data|dataset|query|filter|aggregate)\b',
                r'\b(chart|graph|visualization)\b'
            ],
            'content_generation': [
                r'\b(write|create|generate|compose|draft)\b',
                r'\b(content|article|blog|email|document)\b',
                r'\b(summarize|paraphrase|rewrite)\b'
            ],
            'translation': [
                r'\b(translate|language|locale|localization)\b',
                r'\b(english|spanish|french|german|chinese)\b'
            ],
            'classification': [
                r'\b(classify|categorize|label|tag|sort)\b',
                r'\b(sentiment|emotion|tone|mood)\b'
            ]
        }
    
    def classify_domains(self, text: str) -> List[str]:
        """Classify text into domain categories."""
        if not text:
            return []
        
        text_lower = text.lower()
        matched_domains = []
        
        for domain, patterns in self.domain_patterns.items():
            for pattern in patterns:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    matched_domains.append(domain)
                    break
        
        return matched_domains


class NoveltyDetector:
    """Detects novelty in requests."""
    
    def __init__(self):
        self.historical_patterns = set()
        self.pattern_cache = {}
    
    def calculate_novelty(self, text: str) -> float:
        """Calculate novelty score (0-1, higher = more novel)."""
        if not text:
            return 0.0
        
        # Extract patterns from text
        patterns = self._extract_patterns(text)
        
        # Check against historical patterns
        novel_patterns = 0
        for pattern in patterns:
            if pattern not in self.historical_patterns:
                novel_patterns += 1
        
        novelty_score = novel_patterns / len(patterns) if patterns else 0.0
        
        # Add to historical patterns for future comparisons
        self.historical_patterns.update(patterns)
        
        return novelty_score
    
    def _extract_patterns(self, text: str) -> List[str]:
        """Extract patterns from text for novelty detection."""
        # Simple pattern extraction (in production, use more sophisticated NLP)
        patterns = []
        
        # Extract n-grams
        words = text.lower().split()
        for n in [2, 3]:  # Bigrams and trigrams
            for i in range(len(words) - n + 1):
                ngram = ' '.join(words[i:i+n])
                patterns.append(ngram)
        
        # Extract key phrases (simple regex-based)
        key_phrases = re.findall(r'\b\w+(?:\s+\w+){1,3}\b', text.lower())
        patterns.extend(key_phrases)
        
        return patterns


class HistoricalAnalyzer:
    """Analyzes historical failure rates."""
    
    def __init__(self):
        self.request_history = {}  # pattern_hash -> success/failure counts
        self.time_window = timedelta(hours=24)  # 24-hour window
    
    def get_failure_rate(self, text: str, domain_flags: List[str]) -> float:
        """Get historical failure rate for similar requests."""
        pattern_hash = self._create_pattern_hash(text, domain_flags)
        
        if pattern_hash not in self.request_history:
            return 0.0  # No history, assume low failure rate
        
        history = self.request_history[pattern_hash]
        total_requests = history['success'] + history['failure']
        
        if total_requests == 0:
            return 0.0
        
        return history['failure'] / total_requests
    
    def record_request_outcome(self, text: str, domain_flags: List[str], success: bool):
        """Record the outcome of a request."""
        pattern_hash = self._create_pattern_hash(text, domain_flags)
        
        if pattern_hash not in self.request_history:
            self.request_history[pattern_hash] = {'success': 0, 'failure': 0}
        
        if success:
            self.request_history[pattern_hash]['success'] += 1
        else:
            self.request_history[pattern_hash]['failure'] += 1
    
    def _create_pattern_hash(self, text: str, domain_flags: List[str]) -> str:
        """Create a hash for pattern matching."""
        # Normalize text and combine with domain flags
        normalized_text = re.sub(r'\s+', ' ', text.lower().strip())
        pattern_data = f"{normalized_text}:{':'.join(sorted(domain_flags))}"
        return hashlib.md5(pattern_data.encode()).hexdigest()


class ComplexityAnalyzer:
    """Analyzes request complexity."""
    
    def __init__(self):
        self.complexity_factors = {
            'length': 0.2,
            'json_depth': 0.3,
            'special_chars': 0.1,
            'technical_terms': 0.2,
            'multiple_questions': 0.2
        }
    
    def calculate_complexity(self, text: str, data: Optional[Dict[str, Any]] = None) -> float:
        """Calculate complexity score (0-1, higher = more complex)."""
        scores = {}
        
        # Text length factor
        scores['length'] = min(1.0, len(text) / 1000)  # Normalize to 1000 chars
        
        # JSON depth factor
        if data:
            scores['json_depth'] = self._calculate_json_depth(data)
        else:
            scores['json_depth'] = 0.0
        
        # Special characters factor
        special_chars = len(re.findall(r'[^\w\s]', text))
        scores['special_chars'] = min(1.0, special_chars / 50)  # Normalize to 50 chars
        
        # Technical terms factor
        technical_terms = len(re.findall(r'\b(api|json|xml|http|sql|algorithm|complexity)\b', text.lower()))
        scores['technical_terms'] = min(1.0, technical_terms / 10)  # Normalize to 10 terms
        
        # Multiple questions factor
        question_count = len(re.findall(r'\?', text))
        scores['multiple_questions'] = min(1.0, question_count / 5)  # Normalize to 5 questions
        
        # Calculate weighted score
        total_score = sum(scores[factor] * weight for factor, weight in self.complexity_factors.items())
        return min(1.0, total_score)
    
    def _calculate_json_depth(self, data: Any, current_depth: int = 0) -> float:
        """Calculate maximum depth of JSON structure."""
        if isinstance(data, dict):
            if not data:
                return 0.0
            max_child_depth = max(
                self._calculate_json_depth(value, current_depth + 1) 
                for value in data.values()
            )
            return max_child_depth
        elif isinstance(data, list):
            if not data:
                return 0.0
            max_child_depth = max(
                self._calculate_json_depth(item, current_depth + 1) 
                for item in data
            )
            return max_child_depth
        else:
            return current_depth / 10.0  # Normalize to reasonable range


class UrgencyAnalyzer:
    """Analyzes request urgency."""
    
    def __init__(self):
        self.urgency_indicators = [
            r'\b(urgent|asap|immediately|emergency|critical)\b',
            r'\b(rush|quickly|fast|priority|important)\b',
            r'\b(deadline|due|time sensitive)\b',
            r'\b(production|live|down|broken|outage)\b'
        ]
        
        self.non_urgent_indicators = [
            r'\b(when you have time|no rush|eventually|later)\b',
            r'\b(explore|learn|understand|curious)\b',
            r'\b(draft|example|sample|test)\b'
        ]
    
    def calculate_urgency(self, text: str) -> float:
        """Calculate urgency score (0-1, higher = more urgent)."""
        if not text:
            return 0.0
        
        text_lower = text.lower()
        urgency_score = 0.0
        
        # Check for urgency indicators
        for indicator in self.urgency_indicators:
            if re.search(indicator, text_lower, re.IGNORECASE):
                urgency_score += 0.3
        
        # Check for non-urgent indicators
        for indicator in self.non_urgent_indicators:
            if re.search(indicator, text_lower, re.IGNORECASE):
                urgency_score -= 0.2
        
        # Normalize to 0-1 range
        return max(0.0, min(1.0, urgency_score))


class CostSensitivityAnalyzer:
    """Analyzes cost sensitivity based on request characteristics."""
    
    def __init__(self):
        self.cost_sensitive_indicators = [
            r'\b(budget|cost|price|cheap|expensive|free)\b',
            r'\b(optimize|efficient|minimal|simple)\b',
            r'\b(quick|fast|basic|simple)\b'
        ]
        
        self.cost_insensitive_indicators = [
            r'\b(best|highest|premium|quality|comprehensive)\b',
            r'\b(detailed|thorough|complete|extensive)\b',
            r'\b(advanced|sophisticated|complex)\b'
        ]
    
    def calculate_cost_sensitivity(self, text: str) -> float:
        """Calculate cost sensitivity score (0-1, higher = more cost sensitive)."""
        if not text:
            return 0.5  # Default to medium sensitivity
        
        text_lower = text.lower()
        sensitivity_score = 0.5  # Start with neutral
        
        # Check for cost-sensitive indicators
        for indicator in self.cost_sensitive_indicators:
            if re.search(indicator, text_lower, re.IGNORECASE):
                sensitivity_score += 0.2
        
        # Check for cost-insensitive indicators
        for indicator in self.cost_insensitive_indicators:
            if re.search(indicator, text_lower, re.IGNORECASE):
                sensitivity_score -= 0.2
        
        # Normalize to 0-1 range
        return max(0.0, min(1.0, sensitivity_score))


class FeatureExtractor:
    """Main feature extractor for router decisions."""
    
    def __init__(self):
        self.token_counter = TokenCounter()
        self.schema_analyzer = JSONSchemaAnalyzer()
        self.domain_classifier = DomainClassifier()
        self.novelty_detector = NoveltyDetector()
        self.historical_analyzer = HistoricalAnalyzer()
        self.complexity_analyzer = ComplexityAnalyzer()
        self.urgency_analyzer = UrgencyAnalyzer()
        self.cost_sensitivity_analyzer = CostSensitivityAnalyzer()
    
    def extract_features(
        self, 
        input_text: str, 
        input_data: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> FeatureVector:
        """Extract comprehensive feature vector from input."""
        
        # Token count
        token_count = self.token_counter.count_tokens(input_text)
        if input_data:
            token_count += self.token_counter.count_json_tokens(input_data)
        
        # JSON schema strictness
        json_schema_strictness = 0.0
        if input_data:
            schema = self.schema_analyzer.extract_schema_from_data(input_data)
            json_schema_strictness = self.schema_analyzer.analyze_schema_strictness(schema)
        
        # Domain classification
        domain_flags = self.domain_classifier.classify_domains(input_text)
        
        # Novelty detection
        novelty = self.novelty_detector.calculate_novelty(input_text)
        
        # Historical failure rate
        historical_failure_rate = self.historical_analyzer.get_failure_rate(
            input_text, domain_flags
        )
        
        # Complexity analysis
        complexity_score = self.complexity_analyzer.calculate_complexity(
            input_text, input_data
        )
        
        # Urgency analysis
        urgency_score = self.urgency_analyzer.calculate_urgency(input_text)
        
        # Cost sensitivity analysis
        cost_sensitivity = self.cost_sensitivity_analyzer.calculate_cost_sensitivity(input_text)
        
        return FeatureVector(
            token_count=token_count,
            json_schema_strictness=json_schema_strictness,
            domain_flags=domain_flags,
            novelty=novelty,
            historical_failure_rate=historical_failure_rate,
            complexity_score=complexity_score,
            urgency_score=urgency_score,
            cost_sensitivity=cost_sensitivity
        )
    
    def record_request_outcome(
        self, 
        input_text: str, 
        domain_flags: List[str], 
        success: bool
    ):
        """Record the outcome of a request for historical analysis."""
        self.historical_analyzer.record_request_outcome(input_text, domain_flags, success)
    
    def get_feature_summary(self, features: FeatureVector) -> Dict[str, Any]:
        """Get a summary of extracted features."""
        return {
            "token_count": features.token_count,
            "complexity": "high" if features.complexity_score > 0.7 else "medium" if features.complexity_score > 0.3 else "low",
            "urgency": "high" if features.urgency_score > 0.7 else "medium" if features.urgency_score > 0.3 else "low",
            "cost_sensitivity": "high" if features.cost_sensitivity > 0.7 else "medium" if features.cost_sensitivity > 0.3 else "low",
            "domains": features.domain_flags,
            "novelty": features.novelty,
            "historical_failure_rate": features.historical_failure_rate,
            "json_strictness": features.json_schema_strictness
        }
