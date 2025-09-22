"""Test modes and cassette management."""

import os
import json
import asyncio
from enum import Enum
from typing import Dict, Any, Optional, List
from pathlib import Path


class TestMode(Enum):
    """Test execution modes."""
    MOCK = "mock"           # Use mocked services
    GOLDEN = "golden"       # Use seeded data with temp=0
    LIVE_SMOKE = "live_smoke"  # Use live services for smoke tests


class CassetteManager:
    """Manages test cassettes for recording and playback."""
    
    def __init__(self, cassette_dir: str = "tests/_fixtures/cassettes"):
        self.cassette_dir = Path(cassette_dir)
        self.cassette_dir.mkdir(parents=True, exist_ok=True)
        self.current_cassette: Optional[str] = None
        self.recorded_interactions: List[Dict[str, Any]] = []
    
    def start_recording(self, cassette_name: str) -> None:
        """Start recording interactions to a cassette."""
        self.current_cassette = cassette_name
        self.recorded_interactions = []
    
    def record_interaction(self, request: Dict[str, Any], response: Dict[str, Any]) -> None:
        """Record an interaction between services."""
        interaction = {
            "timestamp": asyncio.get_event_loop().time(),
            "request": request,
            "response": response
        }
        self.recorded_interactions.append(interaction)
    
    def save_cassette(self) -> None:
        """Save the recorded interactions to a cassette file."""
        if not self.current_cassette or not self.recorded_interactions:
            return
        
        cassette_file = self.cassette_dir / f"{self.current_cassette}.json"
        with open(cassette_file, 'w') as f:
            json.dump({
                "cassette_name": self.current_cassette,
                "interactions": self.recorded_interactions
            }, f, indent=2)
    
    def load_cassette(self, cassette_name: str) -> List[Dict[str, Any]]:
        """Load interactions from a cassette file."""
        cassette_file = self.cassette_dir / f"{cassette_name}.json"
        
        if not cassette_file.exists():
            return []
        
        with open(cassette_file, 'r') as f:
            data = json.load(f)
            return data.get("interactions", [])
    
    def normalize_interaction(self, interaction: Dict[str, Any]) -> Dict[str, Any]:
        """Normalize interaction data for comparison."""
        normalized = interaction.copy()
        
        # Remove timestamp for comparison
        if "timestamp" in normalized:
            del normalized["timestamp"]
        
        # Normalize request
        if "request" in normalized:
            request = normalized["request"].copy()
            # Remove non-deterministic fields
            for field in ["timestamp", "request_id", "session_id"]:
                if field in request:
                    request[field] = "[NORMALIZED]"
            normalized["request"] = request
        
        return normalized


class TestModeManager:
    """Manages test mode configuration and execution."""
    
    def __init__(self):
        self.current_mode = TestMode.MOCK
        self.cassette_manager = CassetteManager()
        self.mode_config = {
            TestMode.MOCK: {
                "use_real_services": False,
                "use_cassettes": True,
                "deterministic": True,
                "fast": True
            },
            TestMode.GOLDEN: {
                "use_real_services": False,
                "use_cassettes": True,
                "deterministic": True,
                "fast": True,
                "seeded_data": True,
                "temperature": 0.0
            },
            TestMode.LIVE_SMOKE: {
                "use_real_services": True,
                "use_cassettes": False,
                "deterministic": False,
                "fast": False,
                "smoke_test": True
            }
        }
    
    def set_mode(self, mode: TestMode) -> None:
        """Set the current test mode."""
        self.current_mode = mode
    
    def get_mode_config(self) -> Dict[str, Any]:
        """Get configuration for current mode."""
        return self.mode_config[self.current_mode]
    
    def should_use_real_service(self, service_name: str) -> bool:
        """Check if real service should be used for current mode."""
        config = self.get_mode_config()
        
        # In LIVE_SMOKE mode, use real services
        if config["use_real_services"]:
            return True
        
        # In other modes, check if service is in live services list
        live_services = os.getenv("LIVE_SERVICES", "").split(",")
        return service_name in live_services
    
    def should_record_cassette(self) -> bool:
        """Check if interactions should be recorded to cassette."""
        return not self.get_mode_config()["use_cassettes"]
    
    def is_deterministic(self) -> bool:
        """Check if current mode should produce deterministic results."""
        return self.get_mode_config()["deterministic"]
    
    def is_fast(self) -> bool:
        """Check if current mode should be fast."""
        return self.get_mode_config()["fast"]


# Global test mode manager instance
test_mode_manager = TestModeManager()


def get_test_mode() -> TestMode:
    """Get the current test mode."""
    return test_mode_manager.current_mode


def set_test_mode(mode: TestMode) -> None:
    """Set the current test mode."""
    test_mode_manager.set_mode(mode)


def should_mock_service(service_name: str) -> bool:
    """Check if a service should be mocked."""
    return not test_mode_manager.should_use_real_service(service_name)


def get_cassette_manager() -> CassetteManager:
    """Get the cassette manager instance."""
    return test_mode_manager.cassette_manager
