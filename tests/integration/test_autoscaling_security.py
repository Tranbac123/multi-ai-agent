"""Integration tests for autoscaling and security configurations."""

import pytest
import yaml
import os
from pathlib import Path


class TestKEDAConfiguration:
    """Test KEDA autoscaling configuration."""
    
    def test_keda_operator_deployment(self):
        """Test KEDA operator deployment configuration."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        assert keda_file.exists()
        
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Find KEDA operator deployment
        operator_deployment = None
        for doc in docs:
            if (doc.get("kind") == "Deployment" and 
                doc.get("metadata", {}).get("name") == "keda-operator"):
                operator_deployment = doc
                break
        
        assert operator_deployment is not None
        assert operator_deployment["spec"]["replicas"] == 1
        assert operator_deployment["spec"]["template"]["spec"]["containers"][0]["image"] == "ghcr.io/kedacore/keda:2.12.0"
    
    def test_keda_scaled_objects(self):
        """Test KEDA ScaledObject configurations."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        assert keda_file.exists()
        
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Find all ScaledObjects
        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]
        
        expected_scalers = [
            "orchestrator-scaler",
            "ingestion-scaler",
            "router-service-scaler",
            "realtime-scaler",
            "analytics-service-scaler",
            "billing-service-scaler"
        ]
        
        scaler_names = [so["metadata"]["name"] for so in scaled_objects]
        for expected_scaler in expected_scalers:
            assert expected_scaler in scaler_names
    
    def test_orchestrator_keda_scaler(self):
        """Test orchestrator KEDA scaler configuration."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        orchestrator_scaler = None
        for doc in docs:
            if (doc.get("kind") == "ScaledObject" and 
                doc.get("metadata", {}).get("name") == "orchestrator-scaler"):
                orchestrator_scaler = doc
                break
        
        assert orchestrator_scaler is not None
        assert orchestrator_scaler["spec"]["scaleTargetRef"]["name"] == "orchestrator"
        assert orchestrator_scaler["spec"]["minReplicaCount"] == 2
        assert orchestrator_scaler["spec"]["maxReplicaCount"] == 20
        assert orchestrator_scaler["spec"]["triggers"][0]["type"] == "nats-jetstream"
    
    def test_ingestion_keda_scaler(self):
        """Test ingestion KEDA scaler configuration."""
        keda_file = Path("infra/k8s/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        ingestion_scaler = None
        for doc in docs:
            if (doc.get("kind") == "ScaledObject" and 
                doc.get("metadata", {}).get("name") == "ingestion-scaler"):
                ingestion_scaler = doc
                break
        
        assert ingestion_scaler is not None
        assert ingestion_scaler["spec"]["scaleTargetRef"]["name"] == "ingestion"
        assert ingestion_scaler["spec"]["minReplicaCount"] == 1
        assert ingestion_scaler["spec"]["maxReplicaCount"] == 15
        assert ingestion_scaler["spec"]["triggers"][0]["type"] == "nats-jetstream"


class TestHPAConfiguration:
    """Test HPA configuration."""
    
    def test_hpa_file_exists(self):
        """Test HPA configuration file exists."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        assert hpa_file.exists()
    
    def test_router_service_hpa(self):
        """Test router service HPA configuration."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        router_hpa = None
        for doc in docs:
            if (doc.get("kind") == "HorizontalPodAutoscaler" and 
                doc.get("metadata", {}).get("name") == "router-service-hpa"):
                router_hpa = doc
                break
        
        assert router_hpa is not None
        assert router_hpa["spec"]["scaleTargetRef"]["name"] == "router-service"
        assert router_hpa["spec"]["minReplicas"] == 2
        assert router_hpa["spec"]["maxReplicas"] == 10
        
        # Check CPU and memory metrics
        metrics = router_hpa["spec"]["metrics"]
        cpu_metric = next((m for m in metrics if m["resource"]["name"] == "cpu"), None)
        memory_metric = next((m for m in metrics if m["resource"]["name"] == "memory"), None)
        
        assert cpu_metric is not None
        assert cpu_metric["resource"]["target"]["averageUtilization"] == 70
        assert memory_metric is not None
        assert memory_metric["resource"]["target"]["averageUtilization"] == 80
    
    def test_realtime_service_hpa(self):
        """Test realtime service HPA configuration."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        realtime_hpa = None
        for doc in docs:
            if (doc.get("kind") == "HorizontalPodAutoscaler" and 
                doc.get("metadata", {}).get("name") == "realtime-service-hpa"):
                realtime_hpa = doc
                break
        
        assert realtime_hpa is not None
        assert realtime_hpa["spec"]["scaleTargetRef"]["name"] == "realtime"
        assert realtime_hpa["spec"]["minReplicas"] == 2
        assert realtime_hpa["spec"]["maxReplicas"] == 15
    
    def test_hpa_behavior_configuration(self):
        """Test HPA behavior configuration."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Check that all HPAs have behavior configuration
        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]
        
        for hpa in hpas:
            assert "behavior" in hpa["spec"]
            behavior = hpa["spec"]["behavior"]
            
            # Check scale down behavior
            assert "scaleDown" in behavior
            assert behavior["scaleDown"]["stabilizationWindowSeconds"] == 300
            
            # Check scale up behavior
            assert "scaleUp" in behavior
            assert behavior["scaleUp"]["stabilizationWindowSeconds"] == 60


class TestHealthProbesConfiguration:
    """Test health probes configuration."""
    
    def test_health_probes_file_exists(self):
        """Test health probes configuration file exists."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        assert probes_file.exists()
    
    def test_all_services_have_probes(self):
        """Test all services have health probes configured."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Find all deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        
        expected_services = [
            "api-gateway",
            "router-service", 
            "orchestrator",
            "realtime",
            "analytics-service",
            "billing-service"
        ]
        
        deployment_names = [d["metadata"]["name"] for d in deployments]
        for expected_service in expected_services:
            assert expected_service in deployment_names
    
    def test_liveness_probes_configured(self):
        """Test liveness probes are configured for all services."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        
        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            assert "livenessProbe" in container
            assert container["livenessProbe"]["httpGet"]["path"] == "/health"
            assert container["livenessProbe"]["initialDelaySeconds"] == 30
            assert container["livenessProbe"]["periodSeconds"] == 10
    
    def test_readiness_probes_configured(self):
        """Test readiness probes are configured for all services."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        
        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            assert "readinessProbe" in container
            assert container["readinessProbe"]["httpGet"]["path"] == "/health/ready"
            assert container["readinessProbe"]["initialDelaySeconds"] == 5
            assert container["readinessProbe"]["periodSeconds"] == 5
    
    def test_security_context_configured(self):
        """Test security context is configured for all services."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        
        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            assert "securityContext" in container
            
            security_context = container["securityContext"]
            assert security_context["runAsNonRoot"] is True
            assert security_context["runAsUser"] == 1000
            assert security_context["runAsGroup"] == 1000
            assert security_context["allowPrivilegeEscalation"] is False
            assert security_context["readOnlyRootFilesystem"] is True
            assert "ALL" in security_context["capabilities"]["drop"]


