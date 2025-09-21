"""Integration tests for autoscaling and security configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestAutoscalingSecurityValidation:
    """Test autoscaling and security configuration validation."""

    def test_all_configurations_are_valid_yaml(self):
        """Test all configurations are valid YAML."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            assert (
                len(docs) > 0
            ), f"File {file_path} should contain at least one document"

            # Check that all documents are valid
            for doc in docs:
                assert isinstance(
                    doc, dict
                ), f"Each document in {file_path} should be a dictionary"
                assert (
                    "apiVersion" in doc
                ), f"Each document in {file_path} should have apiVersion"
                assert "kind" in doc, f"Each document in {file_path} should have kind"
                assert (
                    "metadata" in doc
                ), f"Each document in {file_path} should have metadata"

    def test_all_configurations_have_valid_api_versions(self):
        """Test all configurations have valid API versions."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            # Check API versions
            for doc in docs:
                if "apiVersion" in doc:
                    api_version = doc["apiVersion"]
                    assert isinstance(api_version, str)
                    assert len(api_version) > 0
                    assert "/" in api_version or api_version.startswith("v")

    def test_all_configurations_have_valid_kinds(self):
        """Test all configurations have valid kinds."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        valid_kinds = [
            "Deployment",
            "Service",
            "ServiceAccount",
            "ClusterRole",
            "ClusterRoleBinding",
            "ScaledObject",
            "HorizontalPodAutoscaler",
            "ConfigMap",
            "Secret",
            "NetworkPolicy",
            "Namespace",
        ]

        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            # Check kinds
            for doc in docs:
                if "kind" in doc:
                    kind = doc["kind"]
                    assert kind in valid_kinds, f"Invalid kind {kind} in {file_path}"

    def test_all_configurations_have_valid_metadata(self):
        """Test all configurations have valid metadata."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            # Check metadata
            for doc in docs:
                if "metadata" in doc:
                    metadata = doc["metadata"]
                    assert "name" in metadata
                    assert isinstance(metadata["name"], str)
                    assert len(metadata["name"]) > 0
                    assert len(metadata["name"]) <= 63  # Kubernetes name length limit

    def test_all_configurations_have_no_duplicate_names(self):
        """Test all configurations have no duplicate names."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            # Check names
            names = []
            for doc in docs:
                if "metadata" in doc and "name" in doc["metadata"]:
                    name = doc["metadata"]["name"]
                    assert name not in names, f"Duplicate name {name} in {file_path}"
                    names.append(name)

    def test_all_configurations_have_valid_specs(self):
        """Test all configurations have valid specs."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            # Check specs
            for doc in docs:
                if "spec" in doc:
                    spec = doc["spec"]
                    assert isinstance(spec, dict)
                    assert len(spec) > 0

    def test_all_configurations_have_valid_labels(self):
        """Test all configurations have valid labels."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            # Check labels
            for doc in docs:
                if "metadata" in doc and "labels" in doc["metadata"]:
                    labels = doc["metadata"]["labels"]

                    # Check required labels
                    assert "app.kubernetes.io/name" in labels
                    assert "app.kubernetes.io/instance" in labels
                    assert "app.kubernetes.io/version" in labels
                    assert "app.kubernetes.io/component" in labels
                    assert "app.kubernetes.io/part-of" in labels
                    assert "app.kubernetes.io/managed-by" in labels

                    # Check label values are valid
                    for key, value in labels.items():
                        assert isinstance(key, str)
                        assert isinstance(value, str)
                        assert len(key) > 0
                        assert len(value) > 0
                        assert len(key) <= 63  # Kubernetes label key length limit
                        assert len(value) <= 63  # Kubernetes label value length limit

    def test_all_configurations_have_valid_annotations(self):
        """Test all configurations have valid annotations."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            # Check annotations
            for doc in docs:
                if "metadata" in doc and "annotations" in doc["metadata"]:
                    annotations = doc["metadata"]["annotations"]

                    # Check required annotations
                    assert "description" in annotations
                    assert "app.kubernetes.io/created-by" in annotations

                    # Check annotation values are valid
                    for key, value in annotations.items():
                        assert isinstance(key, str)
                        assert isinstance(value, str)
                        assert len(key) > 0
                        assert len(value) > 0
                        assert len(key) <= 63  # Kubernetes annotation key length limit
                        assert (
                            len(value) <= 262144
                        )  # Kubernetes annotation value length limit

    def test_all_configurations_have_consistent_namespaces(self):
        """Test all configurations have consistent namespaces."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            # Check namespaces
            for doc in docs:
                if "metadata" in doc and "namespace" in doc["metadata"]:
                    namespace = doc["metadata"]["namespace"]
                    assert (
                        namespace == "production"
                    ), f"Resource {doc.get('metadata', {}).get('name', 'unknown')} in {file_path} should be in production namespace"

    def test_all_configurations_have_consistent_versions(self):
        """Test all configurations have consistent versions."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        # Collect all versions
        versions = set()
        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            for doc in docs:
                if (
                    "metadata" in doc
                    and "labels" in doc["metadata"]
                    and "app.kubernetes.io/version" in doc["metadata"]["labels"]
                ):
                    version = doc["metadata"]["labels"]["app.kubernetes.io/version"]
                    versions.add(version)

        # All resources should use the same version
        assert (
            len(versions) <= 1
        ), f"All resources should use the same version, but found: {versions}"

    def test_all_configurations_have_consistent_managed_by(self):
        """Test all configurations have consistent managed-by."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        # Collect all managed-by values
        managed_by_values = set()
        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            for doc in docs:
                if (
                    "metadata" in doc
                    and "labels" in doc["metadata"]
                    and "app.kubernetes.io/managed-by" in doc["metadata"]["labels"]
                ):
                    managed_by = doc["metadata"]["labels"][
                        "app.kubernetes.io/managed-by"
                    ]
                    managed_by_values.add(managed_by)

        # All resources should use the same managed-by
        assert (
            len(managed_by_values) <= 1
        ), f"All resources should use the same managed-by, but found: {managed_by_values}"

    def test_all_configurations_have_consistent_part_of(self):
        """Test all configurations have consistent part-of."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        # Collect all part-of values
        part_of_values = set()
        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            for doc in docs:
                if (
                    "metadata" in doc
                    and "labels" in doc["metadata"]
                    and "app.kubernetes.io/part-of" in doc["metadata"]["labels"]
                ):
                    part_of = doc["metadata"]["labels"]["app.kubernetes.io/part-of"]
                    part_of_values.add(part_of)

        # All resources should use the same part-of
        assert (
            len(part_of_values) <= 1
        ), f"All resources should use the same part-of, but found: {part_of_values}"

    def test_all_configurations_have_consistent_created_by(self):
        """Test all configurations have consistent created-by."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        # Collect all created-by values
        created_by_values = set()
        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            for doc in docs:
                if (
                    "metadata" in doc
                    and "annotations" in doc["metadata"]
                    and "app.kubernetes.io/created-by" in doc["metadata"]["annotations"]
                ):
                    created_by = doc["metadata"]["annotations"][
                        "app.kubernetes.io/created-by"
                    ]
                    created_by_values.add(created_by)

        # All resources should use the same created-by
        assert (
            len(created_by_values) <= 1
        ), f"All resources should use the same created-by, but found: {created_by_values}"

    def test_all_configurations_have_consistent_descriptions(self):
        """Test all configurations have consistent descriptions."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        # Collect all descriptions
        descriptions = []
        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            for doc in docs:
                if (
                    "metadata" in doc
                    and "annotations" in doc["metadata"]
                    and "description" in doc["metadata"]["annotations"]
                ):
                    description = doc["metadata"]["annotations"]["description"]
                    descriptions.append(description)

        # All descriptions should be valid
        for description in descriptions:
            assert isinstance(description, str)
            assert len(description) > 0
            assert len(description) <= 1000  # Reasonable length limit

    def test_all_configurations_have_consistent_metadata_structure(self):
        """Test all configurations have consistent metadata structure."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            # Check metadata structure
            for doc in docs:
                if "metadata" in doc:
                    metadata = doc["metadata"]

                    # Check required fields
                    assert "name" in metadata
                    assert isinstance(metadata["name"], str)
                    assert len(metadata["name"]) > 0
                    assert len(metadata["name"]) <= 63  # Kubernetes name length limit

                    # Check optional fields
                    if "namespace" in metadata:
                        assert isinstance(metadata["namespace"], str)
                        assert len(metadata["namespace"]) > 0
                        assert (
                            len(metadata["namespace"]) <= 63
                        )  # Kubernetes namespace length limit

                    if "labels" in metadata:
                        assert isinstance(metadata["labels"], dict)
                        for key, value in metadata["labels"].items():
                            assert isinstance(key, str)
                            assert isinstance(value, str)
                            assert len(key) > 0
                            assert len(value) > 0
                            assert len(key) <= 63  # Kubernetes label key length limit
                            assert (
                                len(value) <= 63
                            )  # Kubernetes label value length limit

                    if "annotations" in metadata:
                        assert isinstance(metadata["annotations"], dict)
                        for key, value in metadata["annotations"].items():
                            assert isinstance(key, str)
                            assert isinstance(value, str)
                            assert len(key) > 0
                            assert len(value) > 0
                            assert (
                                len(key) <= 63
                            )  # Kubernetes annotation key length limit
                            assert (
                                len(value) <= 262144
                            )  # Kubernetes annotation value length limit
