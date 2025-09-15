"""SBOM (Software Bill of Materials) Generator for supply-chain security."""

import json
import hashlib
import subprocess
import asyncio
import tempfile
import os
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from datetime import datetime, timezone
from pathlib import Path

logger = structlog.get_logger(__name__)


class SBOMFormat(Enum):
    """SBOM output formats."""
    SPDX = "spdx"
    CYCLONEDX = "cyclonedx"
    JSON = "json"


class ComponentType(Enum):
    """Component types in SBOM."""
    APPLICATION = "application"
    FRAMEWORK = "framework"
    LIBRARY = "library"
    CONTAINER = "container"
    FILE = "file"
    OPERATING_SYSTEM = "operating-system"


class LicenseType(Enum):
    """License types."""
    OPEN_SOURCE = "open-source"
    PROPRIETARY = "proprietary"
    COMMERCIAL = "commercial"
    UNKNOWN = "unknown"


@dataclass
class Component:
    """SBOM component definition."""
    name: str
    version: str
    component_type: ComponentType
    description: Optional[str] = None
    supplier: Optional[str] = None
    license: Optional[str] = None
    license_type: Optional[LicenseType] = None
    purl: Optional[str] = None  # Package URL
    cpe: Optional[str] = None  # Common Platform Enumeration
    sha256: Optional[str] = None
    source_location: Optional[str] = None
    vulnerabilities: List[str] = None
    dependencies: List[str] = None


@dataclass
class SBOMMetadata:
    """SBOM metadata."""
    tool_name: str
    tool_version: str
    timestamp: datetime
    author: str
    format_version: str
    creation_info: Dict[str, Any]


@dataclass
class SBOMDocument:
    """Complete SBOM document."""
    metadata: SBOMMetadata
    components: List[Component]
    relationships: List[Dict[str, str]]
    format: SBOMFormat


