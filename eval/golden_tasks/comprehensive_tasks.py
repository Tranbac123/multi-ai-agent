"""Comprehensive golden tasks for evaluation suite."""

from typing import List, Dict, Any
from enum import Enum
from dataclasses import dataclass
from eval.golden_tasks.faq_tasks import GoldenTask


class TaskCategory(Enum):
    """Task categories."""
    FAQ = "faq"
    ORDER = "order"
    TRACKING = "tracking"
    LEAD = "lead"


class TaskDifficulty(Enum):
    """Task difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    EXPERT = "expert"


class ExpectedTier(Enum):
    """Expected AI tier for task completion."""
    SLM_A = "SLM_A"
    SLM_B = "SLM_B"
    LLM_C = "LLM_C"


def get_all_tasks() -> List[GoldenTask]:
    """Get all golden tasks for evaluation."""
    tasks = []
    
    # FAQ Tasks
    tasks.extend([
        GoldenTask(
            task_id="faq_001",
            category="faq",
            input_text="What is your return policy?",
            expected_response="Our return policy allows returns within 30 days of purchase with a valid receipt.",
            expected_intent="return_policy",
            expected_confidence=0.9,
            expected_tools=[],
            metadata={"difficulty": "easy", "domain": "customer_service", "subdomain": "returns", "expected_tier": "SLM_A"}
        ),
        GoldenTask(
            task_id="faq_002",
            category="faq",
            input_text="How do I track my order?",
            expected_response="You can track your order using the tracking number sent to your email or by logging into your account.",
            expected_intent="order_tracking",
            expected_confidence=0.9,
            expected_tools=[],
            metadata={"difficulty": "easy", "domain": "customer_service", "subdomain": "orders", "expected_tier": "SLM_A"}
        ),
        GoldenTask(
            task_id="faq_003",
            category="faq",
            input_text="What are the different payment methods you accept?",
            expected_response="We accept credit cards (Visa, MasterCard, American Express), PayPal, Apple Pay, Google Pay, and bank transfers.",
            expected_intent="payment_methods",
            expected_confidence=0.85,
            expected_tools=[],
            metadata={"difficulty": "medium", "domain": "customer_service", "subdomain": "payments", "expected_tier": "SLM_B"}
        )
    ])
    
    # Order Tasks
    tasks.extend([
        GoldenTask(
            task_id="order_001",
            category="order",
            input_text="I want to place an order for 2 units of product ABC123",
            expected_response="I'll help you place an order for 2 units of product ABC123. Let me check availability and pricing for you.",
            expected_intent="place_order",
            expected_confidence=0.95,
            expected_tools=["inventory_check", "pricing_engine"],
            metadata={"difficulty": "easy", "domain": "sales", "subdomain": "order_placement", "expected_tier": "SLM_A"}
        ),
        GoldenTask(
            task_id="order_002",
            category="order",
            input_text="Can you modify my existing order #12345 to add 1 more unit of product XYZ789?",
            expected_response="I can help you modify order #12345. Let me check if the order can still be modified and add 1 unit of product XYZ789. This may affect the shipping date and total cost.",
            expected_intent="modify_order",
            expected_confidence=0.85,
            expected_tools=["order_lookup", "inventory_check", "pricing_engine"],
            metadata={"difficulty": "medium", "domain": "sales", "subdomain": "order_modification", "expected_tier": "SLM_B"}
        )
    ])
    
    # Tracking Tasks
    tasks.extend([
        GoldenTask(
            task_id="tracking_001",
            category="tracking",
            input_text="Where is my order #12345?",
            expected_response="Let me check the status of your order #12345. It was shipped on [date] and is currently in transit. Expected delivery is [date].",
            expected_intent="order_status",
            expected_confidence=0.9,
            expected_tools=["order_lookup", "shipping_tracker"],
            metadata={"difficulty": "easy", "domain": "logistics", "subdomain": "order_tracking", "expected_tier": "SLM_A"}
        )
    ])
    
    # Lead Tasks
    tasks.extend([
        GoldenTask(
            task_id="lead_001",
            category="lead",
            input_text="I'm interested in your enterprise solutions. Can you send me more information?",
            expected_response="I'd be happy to provide information about our enterprise solutions. Let me gather some details about your company and requirements so I can send you the most relevant information.",
            expected_intent="lead_generation",
            expected_confidence=0.9,
            expected_tools=["crm_contact", "email_sender"],
            metadata={"difficulty": "easy", "domain": "sales", "subdomain": "lead_generation", "expected_tier": "SLM_A"}
        )
    ])
    
    return tasks


def get_tasks_by_category(category: TaskCategory) -> List[GoldenTask]:
    """Get tasks filtered by category."""
    return [task for task in get_all_tasks() if task.category == category.value]


def get_tasks_by_difficulty(difficulty: TaskDifficulty) -> List[GoldenTask]:
    """Get tasks filtered by difficulty."""
    return [task for task in get_all_tasks() if task.metadata.get("difficulty") == difficulty.value]


def get_tasks_by_tier(tier: ExpectedTier) -> List[GoldenTask]:
    """Get tasks filtered by expected tier."""
    return [task for task in get_all_tasks() if task.metadata.get("expected_tier") == tier.value]


def get_high_priority_tasks() -> List[GoldenTask]:
    """Get high priority tasks for evaluation."""
    # Return a mix of easy and medium difficulty tasks
    all_tasks = get_all_tasks()
    return [task for task in all_tasks if task.metadata.get("difficulty") in ["easy", "medium"]]


def get_tasks_by_domain(domain: str) -> List[GoldenTask]:
    """Get tasks filtered by domain."""
    return [task for task in get_all_tasks() if task.metadata.get("domain") == domain]


def get_tasks_by_subdomain(subdomain: str) -> List[GoldenTask]:
    """Get tasks filtered by subdomain."""
    return [task for task in get_all_tasks() if task.metadata.get("subdomain") == subdomain]


def get_tasks_by_confidence_threshold(min_confidence: float) -> List[GoldenTask]:
    """Get tasks with minimum confidence threshold."""
    return [task for task in get_all_tasks() if task.expected_confidence >= min_confidence]


def get_tasks_requiring_tools() -> List[GoldenTask]:
    """Get tasks that require tool usage."""
    return [task for task in get_all_tasks() if task.expected_tools]


def get_tasks_by_metadata(key: str, value: Any) -> List[GoldenTask]:
    """Get tasks filtered by metadata key-value pair."""
    return [task for task in get_all_tasks() if task.metadata.get(key) == value]
