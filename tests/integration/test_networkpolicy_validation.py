"""Integration tests for NetworkPolicy configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestNetworkPolicyValidation:
    """Test NetworkPolicy configuration validation."""

    def test_network_policies_have_required_fields(self):
        """Test all NetworkPolicies have required fields."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]

        for netpol in network_policies:
            spec = netpol["spec"]

            # Required fields
            assert "podSelector" in spec
            assert "policyTypes" in spec

            # Check policy types
            assert "Ingress" in spec["policyTypes"] or "Egress" in spec["policyTypes"]

            # Check pod selector
            assert "matchLabels" in spec["podSelector"]
            assert len(spec["podSelector"]["matchLabels"]) > 0

    def test_network_policies_have_unique_names(self):
        """Test NetworkPolicies have unique names."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]
        names = [np["metadata"]["name"] for np in network_policies]

        assert len(names) == len(set(names)), "NetworkPolicy names must be unique"

    def test_network_policies_have_proper_namespace(self):
        """Test NetworkPolicies are in the correct namespace."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]

        for netpol in network_policies:
            namespace = netpol["metadata"].get("namespace", "default")
            assert (
                namespace == "production"
            ), f"NetworkPolicy {netpol['metadata']['name']} should be in production namespace"

    def test_network_policies_have_proper_labels(self):
        """Test NetworkPolicies have proper labels."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]

        for netpol in network_policies:
            labels = netpol["metadata"].get("labels", {})

            # Check required labels
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

    def test_network_policies_have_proper_annotations(self):
        """Test NetworkPolicies have proper annotations."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]

        for netpol in network_policies:
            annotations = netpol["metadata"].get("annotations", {})

            # Check required annotations
            assert "description" in annotations
            assert "app.kubernetes.io/created-by" in annotations

    def test_network_policies_have_valid_ingress_rules(self):
        """Test NetworkPolicies have valid ingress rules."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

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

                            if "port" in port:
                                assert isinstance(port["port"], (int, str))
                                if isinstance(port["port"], str):
                                    assert port["port"].isdigit()
                                else:
                                    assert port["port"] > 0
                                    assert port["port"] <= 65535

    def test_network_policies_have_valid_egress_rules(self):
        """Test NetworkPolicies have valid egress rules."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

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

                            if "port" in port:
                                assert isinstance(port["port"], (int, str))
                                if isinstance(port["port"], str):
                                    assert port["port"].isdigit()
                                else:
                                    assert port["port"] > 0
                                    assert port["port"] <= 65535

    def test_network_policies_have_valid_pod_selectors(self):
        """Test NetworkPolicies have valid pod selectors."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

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

    def test_network_policies_have_valid_namespace_selectors(self):
        """Test NetworkPolicies have valid namespace selectors."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

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

    def test_network_policies_have_valid_ports(self):
        """Test NetworkPolicies have valid ports."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]

        for netpol in network_policies:
            # Check ingress ports
            if "ingress" in netpol["spec"]:
                for rule in netpol["spec"]["ingress"]:
                    if "ports" in rule:
                        for port in rule["ports"]:
                            assert "protocol" in port
                            assert port["protocol"] in ["TCP", "UDP"]

                            if "port" in port:
                                port_value = port["port"]
                                if isinstance(port_value, str):
                                    assert port_value.isdigit()
                                    port_value = int(port_value)
                                assert port_value > 0
                                assert port_value <= 65535

            # Check egress ports
            if "egress" in netpol["spec"]:
                for rule in netpol["spec"]["egress"]:
                    if "ports" in rule:
                        for port in rule["ports"]:
                            assert "protocol" in port
                            assert port["protocol"] in ["TCP", "UDP"]

                            if "port" in port:
                                port_value = port["port"]
                                if isinstance(port_value, str):
                                    assert port_value.isdigit()
                                    port_value = int(port_value)
                                assert port_value > 0
                                assert port_value <= 65535

    def test_network_policies_have_valid_policy_types(self):
        """Test NetworkPolicies have valid policy types."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]

        for netpol in network_policies:
            policy_types = netpol["spec"]["policyTypes"]

            # Check policy types are valid
            for policy_type in policy_types:
                assert policy_type in ["Ingress", "Egress"]

            # Check we have at least one policy type
            assert len(policy_types) > 0

            # Check we don't have duplicate policy types
            assert len(policy_types) == len(set(policy_types))

    def test_network_policies_have_valid_ingress_egress_consistency(self):
        """Test NetworkPolicies have consistent ingress/egress rules."""
        netpol_file = Path("k8s/production/manifests/security/networkpolicy.yaml")
        with open(netpol_file) as f:
            docs = list(yaml.safe_load_all(f))

        network_policies = [doc for doc in docs if doc.get("kind") == "NetworkPolicy"]

        for netpol in network_policies:
            spec = netpol["spec"]
            policy_types = spec["policyTypes"]

            # Check ingress consistency
            if "Ingress" in policy_types:
                assert "ingress" in spec
                assert len(spec["ingress"]) > 0
            else:
                assert "ingress" not in spec or len(spec["ingress"]) == 0

            # Check egress consistency
            if "Egress" in policy_types:
                assert "egress" in spec
                assert len(spec["egress"]) > 0
            else:
                assert "egress" not in spec or len(spec["egress"]) == 0
