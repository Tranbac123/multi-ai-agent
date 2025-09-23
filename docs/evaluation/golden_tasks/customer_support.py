"""Golden tasks for customer support evaluation."""

from typing import Dict, Any, List
from dataclasses import dataclass
from uuid import uuid4

from libs.contracts.agent import AgentSpec, AgentBudgets
from libs.contracts.router import RouterDecisionRequest, RouterTier


@dataclass
class GoldenTask:
    """Golden task for evaluation."""

    task_id: str
    name: str
    description: str
    input_data: Dict[str, Any]
    expected_output: Dict[str, Any]
    expected_tier: RouterTier
    expected_confidence: float
    expected_cost_usd: float
    expected_latency_ms: int
    category: str
    difficulty: str  # easy, medium, hard
    domain: str


class CustomerSupportGoldenTasks:
    """Golden tasks for customer support evaluation."""

    @staticmethod
    def get_tasks() -> List[GoldenTask]:
        """Get all customer support golden tasks."""
        return [
            # Easy tasks
            GoldenTask(
                task_id="cs_001",
                name="Simple Greeting",
                description="Customer says hello",
                input_data={
                    "user_message": "Hello",
                    "conversation_history": [],
                    "user_id": "user123",
                    "session_id": str(uuid4()),
                },
                expected_output={
                    "response": "Hello! How can I help you today?",
                    "confidence": 0.95,
                    "actions": ["greet"],
                },
                expected_tier=RouterTier.SLM_A,
                expected_confidence=0.9,
                expected_cost_usd=0.001,
                expected_latency_ms=100,
                category="greeting",
                difficulty="easy",
                domain="general",
            ),
            GoldenTask(
                task_id="cs_002",
                name="Order Status Inquiry",
                description="Customer asks about order status",
                input_data={
                    "user_message": "What's the status of my order #12345?",
                    "conversation_history": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi! How can I help you?"},
                    ],
                    "user_id": "user123",
                    "session_id": str(uuid4()),
                    "order_id": "12345",
                },
                expected_output={
                    "response": "Let me check the status of your order #12345.",
                    "confidence": 0.9,
                    "actions": ["check_order_status", "provide_order_info"],
                },
                expected_tier=RouterTier.SLM_B,
                expected_confidence=0.8,
                expected_cost_usd=0.005,
                expected_latency_ms=300,
                category="order_inquiry",
                difficulty="easy",
                domain="ecommerce",
            ),
            # Medium tasks
            GoldenTask(
                task_id="cs_003",
                name="Product Recommendation",
                description="Customer asks for product recommendations",
                input_data={
                    "user_message": "I'm looking for a laptop under $1000 for programming. What do you recommend?",
                    "conversation_history": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi! How can I help you?"},
                    ],
                    "user_id": "user123",
                    "session_id": str(uuid4()),
                    "budget": 1000,
                    "use_case": "programming",
                },
                expected_output={
                    "response": "Based on your budget and programming needs, I recommend...",
                    "confidence": 0.8,
                    "actions": [
                        "search_products",
                        "filter_by_budget",
                        "provide_recommendations",
                    ],
                },
                expected_tier=RouterTier.SLM_B,
                expected_confidence=0.7,
                expected_cost_usd=0.008,
                expected_latency_ms=500,
                category="product_recommendation",
                difficulty="medium",
                domain="ecommerce",
            ),
            GoldenTask(
                task_id="cs_004",
                name="Return Request",
                description="Customer wants to return a product",
                input_data={
                    "user_message": "I want to return this laptop. It's not working properly and I'm still within the return window.",
                    "conversation_history": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi! How can I help you?"},
                    ],
                    "user_id": "user123",
                    "session_id": str(uuid4()),
                    "product": "laptop",
                    "issue": "not working properly",
                    "return_window": "within",
                },
                expected_output={
                    "response": "I'll help you process the return. Let me check your order details and return policy.",
                    "confidence": 0.85,
                    "actions": [
                        "check_order_details",
                        "verify_return_policy",
                        "initiate_return",
                    ],
                },
                expected_tier=RouterTier.SLM_B,
                expected_confidence=0.75,
                expected_cost_usd=0.006,
                expected_latency_ms=400,
                category="return_request",
                difficulty="medium",
                domain="ecommerce",
            ),
            # Hard tasks
            GoldenTask(
                task_id="cs_005",
                name="Complex Technical Issue",
                description="Customer has complex technical problem",
                input_data={
                    "user_message": "My laptop keeps crashing when I run Docker containers. I've tried updating drivers, reinstalling Docker, and checking system resources. The error logs show 'container runtime error' but I can't find the root cause. Can you help me troubleshoot this?",
                    "conversation_history": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi! How can I help you?"},
                    ],
                    "user_id": "user123",
                    "session_id": str(uuid4()),
                    "issue": "Docker container crashes",
                    "troubleshooting_steps": [
                        "updated drivers",
                        "reinstalled Docker",
                        "checked resources",
                    ],
                    "error_logs": "container runtime error",
                },
                expected_output={
                    "response": "This is a complex technical issue. Let me help you troubleshoot step by step...",
                    "confidence": 0.7,
                    "actions": [
                        "analyze_error_logs",
                        "check_system_compatibility",
                        "provide_troubleshooting_steps",
                        "escalate_to_technical_team",
                    ],
                },
                expected_tier=RouterTier.LLM,
                expected_confidence=0.6,
                expected_cost_usd=0.02,
                expected_latency_ms=1000,
                category="technical_support",
                difficulty="hard",
                domain="technical",
            ),
            GoldenTask(
                task_id="cs_006",
                name="Billing Dispute",
                description="Customer disputes billing charges",
                input_data={
                    "user_message": "I was charged $299 for a service I never ordered. I've been a customer for 3 years and this is the first time this has happened. I need this resolved immediately and I want to speak to a manager.",
                    "conversation_history": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi! How can I help you?"},
                    ],
                    "user_id": "user123",
                    "session_id": str(uuid4()),
                    "disputed_amount": 299,
                    "service": "unknown",
                    "customer_tenure": "3 years",
                    "urgency": "immediate",
                    "request": "speak to manager",
                },
                expected_output={
                    "response": "I understand your concern about the unauthorized charge. Let me investigate this immediately and connect you with a manager.",
                    "confidence": 0.8,
                    "actions": [
                        "investigate_billing",
                        "escalate_to_manager",
                        "provide_refund",
                        "update_account_security",
                    ],
                },
                expected_tier=RouterTier.LLM,
                expected_confidence=0.7,
                expected_cost_usd=0.025,
                expected_latency_ms=1200,
                category="billing_dispute",
                difficulty="hard",
                domain="finance",
            ),
            # Edge cases
            GoldenTask(
                task_id="cs_007",
                name="Multilingual Request",
                description="Customer writes in non-English",
                input_data={
                    "user_message": "Hola, necesito ayuda con mi pedido. ¿Pueden ayudarme?",
                    "conversation_history": [],
                    "user_id": "user123",
                    "session_id": str(uuid4()),
                    "language": "spanish",
                },
                expected_output={
                    "response": "Hello! I can help you with your order. Let me assist you in English.",
                    "confidence": 0.6,
                    "actions": [
                        "detect_language",
                        "provide_translation",
                        "continue_in_english",
                    ],
                },
                expected_tier=RouterTier.SLM_B,
                expected_confidence=0.6,
                expected_cost_usd=0.007,
                expected_latency_ms=600,
                category="multilingual",
                difficulty="medium",
                domain="general",
            ),
            GoldenTask(
                task_id="cs_008",
                name="Ambiguous Request",
                description="Customer request is unclear",
                input_data={
                    "user_message": "I need help with something",
                    "conversation_history": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi! How can I help you?"},
                    ],
                    "user_id": "user123",
                    "session_id": str(uuid4()),
                },
                expected_output={
                    "response": "I'd be happy to help! Could you please provide more details about what you need assistance with?",
                    "confidence": 0.5,
                    "actions": [
                        "ask_for_clarification",
                        "provide_general_help_options",
                    ],
                },
                expected_tier=RouterTier.SLM_A,
                expected_confidence=0.5,
                expected_cost_usd=0.003,
                expected_latency_ms=200,
                category="clarification",
                difficulty="easy",
                domain="general",
            ),
        ]

    @staticmethod
    def get_tasks_by_difficulty(difficulty: str) -> List[GoldenTask]:
        """Get tasks by difficulty level."""
        tasks = CustomerSupportGoldenTasks.get_tasks()
        return [task for task in tasks if task.difficulty == difficulty]

    @staticmethod
    def get_tasks_by_domain(domain: str) -> List[GoldenTask]:
        """Get tasks by domain."""
        tasks = CustomerSupportGoldenTasks.get_tasks()
        return [task for task in tasks if task.domain == domain]

    @staticmethod
    def get_tasks_by_category(category: str) -> List[GoldenTask]:
        """Get tasks by category."""
        tasks = CustomerSupportGoldenTasks.get_tasks()
        return [task for task in tasks if task.category == category]