class TestNetworkPolicyConfiguration:
    """Test NetworkPolicy configuration."""
    
    def test_network_policy_file_exists(self):
        """Test NetworkPolicy configuration file exists."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        assert netpol_file.exists()
    
    def test_all_services_have_network_policies(self):
        """Test all services have NetworkPolicy configured."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Find all NetworkPolicies
        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
        
        expected_policies = [
            "api-gateway-netpol",
            "orchestrator-netpol",
            "router-service-netpol",
            "realtime-service-netpol",
            "analytics-service-netpol",
            "billing-service-netpol",
            "database-netpol",
            "cache-netpol",
            "messaging-netpol",
            "monitoring-netpol",
            "default-deny-all"
        ]
        
        policy_names = [np["metadata"]["name"] for np in network_policies]
        for expected_policy in expected_policies:
            assert expected_policy in policy_names
    
    def test_api_gateway_network_policy(self):
        """Test API Gateway NetworkPolicy configuration."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        api_gateway_netpol = None
        for doc in docs:
            if (doc.get("kind") == "NetworkPolicy" and 
                doc.get("metadata", {}).get("name") == "api-gateway-netpol"):
                api_gateway_netpol = doc
                break
        
        assert api_gateway_netpol is not None
        assert api_gateway_netpol["spec"]["podSelector"]["matchLabels"]["app"] == "api-gateway"
        
        # Check ingress rules
        ingress_rules = api_gateway_netpol["spec"]["ingress"]
        assert len(ingress_rules) >= 2  # ingress controller + monitoring
        
        # Check egress rules
        egress_rules = api_gateway_netpol["spec"]["egress"]
        assert len(egress_rules) >= 3  # production services + database + cache + messaging
    
    def test_database_network_policy(self):
        """Test database NetworkPolicy configuration."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        database_netpol = None
        for doc in docs:
            if (doc.get("kind") == "NetworkPolicy" and 
                doc.get("metadata", {}).get("name") == "database-netpol"):
                database_netpol = doc
                break
        
        assert database_netpol is not None
        assert database_netpol["spec"]["podSelector"]["matchLabels"]["app"] == "postgres"
        
        # Check ingress rules allow production namespace
        ingress_rules = database_netpol["spec"]["ingress"]
        production_ingress = any(
            rule.get("from", [{}])[0].get("namespaceSelector", {}).get("matchLabels", {}).get("name") == "production"
            for rule in ingress_rules
        )
        assert production_ingress is True
    
    def test_default_deny_all_policy(self):
        """Test default deny all NetworkPolicy exists."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        default_deny = None
        for doc in docs:
            if (doc.get("kind") == "NetworkPolicy" and 
                doc.get("metadata", {}).get("name") == "default-deny-all"):
                default_deny = doc
                break
        
        assert default_deny is not None
        assert default_deny["spec"]["podSelector"] == {}
        assert "policyTypes" in default_deny["spec"]
        assert "Ingress" in default_deny["spec"]["policyTypes"]
        assert "Egress" in default_deny["spec"]["policyTypes"]


class TestNamespaceConfiguration:
    """Test namespace configuration."""
    
    def test_namespace_labels_configured(self):
        """Test namespace labels are configured for network policies."""
        netpol_file = Path("infra/k8s/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        # Find all namespaces
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
            assert expected_namespace in namespace_names
        
        # Check that namespaces have proper labels
        for namespace in namespaces:
            assert "labels" in namespace["metadata"]
            assert "name" in namespace["metadata"]["labels"]


class TestResourceConfiguration:
    """Test resource configuration."""
    
    def test_all_services_have_resource_limits(self):
        """Test all services have resource limits configured."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        
        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            assert "resources" in container
            
            resources = container["resources"]
            assert "limits" in resources
            assert "requests" in resources
            
            # Check CPU and memory limits
            assert "cpu" in resources["limits"]
            assert "memory" in resources["limits"]
            assert "cpu" in resources["requests"]
            assert "memory" in resources["requests"]
    
    def test_resource_limits_are_reasonable(self):
        """Test resource limits are reasonable."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))
        
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        
        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            resources = container["resources"]
            
            # Check CPU limits are reasonable (not too high)
            cpu_limit = resources["limits"]["cpu"]
            if cpu_limit.endswith("m"):
                cpu_millicores = int(cpu_limit[:-1])
                assert cpu_millicores <= 2000  # Max 2 CPU cores
            elif cpu_limit.endswith("Gi"):
                # This shouldn't happen for CPU, but if it does, it's wrong
                assert False, "CPU limit should be in millicores (m), not Gi"
            
            # Check memory limits are reasonable
            memory_limit = resources["limits"]["memory"]
            if memory_limit.endswith("Gi"):
                memory_gb = int(memory_limit[:-2])
                assert memory_gb <= 4  # Max 4GB memory
            elif memory_limit.endswith("Mi"):
                memory_mb = int(memory_limit[:-2])
                assert memory_mb <= 4096  # Max 4GB memory
