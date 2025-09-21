"""
Router Base Class with Enhanced Features

Provides comprehensive router functionality including:
- Token counting and analysis
- JSON schema strictness validation
- Domain-specific flags
- Novelty detection
- Historical failure rate tracking
- Comprehensive metrics
"""

import asyncio
import json
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set, Tuple
from datetime import datetime, timedelta
import redis.asyncio as redis
import tiktoken
from enum import Enum
import structlog

logger = structlog.get_logger(__name__)


class SchemaStrictness(Enum):
    """JSON schema strictness levels."""
    STRICT = "strict"
    MODERATE = "moderate"
    LOOSE = "loose"
    NONE = "none"


class DomainFlag(Enum):
    """Domain-specific flags for routing decisions."""
    TECHNICAL = "technical"
    CREATIVE = "creative"
    ANALYTICAL = "analytical"
    CONVERSATIONAL = "conversational"
    CODE_GENERATION = "code_generation"
    DATA_ANALYSIS = "data_analysis"
    CONTENT_CREATION = "content_creation"
    TRANSLATION = "translation"
    SUMMARIZATION = "summarization"


@dataclass
class TokenAnalysis:
    """Token analysis results."""
    total_tokens: int
    prompt_tokens: int
    completion_tokens: int
    token_distribution: Dict[str, int]
    complexity_score: float
    estimated_cost: float
    model_requirements: Dict[str, Any]


@dataclass
class SchemaValidation:
    """JSON schema validation results."""
    strictness: SchemaStrictness
    validation_errors: List[str]
    schema_complexity: float
    required_fields: Set[str]
    optional_fields: Set[str]
    nested_depth: int


@dataclass
class NoveltyAnalysis:
    """Novelty analysis results."""
    novelty_score: float
    similarity_to_history: float
    unique_patterns: List[str]
    context_familiarity: float
    complexity_novelty: float


@dataclass
class HistoricalMetrics:
    """Historical performance metrics."""
    total_requests: int
    successful_requests: int
    failed_requests: int
    failure_rate: float
    average_response_time: float
    p95_response_time: float
    cost_efficiency: float
    accuracy_score: float


@dataclass
class RouterMetrics:
    """Router performance metrics."""
    router_decision_latency_ms: float
    router_misroute_rate: float
    expected_vs_actual: Dict[str, Any]
    tier_distribution: Dict[str, int]
    confidence_distribution: Dict[str, float]
    feature_importance: Dict[str, float]


