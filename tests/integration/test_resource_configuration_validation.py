"""Integration tests for resource configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestResourceConfigurationValidation:
    """Test resource configuration validation."""

    def test_all_services_have_resource_limits(self):
        """Test all services have resource limits configured."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
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

    def test_resource_limits_are_valid_cpu_format(self):
        """Test resource CPU limits are in valid format."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            resources = container["resources"]

            # Check CPU limits format
            cpu_limit = resources["limits"]["cpu"]
            assert isinstance(cpu_limit, str)
            assert (
                cpu_limit.endswith("m")
                or cpu_limit.endswith("n")
                or cpu_limit.isdigit()
            )

            # Check CPU requests format
            cpu_request = resources["requests"]["cpu"]
            assert isinstance(cpu_request, str)
            assert (
                cpu_request.endswith("m")
                or cpu_request.endswith("n")
                or cpu_request.isdigit()
            )

    def test_resource_limits_are_valid_memory_format(self):
        """Test resource memory limits are in valid format."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            resources = container["resources"]

            # Check memory limits format
            memory_limit = resources["limits"]["memory"]
            assert isinstance(memory_limit, str)
            assert (
                memory_limit.endswith("Gi")
                or memory_limit.endswith("Mi")
                or memory_limit.endswith("Ki")
            )

            # Check memory requests format
            memory_request = resources["requests"]["memory"]
            assert isinstance(memory_request, str)
            assert (
                memory_request.endswith("Gi")
                or memory_request.endswith("Mi")
                or memory_request.endswith("Ki")
            )

    def test_resource_limits_are_reasonable_cpu(self):
        """Test resource CPU limits are reasonable."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            resources = container["resources"]

            # Check CPU limits are reasonable
            cpu_limit = resources["limits"]["cpu"]
            if cpu_limit.endswith("m"):
                cpu_millicores = int(cpu_limit[:-1])
                assert cpu_millicores > 0
                assert cpu_millicores <= 2000  # Max 2 CPU cores
            elif cpu_limit.endswith("n"):
                cpu_nanocores = int(cpu_limit[:-1])
                assert cpu_nanocores > 0
                assert cpu_nanocores <= 2000000000  # Max 2 CPU cores in nanocores
            elif cpu_limit.isdigit():
                cpu_cores = int(cpu_limit)
                assert cpu_cores > 0
                assert cpu_cores <= 2  # Max 2 CPU cores

            # Check CPU requests are reasonable
            cpu_request = resources["requests"]["cpu"]
            if cpu_request.endswith("m"):
                cpu_millicores = int(cpu_request[:-1])
                assert cpu_millicores > 0
                assert cpu_millicores <= 1000  # Max 1 CPU core
            elif cpu_request.endswith("n"):
                cpu_nanocores = int(cpu_request[:-1])
                assert cpu_nanocores > 0
                assert cpu_nanocores <= 1000000000  # Max 1 CPU core in nanocores
            elif cpu_request.isdigit():
                cpu_cores = int(cpu_request)
                assert cpu_cores > 0
                assert cpu_cores <= 1  # Max 1 CPU core

    def test_resource_limits_are_reasonable_memory(self):
        """Test resource memory limits are reasonable."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            resources = container["resources"]

            # Check memory limits are reasonable
            memory_limit = resources["limits"]["memory"]
            if memory_limit.endswith("Gi"):
                memory_gb = int(memory_limit[:-2])
                assert memory_gb > 0
                assert memory_gb <= 4  # Max 4GB memory
            elif memory_limit.endswith("Mi"):
                memory_mb = int(memory_limit[:-2])
                assert memory_mb > 0
                assert memory_mb <= 4096  # Max 4GB memory
            elif memory_limit.endswith("Ki"):
                memory_kb = int(memory_limit[:-2])
                assert memory_kb > 0
                assert memory_kb <= 4194304  # Max 4GB memory in KiB

            # Check memory requests are reasonable
            memory_request = resources["requests"]["memory"]
            if memory_request.endswith("Gi"):
                memory_gb = int(memory_request[:-2])
                assert memory_gb > 0
                assert memory_gb <= 2  # Max 2GB memory
            elif memory_request.endswith("Mi"):
                memory_mb = int(memory_request[:-2])
                assert memory_mb > 0
                assert memory_mb <= 2048  # Max 2GB memory
            elif memory_request.endswith("Ki"):
                memory_kb = int(memory_request[:-2])
                assert memory_kb > 0
                assert memory_kb <= 2097152  # Max 2GB memory in KiB

    def test_resource_limits_are_consistent(self):
        """Test resource limits are consistent with requests."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            resources = container["resources"]

            # Check CPU limits >= requests
            cpu_limit = resources["limits"]["cpu"]
            cpu_request = resources["requests"]["cpu"]

            # Convert to millicores for comparison
            cpu_limit_millicores = self._convert_cpu_to_millicores(cpu_limit)
            cpu_request_millicores = self._convert_cpu_to_millicores(cpu_request)

            assert (
                cpu_limit_millicores >= cpu_request_millicores
            ), f"CPU limit should be >= CPU request for {deployment['metadata']['name']}"

            # Check memory limits >= requests
            memory_limit = resources["limits"]["memory"]
            memory_request = resources["requests"]["memory"]

            # Convert to MiB for comparison
            memory_limit_mib = self._convert_memory_to_mib(memory_limit)
            memory_request_mib = self._convert_memory_to_mib(memory_request)

            assert (
                memory_limit_mib >= memory_request_mib
            ), f"Memory limit should be >= Memory request for {deployment['metadata']['name']}"

    def test_resource_limits_have_required_units(self):
        """Test resource limits have required units."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            resources = container["resources"]

            # Check CPU limits have units
            cpu_limit = resources["limits"]["cpu"]
            assert (
                cpu_limit.endswith("m")
                or cpu_limit.endswith("n")
                or cpu_limit.isdigit()
            )

            # Check memory limits have units
            memory_limit = resources["limits"]["memory"]
            assert (
                memory_limit.endswith("Gi")
                or memory_limit.endswith("Mi")
                or memory_limit.endswith("Ki")
            )

    def test_resource_limits_have_valid_numeric_values(self):
        """Test resource limits have valid numeric values."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            resources = container["resources"]

            # Check CPU limits have valid numeric values
            cpu_limit = resources["limits"]["cpu"]
            if cpu_limit.endswith("m"):
                assert cpu_limit[:-1].isdigit()
            elif cpu_limit.endswith("n"):
                assert cpu_limit[:-1].isdigit()
            elif cpu_limit.isdigit():
                assert cpu_limit.isdigit()

            # Check memory limits have valid numeric values
            memory_limit = resources["limits"]["memory"]
            if memory_limit.endswith("Gi"):
                assert memory_limit[:-2].isdigit()
            elif memory_limit.endswith("Mi"):
                assert memory_limit[:-2].isdigit()
            elif memory_limit.endswith("Ki"):
                assert memory_limit[:-2].isdigit()

    def test_resource_limits_have_positive_values(self):
        """Test resource limits have positive values."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            resources = container["resources"]

            # Check CPU limits have positive values
            cpu_limit = resources["limits"]["cpu"]
            if cpu_limit.endswith("m"):
                assert int(cpu_limit[:-1]) > 0
            elif cpu_limit.endswith("n"):
                assert int(cpu_limit[:-1]) > 0
            elif cpu_limit.isdigit():
                assert int(cpu_limit) > 0

            # Check memory limits have positive values
            memory_limit = resources["limits"]["memory"]
            if memory_limit.endswith("Gi"):
                assert int(memory_limit[:-2]) > 0
            elif memory_limit.endswith("Mi"):
                assert int(memory_limit[:-2]) > 0
            elif memory_limit.endswith("Ki"):
                assert int(memory_limit[:-2]) > 0

    def _convert_cpu_to_millicores(self, cpu_value: str) -> int:
        """Convert CPU value to millicores for comparison."""
        if cpu_value.endswith("m"):
            return int(cpu_value[:-1])
        elif cpu_value.endswith("n"):
            return int(cpu_value[:-1]) // 1000000  # Convert nanocores to millicores
        elif cpu_value.isdigit():
            return int(cpu_value) * 1000  # Convert cores to millicores
        else:
            raise ValueError(f"Invalid CPU format: {cpu_value}")

    def _convert_memory_to_mib(self, memory_value: str) -> int:
        """Convert memory value to MiB for comparison."""
        if memory_value.endswith("Gi"):
            return int(memory_value[:-2]) * 1024  # Convert GiB to MiB
        elif memory_value.endswith("Mi"):
            return int(memory_value[:-2])  # Already in MiB
        elif memory_value.endswith("Ki"):
            return int(memory_value[:-2]) // 1024  # Convert KiB to MiB
        else:
            raise ValueError(f"Invalid memory format: {memory_value}")

    def test_resource_limits_have_consistent_units(self):
        """Test resource limits have consistent units within each resource type."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            resources = container["resources"]

            # Check CPU limits have consistent units
            cpu_limit = resources["limits"]["cpu"]
            cpu_request = resources["requests"]["cpu"]

            # Both should use the same unit type
            if cpu_limit.endswith("m"):
                assert cpu_request.endswith(
                    "m"
                ), f"CPU request should use same unit as limit for {deployment['metadata']['name']}"
            elif cpu_limit.endswith("n"):
                assert cpu_request.endswith(
                    "n"
                ), f"CPU request should use same unit as limit for {deployment['metadata']['name']}"
            elif cpu_limit.isdigit():
                assert (
                    cpu_request.isdigit()
                ), f"CPU request should use same unit as limit for {deployment['metadata']['name']}"

            # Check memory limits have consistent units
            memory_limit = resources["limits"]["memory"]
            memory_request = resources["requests"]["memory"]

            # Both should use the same unit type
            if memory_limit.endswith("Gi"):
                assert memory_request.endswith(
                    "Gi"
                ), f"Memory request should use same unit as limit for {deployment['metadata']['name']}"
            elif memory_limit.endswith("Mi"):
                assert memory_request.endswith(
                    "Mi"
                ), f"Memory request should use same unit as limit for {deployment['metadata']['name']}"
            elif memory_limit.endswith("Ki"):
                assert memory_request.endswith(
                    "Ki"
                ), f"Memory request should use same unit as limit for {deployment['metadata']['name']}"
