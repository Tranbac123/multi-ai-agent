"""Integration tests for health probes configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestHealthProbesConfigurationValidation:
    """Test health probes configuration validation."""
    
    def test_health_probes_configuration_exists(self):
        """Test health probes configuration file exists."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        assert probes_file.exists(), "Health probes configuration file should exist"
    
    def test_health_probes_configuration_is_valid_yaml(self):
        """Test health probes configuration is valid YAML."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        assert len(docs) > 0, "Health probes configuration should contain at least one document"
        
        # Check that all documents are valid
        for doc in docs:
            assert isinstance(doc, dict), "Each document should be a dictionary"
            assert "apiVersion" in doc, "Each document should have apiVersion"
            assert "kind" in doc, "Each document should have kind"
            assert "metadata" in doc, "Each document should have metadata"
    
    def test_health_probes_configuration_has_required_components(self):
        """Test health probes configuration has required components."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check for deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        assert len(deployments) > 0, "Health probes configuration should have deployments"
        
        # Check for services
        services = [doc for doc in docs if doc.get("kind") == "Service"]
        assert len(services) > 0, "Health probes configuration should have services"
    
    def test_health_probes_configuration_has_consistent_namespaces(self):
        """Test health probes configuration has consistent namespaces."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check namespaces
        for doc in docs:
            if "metadata" in doc and "namespace" in doc["metadata"]:
                namespace = doc["metadata"]["namespace"]
                assert namespace == "production", f"Resource {doc.get('metadata', {}).get('name', 'unknown')} should be in production namespace"
    
    def test_health_probes_configuration_has_consistent_labels(self):
        """Test health probes configuration has consistent labels."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
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
    
    def test_health_probes_configuration_has_consistent_annotations(self):
        """Test health probes configuration has consistent annotations."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check annotations
        for doc in docs:
            if "metadata" in doc and "annotations" in doc["metadata"]:
                annotations = doc["metadata"]["annotations"]
                assert "description" in annotations
                assert "app.kubernetes.io/created-by" in annotations
    
    def test_health_probes_configuration_has_valid_api_versions(self):
        """Test health probes configuration has valid API versions."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check API versions
        for doc in docs:
            if "apiVersion" in doc:
                api_version = doc["apiVersion"]
                assert isinstance(api_version, str)
                assert len(api_version) > 0
                assert "/" in api_version or api_version.startswith("v")
    
    def test_health_probes_configuration_has_valid_kinds(self):
        """Test health probes configuration has valid kinds."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check kinds
        valid_kinds = ["Deployment", "Service", "ServiceAccount", "ConfigMap", "Secret"]
        for doc in docs:
            if "kind" in doc:
                kind = doc["kind"]
                assert kind in valid_kinds, f"Invalid kind: {kind}"
    
    def test_health_probes_configuration_has_valid_metadata(self):
        """Test health probes configuration has valid metadata."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check metadata
        for doc in docs:
            if "metadata" in doc:
                metadata = doc["metadata"]
                assert "name" in metadata
                assert isinstance(metadata["name"], str)
                assert len(metadata["name"]) > 0
                assert len(metadata["name"]) <= 63  # Kubernetes name length limit
    
    def test_health_probes_configuration_has_no_duplicate_names(self):
        """Test health probes configuration has no duplicate names."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check names
        names = []
        for doc in docs:
            if "metadata" in doc and "name" in doc["metadata"]:
                name = doc["metadata"]["name"]
                assert name not in names, f"Duplicate name: {name}"
                names.append(name)
    
    def test_health_probes_configuration_has_valid_specs(self):
        """Test health probes configuration has valid specs."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check specs
        for doc in docs:
            if "spec" in doc:
                spec = doc["spec"]
                assert isinstance(spec, dict)
                assert len(spec) > 0
    
    def test_health_probes_configuration_has_valid_deployment_specs(self):
        """Test health probes configuration has valid deployment specs."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check deployment specs
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        for deployment in deployments:
            spec = deployment["spec"]
            assert "replicas" in spec
            assert "selector" in spec
            assert "template" in spec
            
            # Check template spec
            template_spec = spec["template"]["spec"]
            assert "containers" in template_spec
            assert len(template_spec["containers"]) > 0
            
            # Check container spec
            container = template_spec["containers"][0]
            assert "name" in container
            assert "image" in container
            assert "ports" in container
            assert "livenessProbe" in container
            assert "readinessProbe" in container
            assert "resources" in container
            assert "securityContext" in container
    
    def test_health_probes_configuration_has_valid_service_specs(self):
        """Test health probes configuration has valid service specs."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check service specs
        services = [doc for doc in docs if doc.get("kind") == "Service"]
        for service in services:
            spec = service["spec"]
            assert "selector" in spec
            assert "ports" in spec
            assert len(spec["ports"]) > 0
            
            # Check port spec
            for port in spec["ports"]:
                assert "name" in port
                assert "port" in port
                assert "targetPort" in port
                assert "protocol" in port
                assert port["protocol"] in ["TCP", "UDP"]
    
    def test_health_probes_configuration_has_valid_configmap_specs(self):
        """Test health probes configuration has valid ConfigMap specs."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check ConfigMap specs
        configmaps = [doc for doc in docs if doc.get("kind") == "ConfigMap"]
        for configmap in configmaps:
            spec = configmap["spec"]
            assert "data" in spec or "binaryData" in spec
    
    def test_health_probes_configuration_has_valid_secret_specs(self):
        """Test health probes configuration has valid Secret specs."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check Secret specs
        secrets = [doc for doc in docs if doc.get("kind") == "Secret"]
        for secret in secrets:
            spec = secret["spec"]
            assert "data" in spec or "stringData" in spec or "type" in spec
    
    def test_health_probes_configuration_has_valid_serviceaccount_specs(self):
        """Test health probes configuration has valid ServiceAccount specs."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check ServiceAccount specs
        serviceaccounts = [doc for doc in docs if doc.get("kind") == "ServiceAccount"]
        for serviceaccount in serviceaccounts:
            spec = serviceaccount.get("spec", {})
            # ServiceAccount spec is optional, but if present should be valid
            if spec:
                assert isinstance(spec, dict)
