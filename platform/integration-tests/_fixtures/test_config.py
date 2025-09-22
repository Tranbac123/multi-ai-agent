"""Test configuration and modes."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional
import os

class TestMode(Enum):
    """Test execution modes."""
    MOCK = "mock"
    GOLDEN = "golden"
    LIVE_SMOKE = "live_smoke"

@dataclass
class TestConfig:
    """Test configuration."""
    mode: TestMode
    temperature: float
    seed: int
    normalize_outputs: bool
    cassette_dir: str
    golden_dir: str
    
    @classmethod
    def from_env(cls) -> 'TestConfig':
        """Load configuration from environment variables."""
        mode_str = os.getenv('TEST_MODE', 'mock').lower()
        mode = TestMode.MOCK
        if mode_str == 'golden':
            mode = TestMode.GOLDEN
        elif mode_str == 'live_smoke':
            mode = TestMode.LIVE_SMOKE
        
        return cls(
            mode=mode,
            temperature=float(os.getenv('TEST_TEMPERATURE', '0.0')),
            seed=int(os.getenv('TEST_SEED', '42')),
            normalize_outputs=os.getenv('TEST_NORMALIZE_OUTPUTS', 'true').lower() == 'true',
            cassette_dir=os.getenv('TEST_CASSETTE_DIR', 'tests/_fixtures/cassettes'),
            golden_dir=os.getenv('TEST_GOLDEN_DIR', 'tests/_fixtures/golden')
        )
