"""Feature extraction for router decisions."""

import re
import json
from typing import Dict, Any, List
import structlog

from libs.contracts.router import TextFeatures, RouterDecisionRequest

logger = structlog.get_logger(__name__)


class FeatureExtractor:
    """Extract features from text for routing decisions."""

    def __init__(self):
        self.reasoning_keywords = [
            "analyze",
            "compare",
            "evaluate",
            "reason",
            "explain",
            "why",
            "how",
            "because",
            "therefore",
            "however",
            "although",
            "consider",
            "think",
        ]
        self.domain_keywords = {
            "finance": ["money", "cost", "price", "budget", "investment", "revenue"],
            "legal": [
                "law",
                "legal",
                "contract",
                "agreement",
                "liability",
                "compliance",
            ],
            "medical": [
                "health",
                "medical",
                "patient",
                "diagnosis",
                "treatment",
                "symptoms",
            ],
            "ecommerce": [
                "product",
                "order",
                "shipping",
                "payment",
                "cart",
                "checkout",
            ],
        }

    def initialize(self):
        """Initialize feature extractor."""
        logger.info("Feature extractor initialized")

    async def extract(self, request: RouterDecisionRequest) -> TextFeatures:
        """Extract features from request."""
        text = request.requirement

        # Token count
        token_count = len(text.split())

        # JSON schema complexity
        json_schema_complexity = self._calculate_json_complexity(request)

        # Domain flags
        domain_flags = self._detect_domains(text)

        # Novelty score
        novelty_score = self._calculate_novelty(text, request.history_stats)

        # Historical failure rate
        historical_failure_rate = request.history_stats.success_rate

        # Reasoning keywords
        reasoning_keywords = self._extract_reasoning_keywords(text)

        # Entity count
        entity_count = self._count_entities(text)

        # Format strictness
        format_strictness = self._calculate_format_strictness(request)

        return TextFeatures(
            token_count=token_count,
            json_schema_complexity=json_schema_complexity,
            domain_flags=domain_flags,
            novelty_score=novelty_score,
            historical_failure_rate=historical_failure_rate,
            reasoning_keywords=reasoning_keywords,
            entity_count=entity_count,
            format_strictness=format_strictness,
        )

    def _calculate_json_complexity(self, request: RouterDecisionRequest) -> float:
        """Calculate JSON schema complexity."""
        # This would analyze the expected output schema
        # For now, return a simple heuristic
        if "json" in request.requirement.lower():
            return 0.7
        elif "format" in request.requirement.lower():
            return 0.5
        else:
            return 0.2

    def _detect_domains(self, text: str) -> Dict[str, bool]:
        """Detect domain flags in text."""
        text_lower = text.lower()
        domain_flags = {}

        for domain, keywords in self.domain_keywords.items():
            domain_flags[domain] = any(keyword in text_lower for keyword in keywords)

        return domain_flags

    def _calculate_novelty(self, text: str, history_stats: HistoryStats) -> float:
        """Calculate novelty score based on historical data."""
        # Simple heuristic: higher novelty for longer text and complex patterns
        base_novelty = min(len(text) / 1000, 1.0)

        # Adjust based on historical success rate
        if history_stats.total_runs > 0:
            success_rate = history_stats.success_rate
            # Lower success rate indicates higher novelty
            novelty_adjustment = (1.0 - success_rate) * 0.3
            base_novelty = min(base_novelty + novelty_adjustment, 1.0)

        return base_novelty

    def _extract_reasoning_keywords(self, text: str) -> List[str]:
        """Extract reasoning keywords from text."""
        text_lower = text.lower()
        found_keywords = []

        for keyword in self.reasoning_keywords:
            if keyword in text_lower:
                found_keywords.append(keyword)

        return found_keywords

    def _count_entities(self, text: str) -> int:
        """Count entities in text."""
        # Simple entity detection
        email_pattern = r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"
        phone_pattern = r"\b\d{3}[-.]?\d{3}[-.]?\d{4}\b"
        url_pattern = r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+"

        entities = 0
        entities += len(re.findall(email_pattern, text))
        entities += len(re.findall(phone_pattern, text))
        entities += len(re.findall(url_pattern, text))

        return entities

    def _calculate_format_strictness(self, request: RouterDecisionRequest) -> float:
        """Calculate format strictness requirement."""
        text = request.requirement.lower()

        strictness = 0.0

        # Check for specific format requirements
        if "exact" in text or "precise" in text:
            strictness += 0.3
        if "format" in text or "structure" in text:
            strictness += 0.2
        if "json" in text or "xml" in text or "csv" in text:
            strictness += 0.3
        if "template" in text or "pattern" in text:
            strictness += 0.2

        return min(strictness, 1.0)
