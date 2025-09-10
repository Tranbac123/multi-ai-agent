"""Router service core components."""

# Import Router v2 components
from .router_v2 import RouterV2
from .feature_extractor import FeatureExtractor, RouterFeatures, Tier
from .calibrated_classifier import CalibratedClassifier
from .bandit_policy import BanditPolicy
from .early_exit_escalation import EarlyExitEscalation
from .canary_manager import CanaryManager
from .metrics import MetricsCollector

__all__ = [
    "RouterV2",
    "FeatureExtractor",
    "RouterFeatures",
    "Tier",
    "CalibratedClassifier",
    "BanditPolicy",
    "EarlyExitEscalation",
    "CanaryManager",
    "MetricsCollector",
]
