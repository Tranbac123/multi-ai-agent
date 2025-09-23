"""Golden tasks for FAQ handling evaluation."""

from typing import Dict, Any, List
from dataclasses import dataclass
from uuid import UUID


@dataclass
class GoldenTask:
    """Golden task definition."""

    task_id: str
    category: str
    input_text: str
    expected_response: str
    expected_intent: str
    expected_confidence: float
    expected_tools: List[str]
    metadata: Dict[str, Any]


# FAQ Golden Tasks
FAQ_TASKS = [
    GoldenTask(
        task_id="faq_001",
        category="faq",
        input_text="What are your business hours?",
        expected_response="Our business hours are Monday to Friday, 9 AM to 6 PM EST.",
        expected_intent="business_hours",
        expected_confidence=0.9,
        expected_tools=["knowledge_base_tool"],
        metadata={"difficulty": "easy", "domain": "general", "expected_tier": "SLM_A"},
    ),
    GoldenTask(
        task_id="faq_002",
        category="faq",
        input_text="How do I reset my password?",
        expected_response="To reset your password, click on 'Forgot Password' on the login page and follow the instructions sent to your email.",
        expected_intent="password_reset",
        expected_confidence=0.95,
        expected_tools=["knowledge_base_tool"],
        metadata={"difficulty": "easy", "domain": "account", "expected_tier": "SLM_A"},
    ),
    GoldenTask(
        task_id="faq_003",
        category="faq",
        input_text="What is your refund policy?",
        expected_response="We offer a 30-day money-back guarantee for all purchases. Refunds are processed within 5-7 business days.",
        expected_intent="refund_policy",
        expected_confidence=0.9,
        expected_tools=["knowledge_base_tool"],
        metadata={"difficulty": "easy", "domain": "billing", "expected_tier": "SLM_A"},
    ),
    GoldenTask(
        task_id="faq_004",
        category="faq",
        input_text="How do I integrate your API with my application?",
        expected_response="You can integrate our API by following these steps: 1) Get your API key from the dashboard, 2) Review our API documentation, 3) Make authenticated requests to our endpoints. We provide SDKs for Python, JavaScript, and Java.",
        expected_intent="api_integration",
        expected_confidence=0.85,
        expected_tools=["knowledge_base_tool", "documentation_tool"],
        metadata={
            "difficulty": "medium",
            "domain": "technical",
            "expected_tier": "SLM_B",
        },
    ),
    GoldenTask(
        task_id="faq_005",
        category="faq",
        input_text="What security measures do you have in place?",
        expected_response="We implement multiple security measures including: end-to-end encryption, SOC 2 compliance, regular security audits, two-factor authentication, and data encryption at rest and in transit.",
        expected_intent="security_info",
        expected_confidence=0.9,
        expected_tools=["knowledge_base_tool"],
        metadata={
            "difficulty": "medium",
            "domain": "security",
            "expected_tier": "SLM_B",
        },
    ),
]


def get_faq_tasks() -> List[GoldenTask]:
    """Get all FAQ golden tasks."""
    return FAQ_TASKS


def get_faq_task_by_id(task_id: str) -> GoldenTask:
    """Get FAQ task by ID."""
    for task in FAQ_TASKS:
        if task.task_id == task_id:
            return task
    raise ValueError(f"Task {task_id} not found")


def get_faq_tasks_by_difficulty(difficulty: str) -> List[GoldenTask]:
    """Get FAQ tasks by difficulty level."""
    return [task for task in FAQ_TASKS if task.metadata.get("difficulty") == difficulty]


def get_faq_tasks_by_domain(domain: str) -> List[GoldenTask]:
    """Get FAQ tasks by domain."""
    return [task for task in FAQ_TASKS if task.metadata.get("domain") == domain]
