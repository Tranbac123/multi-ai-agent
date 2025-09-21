"""Integration tests for autoscaling and security configuration deployment."""

import pytest
import yaml
from pathlib import Path


class TestAutoscalingSecurityDeployment:
    """Test autoscaling and security configuration deployment."""

    def test_keda_deployment_has_required_components(self):
        """Test KEDA deployment has required components."""
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

        # Check deployment spec
        spec = operator_deployment["spec"]
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
        assert "resources" in container
        assert "securityContext" in container

    def test_hpa_deployment_has_required_components(self):
        """Test HPA deployment has required components."""
        hpa_file = Path("k8s/production/manifests/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check for HPAs
        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]
        assert len(hpas) > 0, "HPA configuration should have HorizontalPodAutoscalers"

        for hpa in hpas:
            spec = hpa["spec"]
            assert "scaleTargetRef" in spec
            assert "minReplicas" in spec
            assert "maxReplicas" in spec
            assert "metrics" in spec

    def test_health_probes_deployment_has_required_components(self):
        """Test health probes deployment has required components."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check for deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        assert (
            len(deployments) > 0
        ), "Health probes configuration should have deployments"

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

    def test_networkpolicy_deployment_has_required_components(self):
        """Test NetworkPolicy deployment has required components."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check for NetworkPolicies
        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
        assert (
            len(network_policies) > 0
        ), "Network policy configuration should have NetworkPolicies"

        for netpol in network_policies:
            spec = netpol["spec"]
            assert "podSelector" in spec
            assert "policyTypes" in spec

            # Check pod selector
            pod_selector = spec["podSelector"]
            assert "matchLabels" in pod_selector
            assert len(pod_selector["matchLabels"]) > 0

            # Check policy types
            policy_types = spec["policyTypes"]
            assert len(policy_types) > 0
            for policy_type in policy_types:
                assert policy_type in ["Ingress", "Egress"]

    def test_all_deployments_have_required_services(self):
        """Test all deployments have required services."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        deployment_names = {d["metadata"]["name"] for d in deployments}

        # Get all services
        services = [doc for doc in docs if doc.get("kind") == "Service"]
        service_names = {s["metadata"]["name"] for s in services}

        # Check that each deployment has a corresponding service
        for deployment in deployments:
            deployment_name = deployment["metadata"]["name"]
            assert (
                deployment_name in service_names
            ), f"Deployment {deployment_name} should have a corresponding service"

    def test_all_deployments_have_required_configmaps(self):
        """Test all deployments have required ConfigMaps."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        # Get all ConfigMaps
        configmaps = [doc for doc in docs if doc.get("kind") == "ConfigMap"]
        configmap_names = {cm["metadata"]["name"] for cm in configmaps}

        # Check that each deployment has a corresponding ConfigMap
        for deployment in deployments:
            deployment_name = deployment["metadata"]["name"]
            configmap_name = f"{deployment_name}-config"
            assert (
                configmap_name in configmap_names
            ), f"Deployment {deployment_name} should have a corresponding ConfigMap {configmap_name}"

    def test_all_deployments_have_required_secrets(self):
        """Test all deployments have required Secrets."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        # Get all Secrets
        secrets = [doc for doc in docs if doc.get("kind") == "Secret"]
        secret_names = {s["metadata"]["name"] for s in secrets}

        # Check that each deployment has a corresponding Secret
        for deployment in deployments:
            deployment_name = deployment["metadata"]["name"]
            secret_name = f"{deployment_name}-secret"
            assert (
                secret_name in secret_names
            ), f"Deployment {deployment_name} should have a corresponding Secret {secret_name}"

    def test_all_deployments_have_required_serviceaccounts(self):
        """Test all deployments have required ServiceAccounts."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        # Get all ServiceAccounts
        serviceaccounts = [doc for doc in docs if doc.get("kind") == "ServiceAccount"]
        serviceaccount_names = {sa["metadata"]["name"] for sa in serviceaccounts}

        # Check that each deployment has a corresponding ServiceAccount
        for deployment in deployments:
            deployment_name = deployment["metadata"]["name"]
            serviceaccount_name = f"{deployment_name}-sa"
            assert (
                serviceaccount_name in serviceaccount_names
            ), f"Deployment {deployment_name} should have a corresponding ServiceAccount {serviceaccount_name}"

    def test_all_deployments_have_required_networkpolicies(self):
        """Test all deployments have required NetworkPolicies."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all NetworkPolicies
        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
        netpol_names = {np["metadata"]["name"] for np in network_policies}

        # Expected NetworkPolicies
        expected_netpols = [
            "api-gateway-netpol",
            "orchestrator-netpol",
            "router_service-netpol",
            "realtime-service-netpol",
            "analytics-service-netpol",
            "billing-service-netpol",
            "database-netpol",
            "cache-netpol",
            "messaging-netpol",
            "monitoring-netpol",
            "default-deny-all",
        ]

        for expected_netpol in expected_netpols:
            assert (
                expected_netpol in netpol_names
            ), f"NetworkPolicy {expected_netpol} should exist"

    def test_all_deployments_have_required_scaled_objects(self):
        """Test all deployments have required ScaledObjects."""
        keda_file = Path("k8s/production/manifests/autoscaling/keda.yaml")
        with open(keda_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all ScaledObjects
        scaled_objects = [doc for doc in docs if doc.get("kind") == "ScaledObject"]
        scaled_object_names = {so["metadata"]["name"] for so in scaled_objects}

        # Expected ScaledObjects
        expected_scaled_objects = [
            "orchestrator-scaler",
            "ingestion-scaler",
            "router_service-scaler",
            "realtime-scaler",
            "analytics-service-scaler",
            "billing-service-scaler",
        ]

        for expected_scaled_object in expected_scaled_objects:
            assert (
                expected_scaled_object in scaled_object_names
            ), f"ScaledObject {expected_scaled_object} should exist"

    def test_all_deployments_have_required_hpas(self):
        """Test all deployments have required HPAs."""
        hpa_file = Path("k8s/production/manifests/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all HPAs
        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]
        hpa_names = {hpa["metadata"]["name"] for hpa in hpas}

        # Expected HPAs
        expected_hpas = [
            "router_service-hpa",
            "realtime-service-hpa",
            "analytics-service-hpa",
            "billing-service-hpa",
        ]

        for expected_hpa in expected_hpas:
            assert expected_hpa in hpa_names, f"HPA {expected_hpa} should exist"

    def test_all_deployments_have_required_namespaces(self):
        """Test all deployments have required namespaces."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all Namespaces
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        namespace_names = {ns["metadata"]["name"] for ns in namespaces}

        # Expected Namespaces
        expected_namespaces = [
            "production",
            "database",
            "cache",
            "messaging",
            "monitoring",
        ]

        for expected_namespace in expected_namespaces:
            assert (
                expected_namespace in namespace_names
            ), f"Namespace {expected_namespace} should exist"

    def test_all_deployments_have_required_health_probes(self):
        """Test all deployments have required health probes."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe
            assert "livenessProbe" in container
            liveness = container["livenessProbe"]
            assert "httpGet" in liveness
            assert "path" in liveness["httpGet"]
            assert "port" in liveness["httpGet"]
            assert "initialDelaySeconds" in liveness
            assert "periodSeconds" in liveness

            # Check readiness probe
            assert "readinessProbe" in container
            readiness = container["readinessProbe"]
            assert "httpGet" in readiness
            assert "path" in readiness["httpGet"]
            assert "port" in readiness["httpGet"]
            assert "initialDelaySeconds" in readiness
            assert "periodSeconds" in readiness

    def test_all_deployments_have_required_resources(self):
        """Test all deployments have required resources."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check resources
            assert "resources" in container
            resources = container["resources"]
            assert "limits" in resources
            assert "requests" in resources

            # Check CPU and memory limits
            assert "cpu" in resources["limits"]
            assert "memory" in resources["limits"]
            assert "cpu" in resources["requests"]
            assert "memory" in resources["requests"]

    def test_all_deployments_have_required_security_context(self):
        """Test all deployments have required security context."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check security context
            assert "securityContext" in container
            security_context = container["securityContext"]

            # Check required fields
            assert "runAsNonRoot" in security_context
            assert "runAsUser" in security_context
            assert "runAsGroup" in security_context
            assert "allowPrivilegeEscalation" in security_context
            assert "readOnlyRootFilesystem" in security_context
            assert "capabilities" in security_context
