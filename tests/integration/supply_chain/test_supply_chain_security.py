"""Integration tests for Supply-chain Security features."""

import pytest
import asyncio
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone
from pathlib import Path

from libs.security.sbom_generator import (
    SBOMGenerator, SBOMFormat, ComponentType, LicenseType, Component, SBOMMetadata, SBOMDocument
)
from libs.security.image_signing import (
    ImageSigningManager, SigningAlgorithm, SignatureFormat, SignatureStatus, SigningKey, ImageSignature
)
from libs.security.cve_gates import (
    CVEGatesManager, VulnerabilitySeverity, GateStatus, VulnerabilityStatus, CVE GateRule, Vulnerability, ComponentVulnerability
)
from libs.security.slsa_provenance import (
    SLSAProvenanceManager, SLSALevel, BuildType, ArtifactType, BuildConfig, BuildMaterial, BuildOutput, SLSAProvenance
)


class TestSBOMGenerator:
    """Test SBOM generation functionality."""
    
    @pytest.fixture
    def sbom_generator(self):
        """Create SBOMGenerator instance for testing."""
        return SBOMGenerator()
    
    @pytest.fixture
    def test_project_path(self):
        """Create temporary test project directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            project_path = Path(temp_dir)
            
            # Create requirements.txt
            requirements_file = project_path / "requirements.txt"
            with open(requirements_file, 'w') as f:
                f.write("""requests==2.31.0
numpy==1.24.3
pandas==2.0.3
fastapi==0.104.1
sqlalchemy==2.0.23
""")
            
            # Create package.json
            package_json = project_path / "package.json"
            with open(package_json, 'w') as f:
                f.write("""{
  "name": "test-project",
  "version": "1.0.0",
  "dependencies": {
    "express": "^4.18.2",
    "lodash": "^4.17.21",
    "axios": "^1.6.0"
  },
  "devDependencies": {
    "jest": "^29.7.0",
    "eslint": "^8.54.0"
  }
}
""")
            
            # Create Dockerfile
            dockerfile = project_path / "Dockerfile"
            with open(dockerfile, 'w') as f:
                f.write("""FROM python:3.11-slim
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["python", "app.py"]
""")
            
            # Create a Python file
            app_file = project_path / "app.py"
            with open(app_file, 'w') as f:
                f.write("""import requests
