"""ML Classifier for router decisions."""

import asyncio
import pickle
from typing import Dict, Any, Optional
import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import StandardScaler
import structlog

from libs.contracts.router import TextFeatures, RouterTier

logger = structlog.get_logger(__name__)


class MLClassifier:
    """ML classifier for tier prediction."""

    def __init__(self, model_path: Optional[str] = None):
        self.model_path = model_path
        self.model = None
        self.scaler = None
        self.feature_names = [
            "token_count",
            "json_schema_complexity",
            "novelty_score",
            "historical_failure_rate",
            "entity_count",
            "format_strictness",
            "has_finance",
            "has_legal",
            "has_medical",
            "has_ecommerce",
        ]
        self.tier_mapping = {
            0: RouterTier.SLM_A,
            1: RouterTier.SLM_B,
            2: RouterTier.LLM,
        }

    def initialize(self):
        """Initialize classifier."""
        try:
            if self.model_path:
                self._load_model()
            else:
                self._create_baseline_model()

            logger.info("ML classifier initialized successfully")
        except Exception as e:
            logger.error("Failed to initialize ML classifier", error=str(e))
            self._create_baseline_model()

    def _load_model(self):
        """Load trained model from file."""
        try:
            with open(self.model_path, "rb") as f:
                model_data = pickle.load(f)
                self.model = model_data["model"]
                self.scaler = model_data["scaler"]

            logger.info("Loaded trained model", model_path=self.model_path)
        except Exception as e:
            logger.warning("Failed to load model, using baseline", error=str(e))
            self._create_baseline_model()

    def _create_baseline_model(self):
        """Create baseline model for fallback."""
        # Create a simple baseline model
        self.model = RandomForestClassifier(
            n_estimators=10, max_depth=5, random_state=42
        )
        self.scaler = StandardScaler()

        # Train on synthetic data
        self._train_baseline()

        logger.info("Created baseline model")

    def _train_baseline(self):
        """Train baseline model on synthetic data."""
        # Generate synthetic training data
        n_samples = 1000
        X = np.random.rand(n_samples, len(self.feature_names))

        # Create synthetic labels based on heuristics
        y = np.zeros(n_samples)
        for i in range(n_samples):
            # Simple heuristics for tier assignment
            if X[i, 0] < 0.3 and X[i, 1] < 0.3:  # Low tokens, low complexity
                y[i] = 0  # SLM_A
            elif X[i, 0] < 0.7 and X[i, 1] < 0.7:  # Medium tokens, medium complexity
                y[i] = 1  # SLM_B
            else:
                y[i] = 2  # LLM

        # Train model
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)

    async def predict(self, features: TextFeatures) -> Dict[str, float]:
        """Predict tier probabilities."""
        try:
            # Convert features to array
            feature_array = self._features_to_array(features)

            # Scale features
            feature_array_scaled = self.scaler.transform([feature_array])

            # Get probabilities
            probabilities = self.model.predict_proba(feature_array_scaled)[0]

            # Convert to tier names
            tier_probs = {}
            for i, prob in enumerate(probabilities):
                tier = self.tier_mapping[i]
                tier_probs[tier.value] = float(prob)

            return tier_probs

        except Exception as e:
            logger.error("Prediction failed", error=str(e))
            # Return default probabilities
            return {
                RouterTier.SLM_A.value: 0.4,
                RouterTier.SLM_B.value: 0.4,
                RouterTier.LLM.value: 0.2,
            }

    def _features_to_array(self, features: TextFeatures) -> np.ndarray:
        """Convert TextFeatures to numpy array."""
        return np.array(
            [
                features.token_count / 1000,  # Normalize token count
                features.json_schema_complexity,
                features.novelty_score,
                features.historical_failure_rate,
                features.entity_count / 10,  # Normalize entity count
                features.format_strictness,
                float(features.domain_flags.get("finance", False)),
                float(features.domain_flags.get("legal", False)),
                float(features.domain_flags.get("medical", False)),
                float(features.domain_flags.get("ecommerce", False)),
            ]
        )

    async def train(self, X: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        """Train classifier on new data."""
        try:
            # Scale features
            X_scaled = self.scaler.fit_transform(X)

            # Train model
            self.model.fit(X_scaled, y)

            # Calculate accuracy
            accuracy = self.model.score(X_scaled, y)

            logger.info("Model trained successfully", accuracy=accuracy)

            return {"accuracy": accuracy, "n_samples": len(X), "n_features": X.shape[1]}

        except Exception as e:
            logger.error("Training failed", error=str(e))
            raise

    async def save_model(self, path: str) -> None:
        """Save trained model to file."""
        try:
            model_data = {
                "model": self.model,
                "scaler": self.scaler,
                "feature_names": self.feature_names,
                "tier_mapping": self.tier_mapping,
            }

            with open(path, "wb") as f:
                pickle.dump(model_data, f)

            logger.info("Model saved successfully", path=path)

        except Exception as e:
            logger.error("Failed to save model", error=str(e))
            raise
