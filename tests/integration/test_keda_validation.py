"""Integration tests for KEDA configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestKEDAValidation:
    """Test KEDA configuration validation."""

    def test_keda_scaled_objects_have_required_fields(self):
        """Test all KEDA ScaledObjects have required fields."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]

        for scaled_object in scaled_objects:
            spec = scaled_object["spec"]

            # Required fields
            assert "scaleTargetRef" in spec
            assert "name" in spec["scaleTargetRef"]
            assert "minReplicaCount" in spec
            assert "maxReplicaCount" in spec
            assert "triggers" in spec
            assert len(spec["triggers"]) > 0

            # Validate replica counts
            assert spec["minReplicaCount"] >= 1
            assert spec["maxReplicaCount"] >= spec["minReplicaCount"]
            assert spec["maxReplicaCount"] <= 50  # Reasonable upper limit

    def test_nats_jetstream_triggers_configured(self):
        """Test NATS JetStream triggers are properly configured."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]

        for scaled_object in scaled_objects:
            triggers = scaled_object["spec"]["triggers"]

            for trigger in triggers:
                if trigger["type"] == "nats-jetstream":
                    # Required NATS JetStream fields
                    assert "metadata" in trigger
                    metadata = trigger["metadata"]

                    assert "natsServerMonitoringEndpoint" in metadata
                    assert "account" in metadata
                    assert "stream" in metadata
                    assert "consumer" in metadata
                    assert "lagThreshold" in metadata

                    # Validate lag threshold is reasonable
                    lag_threshold = int(metadata["lagThreshold"])
                    assert lag_threshold > 0
                    assert lag_threshold <= 1000  # Reasonable upper limit

    def test_redis_triggers_configured(self):
        """Test Redis triggers are properly configured."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]

        for scaled_object in scaled_objects:
            triggers = scaled_object["spec"]["triggers"]

            for trigger in triggers:
                if trigger["type"] == "redis":
                    # Required Redis fields
                    assert "metadata" in trigger
                    metadata = trigger["metadata"]

                    assert "address" in metadata
                    assert "listName" in metadata
                    assert "listLength" in metadata

                    # Validate list length threshold
                    list_length = int(metadata["listLength"])
                    assert list_length > 0
                    assert list_length <= 1000  # Reasonable upper limit

    def test_scaled_objects_target_existing_deployments(self):
        """Test ScaledObjects target existing deployments."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        deployment_names = {d["metadata"]["name"] for d in deployments}

        # Get all ScaledObjects
        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]

        for scaled_object in scaled_objects:
            target_name = scaled_object["spec"]["scaleTargetRef"]["name"]
            assert (
                target_name in deployment_names
            ), f"ScaledObject {scaled_object['metadata']['name']} targets non-existent deployment {target_name}"

    def test_scaled_objects_have_unique_names(self):
        """Test ScaledObjects have unique names."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]
        names = [so["metadata"]["name"] for so in scaled_objects]

        assert len(names) == len(set(names)), "ScaledObject names must be unique"

    def test_scaled_objects_have_proper_namespace(self):
        """Test ScaledObjects are in the correct namespace."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]

        for scaled_object in scaled_objects:
            namespace = scaled_object["metadata"].get("namespace", "default")
            assert (
                namespace == "production"
            ), f"ScaledObject {scaled_object['metadata']['name']} should be in production namespace"

    def test_scaled_objects_have_proper_labels(self):
        """Test ScaledObjects have proper labels."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]

        for scaled_object in scaled_objects:
            labels = scaled_object["metadata"].get("labels", {})

            # Check required labels
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

    def test_scaled_objects_have_proper_annotations(self):
        """Test ScaledObjects have proper annotations."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]

        for scaled_object in scaled_objects:
            annotations = scaled_object["metadata"].get("annotations", {})

            # Check required annotations
            assert "description" in annotations
            assert "app.kubernetes.io/created-by" in annotations

    def test_scaled_objects_have_cooldown_periods(self):
        """Test ScaledObjects have cooldown periods configured."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]

        for scaled_object in scaled_objects:
            spec = scaled_object["spec"]

            # Check cooldown periods are configured
            if "cooldownPeriod" in spec:
                cooldown = int(spec["cooldownPeriod"])
                assert cooldown >= 0
                assert cooldown <= 300  # Max 5 minutes

            if "pollingInterval" in spec:
                polling = int(spec["pollingInterval"])
                assert polling >= 1
                assert polling <= 300  # Max 5 minutes
