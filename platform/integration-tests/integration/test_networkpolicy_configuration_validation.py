"""Integration tests for network policy configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestNetworkPolicyConfigurationValidation:
    """Test network policy configuration validation."""

    def test_networkpolicy_configuration_exists(self):
        """Test network policy configuration file exists."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        assert netpol_file.exists(), "Network policy configuration file should exist"

    def test_networkpolicy_configuration_is_valid_yaml(self):
        """Test network policy configuration is valid YAML."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        assert (
            len(docs) > 0
        ), "Network policy configuration should contain at least one document"

        # Check that all documents are valid
        for doc in docs:
            assert isinstance(doc, dict), "Each document should be a dictionary"
            assert "apiVersion" in doc, "Each document should have apiVersion"
            assert "kind" in doc, "Each document should have kind"
            assert "metadata" in doc, "Each document should have metadata"

    def test_networkpolicy_configuration_has_required_components(self):
        """Test network policy configuration has required components."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check for NetworkPolicies
        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
        assert (
            len(network_policies) > 0
        ), "Network policy configuration should have NetworkPolicies"

        # Check for Namespaces
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        assert (
            len(namespaces) > 0
        ), "Network policy configuration should have Namespaces"

    def test_networkpolicy_configuration_has_consistent_namespaces(self):
        """Test network policy configuration has consistent namespaces."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check namespaces
        for doc in docs:
            if "metadata" in doc and "namespace" in doc["metadata"]:
                namespace = doc["metadata"]["namespace"]
                assert (
                    namespace == "production"
                ), f"Resource {doc.get('metadata', {}).get('name', 'unknown')} should be in production namespace"

    def test_networkpolicy_configuration_has_consistent_labels(self):
        """Test network policy configuration has consistent labels."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
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

    def test_networkpolicy_configuration_has_consistent_annotations(self):
        """Test network policy configuration has consistent annotations."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check annotations
        for doc in docs:
            if "metadata" in doc and "annotations" in doc["metadata"]:
                annotations = doc["metadata"]["annotations"]
                assert "description" in annotations
                assert "app.kubernetes.io/created-by" in annotations

    def test_networkpolicy_configuration_has_valid_api_versions(self):
        """Test network policy configuration has valid API versions."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check API versions
        for doc in docs:
            if "apiVersion" in doc:
                api_version = doc["apiVersion"]
                assert isinstance(api_version, str)
                assert len(api_version) > 0
                assert "/" in api_version or api_version.startswith("v")

    def test_networkpolicy_configuration_has_valid_kinds(self):
        """Test network policy configuration has valid kinds."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check kinds
        valid_kinds = ["NetworkPolicy", "Namespace"]
        for doc in docs:
            if "kind" in doc:
                kind = doc["kind"]
                assert kind in valid_kinds, f"Invalid kind: {kind}"

    def test_networkpolicy_configuration_has_valid_metadata(self):
        """Test network policy configuration has valid metadata."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check metadata
        for doc in docs:
            if "metadata" in doc:
                metadata = doc["metadata"]
                assert "name" in metadata
                assert isinstance(metadata["name"], str)
                assert len(metadata["name"]) > 0
                assert len(metadata["name"]) <= 63  # Kubernetes name length limit

    def test_networkpolicy_configuration_has_no_duplicate_names(self):
        """Test network policy configuration has no duplicate names."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check names
        names = []
        for doc in docs:
            if "metadata" in doc and "name" in doc["metadata"]:
                name = doc["metadata"]["name"]
                assert name not in names, f"Duplicate name: {name}"
                names.append(name)

    def test_networkpolicy_configuration_has_valid_specs(self):
        """Test network policy configuration has valid specs."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check specs
        for doc in docs:
            if "spec" in doc:
                spec = doc["spec"]
                assert isinstance(spec, dict)
                assert len(spec) > 0

    def test_networkpolicy_configuration_has_valid_networkpolicy_specs(self):
        """Test network policy configuration has valid NetworkPolicy specs."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check NetworkPolicy specs
        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
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

    def test_networkpolicy_configuration_has_valid_namespace_specs(self):
        """Test network policy configuration has valid Namespace specs."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check Namespace specs
        namespaces = [doc for doc in docs if doc.get("kind") == "Namespace"]
        for namespace in namespaces:
            spec = namespace.get("spec", {})
            # Namespace spec is optional, but if present should be valid
            if spec:
                assert isinstance(spec, dict)

    def test_networkpolicy_configuration_has_valid_ingress_rules(self):
        """Test network policy configuration has valid ingress rules."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check ingress rules
        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
        for netpol in network_policies:
            if "ingress" in netpol["spec"]:
                ingress_rules = netpol["spec"]["ingress"]
                for rule in ingress_rules:
                    # Check from sources
                    if "from" in rule:
                        for source in rule["from"]:
                            # Check namespace selector
                            if "namespaceSelector" in source:
                                assert "matchLabels" in source["namespaceSelector"]
                                assert (
                                    len(source["namespaceSelector"]["matchLabels"]) > 0
                                )

                            # Check pod selector
                            if "podSelector" in source:
                                assert "matchLabels" in source["podSelector"]
                                assert len(source["podSelector"]["matchLabels"]) > 0

                    # Check ports
                    if "ports" in rule:
                        for port in rule["ports"]:
                            assert "protocol" in port
                            assert port["protocol"] in ["TCP", "UDP"]

    def test_networkpolicy_configuration_has_valid_egress_rules(self):
        """Test network policy configuration has valid egress rules."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check egress rules
        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
        for netpol in network_policies:
            if "egress" in netpol["spec"]:
                egress_rules = netpol["spec"]["egress"]
                for rule in egress_rules:
                    # Check to destinations
                    if "to" in rule:
                        for destination in rule["to"]:
                            # Check namespace selector
                            if "namespaceSelector" in destination:
                                assert "matchLabels" in destination["namespaceSelector"]
                                assert (
                                    len(destination["namespaceSelector"]["matchLabels"])
                                    > 0
                                )

                            # Check pod selector
                            if "podSelector" in destination:
                                assert "matchLabels" in destination["podSelector"]
                                assert (
                                    len(destination["podSelector"]["matchLabels"]) > 0
                                )

                    # Check ports
                    if "ports" in rule:
                        for port in rule["ports"]:
                            assert "protocol" in port
                            assert port["protocol"] in ["TCP", "UDP"]

    def test_networkpolicy_configuration_has_valid_pod_selectors(self):
        """Test network policy configuration has valid pod selectors."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check pod selectors
        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
        for netpol in network_policies:
            pod_selector = netpol["spec"]["podSelector"]

            # Check match labels
            assert "matchLabels" in pod_selector
            assert len(pod_selector["matchLabels"]) > 0

            # Check label values are valid
            for key, value in pod_selector["matchLabels"].items():
                assert isinstance(key, str)
                assert isinstance(value, str)
                assert len(key) > 0
                assert len(value) > 0

    def test_networkpolicy_configuration_has_valid_namespace_selectors(self):
        """Test network policy configuration has valid namespace selectors."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")

        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Check namespace selectors
        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
        for netpol in network_policies:
            # Check ingress rules
            if "ingress" in netpol["spec"]:
                for rule in netpol["spec"]["ingress"]:
                    if "from" in rule:
                        for source in rule["from"]:
                            if "namespaceSelector" in source:
                                ns_selector = source["namespaceSelector"]
                                assert "matchLabels" in ns_selector
                                assert len(ns_selector["matchLabels"]) > 0

                                # Check label values are valid
                                for key, value in ns_selector["matchLabels"].items():
                                    assert isinstance(key, str)
                                    assert isinstance(value, str)
                                    assert len(key) > 0
                                    assert len(value) > 0

            # Check egress rules
            if "egress" in netpol["spec"]:
                for rule in netpol["spec"]["egress"]:
                    if "to" in rule:
                        for destination in rule["to"]:
                            if "namespaceSelector" in destination:
                                ns_selector = destination["namespaceSelector"]
                                assert "matchLabels" in ns_selector
                                assert len(ns_selector["matchLabels"]) > 0

                                # Check label values are valid
                                for key, value in ns_selector["matchLabels"].items():
                                    assert isinstance(key, str)
                                    assert isinstance(value, str)
                                    assert len(key) > 0
                                    assert len(value) > 0