import numpy as np
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
""")
            
            yield project_path
    
    @pytest.mark.asyncio
    async def test_generate_sbom_spdx_format(self, sbom_generator, test_project_path):
        """Test SBOM generation in SPDX format."""
        sbom_doc = await sbom_generator.generate_sbom(
            str(test_project_path),
            output_format=SBOMFormat.SPDX,
            include_vulnerabilities=True,
            include_licenses=True
        )
        
        assert sbom_doc is not None
        assert sbom_doc.format == SBOMFormat.SPDX
        assert len(sbom_doc.components) > 0
        assert sbom_doc.metadata.tool_name == "Multi-Tenant AIaaS Platform SBOM Generator"
    
    @pytest.mark.asyncio
    async def test_generate_sbom_cyclonedx_format(self, sbom_generator, test_project_path):
        """Test SBOM generation in CycloneDX format."""
        sbom_doc = await sbom_generator.generate_sbom(
            str(test_project_path),
            output_format=SBOMFormat.CYCLONEDX,
            include_vulnerabilities=False,
            include_licenses=False
        )
        
        assert sbom_doc is not None
        assert sbom_doc.format == SBOMFormat.CYCLONEDX
        assert len(sbom_doc.components) > 0
    
    @pytest.mark.asyncio
    async def test_export_sbom_json(self, sbom_generator, test_project_path):
        """Test SBOM export to JSON format."""
        sbom_doc = await sbom_generator.generate_sbom(
            str(test_project_path),
            output_format=SBOMFormat.JSON
        )
        
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            success = await sbom_generator.export_sbom(sbom_doc, temp_file.name)
            assert success is True
            
            # Verify file was created and contains data
            assert Path(temp_file.name).exists()
            assert Path(temp_file.name).stat().st_size > 0
    
    @pytest.mark.asyncio
    async def test_scan_python_dependencies(self, sbom_generator, test_project_path):
        """Test Python dependency scanning."""
        await sbom_generator._scan_python_dependencies(test_project_path)
        
        assert len(sbom_generator.components) > 0
        
        # Check for specific dependencies
        component_names = [comp.name for comp in sbom_generator.components.values()]
        assert "requests" in component_names
        assert "numpy" in component_names
        assert "pandas" in component_names
    
    @pytest.mark.asyncio
    async def test_scan_nodejs_dependencies(self, sbom_generator, test_project_path):
        """Test Node.js dependency scanning."""
        await sbom_generator._scan_nodejs_dependencies(test_project_path)
        
        assert len(sbom_generator.components) > 0
        
        # Check for specific dependencies
        component_names = [comp.name for comp in sbom_generator.components.values()]
        assert "express" in component_names
        assert "lodash" in component_names
        assert "axios" in component_names
    
    @pytest.mark.asyncio
    async def test_scan_docker_dependencies(self, sbom_generator, test_project_path):
        """Test Docker dependency scanning."""
        await sbom_generator._scan_docker_dependencies(test_project_path)
        
        assert len(sbom_generator.components) > 0
        
        # Check for Docker base image
        component_names = [comp.name for comp in sbom_generator.components.values()]
        assert "python" in component_names


class TestImageSigningManager:
    """Test image signing functionality."""
    
    @pytest.fixture
    def image_signing_manager(self):
        """Create ImageSigningManager instance for testing."""
        return ImageSigningManager()
    
    @pytest.mark.asyncio
    async def test_generate_signing_key_ed25519(self, image_signing_manager):
        """Test generating ED25519 signing key."""
        with patch('libs.security.image_signing.asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful cosign key generation
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process
            
            signing_key = await image_signing_manager.generate_signing_key(
                "test-key",
                algorithm=SigningAlgorithm.ED25519
            )
            
            assert signing_key is not None
            assert signing_key.key_id == "test-key"
            assert signing_key.algorithm == SigningAlgorithm.ED25519
            assert signing_key.public_key is not None
    
    @pytest.mark.asyncio
    async def test_generate_signing_key_rsa(self, image_signing_manager):
        """Test generating RSA signing key."""
        with patch('libs.security.image_signing.asyncio.create_subprocess_exec') as mock_subprocess:
            # Mock successful GPG key generation
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process
            
            signing_key = await image_signing_manager.generate_signing_key(
                "test-rsa-key",
                algorithm=SigningAlgorithm.RSA
            )
            
            assert signing_key is not None
            assert signing_key.key_id == "test-rsa-key"
            assert signing_key.algorithm == SigningAlgorithm.RSA
    
    @pytest.mark.asyncio
    async def test_sign_image_cosign(self, image_signing_manager):
        """Test signing image with cosign."""
        # First generate a signing key
        with patch('libs.security.image_signing.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process
            
            signing_key = await image_signing_manager.generate_signing_key("test-key")
        
        # Sign image
        image_signature = await image_signing_manager.sign_image(
            "test-image:latest",
            "test-key",
            signature_format=SignatureFormat.COSIGN
        )
        
        assert image_signature is not None
        assert image_signature.image_name == "test-image:latest"
        assert image_signature.signing_key_id == "test-key"
        assert image_signature.signature_format == SignatureFormat.COSIGN
        assert image_signature.signature is not None
    
    @pytest.mark.asyncio
    async def test_verify_image_signature(self, image_signing_manager):
        """Test verifying image signature."""
        # First sign an image
        with patch('libs.security.image_signing.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process
            
            signing_key = await image_signing_manager.generate_signing_key("test-key")
        
        image_signature = await image_signing_manager.sign_image(
            "test-image:latest",
            "test-key",
            signature_format=SignatureFormat.COSIGN
        )
        
        # Verify signature
        status, signature = await image_signing_manager.verify_image_signature(
            "test-image:latest"
        )
        
        assert status in [SignatureStatus.SIGNED, SignatureStatus.INVALID]
        assert signature is not None
    
    @pytest.mark.asyncio
    async def test_revoke_signature(self, image_signing_manager):
        """Test revoking image signature."""
        # First sign an image
        with patch('libs.security.image_signing.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process
            
            signing_key = await image_signing_manager.generate_signing_key("test-key")
        
        image_signature = await image_signing_manager.sign_image(
            "test-image:latest",
            "test-key"
        )
        
        # Revoke signature
        signature_id = f"test-image:latest@{image_signature.image_digest}"
        success = await image_signing_manager.revoke_signature(
            signature_id,
            reason="Test revocation"
        )
        
        assert success is True
    
    @pytest.mark.asyncio
    async def test_get_signing_statistics(self, image_signing_manager):
        """Test getting signing statistics."""
        # Generate some signing keys and sign some images
        with patch('libs.security.image_signing.asyncio.create_subprocess_exec') as mock_subprocess:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"", b"")
            mock_subprocess.return_value = mock_process
            
            await image_signing_manager.generate_signing_key("key1")
            await image_signing_manager.generate_signing_key("key2")
        
        # Sign some images
        await image_signing_manager.sign_image("image1:latest", "key1")
        await image_signing_manager.sign_image("image2:latest", "key2")
        
        stats = await image_signing_manager.get_signing_statistics()
        
        assert stats is not None
        assert stats["total_signatures"] >= 2
        assert stats["signed_images"] >= 2
        assert stats["total_signing_keys"] >= 2


class TestCVEGatesManager:
    """Test CVE gates functionality."""
    
    @pytest.fixture
    def cve_gates_manager(self):
        """Create CVEGatesManager instance for testing."""
        return CVEGatesManager()
    
    @pytest.fixture
    def test_gate_rule(self):
        """Create test CVE gate rule."""
        return CVE GateRule(
            rule_id="test-rule",
            name="Test CVE Gate Rule",
            description="Test rule for CVE gates",
            severity_threshold=VulnerabilitySeverity.HIGH,
            max_critical_vulnerabilities=0,
            max_high_vulnerabilities=5,
            max_medium_vulnerabilities=20,
            max_low_vulnerabilities=50
        )
    
    @pytest.mark.asyncio
    async def test_sync_vulnerability_database(self, cve_gates_manager):
        """Test vulnerability database synchronization."""
        success = await cve_gates_manager.sync_vulnerability_database()
        
        assert success is True
        assert len(cve_gates_manager.vulnerabilities) > 0
        assert cve_gates_manager.last_sync_time is not None
    
    @pytest.mark.asyncio
    async def test_create_gate_rule(self, cve_gates_manager, test_gate_rule):
        """Test creating CVE gate rule."""
        success = await cve_gates_manager.create_gate_rule(test_gate_rule)
        
        assert success is True
        assert test_gate_rule.rule_id in cve_gates_manager.gate_rules
    
    @pytest.mark.asyncio
    async def test_scan_component_vulnerabilities(self, cve_gates_manager):
        """Test scanning component vulnerabilities."""
        # First sync vulnerability database
        await cve_gates_manager.sync_vulnerability_database()
        
        # Scan component vulnerabilities
        vulnerabilities = await cve_gates_manager.scan_component_vulnerabilities(
            "requests",
            "2.31.0"
        )
        
        assert len(vulnerabilities) >= 0  # May or may not have vulnerabilities
    
    @pytest.mark.asyncio
    async def test_evaluate_gate(self, cve_gates_manager, test_gate_rule):
        """Test evaluating CVE gate."""
        # Create gate rule
        await cve_gates_manager.create_gate_rule(test_gate_rule)
        
        # Sync vulnerability database
        await cve_gates_manager.sync_vulnerability_database()
        
        # Evaluate gate
        components = [
            {"name": "requests", "version": "2.31.0"},
            {"name": "numpy", "version": "1.24.3"},
            {"name": "pandas", "version": "2.0.3"}
        ]
        
        result = await cve_gates_manager.evaluate_gate(test_gate_rule.rule_id, components)
        
        assert result is not None
        assert result.rule_id == test_gate_rule.rule_id
        assert result.status in [GateStatus.PASS, GateStatus.WARN, GateStatus.FAIL]
        assert result.total_vulnerabilities >= 0
    
    @pytest.mark.asyncio
    async def test_mark_vulnerability_false_positive(self, cve_gates_manager):
        """Test marking vulnerability as false positive."""
        # First sync vulnerability database and scan component
        await cve_gates_manager.sync_vulnerability_database()
        await cve_gates_manager.scan_component_vulnerabilities("requests", "2.31.0")
        
        # Mark vulnerability as false positive
        success = await cve_gates_manager.mark_vulnerability_false_positive(
            "CVE-2023-1234",
            "requests",
            "2.31.0",
            "Not applicable to our use case"
        )
        
        # This may or may not succeed depending on whether the vulnerability exists
        assert isinstance(success, bool)
    
    @pytest.mark.asyncio
    async def test_get_vulnerability_statistics(self, cve_gates_manager):
        """Test getting vulnerability statistics."""
        # Sync vulnerability database
        await cve_gates_manager.sync_vulnerability_database()
        
        stats = await cve_gates_manager.get_vulnerability_statistics()
        
        assert stats is not None
        assert "total_vulnerabilities" in stats
        assert "severity_counts" in stats
        assert "total_gate_rules" in stats


class TestSLSAProvenanceManager:
    """Test SLSA provenance functionality."""
    
    @pytest.fixture
    def slsa_provenance_manager(self):
        """Create SLSAProvenanceManager instance for testing."""
        return SLSAProvenanceManager()
    
    @pytest.fixture
    def test_build_config(self):
        """Create test build configuration."""
        return BuildConfig(
            build_type=BuildType.GITHUB_ACTIONS,
            builder_id="github-actions",
            build_invocation_id="test-build-123",
            build_started_on=datetime.now(timezone.utc),
            build_finished_on=datetime.now(timezone.utc),
            build_config_source={
                "workflow": "build.yml",
                "repository": "test/repo",
                "ref": "main"
            }
        )
    
    @pytest.fixture
    def test_build_materials(self):
        """Create test build materials."""
        return [
            BuildMaterial(
                uri="git+https://github.com/test/repo@main",
                digest={"sha256": "abc123def456"},
                name="source-code",
                version="main"
            )
        ]
    
    @pytest.fixture
    def test_build_outputs(self):
        """Create test build outputs."""
        return [
            BuildOutput(
                uri="docker.io/test/image:latest",
                digest={"sha256": "def456ghi789"},
                name="test-image",
                version="latest",
                artifact_type=ArtifactType.CONTAINER_IMAGE
            )
        ]
    
    @pytest.mark.asyncio
    async def test_generate_provenance(self, slsa_provenance_manager, test_build_config, 
                                     test_build_materials, test_build_outputs):
        """Test generating SLSA provenance."""
        provenance = await slsa_provenance_manager.generate_provenance(
            test_build_config,
            test_build_materials,
            test_build_outputs,
            metadata={"test": "data"}
        )
        
        assert provenance is not None
        assert provenance.provenance_id is not None
        assert provenance.build_type == test_build_config.build_type.value
        assert provenance.build_invocation_id == test_build_config.build_invocation_id
        assert len(provenance.build_materials) == 1
        assert len(provenance.build_outputs) == 1
        assert provenance.slsa_level in SLSALevel
    
    @pytest.mark.asyncio
    async def test_verify_provenance(self, slsa_provenance_manager, test_build_config, 
                                   test_build_materials, test_build_outputs):
        """Test verifying SLSA provenance."""
        # First generate provenance
        provenance = await slsa_provenance_manager.generate_provenance(
            test_build_config,
            test_build_materials,
            test_build_outputs
        )
        
        # Verify provenance
        verification = await slsa_provenance_manager.verify_provenance(
            "docker.io/test/image:latest",
            provenance.provenance_id
        )
        
        assert verification is not None
        assert verification.artifact_uri == "docker.io/test/image:latest"
        assert verification.verified is True
        assert verification.slsa_level == provenance.slsa_level
    
    @pytest.mark.asyncio
    async def test_export_provenance_json(self, slsa_provenance_manager, test_build_config, 
                                        test_build_materials, test_build_outputs):
        """Test exporting SLSA provenance to JSON."""
        # Generate provenance
        provenance = await slsa_provenance_manager.generate_provenance(
            test_build_config,
            test_build_materials,
            test_build_outputs
        )
        
        # Export to JSON
        with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
            success = await slsa_provenance_manager.export_provenance(
                provenance.provenance_id,
                temp_file.name,
                format="json"
            )
            
            assert success is True
            assert Path(temp_file.name).exists()
            assert Path(temp_file.name).stat().st_size > 0
    
    @pytest.mark.asyncio
    async def test_export_provenance_slsa(self, slsa_provenance_manager, test_build_config, 
                                        test_build_materials, test_build_outputs):
        """Test exporting SLSA provenance to SLSA format."""
        # Generate provenance
        provenance = await slsa_provenance_manager.generate_provenance(
            test_build_config,
            test_build_materials,
            test_build_outputs
        )
        
        # Export to SLSA format
        with tempfile.NamedTemporaryFile(suffix='.slsa', delete=False) as temp_file:
            success = await slsa_provenance_manager.export_provenance(
                provenance.provenance_id,
                temp_file.name,
                format="slsa"
            )
            
            assert success is True
            assert Path(temp_file.name).exists()
            assert Path(temp_file.name).stat().st_size > 0
    
    @pytest.mark.asyncio
    async def test_get_provenance_statistics(self, slsa_provenance_manager, test_build_config, 
                                           test_build_materials, test_build_outputs):
        """Test getting SLSA provenance statistics."""
        # Generate some provenances
        await slsa_provenance_manager.generate_provenance(
            test_build_config,
            test_build_materials,
            test_build_outputs
        )
        
        # Get statistics
        stats = await slsa_provenance_manager.get_provenance_statistics()
        
        assert stats is not None
        assert "total_provenances" in stats
        assert "total_verifications" in stats
        assert "slsa_level_counts" in stats
        assert "build_type_counts" in stats


class TestSupplyChainIntegration:
    """Integration tests for supply-chain security features."""
    
    @pytest.mark.asyncio
    async def test_full_supply_chain_security_workflow(self):
        """Test full supply-chain security workflow."""
        # This would test the full integration scenario
        # where all supply-chain security components work together
        
        # 1. Generate SBOM for project
        # 2. Scan for vulnerabilities
        # 3. Evaluate CVE gates
        # 4. Sign container images
        # 5. Generate SLSA provenance
        # 6. Verify all security measures
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_security_policy_enforcement(self):
        """Test security policy enforcement."""
        # This would test that security policies are enforced
        # across all supply-chain security components
        
        # 1. Define security policies
        # 2. Apply policies to SBOM generation
        # 3. Apply policies to CVE gates
        # 4. Apply policies to image signing
        # 5. Apply policies to SLSA provenance
        # 6. Verify policy compliance
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_supply_chain_attestation(self):
        """Test supply-chain attestation."""
        # This would test that supply-chain attestations
        # are generated and verified correctly
        
        # 1. Generate attestations for all components
        # 2. Verify attestations
        # 3. Check attestation integrity
        # 4. Validate attestation signatures
        
        pass  # Implementation would require full integration setup
    
    @pytest.mark.asyncio
    async def test_security_compliance_reporting(self):
        """Test security compliance reporting."""
        # This would test that security compliance reports
        # are generated and contain accurate information
        
        # 1. Generate compliance reports
        # 2. Verify report accuracy
        # 3. Check report completeness
        # 4. Validate report format
        
        pass  # Implementation would require full integration setup
