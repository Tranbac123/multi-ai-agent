"""Integration tests for autoscaling configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestAutoscalingConfigurationValidation:
    """Test autoscaling configuration validation."""
    
    def test_keda_and_hpa_configurations_exist(self):
        """Test KEDA and HPA configuration files exist."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        assert keda_file.exists(), "KEDA configuration file should exist"
        assert hpa_file.exists(), "HPA configuration file should exist"
    
    def test_keda_configuration_is_valid_yaml(self):
        """Test KEDA configuration is valid YAML."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        assert len(docs) > 0, "KEDA configuration should contain at least one document"
        
        # Check that all documents are valid
        for doc in docs:
            assert isinstance(doc, dict), "Each document should be a dictionary"
            assert "apiVersion" in doc, "Each document should have apiVersion"
            assert "kind" in doc, "Each document should have kind"
            assert "metadata" in doc, "Each document should have metadata"
    
    def test_hpa_configuration_is_valid_yaml(self):
        """Test HPA configuration is valid YAML."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        assert len(docs) > 0, "HPA configuration should contain at least one document"
        
        # Check that all documents are valid
        for doc in docs:
            assert isinstance(doc, dict), "Each document should be a dictionary"
            assert "apiVersion" in doc, "Each document should have apiVersion"
            assert "kind" in doc, "Each document should have kind"
            assert "metadata" in doc, "Each document should have metadata"
    
    def test_keda_has_required_components(self):
        """Test KEDA configuration has required components."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check for KEDA operator deployment
        operator_deployment = None
        for doc in docs:
            if (doc.get("kind") == "Deployment" and 
                doc.get("metadata", {}).get("name") == "keda-operator"):
                operator_deployment = doc
                break
        
        assert operator_deployment is not None, "KEDA operator deployment should exist"
        
        # Check for ScaledObjects
        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]
        assert len(scaled_objects) > 0, "KEDA configuration should have ScaledObjects"
    
    def test_hpa_has_required_components(self):
        """Test HPA configuration has required components."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check for HPAs
        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]
        assert len(hpas) > 0, "HPA configuration should have HorizontalPodAutoscalers"
    
    def test_autoscaling_configurations_have_consistent_namespaces(self):
        """Test autoscaling configurations have consistent namespaces."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))
        
        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))
        
        # Check KEDA namespaces
        for doc in keda_docs:
            if "metadata" in doc and "namespace" in doc["metadata"]:
                namespace = doc["metadata"]["namespace"]
                assert namespace == "production", f"KEDA resource {doc.get('metadata', {}).get('name', 'unknown')} should be in production namespace"
        
        # Check HPA namespaces
        for doc in hpa_docs:
            if "metadata" in doc and "namespace" in doc["metadata"]:
                namespace = doc["metadata"]["namespace"]
                assert namespace == "production", f"HPA resource {doc.get('metadata', {}).get('name', 'unknown')} should be in production namespace"
    
    def test_autoscaling_configurations_have_consistent_labels(self):
        """Test autoscaling configurations have consistent labels."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))
        
        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))
        
        # Check KEDA labels
        for doc in keda_docs:
            if "metadata" in doc and "labels" in doc["metadata"]:
                labels = doc["metadata"]["labels"]
                assert "app.kubernetes.io/name" in labels
                assert "app.kubernetes.io/instance" in labels
                assert "app.kubernetes.io/version" in labels
                assert "app.kubernetes.io/component" in labels
                assert "app.kubernetes.io/part-of" in labels
                assert "app.kubernetes.io/managed-by" in labels
        
        # Check HPA labels
        for doc in hpa_docs:
            if "metadata" in doc and "labels" in doc["metadata"]:
                labels = doc["metadata"]["labels"]
                assert "app.kubernetes.io/name" in labels
                assert "app.kubernetes.io/instance" in labels
                assert "app.kubernetes.io/version" in labels
                assert "app.kubernetes.io/component" in labels
                assert "app.kubernetes.io/part-of" in labels
                assert "app.kubernetes.io/managed-by" in labels
    
    def test_autoscaling_configurations_have_consistent_annotations(self):
        """Test autoscaling configurations have consistent annotations."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))
        
        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))
        
        # Check KEDA annotations
        for doc in keda_docs:
            if "metadata" in doc and "annotations" in doc["metadata"]:
                annotations = doc["metadata"]["annotations"]
                assert "description" in annotations
                assert "app.kubernetes.io/created-by" in annotations
        
        # Check HPA annotations
        for doc in hpa_docs:
            if "metadata" in doc and "annotations" in doc["metadata"]:
                annotations = doc["metadata"]["annotations"]
                assert "description" in annotations
                assert "app.kubernetes.io/created-by" in annotations
    
    def test_autoscaling_configurations_have_valid_api_versions(self):
        """Test autoscaling configurations have valid API versions."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))
        
        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))
        
        # Check KEDA API versions
        for doc in keda_docs:
            if "apiVersion" in doc:
                api_version = doc["apiVersion"]
                assert isinstance(api_version, str)
                assert len(api_version) > 0
                assert "/" in api_version or api_version.startswith("v")
        
        # Check HPA API versions
        for doc in hpa_docs:
            if "apiVersion" in doc:
                api_version = doc["apiVersion"]
                assert isinstance(api_version, str)
                assert len(api_version) > 0
                assert "/" in api_version or api_version.startswith("v")
    
    def test_autoscaling_configurations_have_valid_kinds(self):
        """Test autoscaling configurations have valid kinds."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))
        
        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))
        
        # Check KEDA kinds
        valid_keda_kinds = ["Deployment", "Service", "ServiceAccount", "ClusterRole", "ClusterRoleBinding", "ScaledObject"]
        for doc in keda_docs:
            if "kind" in doc:
                kind = doc["kind"]
                assert kind in valid_keda_kinds, f"Invalid KEDA kind: {kind}"
        
        # Check HPA kinds
        valid_hpa_kinds = ["HorizontalPodAutoscaler"]
        for doc in hpa_docs:
            if "kind" in doc:
                kind = doc["kind"]
                assert kind in valid_hpa_kinds, f"Invalid HPA kind: {kind}"
    
    def test_autoscaling_configurations_have_valid_metadata(self):
        """Test autoscaling configurations have valid metadata."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))
        
        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))
        
        # Check KEDA metadata
        for doc in keda_docs:
            if "metadata" in doc:
                metadata = doc["metadata"]
                assert "name" in metadata
                assert isinstance(metadata["name"], str)
                assert len(metadata["name"]) > 0
                assert len(metadata["name"]) <= 63  # Kubernetes name length limit
        
        # Check HPA metadata
        for doc in hpa_docs:
            if "metadata" in doc:
                metadata = doc["metadata"]
                assert "name" in metadata
                assert isinstance(metadata["name"], str)
                assert len(metadata["name"]) > 0
                assert len(metadata["name"]) <= 63  # Kubernetes name length limit
    
    def test_autoscaling_configurations_have_no_duplicate_names(self):
        """Test autoscaling configurations have no duplicate names."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))
        
        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))
        
        # Check KEDA names
        keda_names = []
        for doc in keda_docs:
            if "metadata" in doc and "name" in doc["metadata"]:
                name = doc["metadata"]["name"]
                assert name not in keda_names, f"Duplicate KEDA name: {name}"
                keda_names.append(name)
        
        # Check HPA names
        hpa_names = []
        for doc in hpa_docs:
            if "metadata" in doc and "name" in doc["metadata"]:
                name = doc["metadata"]["name"]
                assert name not in hpa_names, f"Duplicate HPA name: {name}"
                hpa_names.append(name)
    
    def test_autoscaling_configurations_have_valid_specs(self):
        """Test autoscaling configurations have valid specs."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        
        with open(keda_file) as f:
            keda_docs = list(yaml.safe_load_all(f))
        
        with open(hpa_file) as f:
            hpa_docs = list(yaml.safe_load_all(f))
        
        # Check KEDA specs
        for doc in keda_docs:
            if "spec" in doc:
                spec = doc["spec"]
                assert isinstance(spec, dict)
                assert len(spec) > 0
        
        # Check HPA specs
        for doc in hpa_docs:
            if "spec" in doc:
                spec = doc["spec"]
                assert isinstance(spec, dict)
                assert len(spec) > 0
