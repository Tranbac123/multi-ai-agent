"""Integration tests for HPA configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestHPAValidation:
    """Test HPA configuration validation."""

    def test_hpa_has_required_fields(self):
        """Test all HPAs have required fields."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            spec = hpa["spec"]

            # Required fields
            assert "scaleTargetRef" in spec
            assert "name" in spec["scaleTargetRef"]
            assert "minReplicas" in spec
            assert "maxReplicas" in spec
            assert "metrics" in spec

            # Validate replica counts
            assert spec["minReplicas"] >= 1
            assert spec["maxReplicas"] >= spec["minReplicas"]
            assert spec["maxReplicas"] <= 50  # Reasonable upper limit

    def test_hpa_targets_existing_deployments(self):
        """Test HPAs target existing deployments."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        # Get all deployments
        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]
        deployment_names = {d["metadata"]["name"] for d in deployments}

        # Get all HPAs
        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            target_name = hpa["spec"]["scaleTargetRef"]["name"]
            assert (
                target_name in deployment_names
            ), f"HPA {hpa['metadata']['name']} targets non-existent deployment {target_name}"

    def test_hpa_has_unique_names(self):
        """Test HPAs have unique names."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]
        names = [hpa["metadata"]["name"] for hpa in hpas]

        assert len(names) == len(set(names)), "HPA names must be unique"

    def test_hpa_has_proper_namespace(self):
        """Test HPAs are in the correct namespace."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            namespace = hpa["metadata"].get("namespace", "default")
            assert (
                namespace == "production"
            ), f"HPA {hpa['metadata']['name']} should be in production namespace"

    def test_hpa_has_proper_labels(self):
        """Test HPAs have proper labels."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            labels = hpa["metadata"].get("labels", {})

            # Check required labels
            assert "app.kubernetes.io/name" in labels
            assert "app.kubernetes.io/instance" in labels
            assert "app.kubernetes.io/version" in labels
            assert "app.kubernetes.io/component" in labels
            assert "app.kubernetes.io/part-of" in labels
            assert "app.kubernetes.io/managed-by" in labels

    def test_hpa_has_proper_annotations(self):
        """Test HPAs have proper annotations."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            annotations = hpa["metadata"].get("annotations", {})

            # Check required annotations
            assert "description" in annotations
            assert "app.kubernetes.io/created-by" in annotations

    def test_hpa_has_resource_metrics(self):
        """Test HPAs have resource metrics configured."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            metrics = hpa["spec"]["metrics"]

            # Check that we have resource metrics
            resource_metrics = [m for m in metrics if m.get("type") == "Resource"]
            assert (
                len(resource_metrics) > 0
            ), f"HPA {hpa['metadata']['name']} should have resource metrics"

            # Check CPU and memory metrics
            cpu_metric = next(
                (m for m in resource_metrics if m["resource"]["name"] == "cpu"), None
            )
            memory_metric = next(
                (m for m in resource_metrics if m["resource"]["name"] == "memory"), None
            )

            assert (
                cpu_metric is not None
            ), f"HPA {hpa['metadata']['name']} should have CPU metric"
            assert (
                memory_metric is not None
            ), f"HPA {hpa['metadata']['name']} should have memory metric"

            # Check target utilization values
            assert cpu_metric["resource"]["target"]["averageUtilization"] > 0
            assert cpu_metric["resource"]["target"]["averageUtilization"] <= 100
            assert memory_metric["resource"]["target"]["averageUtilization"] > 0
            assert memory_metric["resource"]["target"]["averageUtilization"] <= 100

    def test_hpa_has_behavior_configuration(self):
        """Test HPAs have behavior configuration."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            assert (
                "behavior" in hpa["spec"]
            ), f"HPA {hpa['metadata']['name']} should have behavior configuration"

            behavior = hpa["spec"]["behavior"]

            # Check scale down behavior
            assert "scaleDown" in behavior
            scale_down = behavior["scaleDown"]
            assert "stabilizationWindowSeconds" in scale_down
            assert scale_down["stabilizationWindowSeconds"] > 0

            # Check scale up behavior
            assert "scaleUp" in behavior
            scale_up = behavior["scaleUp"]
            assert "stabilizationWindowSeconds" in scale_up
            assert scale_up["stabilizationWindowSeconds"] > 0

    def test_hpa_has_reasonable_scaling_limits(self):
        """Test HPAs have reasonable scaling limits."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            spec = hpa["spec"]

            # Check replica limits are reasonable
            min_replicas = spec["minReplicas"]
            max_replicas = spec["maxReplicas"]

            assert (
                min_replicas >= 1
            ), f"HPA {hpa['metadata']['name']} minReplicas should be at least 1"
            assert (
                max_replicas <= 50
            ), f"HPA {hpa['metadata']['name']} maxReplicas should be at most 50"
            assert (
                max_replicas >= min_replicas
            ), f"HPA {hpa['metadata']['name']} maxReplicas should be >= minReplicas"

            # Check scaling ratio is reasonable (not too aggressive)
            scaling_ratio = max_replicas / min_replicas
            assert (
                scaling_ratio <= 10
            ), f"HPA {hpa['metadata']['name']} scaling ratio should be at most 10x"

    def test_hpa_has_proper_metric_targets(self):
        """Test HPAs have proper metric targets."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            metrics = hpa["spec"]["metrics"]

            for metric in metrics:
                if metric.get("type") == "Resource":
                    resource = metric["resource"]
                    target = resource["target"]

                    # Check target utilization is reasonable
                    if "averageUtilization" in target:
                        utilization = target["averageUtilization"]
                        assert (
                            utilization > 0
                        ), f"HPA {hpa['metadata']['name']} metric {resource['name']} utilization should be > 0"
                        assert (
                            utilization <= 100
                        ), f"HPA {hpa['metadata']['name']} metric {resource['name']} utilization should be <= 100"

                    # Check target value is reasonable
                    if "averageValue" in target:
                        value = target["averageValue"]
                        assert (
                            value > 0
                        ), f"HPA {hpa['metadata']['name']} metric {resource['name']} value should be > 0"

    def test_hpa_has_proper_metric_selectors(self):
        """Test HPAs have proper metric selectors."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            metrics = hpa["spec"]["metrics"]

            for metric in metrics:
                if metric.get("type") == "Resource":
                    resource = metric["resource"]

                    # Check resource name is valid
                    assert resource["name"] in [
                        "cpu",
                        "memory",
                    ], f"HPA {hpa['metadata']['name']} has invalid resource name: {resource['name']}"

                    # Check target is properly configured
                    target = resource["target"]
                    assert (
                        "averageUtilization" in target or "averageValue" in target
                    ), f"HPA {hpa['metadata']['name']} metric {resource['name']} should have target"

    def test_hpa_has_proper_behavior_policies(self):
        """Test HPAs have proper behavior policies."""
        hpa_file = Path("infra/k8s/autoscaling/hpa.yaml")
        with open(hpa_file) as f:
            docs = list(yaml.safe_load_all(f))

        hpas = [doc for doc in docs if doc.get("kind") == "HorizontalPodAutoscaler"]

        for hpa in hpas:
            behavior = hpa["spec"]["behavior"]

            # Check scale down behavior
            scale_down = behavior["scaleDown"]
            assert "stabilizationWindowSeconds" in scale_down
            assert scale_down["stabilizationWindowSeconds"] > 0
            assert scale_down["stabilizationWindowSeconds"] <= 300  # Max 5 minutes

            # Check scale up behavior
            scale_up = behavior["scaleUp"]
            assert "stabilizationWindowSeconds" in scale_up
            assert scale_up["stabilizationWindowSeconds"] > 0
            assert scale_up["stabilizationWindowSeconds"] <= 300  # Max 5 minutes

            # Check policies if present
            if "policies" in scale_down:
                for policy in scale_down["policies"]:
                    assert "type" in policy
                    assert "value" in policy
                    assert policy["type"] in ["Pods", "Percent"]
                    assert policy["value"] > 0

            if "policies" in scale_up:
                for policy in scale_up["policies"]:
                    assert "type" in policy
                    assert "value" in policy
                    assert policy["type"] in ["Pods", "Percent"]
                    assert policy["value"] > 0