class TokenCounter:
    """Advanced token counting and analysis."""
    
    def __init__(self):
        self.encoding = tiktoken.get_encoding("cl100k_base")
        self.token_cache = {}
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        if text in self.token_cache:
            return self.token_cache[text]
        
        tokens = len(self.encoding.encode(text))
        self.token_cache[text] = tokens
        return tokens
    
    def analyze_tokens(self, prompt: str, completion: str = "") -> TokenAnalysis:
        """Analyze token usage and complexity."""
        prompt_tokens = self.count_tokens(prompt)
        completion_tokens = self.count_tokens(completion)
        total_tokens = prompt_tokens + completion_tokens
        
        # Analyze token distribution
        token_distribution = {
            "words": len(prompt.split()),
            "sentences": len(prompt.split('.')),
            "paragraphs": len(prompt.split('\n\n')),
            "code_blocks": prompt.count('```'),
            "urls": prompt.count('http'),
            "mentions": prompt.count('@'),
            "hashtags": prompt.count('#')
        }
        
        # Calculate complexity score
        complexity_score = self._calculate_complexity(prompt, token_distribution)
        
        # Estimate cost (using OpenAI pricing)
        estimated_cost = self._estimate_cost(prompt_tokens, completion_tokens)
        
        # Determine model requirements
        model_requirements = self._determine_model_requirements(total_tokens, complexity_score)
        
        return TokenAnalysis(
            total_tokens=total_tokens,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            token_distribution=token_distribution,
            complexity_score=complexity_score,
            estimated_cost=estimated_cost,
            model_requirements=model_requirements
        )
    
    def _calculate_complexity(self, text: str, distribution: Dict[str, int]) -> float:
        """Calculate text complexity score."""
        complexity_factors = {
            "length": min(len(text) / 1000, 1.0),
            "vocabulary": min(distribution["words"] / 100, 1.0),
            "structure": min(distribution["paragraphs"] / 10, 1.0),
            "code": min(distribution["code_blocks"] / 5, 1.0),
            "special_chars": min(text.count('$') + text.count('*') + text.count('_'), 10) / 10
        }
        
        return sum(complexity_factors.values()) / len(complexity_factors)
    
    def _estimate_cost(self, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate API cost (OpenAI pricing)."""
        # GPT-4 pricing: $0.03/1K prompt, $0.06/1K completion
        prompt_cost = (prompt_tokens / 1000) * 0.03
        completion_cost = (completion_tokens / 1000) * 0.06
        return prompt_cost + completion_cost
    
    def _determine_model_requirements(self, total_tokens: int, complexity: float) -> Dict[str, Any]:
        """Determine model requirements based on tokens and complexity."""
        if total_tokens > 32000 or complexity > 0.8:
            return {"model": "gpt-4-32k", "reason": "high_token_complexity"}
        elif total_tokens > 8000 or complexity > 0.6:
            return {"model": "gpt-4", "reason": "medium_token_complexity"}
        elif total_tokens > 4000 or complexity > 0.4:
            return {"model": "gpt-3.5-turbo-16k", "reason": "standard_complexity"}
        else:
            return {"model": "gpt-3.5-turbo", "reason": "simple_request"}


class SchemaValidator:
    """JSON schema validation and analysis."""
    
    def __init__(self):
        self.schema_cache = {}
    
    def validate_schema(self, schema: Dict[str, Any], data: Dict[str, Any]) -> SchemaValidation:
        """Validate data against schema and analyze strictness."""
        validation_errors = []
        required_fields = set()
        optional_fields = set()
        nested_depth = 0
        
        try:
            # Analyze schema structure
            required_fields, optional_fields, nested_depth = self._analyze_schema_structure(schema)
            
            # Validate data against schema
            validation_errors = self._validate_data(schema, data, "")
            
            # Determine strictness level
            strictness = self._determine_strictness(schema, validation_errors)
            
            # Calculate schema complexity
            schema_complexity = self._calculate_schema_complexity(schema)
            
        except Exception as e:
            validation_errors.append(f"Schema analysis error: {str(e)}")
            strictness = SchemaStrictness.NONE
            schema_complexity = 0.0
        
        return SchemaValidation(
            strictness=strictness,
            validation_errors=validation_errors,
            schema_complexity=schema_complexity,
            required_fields=required_fields,
            optional_fields=optional_fields,
            nested_depth=nested_depth
        )
    
    def _analyze_schema_structure(self, schema: Dict[str, Any]) -> Tuple[Set[str], Set[str], int]:
        """Analyze schema structure."""
        required_fields = set()
        optional_fields = set()
        max_depth = 0
        
        def analyze_properties(properties: Dict[str, Any], depth: int = 0):
            nonlocal max_depth
            max_depth = max(max_depth, depth)
            
            for field_name, field_schema in properties.items():
                if isinstance(field_schema, dict):
                    if field_schema.get("required", False):
                        required_fields.add(field_name)
                    else:
                        optional_fields.add(field_name)
                    
                    # Recursively analyze nested schemas
                    if "properties" in field_schema:
                        analyze_properties(field_schema["properties"], depth + 1)
        
        if "properties" in schema:
            analyze_properties(schema["properties"])
        
        return required_fields, optional_fields, max_depth
    
    def _validate_data(self, schema: Dict[str, Any], data: Dict[str, Any], path: str) -> List[str]:
        """Validate data against schema."""
        errors = []
        
        if "properties" in schema:
            for field_name, field_schema in schema["properties"].items():
                field_path = f"{path}.{field_name}" if path else field_name
                
                if field_name not in data:
                    if field_schema.get("required", False):
                        errors.append(f"Missing required field: {field_path}")
                else:
                    # Validate field type
                    expected_type = field_schema.get("type")
                    if expected_type and not self._validate_type(data[field_name], expected_type):
                        errors.append(f"Invalid type for {field_path}: expected {expected_type}")
                    
                    # Recursively validate nested objects
                    if expected_type == "object" and "properties" in field_schema:
                        nested_errors = self._validate_data(
                            field_schema, data[field_name], field_path
                        )
                        errors.extend(nested_errors)
        
        return errors
    
    def _validate_type(self, value: Any, expected_type: str) -> bool:
        """Validate value type."""
        type_mapping = {
            "string": str,
            "integer": int,
            "number": (int, float),
            "boolean": bool,
            "array": list,
            "object": dict
        }
        
        expected_python_type = type_mapping.get(expected_type)
        if expected_python_type:
            return isinstance(value, expected_python_type)
        
        return True
    
    def _determine_strictness(self, schema: Dict[str, Any], errors: List[str]) -> SchemaStrictness:
        """Determine schema strictness level."""
        if not schema or "properties" not in schema:
            return SchemaStrictness.NONE
        
        required_count = len([p for p in schema.get("properties", {}).values() 
                             if p.get("required", False)])
        total_count = len(schema.get("properties", {}))
        
        if required_count / max(total_count, 1) > 0.8 and len(errors) == 0:
            return SchemaStrictness.STRICT
        elif required_count / max(total_count, 1) > 0.5:
            return SchemaStrictness.MODERATE
        elif required_count / max(total_count, 1) > 0.2:
            return SchemaStrictness.LOOSE
        else:
            return SchemaStrictness.NONE
    
    def _calculate_schema_complexity(self, schema: Dict[str, Any]) -> float:
        """Calculate schema complexity score."""
        if not schema or "properties" not in schema:
            return 0.0
        
        properties = schema["properties"]
        complexity_factors = {
            "field_count": min(len(properties) / 20, 1.0),
            "nested_depth": min(self._get_max_nested_depth(properties) / 5, 1.0),
            "required_ratio": len([p for p in properties.values() if p.get("required", False)]) / len(properties),
            "type_diversity": len(set(p.get("type", "unknown") for p in properties.values())) / len(properties)
        }
        
        return sum(complexity_factors.values()) / len(complexity_factors)
    
    def _get_max_nested_depth(self, properties: Dict[str, Any], current_depth: int = 0) -> int:
        """Get maximum nested depth in schema."""
        max_depth = current_depth
        
        for field_schema in properties.values():
            if isinstance(field_schema, dict) and "properties" in field_schema:
                nested_depth = self._get_max_nested_depth(
                    field_schema["properties"], current_depth + 1
                )
                max_depth = max(max_depth, nested_depth)
        
        return max_depth


class NoveltyDetector:
    """Novelty detection and analysis."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.history_window = 1000  # Keep last 1000 requests
    
    async def analyze_novelty(self, request: Dict[str, Any], tenant_id: str) -> NoveltyAnalysis:
        """Analyze novelty of the request."""
        # Extract key features for novelty analysis
        features = self._extract_features(request)
        
        # Get historical patterns
        historical_patterns = await self._get_historical_patterns(tenant_id)
        
        # Calculate novelty score
        novelty_score = self._calculate_novelty_score(features, historical_patterns)
        
        # Calculate similarity to history
        similarity = self._calculate_similarity(features, historical_patterns)
        
        # Identify unique patterns
        unique_patterns = self._identify_unique_patterns(features, historical_patterns)
        
        # Calculate context familiarity
        context_familiarity = self._calculate_context_familiarity(request, tenant_id)
        
        # Calculate complexity novelty
        complexity_novelty = self._calculate_complexity_novelty(features, historical_patterns)
        
        # Store current request for future analysis
        await self._store_request_pattern(features, tenant_id)
        
        return NoveltyAnalysis(
            novelty_score=novelty_score,
            similarity_to_history=similarity,
            unique_patterns=unique_patterns,
            context_familiarity=context_familiarity,
            complexity_novelty=complexity_novelty
        )
    
    def _extract_features(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Extract features for novelty analysis."""
        text = request.get("message", "") or request.get("prompt", "")
        
        return {
            "length": len(text),
            "word_count": len(text.split()),
            "sentence_count": len(text.split('.')),
            "has_code": '```' in text or 'def ' in text or 'class ' in text,
            "has_urls": 'http' in text,
            "has_mentions": '@' in text,
            "has_hashtags": '#' in text,
            "language": self._detect_language(text),
            "complexity": self._calculate_text_complexity(text),
            "topics": self._extract_topics(text)
        }
    
    def _detect_language(self, text: str) -> str:
        """Simple language detection."""
        # This is a simplified implementation
        if any(char in text for char in 'àáảãạăắằẳẵặâấầẩẫậèéẻẽẹêếềểễệìíỉĩịòóỏõọôốồổỗộơớờởỡợùúủũụưứừửữựỳýỷỹỵđ'):
            return "vietnamese"
        elif any(word in text.lower() for word in ['the', 'and', 'is', 'in', 'to', 'of', 'a', 'that', 'it']):
            return "english"
        else:
            return "unknown"
    
    def _calculate_text_complexity(self, text: str) -> float:
        """Calculate text complexity score."""
        if not text:
            return 0.0
        
        factors = {
            "length": min(len(text) / 1000, 1.0),
            "vocabulary": len(set(text.lower().split())) / max(len(text.split()), 1),
            "punctuation": text.count('.') + text.count('!') + text.count('?'),
            "special_chars": len([c for c in text if not c.isalnum() and c not in ' .,!?'])
        }
        
        return sum(factors.values()) / len(factors)
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text."""
        # Simplified topic extraction
        topics = []
        text_lower = text.lower()
        
        topic_keywords = {
            "technical": ["code", "programming", "algorithm", "database", "api"],
            "business": ["revenue", "profit", "customer", "market", "strategy"],
            "creative": ["design", "art", "creative", "story", "imagine"],
            "analytical": ["analyze", "data", "statistics", "trend", "report"]
        }
        
        for topic, keywords in topic_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                topics.append(topic)
        
        return topics
    
    async def _get_historical_patterns(self, tenant_id: str) -> List[Dict[str, Any]]:
        """Get historical request patterns."""
        try:
            key = f"novelty_history:{tenant_id}"
            patterns = await self.redis.lrange(key, 0, self.history_window - 1)
            return [json.loads(pattern) for pattern in patterns]
        except Exception as e:
            logger.warning(f"Failed to get historical patterns: {e}")
            return []
    
    def _calculate_novelty_score(self, features: Dict[str, Any], 
                                historical_patterns: List[Dict[str, Any]]) -> float:
        """Calculate novelty score."""
        if not historical_patterns:
            return 1.0  # Completely novel if no history
        
        similarities = []
        for pattern in historical_patterns:
            similarity = self._calculate_feature_similarity(features, pattern)
            similarities.append(similarity)
        
        # Novelty is inverse of maximum similarity
        max_similarity = max(similarities) if similarities else 0.0
        return 1.0 - max_similarity
    
    def _calculate_similarity(self, features: Dict[str, Any], 
                             historical_patterns: List[Dict[str, Any]]) -> float:
        """Calculate similarity to historical patterns."""
        if not historical_patterns:
            return 0.0
        
        similarities = [self._calculate_feature_similarity(features, pattern) 
                       for pattern in historical_patterns]
        
        return sum(similarities) / len(similarities)
    
    def _calculate_feature_similarity(self, features1: Dict[str, Any], 
                                     features2: Dict[str, Any]) -> float:
        """Calculate similarity between two feature sets."""
        similarities = []
        
        for key in set(features1.keys()) & set(features2.keys()):
            if isinstance(features1[key], (int, float)) and isinstance(features2[key], (int, float)):
                # Numerical similarity
                max_val = max(abs(features1[key]), abs(features2[key]), 1)
                similarity = 1.0 - abs(features1[key] - features2[key]) / max_val
                similarities.append(max(0.0, similarity))
            elif isinstance(features1[key], bool) and isinstance(features2[key], bool):
                # Boolean similarity
                similarities.append(1.0 if features1[key] == features2[key] else 0.0)
            elif isinstance(features1[key], list) and isinstance(features2[key], list):
                # List similarity (Jaccard similarity)
                set1, set2 = set(features1[key]), set(features2[key])
                if set1 or set2:
                    jaccard = len(set1 & set2) / len(set1 | set2)
                    similarities.append(jaccard)
                else:
                    similarities.append(1.0)
        
        return sum(similarities) / len(similarities) if similarities else 0.0
    
    def _identify_unique_patterns(self, features: Dict[str, Any], 
                                 historical_patterns: List[Dict[str, Any]]) -> List[str]:
        """Identify unique patterns in the request."""
        unique_patterns = []
        
        for key, value in features.items():
            if isinstance(value, bool) and value:
                # Check if this boolean feature is rare in history
                historical_count = sum(1 for pattern in historical_patterns 
                                     if pattern.get(key, False))
                if historical_count < len(historical_patterns) * 0.1:  # Less than 10%
                    unique_patterns.append(f"rare_{key}")
            
            elif isinstance(value, list) and value:
                # Check for unique topic combinations
                for item in value:
                    historical_count = sum(1 for pattern in historical_patterns 
                                         if item in pattern.get(key, []))
                    if historical_count < len(historical_patterns) * 0.2:  # Less than 20%
                        unique_patterns.append(f"unique_{key}_{item}")
        
        return unique_patterns
    
    async def _calculate_context_familiarity(self, request: Dict[str, Any], 
                                            tenant_id: str) -> float:
        """Calculate context familiarity score."""
        # This would analyze conversation history, user patterns, etc.
        # For now, return a placeholder value
        return 0.7
    
    def _calculate_complexity_novelty(self, features: Dict[str, Any], 
                                     historical_patterns: List[Dict[str, Any]]) -> float:
        """Calculate complexity novelty score."""
        if not historical_patterns:
            return 1.0
        
        current_complexity = features.get("complexity", 0.0)
        historical_complexities = [p.get("complexity", 0.0) for p in historical_patterns]
        
        if not historical_complexities:
            return 1.0
        
        avg_historical = sum(historical_complexities) / len(historical_complexities)
        complexity_diff = abs(current_complexity - avg_historical)
        
        return min(complexity_diff * 2, 1.0)  # Scale to 0-1
    
    async def _store_request_pattern(self, features: Dict[str, Any], tenant_id: str):
        """Store request pattern for future analysis."""
        try:
            key = f"novelty_history:{tenant_id}"
            await self.redis.lpush(key, json.dumps(features))
            await self.redis.ltrim(key, 0, self.history_window - 1)
        except Exception as e:
            logger.warning(f"Failed to store request pattern: {e}")


class HistoricalTracker:
    """Historical performance tracking."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
        self.metrics_window = 86400  # 24 hours
    
    async def track_request(self, tenant_id: str, user_id: str, tier: str, 
                           success: bool, response_time: float, cost: float):
        """Track request metrics."""
        timestamp = int(time.time())
        
        # Store individual request
        request_key = f"requests:{tenant_id}:{timestamp}:{user_id}"
        await self.redis.hset(request_key, mapping={
            "tier": tier,
            "success": str(success),
            "response_time": str(response_time),
            "cost": str(cost),
            "timestamp": str(timestamp)
        })
        await self.redis.expire(request_key, self.metrics_window)
        
        # Update aggregated metrics
        await self._update_aggregated_metrics(tenant_id, tier, success, response_time, cost)
    
    async def get_historical_metrics(self, tenant_id: str, tier: str = None) -> HistoricalMetrics:
        """Get historical performance metrics."""
        if tier:
            key = f"metrics:{tenant_id}:{tier}"
        else:
            key = f"metrics:{tenant_id}:all"
        
        try:
            metrics_data = await self.redis.hgetall(key)
            
            total_requests = int(metrics_data.get("total_requests", 0))
            successful_requests = int(metrics_data.get("successful_requests", 0))
            failed_requests = total_requests - successful_requests
            failure_rate = failed_requests / max(total_requests, 1)
            
            avg_response_time = float(metrics_data.get("avg_response_time", 0.0))
            p95_response_time = float(metrics_data.get("p95_response_time", 0.0))
            total_cost = float(metrics_data.get("total_cost", 0.0))
            
            cost_efficiency = successful_requests / max(total_cost, 0.01)  # Requests per dollar
            accuracy_score = successful_requests / max(total_requests, 1)
            
            return HistoricalMetrics(
                total_requests=total_requests,
                successful_requests=successful_requests,
                failed_requests=failed_requests,
                failure_rate=failure_rate,
                average_response_time=avg_response_time,
                p95_response_time=p95_response_time,
                cost_efficiency=cost_efficiency,
                accuracy_score=accuracy_score
            )
            
        except Exception as e:
            logger.error(f"Failed to get historical metrics: {e}")
            return HistoricalMetrics(
                total_requests=0,
                successful_requests=0,
                failed_requests=0,
                failure_rate=0.0,
                average_response_time=0.0,
                p95_response_time=0.0,
                cost_efficiency=0.0,
                accuracy_score=0.0
            )
    
    async def _update_aggregated_metrics(self, tenant_id: str, tier: str, 
                                        success: bool, response_time: float, cost: float):
        """Update aggregated metrics."""
        keys = [
            f"metrics:{tenant_id}:{tier}",
            f"metrics:{tenant_id}:all"
        ]
        
        for key in keys:
            pipe = self.redis.pipeline()
            
            # Increment counters
            pipe.hincrby(key, "total_requests", 1)
            if success:
                pipe.hincrby(key, "successful_requests", 1)
            
            # Update response time metrics
            pipe.hincrbyfloat(key, "total_response_time", response_time)
            pipe.hincrbyfloat(key, "total_cost", cost)
            
            # Update averages
            total_requests = int(await self.redis.hget(key, "total_requests") or 0) + 1
            pipe.hset(key, "avg_response_time", 
                     (await self.redis.hget(key, "total_response_time") or 0) / total_requests)
            
            # Set expiration
            pipe.expire(key, self.metrics_window)
            
            await pipe.execute()


class EnhancedRouterBase(ABC):
    """Enhanced router base class with comprehensive features."""
    
    def __init__(self, redis_client: redis.Redis, name: str = "enhanced_router"):
        self.redis = redis_client
        self.name = name
        
        # Initialize components
        self.token_counter = TokenCounter()
        self.schema_validator = SchemaValidator()
        self.novelty_detector = NoveltyDetector(redis_client)
        self.historical_tracker = HistoricalTracker(redis_client)
        
        # Metrics
        self.metrics = RouterMetrics(
            router_decision_latency_ms=0.0,
            router_misroute_rate=0.0,
            expected_vs_actual={},
            tier_distribution={},
            confidence_distribution={},
            feature_importance={}
        )
    
    @abstractmethod
    async def route_request(self, request: Dict[str, Any], tenant_id: str, 
                           user_id: str) -> Dict[str, Any]:
        """Route request and return decision."""
        pass
    
    async def analyze_request(self, request: Dict[str, Any], tenant_id: str) -> Dict[str, Any]:
        """Comprehensive request analysis."""
        analysis = {
            "token_count": None,
            "json_schema_strictness": None,
            "domain_flags": [],
            "novelty": None,
            "historical_failure_rate": 0.0
        }
        
        # Token analysis
        text = request.get("message", "") or request.get("prompt", "")
        if text:
            analysis["token_count"] = self.token_counter.analyze_tokens(text)
        
        # Schema validation
        schema = request.get("schema")
        if schema:
            data = request.get("data", {})
            analysis["json_schema_strictness"] = self.schema_validator.validate_schema(schema, data)
        
        # Domain flags
        analysis["domain_flags"] = self._detect_domain_flags(request)
        
        # Novelty analysis
        analysis["novelty"] = await self.novelty_detector.analyze_novelty(request, tenant_id)
        
        # Historical failure rate
        historical_metrics = await self.historical_tracker.get_historical_metrics(tenant_id)
        analysis["historical_failure_rate"] = historical_metrics.failure_rate
        
        return analysis
    
    def _detect_domain_flags(self, request: Dict[str, Any]) -> List[DomainFlag]:
        """Detect domain-specific flags."""
        flags = []
        text = request.get("message", "") or request.get("prompt", "")
        text_lower = text.lower()
        
        # Technical flags
        if any(keyword in text_lower for keyword in ["code", "programming", "algorithm", "database", "api"]):
            flags.append(DomainFlag.TECHNICAL)
        
        # Creative flags
        if any(keyword in text_lower for keyword in ["design", "art", "creative", "story", "imagine"]):
            flags.append(DomainFlag.CREATIVE)
        
        # Analytical flags
        if any(keyword in text_lower for keyword in ["analyze", "data", "statistics", "trend", "report"]):
            flags.append(DomainFlag.ANALYTICAL)
        
        # Conversational flags
        if any(keyword in text_lower for keyword in ["hello", "how are you", "thank you", "please"]):
            flags.append(DomainFlag.CONVERSATIONAL)
        
        # Code generation flags
        if any(keyword in text_lower for keyword in ["write code", "implement", "function", "class"]):
            flags.append(DomainFlag.CODE_GENERATION)
        
        # Data analysis flags
        if any(keyword in text_lower for keyword in ["data analysis", "visualization", "chart", "graph"]):
            flags.append(DomainFlag.DATA_ANALYSIS)
        
        # Content creation flags
        if any(keyword in text_lower for keyword in ["write", "article", "blog", "content"]):
            flags.append(DomainFlag.CONTENT_CREATION)
        
        # Translation flags
        if any(keyword in text_lower for keyword in ["translate", "translation", "language"]):
            flags.append(DomainFlag.TRANSLATION)
        
        # Summarization flags
        if any(keyword in text_lower for keyword in ["summarize", "summary", "brief"]):
            flags.append(DomainFlag.SUMMARIZATION)
        
        return flags
    
    def update_metrics(self, decision_time: float, tier: str, confidence: float, 
                      expected_tier: str = None):
        """Update router metrics."""
        self.metrics.router_decision_latency_ms = decision_time * 1000
        
        # Update tier distribution
        self.metrics.tier_distribution[tier] = self.metrics.tier_distribution.get(tier, 0) + 1
        
        # Update confidence distribution
        confidence_bucket = f"{int(confidence * 10) * 10}%"
        self.metrics.confidence_distribution[confidence_bucket] = \
            self.metrics.confidence_distribution.get(confidence_bucket, 0) + 1
        
        # Update expected vs actual
        if expected_tier:
            if expected_tier not in self.metrics.expected_vs_actual:
                self.metrics.expected_vs_actual[expected_tier] = {}
            
            actual_tier = self.metrics.expected_vs_actual[expected_tier].get(tier, 0)
            self.metrics.expected_vs_actual[expected_tier][tier] = actual_tier + 1
            
            # Calculate misroute rate
            if expected_tier != tier:
                total_requests = sum(self.metrics.expected_vs_actual[expected_tier].values())
                self.metrics.router_misroute_rate = 1.0 - (self.metrics.expected_vs_actual[expected_tier].get(expected_tier, 0) / max(total_requests, 1))
    
    def get_metrics(self) -> RouterMetrics:
        """Get current router metrics."""
        return self.metrics

