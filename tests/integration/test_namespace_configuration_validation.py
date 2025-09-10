"""Integration tests for namespace configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestNamespaceConfigurationValidation:
    """Test namespace configuration validation."""
    
    def test_all_namespaces_have_required_fields(self):
        """Test all namespaces have required fields."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            metadata = namespace["metadata"]
            
            # Check required fields
            assert "name" in metadata
            assert "labels" in metadata
            assert "annotations" in metadata
    
    def test_namespaces_have_unique_names(self):
        """Test namespaces have unique names."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        names = [ns["metadata"]["name"] for ns in namespaces]
        
        assert len(names) == len(set(names)), "Namespace names must be unique"
    
    def test_namespaces_have_proper_labels(self):
        """Test namespaces have proper labels."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            labels = namespace["metadata"]["labels"]
            
            # Check required labels
            assert "name" in labels
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels
    
    def test_namespaces_have_proper_annotations(self):
        """Test namespaces have proper annotations."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            annotations = namespace["metadata"]["annotations"]
            
            # Check required annotations
            assert "description" in annotations
            assert "app.kubernetes.io/created-by" in annotations
    
    def test_namespaces_have_valid_names(self):
        """Test namespaces have valid names."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            name = namespace["metadata"]["name"]
            
            # Check name format
            assert isinstance(name, str)
            assert len(name) > 0
            assert len(name) <= 63  # Kubernetes name length limit
            assert name.islower()  # Kubernetes names must be lowercase
            assert name.replace("-", "").replace(".", "").isalnum()  # Valid characters
    
    def test_namespaces_have_valid_label_values(self):
        """Test namespaces have valid label values."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            labels = namespace["metadata"]["labels"]
            
            for key, value in labels.items():
                # Check key format
                assert isinstance(key, str)
                assert len(key) > 0
                assert len(key) <= 63  # Kubernetes label key length limit
                assert key.replace("/", "").replace(".", "").replace("-", "").replace("_", "").isalnum()
                
                # Check value format
                assert isinstance(value, str)
                assert len(value) > 0
                assert len(value) <= 63  # Kubernetes label value length limit
                assert value.replace("-", "").replace(".", "").replace("_", "").isalnum()
    
    def test_namespaces_have_valid_annotation_values(self):
        """Test namespaces have valid annotation values."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            annotations = namespace["metadata"]["annotations"]
            
            for key, value in annotations.items():
                # Check key format
                assert isinstance(key, str)
                assert len(key) > 0
                assert len(key) <= 63  # Kubernetes annotation key length limit
                assert key.replace("/", "").replace(".", "").replace("-", "").replace("_", "").isalnum()
                
                # Check value format
                assert isinstance(value, str)
                assert len(value) > 0
                assert len(value) <= 262144  # Kubernetes annotation value length limit
    
    def test_namespaces_have_required_namespace_labels(self):
        """Test namespaces have required namespace labels for network policies."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        expected_namespaces = [
            "production",
            "database", 
            "cache",
            "messaging",
            "monitoring"
        ]
        
        namespace_names = [ns["metadata"]["name"] for ns in namespaces]
        for expected_namespace in expected_namespaces:
            assert expected_namespace in namespace_names, f"Namespace {expected_namespace} should exist"
    
    def test_namespaces_have_consistent_label_values(self):
        """Test namespaces have consistent label values."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            labels = namespace["metadata"]["labels"]
            
            # Check that name label matches metadata name
            assert labels["name"] == namespace["metadata"]["name"]
            
            # Check that component label is consistent
            if "app.kubernetes.io/component" in labels:
                component = labels["app.kubernetes.io/component"]
                assert component in ["namespace", "infrastructure", "monitoring", "database", "cache", "messaging"]
    
    def test_namespaces_have_consistent_annotation_values(self):
        """Test namespaces have consistent annotation values."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            annotations = namespace["metadata"]["annotations"]
            
            # Check that description is present and meaningful
            assert "description" in annotations
            description = annotations["description"]
            assert isinstance(description, str)
            assert len(description) > 10  # Should be meaningful
            assert len(description) <= 1000  # Should not be too long
    
    def test_namespaces_have_proper_managed_by_label(self):
        """Test namespaces have proper managed-by label."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            labels = namespace["metadata"]["labels"]
            
            # Check managed-by label
            assert "app.kubernetes.io/managed-by" in labels
            managed_by = labels["app.kubernetes.io/managed-by"]
            assert managed_by in ["kubectl", "helm", "kustomize", "terraform", "pulumi"]
    
    def test_namespaces_have_proper_part_of_label(self):
        """Test namespaces have proper part-of label."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            labels = namespace["metadata"]["labels"]
            
            # Check part-of label
            assert "app.kubernetes.io/part-of" in labels
            part_of = labels["app.kubernetes.io/part-of"]
            assert part_of in ["multi-ai-agent", "ai-agent-platform", "production-system"]
    
    def test_namespaces_have_proper_version_label(self):
        """Test namespaces have proper version label."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            labels = namespace["metadata"]["labels"]
            
            # Check version label
            assert "app.kubernetes.io/version" in labels
            version = labels["app.kubernetes.io/version"]
            assert isinstance(version, str)
            assert len(version) > 0
            assert version.count(".") >= 1  # Should be semantic version format
    
    def test_namespaces_have_proper_instance_label(self):
        """Test namespaces have proper instance label."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        
        for namespace in namespaces:
            labels = namespace["metadata"]["labels"]
            
            # Check instance label
            assert "app.kubernetes.io/instance" in labels
            instance = labels["app.kubernetes.io/instance"]
            assert isinstance(instance, str)
            assert len(instance) > 0
            assert instance.islower()  # Should be lowercase
            assert instance.replace("-", "").replace(".", "").isalnum()  # Valid characters
