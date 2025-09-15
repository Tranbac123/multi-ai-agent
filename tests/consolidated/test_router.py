import pytest
from app.agent.router import IntentRouter


class TestIntentRouter:
    def setup_method(self):
        self.router = IntentRouter()

    def test_heuristic_routing_order(self):
        """Test heuristic routing for order-related messages"""
        message = "I want to buy a t-shirt size M"
        route_type, workflow = self.router.route(message)

        assert route_type == "WORKFLOW"
        assert workflow == "ORDER_FLOW"

    def test_heuristic_routing_tracking(self):
        """Test heuristic routing for tracking messages"""
        message = "Where is my order #12345?"
        route_type, workflow = self.router.route(message)

        assert route_type == "WORKFLOW"
        assert workflow == "TRACKING_FLOW"

    def test_heuristic_routing_faq(self):
        """Test heuristic routing for FAQ messages"""
        message = "What is your return policy?"
        route_type, workflow = self.router.route(message)

        assert route_type == "WORKFLOW"
        assert workflow == "FAQ_FLOW"

    def test_heuristic_routing_lead(self):
        """Test heuristic routing for lead capture messages"""
        message = "Can I speak to a human representative?"
        route_type, workflow = self.router.route(message)

        assert route_type == "WORKFLOW"
        assert workflow == "LEAD_CAPTURE_FLOW"

    def test_confidence_scoring(self):
        """Test confidence scoring for workflows"""
        message = "I want to buy a t-shirt size M"
        confidence = self.router.get_confidence_score(message, "ORDER_FLOW")

        assert confidence > 0.0
        assert confidence <= 1.0

    def test_complex_message_routing(self):
        """Test that complex messages route to agent"""
        message = "I have a very complex issue that requires multiple steps and detailed analysis"
        route_type, workflow = self.router.route(message)

        assert route_type == "AGENT"
        assert workflow is None


if __name__ == "__main__":
    pytest.main([__file__])
