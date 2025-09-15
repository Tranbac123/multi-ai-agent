"""SLSA (Supply-chain Levels for Software Artifacts) Provenance Manager for supply-chain security."""

import json
import hashlib
import asyncio
import subprocess
import tempfile
import os
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from datetime import datetime, timezone
from pathlib import Path

logger = structlog.get_logger(__name__)


class SLSALevel(Enum):
    """SLSA levels."""
    LEVEL_0 = "SLSA_LEVEL_0"
    LEVEL_1 = "SLSA_LEVEL_1"
    LEVEL_2 = "SLSA_LEVEL_2"
    LEVEL_3 = "SLSA_LEVEL_3"
    LEVEL_4 = "SLSA_LEVEL_4"


class BuildType(Enum):
    """Build types."""
    DOCKER = "docker"
    GITHUB_ACTIONS = "github_actions"
    JENKINS = "jenkins"
    GITLAB_CI = "gitlab_ci"
    AZURE_DEVOPS = "azure_devops"
    CUSTOM = "custom"


class ArtifactType(Enum):
    """Artifact types."""
    CONTAINER_IMAGE = "container_image"
    PYTHON_WHEEL = "python_wheel"
    NODE_PACKAGE = "node_package"
    BINARY = "binary"
    SOURCE_CODE = "source_code"


@dataclass
class BuildConfig:
    """Build configuration."""
    build_type: BuildType
    builder_id: str
    build_invocation_id: str
    build_started_on: datetime
    build_finished_on: datetime
    build_config_source: Dict[str, Any]
    build_config_path: Optional[str] = None


@dataclass
class BuildMaterial:
    """Build material (input to build)."""
    uri: str
    digest: Dict[str, str]  # algorithm -> hash
    name: Optional[str] = None
    version: Optional[str] = None


@dataclass
class BuildOutput:
    """Build output (artifact produced by build)."""
    uri: str
    digest: Dict[str, str]  # algorithm -> hash
    name: Optional[str] = None
    version: Optional[str] = None
    artifact_type: ArtifactType = ArtifactType.BINARY


@dataclass
class SLSAProvenance:
    """SLSA provenance document."""
    provenance_id: str
    slsa_version: str
    build_type: str
    build_invocation_id: str
    build_started_on: datetime
    build_finished_on: datetime
    build_config: BuildConfig
    build_materials: List[BuildMaterial]
    build_outputs: List[BuildOutput]
    metadata: Dict[str, Any]
    signature: Optional[str] = None
    slsa_level: SLSALevel = SLSALevel.LEVEL_0


@dataclass
class ProvenanceVerification:
    """Provenance verification result."""
    artifact_uri: str
    verified: bool
    slsa_level: SLSALevel
    verification_details: Dict[str, Any]
    verified_at: datetime
    error_message: Optional[str] = None


