"""CVE Gates Manager for vulnerability scanning and security enforcement."""

import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, asdict
from enum import Enum
import structlog
from datetime import datetime, timezone, timedelta

logger = structlog.get_logger(__name__)


class VulnerabilitySeverity(Enum):
    """Vulnerability severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class GateStatus(Enum):
    """Gate status."""
    PASS = "pass"
    FAIL = "fail"
    WARN = "warn"
    SKIP = "skip"


class VulnerabilityStatus(Enum):
    """Vulnerability status."""
    OPEN = "open"
    FIXED = "fixed"
    MITIGATED = "mitigated"
    ACCEPTED = "accepted"
    FALSE_POSITIVE = "false_positive"


@dataclass
class Vulnerability:
    """Vulnerability definition."""
    cve_id: str
    title: str
    description: str
    severity: VulnerabilitySeverity
    cvss_score: float
    cvss_vector: str
    published_date: datetime
    modified_date: datetime
    affected_components: List[str]
    references: List[str]
    status: VulnerabilityStatus = VulnerabilityStatus.OPEN
    false_positive_reason: Optional[str] = None
    mitigation: Optional[str] = None


@dataclass
class ComponentVulnerability:
    """Component vulnerability mapping."""
    component_name: str
    component_version: str
    vulnerability: Vulnerability
    detected_date: datetime
    fixed_version: Optional[str] = None
    workaround: Optional[str] = None


@dataclass
class CVEGateRule:
    """CVE gate rule definition."""
    rule_id: str
    name: str
    description: str
    severity_threshold: VulnerabilitySeverity
    max_critical_vulnerabilities: int = 0
    max_high_vulnerabilities: int = 5
    max_medium_vulnerabilities: int = 20
    max_low_vulnerabilities: int = 50
    allowed_cve_ids: Set[str] = None
    blocked_cve_ids: Set[str] = None
    component_whitelist: Set[str] = None
    component_blacklist: Set[str] = None


@dataclass
class GateResult:
    """Gate evaluation result."""
    rule_id: str
    status: GateStatus
    total_vulnerabilities: int
    critical_vulnerabilities: int
    high_vulnerabilities: int
    medium_vulnerabilities: int
    low_vulnerabilities: int
    blocked_vulnerabilities: List[str]
    allowed_vulnerabilities: List[str]
    message: str
    evaluated_at: datetime


class CVEGatesManager:
    """Manages CVE gates for vulnerability scanning and security enforcement."""
    
    def __init__(self):
        self.vulnerabilities: Dict[str, Vulnerability] = {}
        self.component_vulnerabilities: Dict[str, ComponentVulnerability] = {}
        self.gate_rules: Dict[str, CVEGateRule] = {}
        self.vulnerability_databases = [
            "https://cve.mitre.org/data/downloads/allitems.xml",
            "https://nvd.nist.gov/feeds/xml/cve/2.0/nvdcve-2.0-modified.xml",
            "https://nvd.nist.gov/feeds/xml/cve/2.0/nvdcve-2.0-recent.xml"
        ]
        self.last_sync_time: Optional[datetime] = None
    
    async def sync_vulnerability_database(self) -> bool:
        """Sync vulnerability database from external sources."""
        try:
            logger.info("Starting vulnerability database sync")
            
            # Sync from multiple sources
            for db_url in self.vulnerability_databases:
                await self._sync_from_source(db_url)
            
            self.last_sync_time = datetime.now(timezone.utc)
            
            logger.info("Vulnerability database sync completed",
                       total_vulnerabilities=len(self.vulnerabilities))
            
            return True
            
        except Exception as e:
            logger.error("Vulnerability database sync failed", error=str(e))
            return False
    
    async def _sync_from_source(self, source_url: str):
        """Sync vulnerabilities from a specific source."""
        try:
            logger.info("Syncing from source", source_url=source_url)
            
            # In production, this would parse XML/JSON feeds
            # For this implementation, we'll simulate vulnerability data
            
            # Simulate some common vulnerabilities
            simulated_vulnerabilities = [
                {
                    "cve_id": "CVE-2023-1234",
                    "title": "Remote Code Execution in Python requests library",
                    "description": "A vulnerability in the Python requests library allows remote code execution.",
                    "severity": VulnerabilitySeverity.CRITICAL,
                    "cvss_score": 9.8,
                    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H",
                    "affected_components": ["requests", "urllib3"],
                    "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2023-1234"]
                },
                {
                    "cve_id": "CVE-2023-5678",
                    "title": "SQL Injection in SQLAlchemy",
                    "description": "SQLAlchemy is vulnerable to SQL injection attacks.",
                    "severity": VulnerabilitySeverity.HIGH,
                    "cvss_score": 8.1,
                    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:L/UI:N/S:U/C:H/I:H/A:N",
                    "affected_components": ["sqlalchemy"],
                    "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2023-5678"]
                },
                {
                    "cve_id": "CVE-2023-9012",
                    "title": "Information Disclosure in FastAPI",
                    "description": "FastAPI may leak sensitive information in error messages.",
                    "severity": VulnerabilitySeverity.MEDIUM,
                    "cvss_score": 5.3,
                    "cvss_vector": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:L/I:N/A:N",
                    "affected_components": ["fastapi", "starlette"],
                    "references": ["https://cve.mitre.org/cgi-bin/cvename.cgi?name=CVE-2023-9012"]
                }
            ]
            
            for vuln_data in simulated_vulnerabilities:
                vulnerability = Vulnerability(
                    cve_id=vuln_data["cve_id"],
                    title=vuln_data["title"],
                    description=vuln_data["description"],
                    severity=vuln_data["severity"],
                    cvss_score=vuln_data["cvss_score"],
                    cvss_vector=vuln_data["cvss_vector"],
                    published_date=datetime.now(timezone.utc) - timedelta(days=30),
                    modified_date=datetime.now(timezone.utc),
                    affected_components=vuln_data["affected_components"],
                    references=vuln_data["references"]
                )
                
                self.vulnerabilities[vuln_data["cve_id"]] = vulnerability
            
            logger.info("Source sync completed", source_url=source_url)
            
        except Exception as e:
            logger.error("Failed to sync from source", source_url=source_url, error=str(e))
    
    async def scan_component_vulnerabilities(self, component_name: str, component_version: str) -> List[ComponentVulnerability]:
        """Scan component for vulnerabilities."""
        try:
            logger.info("Scanning component vulnerabilities",
                       component_name=component_name,
                       component_version=component_version)
            
            component_vulnerabilities = []
            
            # Check for vulnerabilities affecting this component
            for vuln_id, vulnerability in self.vulnerabilities.items():
                if component_name.lower() in [comp.lower() for comp in vulnerability.affected_components]:
                    component_vuln = ComponentVulnerability(
                        component_name=component_name,
                        component_version=component_version,
                        vulnerability=vulnerability,
                        detected_date=datetime.now(timezone.utc)
                    )
                    
                    component_vulnerabilities.append(component_vuln)
                    
                    # Store component vulnerability
                    vuln_key = f"{component_name}@{component_version}#{vuln_id}"
                    self.component_vulnerabilities[vuln_key] = component_vuln
            
            logger.info("Component vulnerability scan completed",
                       component_name=component_name,
                       vulnerabilities_found=len(component_vulnerabilities))
            
            return component_vulnerabilities
            
        except Exception as e:
            logger.error("Failed to scan component vulnerabilities",
                        component_name=component_name,
                        error=str(e))
            return []
    
    async def create_gate_rule(self, rule: CVEGateRule) -> bool:
        """Create a new CVE gate rule."""
        try:
            logger.info("Creating CVE gate rule",
                       rule_id=rule.rule_id,
                       name=rule.name)
            
            # Validate rule
            if not self._validate_gate_rule(rule):
                logger.error("Invalid gate rule", rule_id=rule.rule_id)
                return False
            
            # Store rule
            self.gate_rules[rule.rule_id] = rule
            
            logger.info("CVE gate rule created successfully", rule_id=rule.rule_id)
            return True
            
        except Exception as e:
            logger.error("Failed to create CVE gate rule",
                        rule_id=rule.rule_id,
                        error=str(e))
            return False
    
    def _validate_gate_rule(self, rule: CVEGateRule) -> bool:
        """Validate CVE gate rule."""
        try:
            # Check required fields
            if not rule.rule_id or not rule.name:
                return False
            
            # Check severity threshold
            if rule.severity_threshold not in VulnerabilitySeverity:
                return False
            
            # Check vulnerability limits
            if (rule.max_critical_vulnerabilities < 0 or
                rule.max_high_vulnerabilities < 0 or
                rule.max_medium_vulnerabilities < 0 or
                rule.max_low_vulnerabilities < 0):
                return False
            
            return True
            
        except Exception as e:
            logger.error("Gate rule validation failed", error=str(e))
            return False
    
    async def evaluate_gate(self, rule_id: str, components: List[Dict[str, str]]) -> GateResult:
        """Evaluate CVE gate for components."""
        try:
            logger.info("Evaluating CVE gate",
                       rule_id=rule_id,
                       component_count=len(components))
            
            if rule_id not in self.gate_rules:
                raise ValueError(f"Gate rule {rule_id} not found")
            
            rule = self.gate_rules[rule_id]
            
            # Collect all vulnerabilities
            all_vulnerabilities = []
            for component in components:
                component_name = component.get("name")
                component_version = component.get("version")
                
                if component_name and component_version:
                    vulns = await self.scan_component_vulnerabilities(component_name, component_version)
                    all_vulnerabilities.extend(vulns)
            
            # Filter vulnerabilities based on rule criteria
            filtered_vulnerabilities = self._filter_vulnerabilities(all_vulnerabilities, rule)
            
            # Count vulnerabilities by severity
            severity_counts = self._count_vulnerabilities_by_severity(filtered_vulnerabilities)
            
            # Check if any vulnerabilities are blocked
            blocked_vulnerabilities = []
            allowed_vulnerabilities = []
            
            for vuln in filtered_vulnerabilities:
                if rule.blocked_cve_ids and vuln.vulnerability.cve_id in rule.blocked_cve_ids:
                    blocked_vulnerabilities.append(vuln.vulnerability.cve_id)
                elif rule.allowed_cve_ids and vuln.vulnerability.cve_id in rule.allowed_cve_ids:
                    allowed_vulnerabilities.append(vuln.vulnerability.cve_id)
            
            # Determine gate status
            status = self._determine_gate_status(severity_counts, rule, blocked_vulnerabilities)
            
            # Create gate result
            result = GateResult(
                rule_id=rule_id,
                status=status,
                total_vulnerabilities=len(filtered_vulnerabilities),
                critical_vulnerabilities=severity_counts.get(VulnerabilitySeverity.CRITICAL, 0),
                high_vulnerabilities=severity_counts.get(VulnerabilitySeverity.HIGH, 0),
                medium_vulnerabilities=severity_counts.get(VulnerabilitySeverity.MEDIUM, 0),
                low_vulnerabilities=severity_counts.get(VulnerabilitySeverity.LOW, 0),
                blocked_vulnerabilities=blocked_vulnerabilities,
                allowed_vulnerabilities=allowed_vulnerabilities,
                message=self._generate_gate_message(status, severity_counts, rule),
                evaluated_at=datetime.now(timezone.utc)
            )
            
            logger.info("CVE gate evaluation completed",
                       rule_id=rule_id,
                       status=status.value,
                       total_vulnerabilities=result.total_vulnerabilities)
            
            return result
            
        except Exception as e:
            logger.error("Failed to evaluate CVE gate",
                        rule_id=rule_id,
                        error=str(e))
            raise
    
    def _filter_vulnerabilities(self, vulnerabilities: List[ComponentVulnerability], rule: CVEGateRule) -> List[ComponentVulnerability]:
        """Filter vulnerabilities based on gate rule criteria."""
        try:
            filtered = []
            
            for vuln in vulnerabilities:
                # Check component whitelist/blacklist
                if rule.component_whitelist and vuln.component_name not in rule.component_whitelist:
                    continue
                
                if rule.component_blacklist and vuln.component_name in rule.component_blacklist:
                    continue
                
                # Check severity threshold
                if self._get_severity_level(vuln.vulnerability.severity) > self._get_severity_level(rule.severity_threshold):
                    continue
                
                # Check if vulnerability is in allowed list
                if rule.allowed_cve_ids and vuln.vulnerability.cve_id in rule.allowed_cve_ids:
                    continue
                
                filtered.append(vuln)
            
            return filtered
            
        except Exception as e:
            logger.error("Failed to filter vulnerabilities", error=str(e))
            return vulnerabilities
    
    def _count_vulnerabilities_by_severity(self, vulnerabilities: List[ComponentVulnerability]) -> Dict[VulnerabilitySeverity, int]:
        """Count vulnerabilities by severity."""
        try:
            counts = {
                VulnerabilitySeverity.CRITICAL: 0,
                VulnerabilitySeverity.HIGH: 0,
                VulnerabilitySeverity.MEDIUM: 0,
                VulnerabilitySeverity.LOW: 0,
                VulnerabilitySeverity.INFO: 0
            }
            
            for vuln in vulnerabilities:
                severity = vuln.vulnerability.severity
                counts[severity] = counts.get(severity, 0) + 1
            
            return counts
            
        except Exception as e:
            logger.error("Failed to count vulnerabilities by severity", error=str(e))
            return {}
    
    def _determine_gate_status(self, severity_counts: Dict[VulnerabilitySeverity, int], 
                             rule: CVEGateRule, blocked_vulnerabilities: List[str]) -> GateStatus:
        """Determine gate status based on vulnerability counts and rule criteria."""
        try:
            # Check for blocked vulnerabilities
            if blocked_vulnerabilities:
                return GateStatus.FAIL
            
            # Check severity thresholds
            if severity_counts.get(VulnerabilitySeverity.CRITICAL, 0) > rule.max_critical_vulnerabilities:
                return GateStatus.FAIL
            
            if severity_counts.get(VulnerabilitySeverity.HIGH, 0) > rule.max_high_vulnerabilities:
                return GateStatus.FAIL
            
            if severity_counts.get(VulnerabilitySeverity.MEDIUM, 0) > rule.max_medium_vulnerabilities:
                return GateStatus.WARN
            
            if severity_counts.get(VulnerabilitySeverity.LOW, 0) > rule.max_low_vulnerabilities:
                return GateStatus.WARN
            
            return GateStatus.PASS
            
        except Exception as e:
            logger.error("Failed to determine gate status", error=str(e))
            return GateStatus.FAIL
    
    def _generate_gate_message(self, status: GateStatus, severity_counts: Dict[VulnerabilitySeverity, int], 
                             rule: CVEGateRule) -> str:
        """Generate gate evaluation message."""
        try:
            if status == GateStatus.PASS:
                return f"Gate passed: All vulnerability thresholds met"
            elif status == GateStatus.WARN:
                return f"Gate warning: Some vulnerability thresholds exceeded"
            elif status == GateStatus.FAIL:
                return f"Gate failed: Critical or high severity vulnerabilities exceed thresholds"
            else:
                return f"Gate skipped: No vulnerabilities found"
            
        except Exception as e:
            logger.error("Failed to generate gate message", error=str(e))
            return "Gate evaluation failed"
    
    def _get_severity_level(self, severity: VulnerabilitySeverity) -> int:
        """Get numeric severity level for comparison."""
        severity_levels = {
            VulnerabilitySeverity.CRITICAL: 4,
            VulnerabilitySeverity.HIGH: 3,
            VulnerabilitySeverity.MEDIUM: 2,
            VulnerabilitySeverity.LOW: 1,
            VulnerabilitySeverity.INFO: 0
        }
        return severity_levels.get(severity, 0)
    
    async def mark_vulnerability_false_positive(self, cve_id: str, component_name: str, 
                                              component_version: str, reason: str) -> bool:
        """Mark vulnerability as false positive."""
        try:
            logger.info("Marking vulnerability as false positive",
                       cve_id=cve_id,
                       component_name=component_name,
                       component_version=component_version)
            
            vuln_key = f"{component_name}@{component_version}#{cve_id}"
            
            if vuln_key in self.component_vulnerabilities:
                component_vuln = self.component_vulnerabilities[vuln_key]
                component_vuln.vulnerability.status = VulnerabilityStatus.FALSE_POSITIVE
                component_vuln.vulnerability.false_positive_reason = reason
                
                logger.info("Vulnerability marked as false positive", vuln_key=vuln_key)
                return True
            else:
                logger.error("Component vulnerability not found", vuln_key=vuln_key)
                return False
            
        except Exception as e:
            logger.error("Failed to mark vulnerability as false positive", error=str(e))
            return False
    
    async def mark_vulnerability_mitigated(self, cve_id: str, component_name: str, 
                                         component_version: str, mitigation: str) -> bool:
        """Mark vulnerability as mitigated."""
        try:
            logger.info("Marking vulnerability as mitigated",
                       cve_id=cve_id,
                       component_name=component_name,
                       component_version=component_version)
            
            vuln_key = f"{component_name}@{component_version}#{cve_id}"
            
            if vuln_key in self.component_vulnerabilities:
                component_vuln = self.component_vulnerabilities[vuln_key]
                component_vuln.vulnerability.status = VulnerabilityStatus.MITIGATED
                component_vuln.vulnerability.mitigation = mitigation
                
                logger.info("Vulnerability marked as mitigated", vuln_key=vuln_key)
                return True
            else:
                logger.error("Component vulnerability not found", vuln_key=vuln_key)
                return False
            
        except Exception as e:
            logger.error("Failed to mark vulnerability as mitigated", error=str(e))
            return False
    
    async def get_vulnerability_statistics(self) -> Dict[str, Any]:
        """Get vulnerability statistics."""
        try:
            total_vulnerabilities = len(self.vulnerabilities)
            total_component_vulnerabilities = len(self.component_vulnerabilities)
            
            # Count by severity
            severity_counts = {}
            for vuln in self.vulnerabilities.values():
                severity = vuln.severity.value
                severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count by status
            status_counts = {}
            for vuln in self.component_vulnerabilities.values():
                status = vuln.vulnerability.status.value
                status_counts[status] = status_counts.get(status, 0) + 1
            
            # Count by component
            component_counts = {}
            for vuln in self.component_vulnerabilities.values():
                component = vuln.component_name
                component_counts[component] = component_counts.get(component, 0) + 1
            
            return {
                "total_vulnerabilities": total_vulnerabilities,
                "total_component_vulnerabilities": total_component_vulnerabilities,
                "severity_counts": severity_counts,
                "status_counts": status_counts,
                "component_counts": component_counts,
                "last_sync_time": self.last_sync_time.isoformat() if self.last_sync_time else None,
                "total_gate_rules": len(self.gate_rules)
            }
            
        except Exception as e:
            logger.error("Failed to get vulnerability statistics", error=str(e))
            return {}
    
    async def get_component_vulnerabilities(self, component_name: str, 
                                          component_version: Optional[str] = None) -> List[ComponentVulnerability]:
        """Get vulnerabilities for a specific component."""
        try:
            vulnerabilities = []
            
            for vuln_key, component_vuln in self.component_vulnerabilities.items():
                if component_vuln.component_name == component_name:
                    if component_version is None or component_vuln.component_version == component_version:
                        vulnerabilities.append(component_vuln)
            
            return vulnerabilities
            
        except Exception as e:
            logger.error("Failed to get component vulnerabilities", error=str(e))
            return []
    
    async def export_vulnerability_report(self, output_path: str, format: str = "json") -> bool:
        """Export vulnerability report."""
        try:
            logger.info("Exporting vulnerability report", output_path=output_path)
            
            if format == "json":
                report_data = {
                    "vulnerabilities": [asdict(vuln) for vuln in self.vulnerabilities.values()],
                    "component_vulnerabilities": [asdict(vuln) for vuln in self.component_vulnerabilities.values()],
                    "gate_rules": [asdict(rule) for rule in self.gate_rules.values()],
                    "statistics": await self.get_vulnerability_statistics(),
                    "exported_at": datetime.now(timezone.utc).isoformat()
                }
                
                with open(output_path, 'w') as f:
                    json.dump(report_data, f, indent=2, default=str)
            
            logger.info("Vulnerability report exported", output_path=output_path)
            return True
            
        except Exception as e:
            logger.error("Failed to export vulnerability report", error=str(e))
            return False
