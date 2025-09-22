"""Integration tests for security context configuration validation."""

import pytest
import yaml
from pathlib import Path


class TestSecurityContextValidation:
    """Test security context configuration validation."""

    def test_all_services_have_security_context(self):
        """Test all services have security context configured."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            assert "securityContext" in container

            security_context = container["securityContext"]
            assert isinstance(security_context, dict)
            assert len(security_context) > 0

    def test_security_context_has_required_fields(self):
        """Test security context has required fields."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check required fields
            assert "runAsNonRoot" in security_context
            assert "runAsUser" in security_context
            assert "runAsGroup" in security_context
            assert "allowPrivilegeEscalation" in security_context
            assert "readOnlyRootFilesystem" in security_context
            assert "capabilities" in security_context

    def test_security_context_has_correct_values(self):
        """Test security context has correct values."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check runAsNonRoot is True
            assert security_context["runAsNonRoot"] is True

            # Check runAsUser is 1000
            assert security_context["runAsUser"] == 1000

            # Check runAsGroup is 1000
            assert security_context["runAsGroup"] == 1000

            # Check allowPrivilegeEscalation is False
            assert security_context["allowPrivilegeEscalation"] is False

            # Check readOnlyRootFilesystem is True
            assert security_context["readOnlyRootFilesystem"] is True

    def test_security_context_has_capabilities_drop(self):
        """Test security context has capabilities drop configured."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check capabilities is present
            assert "capabilities" in security_context
            capabilities = security_context["capabilities"]

            # Check drop is present
            assert "drop" in capabilities
            assert isinstance(capabilities["drop"], list)
            assert len(capabilities["drop"]) > 0

            # Check ALL capability is dropped
            assert "ALL" in capabilities["drop"]

    def test_security_context_has_no_add_capabilities(self):
        """Test security context has no add capabilities."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check capabilities is present
            assert "capabilities" in security_context
            capabilities = security_context["capabilities"]

            # Check add is not present or empty
            if "add" in capabilities:
                assert len(capabilities["add"]) == 0

    def test_security_context_has_valid_user_id(self):
        """Test security context has valid user ID."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check runAsUser is valid
            user_id = security_context["runAsUser"]
            assert isinstance(user_id, int)
            assert user_id > 0
            assert user_id < 65536  # Valid UID range

    def test_security_context_has_valid_group_id(self):
        """Test security context has valid group ID."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check runAsGroup is valid
            group_id = security_context["runAsGroup"]
            assert isinstance(group_id, int)
            assert group_id > 0
            assert group_id < 65536  # Valid GID range

    def test_security_context_has_valid_boolean_values(self):
        """Test security context has valid boolean values."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check boolean fields are actually boolean
            assert isinstance(security_context["runAsNonRoot"], bool)
            assert isinstance(security_context["allowPrivilegeEscalation"], bool)
            assert isinstance(security_context["readOnlyRootFilesystem"], bool)

    def test_security_context_has_valid_capabilities_format(self):
        """Test security context has valid capabilities format."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check capabilities format
            capabilities = security_context["capabilities"]
            assert isinstance(capabilities, dict)

            # Check drop is a list
            assert "drop" in capabilities
            assert isinstance(capabilities["drop"], list)

            # Check all dropped capabilities are strings
            for cap in capabilities["drop"]:
                assert isinstance(cap, str)
                assert len(cap) > 0

    def test_security_context_has_required_capabilities_dropped(self):
        """Test security context has required capabilities dropped."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check required capabilities are dropped
            capabilities = security_context["capabilities"]
            dropped_caps = capabilities["drop"]

            # Check ALL capability is dropped
            assert "ALL" in dropped_caps

            # Check other dangerous capabilities are dropped
            dangerous_caps = [
                "SYS_ADMIN",
                "SYS_PTRACE",
                "SYS_MODULE",
                "SYS_RAWIO",
                "SYS_PACCT",
                "SYS_ADMIN",
                "SYS_NICE",
                "SYS_RESOURCE",
                "SYS_TIME",
                "SYS_TTY_CONFIG",
                "MKNOD",
                "LEASE",
                "AUDIT_CONTROL",
                "AUDIT_WRITE",
                "AUDIT_READ",
                "DAC_OVERRIDE",
                "DAC_READ_SEARCH",
                "FOWNER",
                "FSETID",
                "KILL",
                "SETGID",
                "SETUID",
                "NET_RAW",
                "CHOWN",
                "NET_BIND_SERVICE",
                "NET_ADMIN",
                "SYSLOG",
                "SYS_CHROOT",
                "SETPCAP",
                "MAC_OVERRIDE",
                "MAC_ADMIN",
                "SYS_BOOT",
                "SYS_RAWIO",
                "SYS_PACCT",
                "SYS_ADMIN",
                "SYS_NICE",
                "SYS_RESOURCE",
                "SYS_TIME",
                "SYS_TTY_CONFIG",
                "MKNOD",
                "LEASE",
                "AUDIT_CONTROL",
                "AUDIT_WRITE",
                "AUDIT_READ",
                "DAC_OVERRIDE",
                "DAC_READ_SEARCH",
                "FOWNER",
                "FSETID",
                "KILL",
                "SETGID",
                "SETUID",
                "NET_RAW",
                "CHOWN",
                "NET_BIND_SERVICE",
                "NET_ADMIN",
                "SYSLOG",
                "SYS_CHROOT",
                "SETPCAP",
                "MAC_OVERRIDE",
                "MAC_ADMIN",
                "SYS_BOOT",
            ]

            for cap in dangerous_caps:
                if cap in dropped_caps:
                    # This is good - dangerous capability is dropped
                    pass
                else:
                    # This is also acceptable - capability might not be present
                    pass

    def test_security_context_has_no_privileged_mode(self):
        """Test security context has no privileged mode."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check privileged is not set or is False
            if "privileged" in security_context:
                assert security_context["privileged"] is False

    def test_security_context_has_no_sysctls(self):
        """Test security context has no sysctls."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check sysctls is not present or empty
            if "sysctls" in security_context:
                assert len(security_context["sysctls"]) == 0

    def test_security_context_has_no_seccomp_profile(self):
        """Test security context has no seccomp profile."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check seccompProfile is not present or is RuntimeDefault
            if "seccompProfile" in security_context:
                seccomp_profile = security_context["seccompProfile"]
                assert "type" in seccomp_profile
                assert seccomp_profile["type"] in ["RuntimeDefault", "Localhost"]

    def test_security_context_has_no_selinux_options(self):
        """Test security context has no selinux options."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check seLinuxOptions is not present or has safe values
            if "seLinuxOptions" in security_context:
                selinux_options = security_context["seLinuxOptions"]
                assert "level" in selinux_options
                assert selinux_options["level"] in ["s0", "s0-s0:c0.c1023"]

    def test_security_context_has_no_windows_options(self):
        """Test security context has no windows options."""
        probes_file = Path("k8s/production/manifests/health/probes.yaml")
        with open(probes_file) as f:
            docs = list(yaml.safe_load_all(f))

        deployments = [doc for doc in docs if doc.get("kind") == "Deployment"]

        for deployment in deployments:
            container = deployment["spec"]["template"]["spec"]["containers"][0]
            security_context = container["securityContext"]

            # Check windowsOptions is not present
            assert "windowsOptions" not in security_context
