"""Integration tests for autoscaling and security configuration integration."""

import pytest
import yaml
from pathlib import Path


class TestAutoscalingSecurityIntegration:
    """Test autoscaling and security configuration integration."""

    def test_all_autoscaling_security_files_exist(self):
        """Test all autoscaling and security configuration files exist."""
        required_files = [
            "infra/k8s/autoscaling/keda.yaml",
            "infra/k8s/autoscaling/hpa.yaml",
            "infra/k8s/health/probes.yaml",
            "infra/k8s/security/networkpolicy.yaml",
        ]

        for file_path in required_files:
            assert Path(file_path).exists(), f"Required file {file_path} should exist"

    def test_all_autoscaling_security_files_are_valid_yaml(self):
        """Test all autoscaling and security configuration files are valid YAML."""
        files = [
            "infra/k8s/autoscaling/keda.yaml",
            "infra/k8s/autoscaling/hpa.yaml",
            "infra/k8s/health/probes.yaml",
            "infra/k8s/security/networkpolicy.yaml",
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

    def test_all_autoscaling_security_files_have_consistent_namespaces(self):
        """Test all autoscaling and security configuration files have consistent namespaces."""
        files = [
            "infra/k8s/autoscaling/keda.yaml",
            "infra/k8s/autoscaling/hpa.yaml",
            "infra/k8s/health/probes.yaml",
            "infra/k8s/security/networkpolicy.yaml",
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

    def test_all_autoscaling_security_files_have_consistent_labels(self):
        """Test all autoscaling and security configuration files have consistent labels."""
        files = [
            "infra/k8s/autoscaling/keda.yaml",
            "infra/k8s/autoscaling/hpa.yaml",
            "infra/k8s/health/probes.yaml",
            "infra/k8s/security/networkpolicy.yaml",
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

    def test_all_autoscaling_security_files_have_consistent_annotations(self):
        """Test all autoscaling and security configuration files have consistent annotations."""
        files = [
            "infra/k8s/autoscaling/keda.yaml",
            "infra/k8s/autoscaling/hpa.yaml",
            "infra/k8s/health/probes.yaml",
            "infra/k8s/security/networkpolicy.yaml",
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

    def test_all_autoscaling_security_files_have_valid_api_versions(self):
        """Test all autoscaling and security configuration files have valid API versions."""
        files = [
            "infra/k8s/autoscaling/keda.yaml",
            "infra/k8s/autoscaling/hpa.yaml",
            "infra/k8s/health/probes.yaml",
            "infra/k8s/security/networkpolicy.yaml",
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

    def test_all_autoscaling_security_files_have_valid_kinds(self):
        """Test all autoscaling and security configuration files have valid kinds."""
        files = [
            "infra/k8s/autoscaling/keda.yaml",
            "infra/k8s/autoscaling/hpa.yaml",
            "infra/k8s/health/probes.yaml",
            "infra/k8s/security/networkpolicy.yaml",
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

    def test_all_autoscaling_security_files_have_valid_metadata(self):
        """Test all autoscaling and security configuration files have valid metadata."""
        files = [
            "infra/k8s/autoscaling/keda.yaml",
            "infra/k8s/autoscaling/hpa.yaml",
            "infra/k8s/health/probes.yaml",
            "infra/k8s/security/networkpolicy.yaml",
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

    def test_all_autoscaling_security_files_have_no_duplicate_names(self):
        """Test all autoscaling and security configuration files have no duplicate names."""
        files = [
            "infra/k8s/autoscaling/keda.yaml",
            "infra/k8s/autoscaling/hpa.yaml",
            "infra/k8s/health/probes.yaml",
            "infra/k8s/security/networkpolicy.yaml",
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

    def test_all_autoscaling_security_files_have_valid_specs(self):
        """Test all autoscaling and security configuration files have valid specs."""
        files = [
            "infra/k8s/autoscaling/keda.yaml",
            "infra/k8s/autoscaling/hpa.yaml",
            "infra/k8s/health/probes.yaml",
            "infra/k8s/security/networkpolicy.yaml",
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

    def test_autoscaling_security_configurations_are_consistent(self):
        """Test autoscaling and security configurations are consistent with each other."""
        # Load all configurations
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        probes_file = Path("infra/k8s/health/probes.yaml")
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")

        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))

        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))

        with open(probes_file) as f:
            probes_docs = list(yaml.safe_load_all(f))

        with open(netpol_file) as f:
            netpol_docs = list(yaml.safe_load_all(f))

        # Check that all configurations use the same namespace
        all_docs = keda_docs + hpa_docs + probes_docs + netpol_docs

        for doc in all_docs:
            if "metadata" in doc and "namespace" in doc["metadata"]:
                namespace = doc["metadata"]["namespace"]
                assert (
                    namespace == "production"
                ), f"All resources should be in production namespace, but {doc.get('metadata', {}).get('name', 'unknown')} is in {namespace}"

    def test_autoscaling_security_configurations_have_consistent_versions(self):
        """Test autoscaling and security configurations have consistent versions."""
        # Load all configurations
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        probes_file = Path("infra/k8s/health/probes.yaml")
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")

        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))

        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))

        with open(probes_file) as f:
            probes_docs = list(yaml.safe_load_all(f))

        with open(netpol_file) as f:
            netpol_docs = list(yaml.safe_load_all(f))

        # Check that all configurations use the same version
        all_docs = keda_docs + hpa_docs + probes_docs + netpol_docs

        versions = set()
        for doc in all_docs:
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

    def test_autoscaling_security_configurations_have_consistent_managed_by(self):
        """Test autoscaling and security configurations have consistent managed-by."""
        # Load all configurations
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        probes_file = Path("infra/k8s/health/probes.yaml")
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")

        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))

        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))

        with open(probes_file) as f:
            probes_docs = list(yaml.safe_load_all(f))

        with open(netpol_file) as f:
            netpol_docs = list(yaml.safe_load_all(f))

        # Check that all configurations use the same managed-by
        all_docs = keda_docs + hpa_docs + probes_docs + netpol_docs

        managed_by_values = set()
        for doc in all_docs:
            if (
                "metadata" in doc
                and "labels" in doc["metadata"]
                and "app.kubernetes.io/managed-by" in doc["metadata"]["labels"]
            ):
                managed_by = doc["metadata"]["labels"]["app.kubernetes.io/managed-by"]
                managed_by_values.add(managed_by)

        # All resources should use the same managed-by
        assert (
            len(managed_by_values) <= 1
        ), f"All resources should use the same managed-by, but found: {managed_by_values}"

    def test_autoscaling_security_configurations_have_consistent_part_of(self):
        """Test autoscaling and security configurations have consistent part-of."""
        # Load all configurations
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        probes_file = Path("infra/k8s/health/probes.yaml")
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")

        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))

        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))

        with open(probes_file) as f:
            probes_docs = list(yaml.safe_load_all(f))

        with open(netpol_file) as f:
            netpol_docs = list(yaml.safe_load_all(f))

        # Check that all configurations use the same part-of
        all_docs = keda_docs + hpa_docs + probes_docs + netpol_docs

        part_of_values = set()
        for doc in all_docs:
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
