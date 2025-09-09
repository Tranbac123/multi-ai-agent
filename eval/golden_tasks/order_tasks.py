"""Golden tasks for order handling evaluation."""

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


# Order Golden Tasks
ORDER_TASKS = [
    GoldenTask(
        task_id="order_001",
        category="order",
        input_text="I want to place an order for 2 units of Product A",
        expected_response="I'll help you place an order for 2 units of Product A. Let me check availability and pricing for you.",
        expected_intent="place_order",
        expected_confidence=0.95,
        expected_tools=["product_db_tool", "order_tool"],
        metadata={
            "difficulty": "medium",
            "domain": "ecommerce",
            "expected_tier": "SLM_B",
            "expected_actions": ["check_inventory", "calculate_price", "create_order"]
        }
    ),
    GoldenTask(
        task_id="order_002",
        category="order",
        input_text="What's the status of my order #12345?",
        expected_response="Let me check the status of your order #12345. I'll look up the current status and provide you with the details.",
        expected_intent="order_status",
        expected_confidence=0.9,
        expected_tools=["order_tool"],
        metadata={
            "difficulty": "easy",
            "domain": "ecommerce",
            "expected_tier": "SLM_A",
            "expected_actions": ["lookup_order", "provide_status"]
        }
    ),
    GoldenTask(
        task_id="order_003",
        category="order",
        input_text="I need to cancel my order #12345 and get a refund",
        expected_response="I understand you want to cancel order #12345 and receive a refund. Let me check the order status and process the cancellation for you.",
        expected_intent="cancel_order",
        expected_confidence=0.9,
        expected_tools=["order_tool", "payment_tool"],
        metadata={
            "difficulty": "medium",
            "domain": "ecommerce",
            "expected_tier": "SLM_B",
            "expected_actions": ["verify_order", "cancel_order", "process_refund"]
        }
    ),
    GoldenTask(
        task_id="order_004",
        category="order",
        input_text="Can you modify my order to change the shipping address?",
        expected_response="I can help you modify the shipping address for your order. Let me check if the order can still be modified and update the address for you.",
        expected_intent="modify_order",
        expected_confidence=0.85,
        expected_tools=["order_tool"],
        metadata={
            "difficulty": "medium",
            "domain": "ecommerce",
            "expected_tier": "SLM_B",
            "expected_actions": ["check_modification_eligibility", "update_address"]
        }
    ),
    GoldenTask(
        task_id="order_005",
        category="order",
        input_text="I want to return an item from my recent order",
        expected_response="I'll help you process a return for an item from your recent order. Let me check the return policy and guide you through the process.",
        expected_intent="return_item",
        expected_confidence=0.9,
        expected_tools=["order_tool", "knowledge_base_tool"],
        metadata={
            "difficulty": "medium",
            "domain": "ecommerce",
            "expected_tier": "SLM_B",
            "expected_actions": ["check_return_policy", "initiate_return", "generate_return_label"]
        }
    ),
    GoldenTask(
        task_id="order_006",
        category="order",
        input_text="What's the estimated delivery time for orders to New York?",
        expected_response="For orders shipped to New York, the estimated delivery time is 2-3 business days for standard shipping and 1-2 business days for express shipping.",
        expected_intent="delivery_info",
        expected_confidence=0.9,
        expected_tools=["knowledge_base_tool"],
        metadata={
            "difficulty": "easy",
            "domain": "shipping",
            "expected_tier": "SLM_A",
            "expected_actions": ["lookup_shipping_info"]
        }
    ),
    GoldenTask(
        task_id="order_007",
        category="order",
        input_text="I need to track multiple orders and see their combined status",
        expected_response="I can help you track multiple orders and provide a combined status overview. Please provide the order numbers and I'll check their current status.",
        expected_intent="bulk_order_tracking",
        expected_confidence=0.8,
        expected_tools=["order_tool"],
        metadata={
            "difficulty": "hard",
            "domain": "ecommerce",
            "expected_tier": "LLM",
            "expected_actions": ["lookup_multiple_orders", "aggregate_status", "present_summary"]
        }
    ),
    GoldenTask(
        task_id="order_008",
        category="order",
        input_text="Can you help me reorder the same items I bought last month?",
        expected_response="I can help you reorder items from your previous purchase. Let me look up your order history and recreate the order with the same items.",
        expected_intent="reorder",
        expected_confidence=0.9,
        expected_tools=["order_tool", "product_db_tool"],
        metadata={
            "difficulty": "medium",
            "domain": "ecommerce",
            "expected_tier": "SLM_B",
            "expected_actions": ["lookup_order_history", "identify_items", "create_new_order"]
        }
    )
]


def get_order_tasks() -> List[GoldenTask]:
    """Get all order golden tasks."""
    return ORDER_TASKS


def get_order_task_by_id(task_id: str) -> GoldenTask:
    """Get order task by ID."""
    for task in ORDER_TASKS:
        if task.task_id == task_id:
            return task
    raise ValueError(f"Task {task_id} not found")


def get_order_tasks_by_difficulty(difficulty: str) -> List[GoldenTask]:
    """Get order tasks by difficulty level."""
    return [task for task in ORDER_TASKS if task.metadata.get("difficulty") == difficulty]


def get_order_tasks_by_domain(domain: str) -> List[GoldenTask]:
    """Get order tasks by domain."""
    return [task for task in ORDER_TASKS if task.metadata.get("domain") == domain]