class SLSAProvenanceManager:
    """Manages SLSA provenance for supply-chain security."""
    
    def __init__(self):
        self.provenances: Dict[str, SLSAProvenance] = {}
        self.verification_results: Dict[str, ProvenanceVerification] = {}
        self.build_configs: Dict[str, BuildConfig] = {}
        self.slsa_version = "1.0"
    
    async def generate_provenance(self, build_config: BuildConfig, 
                                build_materials: List[BuildMaterial],
                                build_outputs: List[BuildOutput],
                                metadata: Optional[Dict[str, Any]] = None) -> SLSAProvenance:
        """Generate SLSA provenance for a build."""
        try:
            logger.info("Generating SLSA provenance",
                       build_type=build_config.build_type.value,
                       build_invocation_id=build_config.build_invocation_id)
            
            # Create provenance ID
            provenance_id = f"provenance_{build_config.build_invocation_id}_{int(datetime.now().timestamp())}"
            
            # Create SLSA provenance
            provenance = SLSAProvenance(
                provenance_id=provenance_id,
                slsa_version=self.slsa_version,
                build_type=build_config.build_type.value,
                build_invocation_id=build_config.build_invocation_id,
                build_started_on=build_config.build_started_on,
                build_finished_on=build_config.build_finished_on,
                build_config=build_config,
                build_materials=build_materials,
                build_outputs=build_outputs,
                metadata=metadata or {},
                slsa_level=await self._determine_slsa_level(build_config, build_materials, build_outputs)
            )
            
            # Store provenance
            self.provenances[provenance_id] = provenance
            
            logger.info("SLSA provenance generated successfully",
                       provenance_id=provenance_id,
                       slsa_level=provenance.slsa_level.value)
            
            return provenance
            
        except Exception as e:
            logger.error("Failed to generate SLSA provenance", error=str(e))
            raise
    
    async def _determine_slsa_level(self, build_config: BuildConfig, 
                                  build_materials: List[BuildMaterial],
                                  build_outputs: List[BuildOutput]) -> SLSALevel:
        """Determine SLSA level based on build configuration and materials."""
        try:
            # Start with Level 0
            level = SLSALevel.LEVEL_0
            
            # Check for Level 1 requirements
            if self._meets_level_1_requirements(build_config, build_materials, build_outputs):
                level = SLSALevel.LEVEL_1
            
            # Check for Level 2 requirements
            if self._meets_level_2_requirements(build_config, build_materials, build_outputs):
                level = SLSALevel.LEVEL_2
            
            # Check for Level 3 requirements
            if self._meets_level_3_requirements(build_config, build_materials, build_outputs):
                level = SLSALevel.LEVEL_3
            
            # Check for Level 4 requirements
            if self._meets_level_4_requirements(build_config, build_materials, build_outputs):
                level = SLSALevel.LEVEL_4
            
            return level
            
        except Exception as e:
            logger.error("Failed to determine SLSA level", error=str(e))
            return SLSALevel.LEVEL_0
    
    def _meets_level_1_requirements(self, build_config: BuildConfig, 
                                   build_materials: List[BuildMaterial],
                                   build_outputs: List[BuildOutput]) -> bool:
        """Check if build meets SLSA Level 1 requirements."""
        try:
            # Level 1: Scripted Build
            # - Build process is scripted/automated
            # - Build outputs are identifiable
            
            # Check if build is automated
            if build_config.build_type in [BuildType.GITHUB_ACTIONS, BuildType.JENKINS, 
                                          BuildType.GITLAB_CI, BuildType.AZURE_DEVOPS]:
                return True
            
            # Check if build outputs are identifiable
            if build_outputs and all(output.uri and output.digest for output in build_outputs):
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to check Level 1 requirements", error=str(e))
            return False
    
    def _meets_level_2_requirements(self, build_config: BuildConfig, 
                                   build_materials: List[BuildMaterial],
                                   build_outputs: List[BuildOutput]) -> bool:
        """Check if build meets SLSA Level 2 requirements."""
        try:
            # Level 2: Version Controlled and Hosted
            # - Build process is version controlled
            # - Build is hosted in a trusted environment
            # - Build materials are version controlled
            
            if not self._meets_level_1_requirements(build_config, build_materials, build_outputs):
                return False
            
            # Check if build materials are version controlled
            version_controlled_materials = 0
            for material in build_materials:
                if self._is_version_controlled(material.uri):
                    version_controlled_materials += 1
            
            # At least 80% of materials should be version controlled
            if len(build_materials) > 0 and version_controlled_materials / len(build_materials) >= 0.8:
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to check Level 2 requirements", error=str(e))
            return False
    
    def _meets_level_3_requirements(self, build_config: BuildConfig, 
                                   build_materials: List[BuildMaterial],
                                   build_outputs: List[BuildOutput]) -> bool:
        """Check if build meets SLSA Level 3 requirements."""
        try:
            # Level 3: Non-Falsifiable
            # - Build process is non-falsifiable
            # - Build materials are authenticated
            # - Build outputs are signed
            
            if not self._meets_level_2_requirements(build_config, build_materials, build_outputs):
                return False
            
            # Check if build is non-falsifiable (hosted in trusted environment)
            if build_config.build_type in [BuildType.GITHUB_ACTIONS, BuildType.GITLAB_CI, 
                                          BuildType.AZURE_DEVOPS]:
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to check Level 3 requirements", error=str(e))
            return False
    
    def _meets_level_4_requirements(self, build_config: BuildConfig, 
                                   build_materials: List[BuildMaterial],
                                   build_outputs: List[BuildOutput]) -> bool:
        """Check if build meets SLSA Level 4 requirements."""
        try:
            # Level 4: Two-Person Review
            # - Build process requires two-person review
            # - All materials are authenticated
            # - Build outputs are signed and verified
            
            if not self._meets_level_3_requirements(build_config, build_materials, build_outputs):
                return False
            
            # Check if build requires two-person review
            if build_config.build_type == BuildType.GITHUB_ACTIONS:
                # Check if GitHub Actions requires approval
                build_config_source = build_config.build_config_source
                if build_config_source.get("requires_approval", False):
                    return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to check Level 4 requirements", error=str(e))
            return False
    
    def _is_version_controlled(self, uri: str) -> bool:
        """Check if URI points to a version controlled resource."""
        try:
            # Check if URI points to a Git repository
            if uri.startswith("git+") or "github.com" in uri or "gitlab.com" in uri:
                return True
            
            # Check if URI points to a versioned resource
            if "@" in uri or "?version=" in uri or "&version=" in uri:
                return True
            
            return False
            
        except Exception as e:
            logger.error("Failed to check version control", error=str(e))
            return False
    
    async def verify_provenance(self, artifact_uri: str, provenance_id: str) -> ProvenanceVerification:
        """Verify SLSA provenance for an artifact."""
        try:
            logger.info("Verifying SLSA provenance",
                       artifact_uri=artifact_uri,
                       provenance_id=provenance_id)
            
            # Get provenance
            if provenance_id not in self.provenances:
                return ProvenanceVerification(
                    artifact_uri=artifact_uri,
                    verified=False,
                    slsa_level=SLSALevel.LEVEL_0,
                    verification_details={"error": "Provenance not found"},
                    verified_at=datetime.now(timezone.utc),
                    error_message=f"Provenance {provenance_id} not found"
                )
            
            provenance = self.provenances[provenance_id]
            
            # Verify artifact is in build outputs
            artifact_found = False
            for output in provenance.build_outputs:
                if output.uri == artifact_uri:
                    artifact_found = True
                    break
            
            if not artifact_found:
                return ProvenanceVerification(
                    artifact_uri=artifact_uri,
                    verified=False,
                    slsa_level=SLSALevel.LEVEL_0,
                    verification_details={"error": "Artifact not found in build outputs"},
                    verified_at=datetime.now(timezone.utc),
                    error_message=f"Artifact {artifact_uri} not found in build outputs"
                )
            
            # Verify build configuration
            build_config_valid = await self._verify_build_config(provenance.build_config)
            
            # Verify build materials
            materials_valid = await self._verify_build_materials(provenance.build_materials)
            
            # Verify build outputs
            outputs_valid = await self._verify_build_outputs(provenance.build_outputs)
            
            # Determine overall verification result
            verified = build_config_valid and materials_valid and outputs_valid
            
            verification = ProvenanceVerification(
                artifact_uri=artifact_uri,
                verified=verified,
                slsa_level=provenance.slsa_level,
                verification_details={
                    "build_config_valid": build_config_valid,
                    "materials_valid": materials_valid,
                    "outputs_valid": outputs_valid,
                    "provenance_id": provenance_id,
                    "build_type": provenance.build_type,
                    "build_invocation_id": provenance.build_invocation_id
                },
                verified_at=datetime.now(timezone.utc)
            )
            
            # Store verification result
            verification_key = f"{artifact_uri}#{provenance_id}"
            self.verification_results[verification_key] = verification
            
            logger.info("SLSA provenance verification completed",
                       artifact_uri=artifact_uri,
                       verified=verified,
                       slsa_level=provenance.slsa_level.value)
            
            return verification
            
        except Exception as e:
            logger.error("Failed to verify SLSA provenance", error=str(e))
            return ProvenanceVerification(
                artifact_uri=artifact_uri,
                verified=False,
                slsa_level=SLSALevel.LEVEL_0,
                verification_details={"error": str(e)},
                verified_at=datetime.now(timezone.utc),
                error_message=str(e)
            )
    
    async def _verify_build_config(self, build_config: BuildConfig) -> bool:
        """Verify build configuration."""
        try:
            # Check if build configuration is valid
            if not build_config.build_type or not build_config.build_invocation_id:
                return False
            
            # Check if build times are valid
            if build_config.build_started_on >= build_config.build_finished_on:
                return False
            
            # Check if build configuration source is valid
            if not build_config.build_config_source:
                return False
            
            return True
            
        except Exception as e:
            logger.error("Failed to verify build config", error=str(e))
            return False
    
    async def _verify_build_materials(self, build_materials: List[BuildMaterial]) -> bool:
        """Verify build materials."""
        try:
            # Check if all materials have valid URIs and digests
            for material in build_materials:
                if not material.uri or not material.digest:
                    return False
                
                # Check if digest has at least one hash
                if not material.digest:
                    return False
            
            return True
            
        except Exception as e:
            logger.error("Failed to verify build materials", error=str(e))
            return False
    
    async def _verify_build_outputs(self, build_outputs: List[BuildOutput]) -> bool:
        """Verify build outputs."""
        try:
            # Check if all outputs have valid URIs and digests
            for output in build_outputs:
                if not output.uri or not output.digest:
                    return False
                
                # Check if digest has at least one hash
                if not output.digest:
                    return False
            
            return True
            
        except Exception as e:
            logger.error("Failed to verify build outputs", error=str(e))
            return False
    
    async def export_provenance(self, provenance_id: str, output_path: str, format: str = "json") -> bool:
        """Export SLSA provenance to file."""
        try:
            logger.info("Exporting SLSA provenance",
                       provenance_id=provenance_id,
                       output_path=output_path)
            
            if provenance_id not in self.provenances:
                logger.error("Provenance not found", provenance_id=provenance_id)
                return False
            
            provenance = self.provenances[provenance_id]
            
            if format == "json":
                # Convert to dictionary
                provenance_dict = asdict(provenance)
                
                # Write JSON file
                with open(output_path, 'w') as f:
                    json.dump(provenance_dict, f, indent=2, default=str)
            
            elif format == "slsa":
                # Generate SLSA format
                slsa_content = await self._generate_slsa_format(provenance)
                
                # Write SLSA file
                with open(output_path, 'w') as f:
                    f.write(slsa_content)
            
            logger.info("SLSA provenance exported successfully", output_path=output_path)
            return True
            
        except Exception as e:
            logger.error("Failed to export SLSA provenance", error=str(e))
            return False
    
    async def _generate_slsa_format(self, provenance: SLSAProvenance) -> str:
        """Generate SLSA format content."""
        try:
            # Generate SLSA format content
            slsa_content = f"""SLSA_PROVENANCE_VERSION={provenance.slsa_version}
BUILD_TYPE={provenance.build_type}
BUILD_INVOCATION_ID={provenance.build_invocation_id}
BUILD_STARTED_ON={provenance.build_started_on.isoformat()}
BUILD_FINISHED_ON={provenance.build_finished_on.isoformat()}
SLSA_LEVEL={provenance.slsa_level.value}

BUILD_CONFIG:
{json.dumps(provenance.build_config.build_config_source, indent=2)}

BUILD_MATERIALS:
"""
            
            for i, material in enumerate(provenance.build_materials):
                slsa_content += f"""
MATERIAL_{i}_URI={material.uri}
MATERIAL_{i}_DIGEST={json.dumps(material.digest)}
"""
            
            slsa_content += "\nBUILD_OUTPUTS:\n"
            
            for i, output in enumerate(provenance.build_outputs):
                slsa_content += f"""
OUTPUT_{i}_URI={output.uri}
OUTPUT_{i}_DIGEST={json.dumps(output.digest)}
OUTPUT_{i}_TYPE={output.artifact_type.value}
"""
            
            slsa_content += f"\nMETADATA:\n{json.dumps(provenance.metadata, indent=2)}\n"
            
            return slsa_content
            
        except Exception as e:
            logger.error("Failed to generate SLSA format", error=str(e))
            return ""
    
    async def get_provenance_statistics(self) -> Dict[str, Any]:
        """Get SLSA provenance statistics."""
        try:
            total_provenances = len(self.provenances)
            total_verifications = len(self.verification_results)
            
            # Count by SLSA level
            slsa_level_counts = {}
            for provenance in self.provenances.values():
                level = provenance.slsa_level.value
                slsa_level_counts[level] = slsa_level_counts.get(level, 0) + 1
            
            # Count by build type
            build_type_counts = {}
            for provenance in self.provenances.values():
                build_type = provenance.build_type
                build_type_counts[build_type] = build_type_counts.get(build_type, 0) + 1
            
            # Count verification results
            verified_count = sum(1 for v in self.verification_results.values() if v.verified)
            failed_count = total_verifications - verified_count
            
            return {
                "total_provenances": total_provenances,
                "total_verifications": total_verifications,
                "verified_count": verified_count,
                "failed_count": failed_count,
                "verification_success_rate": (verified_count / total_verifications * 100) if total_verifications > 0 else 0,
                "slsa_level_counts": slsa_level_counts,
                "build_type_counts": build_type_counts,
                "slsa_version": self.slsa_version
            }
            
        except Exception as e:
            logger.error("Failed to get provenance statistics", error=str(e))
            return {}
    
    async def get_provenance_by_artifact(self, artifact_uri: str) -> Optional[SLSAProvenance]:
        """Get provenance for a specific artifact."""
        try:
            for provenance in self.provenances.values():
                for output in provenance.build_outputs:
                    if output.uri == artifact_uri:
                        return provenance
            
            return None
            
        except Exception as e:
            logger.error("Failed to get provenance by artifact", error=str(e))
            return None
    
    async def get_verification_history(self, artifact_uri: str) -> List[ProvenanceVerification]:
        """Get verification history for an artifact."""
        try:
            verifications = []
            
            for verification in self.verification_results.values():
                if verification.artifact_uri == artifact_uri:
                    verifications.append(verification)
            
            # Sort by verification time (newest first)
            verifications.sort(key=lambda v: v.verified_at, reverse=True)
            
            return verifications
            
        except Exception as e:
            logger.error("Failed to get verification history", error=str(e))
            return []
