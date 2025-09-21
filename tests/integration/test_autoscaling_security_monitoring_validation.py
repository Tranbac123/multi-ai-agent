"""Integration tests for autoscaling and security configuration monitoring validation."""

import pytest
import yaml
from pathlib import Path


class TestAutoscalingSecurityMonitoringValidation:
    """Test autoscaling and security configuration monitoring validation."""

    def test_keda_monitoring_validation(self):
        """Test KEDA monitoring validation."""
        keda_file = Path("k8s/production/manifests/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check for KEDA operator deployment
        operator_deployment = None
        for doc in docs:
            if (
                doc.get("kind") == "Deployment"
                and doc.get("metadata", {}).get("name") == "keda-operator"
            ):
                operator_deployment = doc
                break

        assert operator_deployment is not None, "KEDA operator deployment should exist"

        # Check deployment has monitoring labels
        labels = operator_deployment["metadata"]["labels"]
        assert "app.kubernetes.io/name" in labels
        assert "app.kubernetes.io/instance" in labels
        assert "app.kubernetes.io/version" in labels
        assert "app.kubernetes.io/component" in labels
        assert "app.kubernetes.io/part-of" in labels
        assert "app.kubernetes.io/managed-by" in labels

        # Check ScaledObjects have monitoring labels
        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]
        for scaled_object in scaled_objects:
            labels = scaled_object["metadata"]["labels"]
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

    def test_hpa_monitoring_validation(self):
        """Test HPA monitoring validation."""
        hpa_file = Path("k8s/production/manifests/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check for HPAs
        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]
        assert len(hpas) > 0, "HPA configuration should have HorizontalPodAutoscalers"

        for hpa in hpas:
            # Check HPA has monitoring labels
            labels = hpa["metadata"]["labels"]
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

    def test_health_probes_monitoring_validation(self):
        """Test health probes monitoring validation."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check for deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        assert (
            len(deployments) > 0
        ), "Health probes configuration should have deployments"

        for deployment in deployments:
            # Check deployment has monitoring labels
            labels = deployment["metadata"]["labels"]
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

        # Check services have monitoring labels
        services = [doc for doc in docs if doc.get("kind") == "Service"]
        for service in services:
            labels = service["metadata"]["labels"]
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

        # Check ConfigMaps have monitoring labels
        configmaps = [doc for doc in docs if doc.get("kind") == "ConfigMap"]
        for configmap in configmaps:
            labels = configmap["metadata"]["labels"]
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

        # Check Secrets have monitoring labels
        secrets = [doc for doc in docs if doc.get("kind") == "Secret"]
        for secret in secrets:
            labels = secret["metadata"]["labels"]
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

        # Check ServiceAccounts have monitoring labels
        serviceaccounts = [doc for doc in docs if doc.get("kind") == "ServiceAccount"]
        for serviceaccount in serviceaccounts:
            labels = serviceaccount["metadata"]["labels"]
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

    def test_networkpolicy_monitoring_validation(self):
        """Test NetworkPolicy monitoring validation."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check for NetworkPolicies
        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
        assert (
            len(network_policies) > 0
        ), "Network policy configuration should have NetworkPolicies"

        for netpol in network_policies:
            # Check NetworkPolicy has monitoring labels
            labels = netpol["metadata"]["labels"]
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

        # Check Namespaces have monitoring labels
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        for namespace in namespaces:
            labels = namespace["metadata"]["labels"]
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

    def test_all_configurations_have_monitoring_annotations(self):
        """Test all configurations have monitoring annotations."""
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
                    assert "description" in annotations
                    assert "app.kubernetes.io/created-by" in annotations

    def test_all_configurations_have_monitoring_labels(self):
        """Test all configurations have monitoring labels."""
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
                    assert "app.kubernetes.io/name" in labels
                    assert "app.kubernetes.io/instance" in labels
                    assert "app.kubernetes.io/version" in labels
                    assert "app.kubernetes.io/component" in labels
                    assert "app.kubernetes.io/part-of" in labels
                    assert "app.kubernetes.io/managed-by" in labels

    def test_all_configurations_have_consistent_monitoring_metadata(self):
        """Test all configurations have consistent monitoring metadata."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        # Collect all metadata
        all_metadata = []
        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            for doc in docs:
                if "metadata" in doc:
                    all_metadata.append(doc["metadata"])

        # Check that all resources have consistent monitoring metadata
        for metadata in all_metadata:
            if "labels" in metadata:
                labels = metadata["labels"]

                # Check required monitoring labels
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

            if "annotations" in metadata:
                annotations = metadata["annotations"]

                # Check required monitoring annotations
                assert "description" in annotations
                assert "app.kubernetes.io/created-by" in annotations

                # Check annotation values are valid
                for key, value in annotations.items():
                    assert isinstance(key, str)
                    assert isinstance(value, str)
                    assert len(key) > 0
                    assert len(value) > 0

    def test_all_configurations_have_consistent_monitoring_versions(self):
        """Test all configurations have consistent monitoring versions."""
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

    def test_all_configurations_have_consistent_monitoring_managed_by(self):
        """Test all configurations have consistent monitoring managed-by."""
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

    def test_all_configurations_have_consistent_monitoring_part_of(self):
        """Test all configurations have consistent monitoring part-of."""
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

    def test_all_configurations_have_consistent_monitoring_namespaces(self):
        """Test all configurations have consistent monitoring namespaces."""
        files = [
            "k8s/production/manifests/autoscaling/keda.yaml",
            "k8s/production/manifests/autoscaling/hpa.yaml",
            "k8s/production/manifests/health/probes.yaml",
            "k8s/production/manifests/security/networkpolicy.yaml",
        ]

        # Collect all namespaces
        namespaces = set()
        for file_path in files:
            with open(file_path) as f:
                docs = list(yaml.safe_load_all(f))

            for doc in docs:
                if "metadata" in doc and "namespace" in doc["metadata"]:
                    namespace = doc["metadata"]["namespace"]
                    namespaces.add(namespace)

        # All resources should use the same namespace
        assert (
            len(namespaces) <= 1
        ), f"All resources should use the same namespace, but found: {namespaces}"
        assert (
            "production" in namespaces
        ), "All resources should be in production namespace"

    def test_all_configurations_have_consistent_monitoring_created_by(self):
        """Test all configurations have consistent monitoring created-by."""
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

    def test_all_configurations_have_consistent_monitoring_descriptions(self):
        """Test all configurations have consistent monitoring descriptions."""
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