class SBOMGenerator:
    """Generates Software Bill of Materials for supply-chain security."""
    
    def __init__(self):
        self.components: Dict[str, Component] = {}
        self.relationships: List[Dict[str, str]] = []
        self.vulnerability_scanner = None
        self.license_scanner = None
    
    async def generate_sbom(self, project_path: str, output_format: SBOMFormat = SBOMFormat.SPDX,
                          include_vulnerabilities: bool = True,
                          include_licenses: bool = True) -> SBOMDocument:
        """Generate SBOM for a project."""
        try:
            logger.info("Starting SBOM generation",
                       project_path=project_path,
                       output_format=output_format.value)
            
            # Clear previous data
            self.components.clear()
            self.relationships.clear()
            
            # Scan for components
            await self._scan_project_components(project_path)
            
            # Scan for vulnerabilities if requested
            if include_vulnerabilities:
                await self._scan_vulnerabilities()
            
            # Scan for licenses if requested
            if include_licenses:
                await self._scan_licenses()
            
            # Create SBOM document
            sbom_doc = self._create_sbom_document(output_format)
            
            logger.info("SBOM generation completed",
                       total_components=len(self.components),
                       output_format=output_format.value)
            
            return sbom_doc
            
        except Exception as e:
            logger.error("SBOM generation failed",
                        project_path=project_path,
                        error=str(e))
            raise
    
    async def _scan_project_components(self, project_path: str):
        """Scan project for components."""
        try:
            project_path = Path(project_path)
            
            # Scan Python dependencies
            await self._scan_python_dependencies(project_path)
            
            # Scan Node.js dependencies
            await self._scan_nodejs_dependencies(project_path)
            
            # Scan Docker dependencies
            await self._scan_docker_dependencies(project_path)
            
            # Scan system dependencies
            await self._scan_system_dependencies(project_path)
            
            # Scan application files
            await self._scan_application_files(project_path)
            
            logger.info("Component scanning completed",
                       total_components=len(self.components))
            
        except Exception as e:
            logger.error("Component scanning failed",
                        project_path=project_path,
                        error=str(e))
            raise
    
    async def _scan_python_dependencies(self, project_path: Path):
        """Scan Python dependencies."""
        try:
            # Check for requirements.txt
            requirements_file = project_path / "requirements.txt"
            if requirements_file.exists():
                await self._parse_requirements_file(requirements_file)
            
            # Check for pyproject.toml
            pyproject_file = project_path / "pyproject.toml"
            if pyproject_file.exists():
                await self._parse_pyproject_file(pyproject_file)
            
            # Check for Pipfile
            pipfile = project_path / "Pipfile"
            if pipfile.exists():
                await self._parse_pipfile(pipfile)
            
            # Check for poetry.lock
            poetry_lock = project_path / "poetry.lock"
            if poetry_lock.exists():
                await self._parse_poetry_lock(poetry_lock)
            
            # Check for pip freeze output
            await self._scan_pip_freeze()
            
        except Exception as e:
            logger.error("Python dependency scanning failed", error=str(e))
    
    async def _parse_requirements_file(self, requirements_file: Path):
        """Parse requirements.txt file."""
        try:
            with open(requirements_file, 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Parse package name and version
                    if '==' in line:
                        name, version = line.split('==', 1)
                    elif '>=' in line:
                        name, version = line.split('>=', 1)
                    elif '<=' in line:
                        name, version = line.split('<=', 1)
                    else:
                        name = line
                        version = "unknown"
                    
                    component = Component(
                        name=name.strip(),
                        version=version.strip(),
                        component_type=ComponentType.LIBRARY,
                        description=f"Python package: {name}",
                        supplier="PyPI",
                        purl=f"pkg:pypi/{name}@{version}",
                        source_location=f"https://pypi.org/project/{name}/"
                    )
                    
                    self._add_component(component)
            
        except Exception as e:
            logger.error("Failed to parse requirements.txt", error=str(e))
    
    async def _parse_pyproject_file(self, pyproject_file: Path):
        """Parse pyproject.toml file."""
        try:
            # In production, this would use toml library
            # For this implementation, we'll simulate parsing
            
            logger.info("Parsing pyproject.toml", file_path=str(pyproject_file))
            
            # Simulate parsing dependencies
            # This would extract dependencies from [tool.poetry.dependencies] or [project.dependencies]
            
        except Exception as e:
            logger.error("Failed to parse pyproject.toml", error=str(e))
    
    async def _parse_pipfile(self, pipfile: Path):
        """Parse Pipfile."""
        try:
            logger.info("Parsing Pipfile", file_path=str(pipfile))
            
            # In production, this would parse TOML format
            # For this implementation, we'll simulate parsing
            
        except Exception as e:
            logger.error("Failed to parse Pipfile", error=str(e))
    
    async def _parse_poetry_lock(self, poetry_lock: Path):
        """Parse poetry.lock file."""
        try:
            logger.info("Parsing poetry.lock", file_path=str(poetry_lock))
            
            # In production, this would parse TOML format
            # For this implementation, we'll simulate parsing
            
        except Exception as e:
            logger.error("Failed to parse poetry.lock", error=str(e))
    
    async def _scan_pip_freeze(self):
        """Scan pip freeze output."""
        try:
            result = await asyncio.create_subprocess_exec(
                'pip', 'freeze',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await result.communicate()
            
            if result.returncode == 0:
                lines = stdout.decode().split('\n')
                for line in lines:
                    line = line.strip()
                    if line and '==' in line:
                        name, version = line.split('==', 1)
                        
                        component = Component(
                            name=name.strip(),
                            version=version.strip(),
                            component_type=ComponentType.LIBRARY,
                            description=f"Python package: {name}",
                            supplier="PyPI",
                            purl=f"pkg:pypi/{name}@{version}",
                            source_location=f"https://pypi.org/project/{name}/"
                        )
                        
                        self._add_component(component)
            else:
                logger.warning("pip freeze failed", error=stderr.decode())
                
        except Exception as e:
            logger.error("Failed to scan pip freeze", error=str(e))
    
    async def _scan_nodejs_dependencies(self, project_path: Path):
        """Scan Node.js dependencies."""
        try:
            # Check for package.json
            package_json = project_path / "package.json"
            if package_json.exists():
                await self._parse_package_json(package_json)
            
            # Check for package-lock.json
            package_lock = project_path / "package-lock.json"
            if package_lock.exists():
                await self._parse_package_lock(package_lock)
            
            # Check for yarn.lock
            yarn_lock = project_path / "yarn.lock"
            if yarn_lock.exists():
                await self._parse_yarn_lock(yarn_lock)
            
        except Exception as e:
            logger.error("Node.js dependency scanning failed", error=str(e))
    
    async def _parse_package_json(self, package_json: Path):
        """Parse package.json file."""
        try:
            with open(package_json, 'r') as f:
                data = json.load(f)
            
            # Parse dependencies
            dependencies = data.get('dependencies', {})
            dev_dependencies = data.get('devDependencies', {})
            
            for name, version in {**dependencies, **dev_dependencies}.items():
                component = Component(
                    name=name,
                    version=version,
                    component_type=ComponentType.LIBRARY,
                    description=f"Node.js package: {name}",
                    supplier="npm",
                    purl=f"pkg:npm/{name}@{version}",
                    source_location=f"https://www.npmjs.com/package/{name}"
                )
                
                self._add_component(component)
            
        except Exception as e:
            logger.error("Failed to parse package.json", error=str(e))
    
    async def _parse_package_lock(self, package_lock: Path):
        """Parse package-lock.json file."""
        try:
            with open(package_lock, 'r') as f:
                data = json.load(f)
            
            # Parse dependencies from lock file
            dependencies = data.get('dependencies', {})
            
            for name, dep_data in dependencies.items():
                version = dep_data.get('version', 'unknown')
                
                component = Component(
                    name=name,
                    version=version,
                    component_type=ComponentType.LIBRARY,
                    description=f"Node.js package: {name}",
                    supplier="npm",
                    purl=f"pkg:npm/{name}@{version}",
                    source_location=f"https://www.npmjs.com/package/{name}"
                )
                
                self._add_component(component)
            
        except Exception as e:
            logger.error("Failed to parse package-lock.json", error=str(e))
    
    async def _parse_yarn_lock(self, yarn_lock: Path):
        """Parse yarn.lock file."""
        try:
            logger.info("Parsing yarn.lock", file_path=str(yarn_lock))
            
            # In production, this would parse Yarn lock format
            # For this implementation, we'll simulate parsing
            
        except Exception as e:
            logger.error("Failed to parse yarn.lock", error=str(e))
    
    async def _scan_docker_dependencies(self, project_path: Path):
        """Scan Docker dependencies."""
        try:
            # Check for Dockerfile
            dockerfile = project_path / "Dockerfile"
            if dockerfile.exists():
                await self._parse_dockerfile(dockerfile)
            
            # Check for docker-compose.yml
            docker_compose = project_path / "docker-compose.yml"
            if docker_compose.exists():
                await self._parse_docker_compose(docker_compose)
            
        except Exception as e:
            logger.error("Docker dependency scanning failed", error=str(e))
    
    async def _parse_dockerfile(self, dockerfile: Path):
        """Parse Dockerfile for base images."""
        try:
            with open(dockerfile, 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip().upper()
                if line.startswith('FROM'):
                    # Extract base image
                    image = line.split()[1]
                    if ':' in image:
                        name, version = image.split(':', 1)
                    else:
                        name = image
                        version = "latest"
                    
                    component = Component(
                        name=name,
                        version=version,
                        component_type=ComponentType.CONTAINER,
                        description=f"Docker base image: {name}",
                        supplier="Docker Hub",
                        purl=f"pkg:docker/{name}@{version}",
                        source_location=f"https://hub.docker.com/_/{name}"
                    )
                    
                    self._add_component(component)
            
        except Exception as e:
            logger.error("Failed to parse Dockerfile", error=str(e))
    
    async def _parse_docker_compose(self, docker_compose: Path):
        """Parse docker-compose.yml for images."""
        try:
            # In production, this would parse YAML
            # For this implementation, we'll simulate parsing
            
            logger.info("Parsing docker-compose.yml", file_path=str(docker_compose))
            
        except Exception as e:
            logger.error("Failed to parse docker-compose.yml", error=str(e))
    
    async def _scan_system_dependencies(self, project_path: Path):
        """Scan system dependencies."""
        try:
            # Check for system package files
            system_files = [
                "apt-packages.txt",
                "yum-packages.txt",
                "apk-packages.txt",
                "brew-packages.txt"
            ]
            
            for filename in system_files:
                file_path = project_path / filename
                if file_path.exists():
                    await self._parse_system_packages(file_path)
            
        except Exception as e:
            logger.error("System dependency scanning failed", error=str(e))
    
    async def _parse_system_packages(self, packages_file: Path):
        """Parse system packages file."""
        try:
            with open(packages_file, 'r') as f:
                lines = f.readlines()
            
            for line in lines:
                line = line.strip()
                if line and not line.startswith('#'):
                    # Parse package name and version
                    parts = line.split()
                    if len(parts) >= 2:
                        name = parts[0]
                        version = parts[1]
                        
                        component = Component(
                            name=name,
                            version=version,
                            component_type=ComponentType.LIBRARY,
                            description=f"System package: {name}",
                            supplier="System Package Manager"
                        )
                        
                        self._add_component(component)
            
        except Exception as e:
            logger.error("Failed to parse system packages", error=str(e))
    
    async def _scan_application_files(self, project_path: Path):
        """Scan application files."""
        try:
            # Scan for Python files
            for py_file in project_path.rglob("*.py"):
                if self._is_application_file(py_file):
                    await self._analyze_python_file(py_file)
            
            # Scan for JavaScript files
            for js_file in project_path.rglob("*.js"):
                if self._is_application_file(js_file):
                    await self._analyze_javascript_file(js_file)
            
            # Scan for other application files
            for file_path in project_path.rglob("*"):
                if (file_path.is_file() and 
                    file_path.suffix in ['.py', '.js', '.ts', '.java', '.go', '.rs'] and
                    self._is_application_file(file_path)):
                    await self._analyze_application_file(file_path)
            
        except Exception as e:
            logger.error("Application file scanning failed", error=str(e))
    
    def _is_application_file(self, file_path: Path) -> bool:
        """Check if file is an application file (not in build/test directories)."""
        try:
            # Skip common non-application directories
            skip_dirs = {
                '__pycache__', '.git', '.venv', 'venv', 'env',
                'node_modules', '.pytest_cache', '.coverage',
                'build', 'dist', 'target', 'bin', 'obj'
            }
            
            for part in file_path.parts:
                if part in skip_dirs:
                    return False
            
            return True
            
        except Exception as e:
            logger.error("Failed to check application file", error=str(e))
            return False
    
    async def _analyze_python_file(self, file_path: Path):
        """Analyze Python file for imports and dependencies."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Extract imports
            import re
            imports = re.findall(r'^(?:from\s+(\S+)\s+)?import\s+(\S+)', content, re.MULTILINE)
            
            for from_module, import_name in imports:
                if from_module:
                    module_name = from_module
                else:
                    module_name = import_name.split('.')[0]
                
                # Create component for imported module
                component = Component(
                    name=module_name,
                    version="unknown",
                    component_type=ComponentType.LIBRARY,
                    description=f"Python module: {module_name}",
                    supplier="PyPI",
                    purl=f"pkg:pypi/{module_name}"
                )
                
                self._add_component(component)
            
        except Exception as e:
            logger.error("Failed to analyze Python file", error=str(e))
    
    async def _analyze_javascript_file(self, file_path: Path):
        """Analyze JavaScript file for imports and dependencies."""
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            # Extract imports
            import re
            imports = re.findall(r'import\s+(?:.*?\s+from\s+)?[\'"]([^\'"]+)[\'"]', content)
            
            for import_path in imports:
                # Extract package name from import path
                package_name = import_path.split('/')[0]
                
                component = Component(
                    name=package_name,
                    version="unknown",
                    component_type=ComponentType.LIBRARY,
                    description=f"Node.js package: {package_name}",
                    supplier="npm",
                    purl=f"pkg:npm/{package_name}"
                )
                
                self._add_component(component)
            
        except Exception as e:
            logger.error("Failed to analyze JavaScript file", error=str(e))
    
    async def _analyze_application_file(self, file_path: Path):
        """Analyze general application file."""
        try:
            # Calculate file hash
            with open(file_path, 'rb') as f:
                content = f.read()
                sha256 = hashlib.sha256(content).hexdigest()
            
            component = Component(
                name=file_path.name,
                version="1.0.0",
                component_type=ComponentType.FILE,
                description=f"Application file: {file_path.name}",
                sha256=sha256,
                source_location=str(file_path)
            )
            
            self._add_component(component)
            
        except Exception as e:
            logger.error("Failed to analyze application file", error=str(e))
    
    async def _scan_vulnerabilities(self):
        """Scan components for vulnerabilities."""
        try:
            logger.info("Scanning for vulnerabilities",
                       total_components=len(self.components))
            
            # In production, this would integrate with vulnerability databases
            # For this implementation, we'll simulate vulnerability scanning
            
            for component_id, component in self.components.items():
                # Simulate vulnerability scanning
                vulnerabilities = await self._check_component_vulnerabilities(component)
                if vulnerabilities:
                    component.vulnerabilities = vulnerabilities
            
            logger.info("Vulnerability scanning completed")
            
        except Exception as e:
            logger.error("Vulnerability scanning failed", error=str(e))
    
    async def _check_component_vulnerabilities(self, component: Component) -> List[str]:
        """Check vulnerabilities for a specific component."""
        try:
            # In production, this would query vulnerability databases
            # For this implementation, we'll simulate vulnerability checking
            
            # Simulate some vulnerabilities for testing
            if component.name in ["requests", "urllib3", "cryptography"]:
                return [f"CVE-2023-{hash(component.name) % 10000:04d}"]
            
            return []
            
        except Exception as e:
            logger.error("Failed to check component vulnerabilities", error=str(e))
            return []
    
    async def _scan_licenses(self):
        """Scan components for licenses."""
        try:
            logger.info("Scanning for licenses",
                       total_components=len(self.components))
            
            # In production, this would integrate with license databases
            # For this implementation, we'll simulate license scanning
            
            for component_id, component in self.components.items():
                license_info = await self._check_component_license(component)
                if license_info:
                    component.license = license_info.get("license")
                    component.license_type = license_info.get("license_type")
            
            logger.info("License scanning completed")
            
        except Exception as e:
            logger.error("License scanning failed", error=str(e))
    
    async def _check_component_license(self, component: Component) -> Optional[Dict[str, Any]]:
        """Check license for a specific component."""
        try:
            # In production, this would query license databases
            # For this implementation, we'll simulate license checking
            
            # Simulate license information
            license_mapping = {
                "requests": {"license": "Apache-2.0", "license_type": LicenseType.OPEN_SOURCE},
                "numpy": {"license": "BSD-3-Clause", "license_type": LicenseType.OPEN_SOURCE},
                "pandas": {"license": "BSD-3-Clause", "license_type": LicenseType.OPEN_SOURCE},
                "fastapi": {"license": "MIT", "license_type": LicenseType.OPEN_SOURCE},
                "sqlalchemy": {"license": "MIT", "license_type": LicenseType.OPEN_SOURCE}
            }
            
            return license_mapping.get(component.name, {
                "license": "Unknown",
                "license_type": LicenseType.UNKNOWN
            })
            
        except Exception as e:
            logger.error("Failed to check component license", error=str(e))
            return None
    
    def _add_component(self, component: Component):
        """Add component to SBOM."""
        try:
            # Create unique component ID
            component_id = f"{component.name}@{component.version}"
            
            # Add component
            self.components[component_id] = component
            
        except Exception as e:
            logger.error("Failed to add component", error=str(e))
    
    def _create_sbom_document(self, output_format: SBOMFormat) -> SBOMDocument:
        """Create SBOM document."""
        try:
            # Create metadata
            metadata = SBOMMetadata(
                tool_name="Multi-Tenant AIaaS Platform SBOM Generator",
                tool_version="1.0.0",
                timestamp=datetime.now(timezone.utc),
                author="Platform Security Team",
                format_version="1.0",
                creation_info={
                    "created_by": "SBOM Generator",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "total_components": len(self.components)
                }
            )
            
            # Create SBOM document
            sbom_doc = SBOMDocument(
                metadata=metadata,
                components=list(self.components.values()),
                relationships=self.relationships,
                format=output_format
            )
            
            return sbom_doc
            
        except Exception as e:
            logger.error("Failed to create SBOM document", error=str(e))
            raise
    
    async def export_sbom(self, sbom_doc: SBOMDocument, output_path: str) -> bool:
        """Export SBOM to file."""
        try:
            output_path = Path(output_path)
            
            if sbom_doc.format == SBOMFormat.JSON:
                await self._export_json(sbom_doc, output_path)
            elif sbom_doc.format == SBOMFormat.SPDX:
                await self._export_spdx(sbom_doc, output_path)
            elif sbom_doc.format == SBOMFormat.CYCLONEDX:
                await self._export_cyclonedx(sbom_doc, output_path)
            
            logger.info("SBOM exported successfully", output_path=str(output_path))
            return True
            
        except Exception as e:
            logger.error("Failed to export SBOM", error=str(e))
            return False
    
    async def _export_json(self, sbom_doc: SBOMDocument, output_path: Path):
        """Export SBOM as JSON."""
        try:
            # Convert to dictionary
            sbom_dict = {
                "metadata": asdict(sbom_doc.metadata),
                "components": [asdict(component) for component in sbom_doc.components],
                "relationships": sbom_doc.relationships,
                "format": sbom_doc.format.value
            }
            
            # Write JSON file
            with open(output_path, 'w') as f:
                json.dump(sbom_dict, f, indent=2, default=str)
            
        except Exception as e:
            logger.error("Failed to export JSON SBOM", error=str(e))
            raise
    
    async def _export_spdx(self, sbom_doc: SBOMDocument, output_path: Path):
        """Export SBOM as SPDX format."""
        try:
            # In production, this would generate proper SPDX format
            # For this implementation, we'll generate a simplified version
            
            spdx_content = f"""SPDXVersion: SPDX-2.3
DataLicense: CC0-1.0
SPDXID: SPDXRef-DOCUMENT
DocumentName: {sbom_doc.metadata.tool_name}
DocumentNamespace: https://spdx.org/spdxdocs/{sbom_doc.metadata.tool_name}-{sbom_doc.metadata.timestamp.isoformat()}
Creator: Tool: {sbom_doc.metadata.tool_name} v{sbom_doc.metadata.tool_version}
Created: {sbom_doc.metadata.timestamp.isoformat()}

"""
            
            # Add components
            for i, component in enumerate(sbom_doc.components):
                spdx_content += f"""PackageName: {component.name}
SPDXID: SPDXRef-Package-{i}
PackageVersion: {component.version}
PackageDownloadLocation: {component.source_location or "NOASSERTION"}
PackageLicenseDeclared: {component.license or "NOASSERTION"}
PackageDescription: {component.description or "NOASSERTION"}

"""
            
            # Write SPDX file
            with open(output_path, 'w') as f:
                f.write(spdx_content)
            
        except Exception as e:
            logger.error("Failed to export SPDX SBOM", error=str(e))
            raise
    
    async def _export_cyclonedx(self, sbom_doc: SBOMDocument, output_path: Path):
        """Export SBOM as CycloneDX format."""
        try:
            # In production, this would generate proper CycloneDX format
            # For this implementation, we'll generate a simplified version
            
            cyclonedx_dict = {
                "bomFormat": "CycloneDX",
                "specVersion": "1.4",
                "version": 1,
                "metadata": {
                    "timestamp": sbom_doc.metadata.timestamp.isoformat(),
                    "tools": [{
                        "vendor": "Multi-Tenant AIaaS Platform",
                        "name": sbom_doc.metadata.tool_name,
                        "version": sbom_doc.metadata.tool_version
                    }]
                },
                "components": []
            }
            
            # Add components
            for component in sbom_doc.components:
                cyclonedx_component = {
                    "type": component.component_type.value,
                    "name": component.name,
                    "version": component.version,
                    "description": component.description,
                    "purl": component.purl,
                    "externalReferences": []
                }
                
                if component.source_location:
                    cyclonedx_component["externalReferences"].append({
                        "type": "website",
                        "url": component.source_location
                    })
                
                cyclonedx_dict["components"].append(cyclonedx_component)
            
            # Write CycloneDX file
            with open(output_path, 'w') as f:
                json.dump(cyclonedx_dict, f, indent=2)
            
        except Exception as e:
            logger.error("Failed to export CycloneDX SBOM", error=str(e))
            raise
