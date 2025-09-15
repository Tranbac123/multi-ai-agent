"""Integration tests for health probes configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestHealthProbesValidation:
    """Test health probes configuration validation."""

    def test_health_probes_have_required_fields(self):
        """Test all health probe configurations have required fields."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

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

    def test_health_probes_have_valid_paths(self):
        """Test health probe paths are valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe path
            liveness_path = container["livenessProbe"]["httpGet"]["path"]
            assert liveness_path.startswith("/")
            assert liveness_path == "/health"

            # Check readiness probe path
            readiness_path = container["readinessProbe"]["httpGet"]["path"]
            assert readiness_path.startswith("/")
            assert readiness_path == "/health/ready"

    def test_health_probes_have_valid_ports(self):
        """Test health probe ports are valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe port
            liveness_port = container["livenessProbe"]["httpGet"]["port"]
            assert isinstance(liveness_port, (int, str))
            if isinstance(liveness_port, str):
                assert liveness_port.isdigit()
                liveness_port = int(liveness_port)
            assert liveness_port > 0
            assert liveness_port <= 65535

            # Check readiness probe port
            readiness_port = container["readinessProbe"]["httpGet"]["port"]
            assert isinstance(readiness_port, (int, str))
            if isinstance(readiness_port, str):
                assert readiness_port.isdigit()
                readiness_port = int(readiness_port)
            assert readiness_port > 0
            assert readiness_port <= 65535

    def test_health_probes_have_valid_timing(self):
        """Test health probe timing is valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe timing
            liveness = container["livenessProbe"]
            assert liveness["initialDelaySeconds"] > 0
            assert liveness["initialDelaySeconds"] <= 300  # Max 5 minutes
            assert liveness["periodSeconds"] > 0
            assert liveness["periodSeconds"] <= 60  # Max 1 minute

            # Check readiness probe timing
            readiness = container["readinessProbe"]
            assert readiness["initialDelaySeconds"] > 0
            assert readiness["initialDelaySeconds"] <= 60  # Max 1 minute
            assert readiness["periodSeconds"] > 0
            assert readiness["periodSeconds"] <= 30  # Max 30 seconds

    def test_health_probes_have_valid_timeouts(self):
        """Test health probe timeouts are valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe timeout
            if "timeoutSeconds" in container["livenessProbe"]:
                timeout = container["livenessProbe"]["timeoutSeconds"]
                assert timeout > 0
                assert timeout <= 30  # Max 30 seconds

            # Check readiness probe timeout
            if "timeoutSeconds" in container["readinessProbe"]:
                timeout = container["readinessProbe"]["timeoutSeconds"]
                assert timeout > 0
                assert timeout <= 30  # Max 30 seconds

    def test_health_probes_have_valid_failure_thresholds(self):
        """Test health probe failure thresholds are valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe failure threshold
            if "failureThreshold" in container["livenessProbe"]:
                threshold = container["livenessProbe"]["failureThreshold"]
                assert threshold > 0
                assert threshold <= 10  # Max 10 failures

            # Check readiness probe failure threshold
            if "failureThreshold" in container["readinessProbe"]:
                threshold = container["readinessProbe"]["failureThreshold"]
                assert threshold > 0
                assert threshold <= 10  # Max 10 failures

    def test_health_probes_have_valid_success_thresholds(self):
        """Test health probe success thresholds are valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe success threshold
            if "successThreshold" in container["livenessProbe"]:
                threshold = container["livenessProbe"]["successThreshold"]
                assert threshold > 0
                assert threshold <= 5  # Max 5 successes

            # Check readiness probe success threshold
            if "successThreshold" in container["readinessProbe"]:
                threshold = container["readinessProbe"]["successThreshold"]
                assert threshold > 0
                assert threshold <= 5  # Max 5 successes

    def test_health_probes_have_valid_http_headers(self):
        """Test health probe HTTP headers are valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe headers
            if "httpHeaders" in container["livenessProbe"]["httpGet"]:
                headers = container["livenessProbe"]["httpGet"]["httpHeaders"]
                for header in headers:
                    assert "name" in header
                    assert "value" in header
                    assert isinstance(header["name"], str)
                    assert isinstance(header["value"], str)
                    assert len(header["name"]) > 0
                    assert len(header["value"]) > 0

            # Check readiness probe headers
            if "httpHeaders" in container["readinessProbe"]["httpGet"]:
                headers = container["readinessProbe"]["httpGet"]["httpHeaders"]
                for header in headers:
                    assert "name" in header
                    assert "value" in header
                    assert isinstance(header["name"], str)
                    assert isinstance(header["value"], str)
                    assert len(header["name"]) > 0
                    assert len(header["value"]) > 0

    def test_health_probes_have_valid_schemes(self):
        """Test health probe schemes are valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe scheme
            if "scheme" in container["livenessProbe"]["httpGet"]:
                scheme = container["livenessProbe"]["httpGet"]["scheme"]
                assert scheme in ["HTTP", "HTTPS"]

            # Check readiness probe scheme
            if "scheme" in container["readinessProbe"]["httpGet"]:
                scheme = container["readinessProbe"]["httpGet"]["scheme"]
                assert scheme in ["HTTP", "HTTPS"]

    def test_health_probes_have_valid_initial_delay_relationships(self):
        """Test health probe initial delay relationships are valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            liveness = container["livenessProbe"]
            readiness = container["readinessProbe"]

            # Check that liveness initial delay is >= readiness initial delay
            liveness_delay = liveness["initialDelaySeconds"]
            readiness_delay = readiness["initialDelaySeconds"]
            assert (
                liveness_delay >= readiness_delay
            ), "Liveness probe initial delay should be >= readiness probe initial delay"

    def test_health_probes_have_valid_period_relationships(self):
        """Test health probe period relationships are valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            liveness = container["livenessProbe"]
            readiness = container["readinessProbe"]

            # Check that liveness period is >= readiness period
            liveness_period = liveness["periodSeconds"]
            readiness_period = readiness["periodSeconds"]
            assert (
                liveness_period >= readiness_period
            ), "Liveness probe period should be >= readiness probe period"

    def test_health_probes_have_valid_http_get_configuration(self):
        """Test health probe HTTP GET configuration is valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe HTTP GET
            liveness_http = container["livenessProbe"]["httpGet"]
            assert "path" in liveness_http
            assert "port" in liveness_http
            assert liveness_http["path"].startswith("/")

            # Check readiness probe HTTP GET
            readiness_http = container["readinessProbe"]["httpGet"]
            assert "path" in readiness_http
            assert "port" in readiness_http
            assert readiness_http["path"].startswith("/")

    def test_health_probes_have_valid_probe_types(self):
        """Test health probe types are valid."""
        probes_file = Path("infra/k8s/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]

            # Check liveness probe type
            liveness = container["livenessProbe"]
            assert (
                "httpGet" in liveness or "exec" in liveness or "tcpSocket" in liveness
            )

            # Check readiness probe type
            readiness = container["readinessProbe"]
            assert (
                "httpGet" in readiness
                or "exec" in readiness
                or "tcpSocket" in readiness
            )
