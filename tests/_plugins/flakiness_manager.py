"""Flakiness detection and test impact selection plugin."""

import pytest
import asyncio
import time
import json
import os
import subprocess
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, asdict
from enum import Enum
import sqlite3
import pathlib

from tests._fixtures.test_config import TestConfig


class FlakinessStatus(Enum):
    """Flakiness status."""
    STABLE = "stable"
    FLAKY = "flaky"
    QUARANTINED = "quarantined"
    UNKNOWN = "unknown"


class TestImpact(Enum):
    """Test impact level."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


@dataclass
class TestExecution:
    """Test execution record."""
    test_id: str
    test_name: str
    file_path: str
    status: str  # "passed", "failed", "skipped"
    execution_time_ms: float
    timestamp: datetime
    retry_count: int = 0
    flakiness_score: float = 0.0
    impact_level: TestImpact = TestImpact.NONE
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['timestamp'] = self.timestamp.isoformat()
        return data


@dataclass
class FlakinessReport:
    """Flakiness analysis report."""
    test_id: str
    test_name: str
    file_path: str
    total_executions: int
    passed_count: int
    failed_count: int
    flakiness_rate: float
    status: FlakinessStatus
    quarantine_reason: Optional[str]
    last_updated: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['last_updated'] = self.last_updated.isoformat()
        return data


@dataclass
class TestImpactAnalysis:
    """Test impact analysis result."""
    test_id: str
    test_name: str
    file_path: str
    impact_level: TestImpact
    affected_services: List[str]
    critical_path: bool
    coverage_score: float
    last_updated: datetime
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        data = asdict(self)
        data['last_updated'] = self.last_updated.isoformat()
        return data


class FlakinessDetector:
    """Detects flaky tests based on execution history."""
    
    def __init__(self, db_path: str = "test_flakiness.db"):
        """Initialize flakiness detector."""
        self.db_path = db_path
        self.db_connection = None
        self._init_database()
    
    def _init_database(self):
        """Initialize SQLite database for test tracking."""
        self.db_connection = sqlite3.connect(self.db_path, check_same_thread=False)
        
        # Create tables
        self.db_connection.execute("""
            CREATE TABLE IF NOT EXISTS test_executions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL,
                test_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                status TEXT NOT NULL,
                execution_time_ms REAL NOT NULL,
                timestamp TEXT NOT NULL,
                retry_count INTEGER DEFAULT 0,
                flakiness_score REAL DEFAULT 0.0,
                impact_level TEXT DEFAULT 'none'
            )
        """)
        
        self.db_connection.execute("""
            CREATE TABLE IF NOT EXISTS flakiness_reports (
                test_id TEXT PRIMARY KEY,
                test_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                total_executions INTEGER DEFAULT 0,
                passed_count INTEGER DEFAULT 0,
                failed_count INTEGER DEFAULT 0,
                flakiness_rate REAL DEFAULT 0.0,
                status TEXT DEFAULT 'unknown',
                quarantine_reason TEXT,
                last_updated TEXT NOT NULL
            )
        """)
        
        self.db_connection.execute("""
            CREATE TABLE IF NOT EXISTS test_impact_analysis (
                test_id TEXT PRIMARY KEY,
                test_name TEXT NOT NULL,
                file_path TEXT NOT NULL,
                impact_level TEXT DEFAULT 'none',
                affected_services TEXT,
                critical_path BOOLEAN DEFAULT FALSE,
                coverage_score REAL DEFAULT 0.0,
                last_updated TEXT NOT NULL
            )
        """)
        
        self.db_connection.commit()
    
    def record_test_execution(self, execution: TestExecution):
        """Record test execution."""
        cursor = self.db_connection.cursor()
        cursor.execute("""
            INSERT INTO test_executions 
            (test_id, test_name, file_path, status, execution_time_ms, timestamp, retry_count, flakiness_score, impact_level)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            execution.test_id,
            execution.test_name,
            execution.file_path,
            execution.status,
            execution.execution_time_ms,
            execution.timestamp.isoformat(),
            execution.retry_count,
            execution.flakiness_score,
            execution.impact_level.value
        ))
        self.db_connection.commit()
    
    def analyze_flakiness(self, test_id: str, window_days: int = 30) -> FlakinessReport:
        """Analyze flakiness for a specific test."""
        cursor = self.db_connection.cursor()
        
        # Get executions within window
        cutoff_date = (datetime.now(timezone.utc) - timedelta(days=window_days)).isoformat()
        cursor.execute("""
            SELECT status, execution_time_ms, retry_count
            FROM test_executions 
            WHERE test_id = ? AND timestamp >= ?
            ORDER BY timestamp DESC
        """, (test_id, cutoff_date))
        
        executions = cursor.fetchall()
        
        if not executions:
            return FlakinessReport(
                test_id=test_id,
                test_name="Unknown",
                file_path="Unknown",
                total_executions=0,
                passed_count=0,
                failed_count=0,
                flakiness_rate=0.0,
                status=FlakinessStatus.UNKNOWN,
                quarantine_reason=None,
                last_updated=datetime.now(timezone.utc)
            )
        
        # Calculate flakiness metrics
        total_executions = len(executions)
        passed_count = len([e for e in executions if e[0] == "passed"])
        failed_count = len([e for e in executions if e[0] == "failed"])
        
        flakiness_rate = (failed_count / total_executions) * 100 if total_executions > 0 else 0
        
        # Determine status
        if flakiness_rate >= 20:  # 20% failure rate
            status = FlakinessStatus.FLAKY
            quarantine_reason = f"High flakiness rate: {flakiness_rate:.1f}%"
        elif flakiness_rate >= 10:  # 10% failure rate
            status = FlakinessStatus.FLAKY
            quarantine_reason = None
        else:
            status = FlakinessStatus.STABLE
            quarantine_reason = None
        
        # Get test metadata
        cursor.execute("""
            SELECT test_name, file_path FROM test_executions 
            WHERE test_id = ? LIMIT 1
        """, (test_id,))
        
        test_info = cursor.fetchone()
        test_name = test_info[0] if test_info else "Unknown"
        file_path = test_info[1] if test_info else "Unknown"
        
        report = FlakinessReport(
            test_id=test_id,
            test_name=test_name,
            file_path=file_path,
            total_executions=total_executions,
            passed_count=passed_count,
            failed_count=failed_count,
            flakiness_rate=flakiness_rate,
            status=status,
            quarantine_reason=quarantine_reason,
            last_updated=datetime.now(timezone.utc)
        )
        
        # Store report
        self._store_flakiness_report(report)
        
        return report
    
    def _store_flakiness_report(self, report: FlakinessReport):
        """Store flakiness report in database."""
        cursor = self.db_connection.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO flakiness_reports
            (test_id, test_name, file_path, total_executions, passed_count, failed_count, 
             flakiness_rate, status, quarantine_reason, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            report.test_id,
            report.test_name,
            report.file_path,
            report.total_executions,
            report.passed_count,
            report.failed_count,
            report.flakiness_rate,
            report.status.value,
            report.quarantine_reason,
            report.last_updated.isoformat()
        ))
        self.db_connection.commit()
    
    def get_quarantine_list(self) -> List[FlakinessReport]:
        """Get list of quarantined tests."""
        cursor = self.db_connection.cursor()
        cursor.execute("""
            SELECT test_id, test_name, file_path, total_executions, passed_count, failed_count,
                   flakiness_rate, status, quarantine_reason, last_updated
            FROM flakiness_reports
            WHERE status = 'quarantined'
            ORDER BY flakiness_rate DESC
        """)
        
        reports = []
        for row in cursor.fetchall():
            reports.append(FlakinessReport(
                test_id=row[0],
                test_name=row[1],
                file_path=row[2],
                total_executions=row[3],
                passed_count=row[4],
                failed_count=row[5],
                flakiness_rate=row[6],
                status=FlakinessStatus(row[7]),
                quarantine_reason=row[8],
                last_updated=datetime.fromisoformat(row[9])
            ))
        
        return reports
    
    def get_global_flakiness_metrics(self) -> Dict[str, Any]:
        """Get global flakiness metrics."""
        cursor = self.db_connection.cursor()
        
        # Get total test counts
        cursor.execute("SELECT COUNT(*) FROM flakiness_reports")
        total_tests = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM flakiness_reports WHERE status = 'stable'")
        stable_tests = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM flakiness_reports WHERE status = 'flaky'")
        flaky_tests = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM flakiness_reports WHERE status = 'quarantined'")
        quarantined_tests = cursor.fetchone()[0]
        
        # Calculate average flakiness rate
        cursor.execute("SELECT AVG(flakiness_rate) FROM flakiness_reports")
        avg_flakiness = cursor.fetchone()[0] or 0
        
        return {
            "total_tests": total_tests,
            "stable_tests": stable_tests,
            "flaky_tests": flaky_tests,
            "quarantined_tests": quarantined_tests,
            "stability_rate": (stable_tests / max(total_tests, 1)) * 100,
            "flakiness_rate": (flaky_tests / max(total_tests, 1)) * 100,
            "quarantine_rate": (quarantined_tests / max(total_tests, 1)) * 100,
            "avg_flakiness_rate": avg_flakiness
        }


class TestImpactAnalyzer:
    """Analyzes test impact based on code changes."""
    
    def __init__(self, repo_root: str = "."):
        """Initialize test impact analyzer."""
        self.repo_root = pathlib.Path(repo_root)
        self.service_mappings = {
            "api_gateway": ["tests/unit/test_api_gateway.py", "tests/integration/test_api_gateway.py"],
            "orchestrator": ["tests/unit/test_orchestrator.py", "tests/integration/test_orchestrator.py"],
            "router": ["tests/unit/test_router.py", "tests/integration/router/"],
            "tools": ["tests/integration/tools/"],
            "security": ["tests/integration/security/"],
            "rag": ["tests/rag/"],
            "realtime": ["tests/realtime/"],
            "e2e": ["tests/e2e/"],
            "performance": ["tests/performance/"],
            "observability": ["tests/observability/"],
            "chaos": ["tests/chaos/"],
            "adversarial": ["tests/adversarial/"]
        }
    
    def analyze_changed_files(self, changed_files: List[str]) -> TestImpactAnalysis:
        """Analyze test impact based on changed files."""
        affected_services = set()
        critical_path = False
        coverage_score = 0.0
        
        # Map changed files to services
        for file_path in changed_files:
            file_path_obj = pathlib.Path(file_path)
            
            for service, test_paths in self.service_mappings.items():
                for test_path in test_paths:
                    if str(file_path_obj).startswith(test_path) or test_path in str(file_path_obj):
                        affected_services.add(service)
                        break
            
            # Check for critical files
            if self._is_critical_file(file_path):
                critical_path = True
            
            # Calculate coverage score
            coverage_score += self._get_file_coverage_score(file_path)
        
        # Determine impact level
        if critical_path or len(affected_services) >= 5:
            impact_level = TestImpact.HIGH
        elif len(affected_services) >= 3:
            impact_level = TestImpact.MEDIUM
        elif len(affected_services) >= 1:
            impact_level = TestImpact.LOW
        else:
            impact_level = TestImpact.NONE
        
        return TestImpactAnalysis(
            test_id="impact_analysis",
            test_name="Test Impact Analysis",
            file_path="multiple",
            impact_level=impact_level,
            affected_services=list(affected_services),
            critical_path=critical_path,
            coverage_score=coverage_score,
            last_updated=datetime.now(timezone.utc)
        )
    
    def _is_critical_file(self, file_path: str) -> bool:
        """Check if file is critical for system operation."""
        critical_patterns = [
            "app/api/main.py",
            "app/core/config.py",
            "app/db/models/",
            "app/agent/router.py",
            "app/agent/workflows/",
            "requirements.txt",
            "docker-compose.yml"
        ]
        
        return any(pattern in file_path for pattern in critical_patterns)
    
    def _get_file_coverage_score(self, file_path: str) -> float:
        """Get coverage score for file."""
        # Simple scoring based on file type and location
        if file_path.endswith(".py"):
            if "test" in file_path:
                return 0.1  # Test files have lower impact
            elif "app/" in file_path:
                return 0.8  # Application code has high impact
            elif "config" in file_path:
                return 0.9  # Configuration has very high impact
            else:
                return 0.5  # Other Python files
        else:
            return 0.3  # Non-Python files
    
    def get_impacted_tests(self, changed_files: List[str]) -> List[str]:
        """Get list of tests that should be run based on changed files."""
        impacted_tests = set()
        
        for file_path in changed_files:
            file_path_obj = pathlib.Path(file_path)
            
            # Direct test file changes
            if "test" in str(file_path_obj) and file_path_obj.suffix == ".py":
                impacted_tests.add(str(file_path_obj))
            
            # Map application changes to test files
            for service, test_paths in self.service_mappings.items():
                if self._file_affects_service(file_path, service):
                    for test_path in test_paths:
                        if test_path.endswith("/"):
                            # Directory - find all test files
                            test_dir = self.repo_root / test_path
                            if test_dir.exists():
                                for test_file in test_dir.glob("test_*.py"):
                                    impacted_tests.add(str(test_file))
                        else:
                            # Specific test file
                            test_file = self.repo_root / test_path
                            if test_file.exists():
                                impacted_tests.add(str(test_file))
        
        return list(impacted_tests)
    
    def _file_affects_service(self, file_path: str, service: str) -> bool:
        """Check if file change affects a specific service."""
        service_mappings = {
            "api_gateway": ["app/api/", "app/core/"],
            "orchestrator": ["app/orchestrator/", "app/core/"],
            "router": ["app/agent/router.py", "app/agent/"],
            "tools": ["app/agent/tools/", "app/agent/workflows/"],
            "security": ["app/core/security.py", "app/db/"],
            "rag": ["app/rag/", "app/vector/"],
            "realtime": ["app/realtime/", "app/websocket/"],
            "e2e": ["app/", "tests/fixtures/"],
            "performance": ["app/", "scripts/"],
            "observability": ["app/core/logging.py", "app/monitoring/"],
            "chaos": ["app/", "scripts/"],
            "adversarial": ["app/core/", "app/security/"]
        }
        
        if service in service_mappings:
            return any(pattern in file_path for pattern in service_mappings[service])
        
        return False


class FlakinessReporter:
    """Generates flakiness reports."""
    
    def __init__(self, detector: FlakinessDetector):
        """Initialize flakiness reporter."""
        self.detector = detector
    
    def generate_weekly_report(self) -> Dict[str, Any]:
        """Generate weekly flakiness report."""
        metrics = self.detector.get_global_flakiness_metrics()
        quarantine_list = self.detector.get_quarantine_list()
        
        # Get flaky tests
        cursor = self.detector.db_connection.cursor()
        cursor.execute("""
            SELECT test_id, test_name, file_path, flakiness_rate
            FROM flakiness_reports
            WHERE status = 'flaky'
            ORDER BY flakiness_rate DESC
            LIMIT 10
        """)
        
        top_flaky_tests = []
        for row in cursor.fetchall():
            top_flaky_tests.append({
                "test_id": row[0],
                "test_name": row[1],
                "file_path": row[2],
                "flakiness_rate": row[3]
            })
        
        return {
            "report_type": "weekly_flakiness_report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "metrics": metrics,
            "quarantine_list": [report.to_dict() for report in quarantine_list],
            "top_flaky_tests": top_flaky_tests,
            "recommendations": self._generate_recommendations(metrics, quarantine_list)
        }
    
    def _generate_recommendations(self, metrics: Dict[str, Any], quarantine_list: List[FlakinessReport]) -> List[str]:
        """Generate recommendations based on metrics."""
        recommendations = []
        
        if metrics["flakiness_rate"] > 10:
            recommendations.append("High flakiness rate detected. Review test stability.")
        
        if metrics["quarantine_rate"] > 5:
            recommendations.append("High quarantine rate. Consider test infrastructure improvements.")
        
        if len(quarantine_list) > 0:
            recommendations.append(f"{len(quarantine_list)} tests in quarantine. Review and fix.")
        
        if metrics["avg_flakiness_rate"] > 15:
            recommendations.append("Average flakiness rate is high. Implement better test isolation.")
        
        return recommendations


# Global instances
flakiness_detector = FlakinessDetector()
test_impact_analyzer = TestImpactAnalyzer()
flakiness_reporter = FlakinessReporter(flakiness_detector)


def pytest_configure(config):
    """Configure pytest with flakiness tracking."""
    config.addinivalue_line("markers", "flaky: mark test as potentially flaky")
    config.addinivalue_line("markers", "quarantine: mark test as quarantined")
    config.addinivalue_line("markers", "impact_high: mark test as high impact")
    config.addinivalue_line("markers", "impact_medium: mark test as medium impact")
    config.addinivalue_line("markers", "impact_low: mark test as low impact")


def pytest_collection_modifyitems(config, items):
    """Modify test collection based on flakiness and impact analysis."""
    # Get changed files from environment or git
    changed_files = _get_changed_files()
    
    if changed_files:
        # Analyze impact
        impact_analysis = test_impact_analyzer.analyze_changed_files(changed_files)
        impacted_tests = test_impact_analyzer.get_impacted_tests(changed_files)
        
        # Filter tests based on impact
        if impact_analysis.impact_level == TestImpact.LOW:
            # Run only directly impacted tests
            items[:] = [item for item in items if str(item.fspath) in impacted_tests]
        elif impact_analysis.impact_level == TestImpact.MEDIUM:
            # Run impacted tests and related tests
            items[:] = [item for item in items if _should_run_test(item, impacted_tests, impact_analysis)]
        # HIGH impact runs all tests (no filtering)
    
    # Apply flakiness markers
    for item in items:
        test_id = f"{item.fspath}::{item.name}"
        flakiness_report = flakiness_detector.analyze_flakiness(test_id)
        
        if flakiness_report.status == FlakinessStatus.QUARANTINED:
            item.add_marker(pytest.mark.quarantine(reason=flakiness_report.quarantine_reason))
        elif flakiness_report.status == FlakinessStatus.FLAKY:
            item.add_marker(pytest.mark.flaky(reruns=2))


def pytest_runtest_setup(item):
    """Setup test with flakiness tracking."""
    test_id = f"{item.fspath}::{item.name}"
    
    # Check if test is quarantined
    quarantine_marker = item.get_closest_marker("quarantine")
    if quarantine_marker:
        pytest.skip(f"Test quarantined: {quarantine_marker.kwargs.get('reason', 'Unknown')}")


def pytest_runtest_logreport(report):
    """Log test execution for flakiness analysis."""
    if report.when == "call":
        test_id = f"{report.nodeid}"
        test_name = report.nodeid.split("::")[-1]
        file_path = str(report.nodeid.split("::")[0])
        
        # Determine impact level from markers
        impact_level = TestImpact.NONE
        if report.node.get_closest_marker("impact_high"):
            impact_level = TestImpact.HIGH
        elif report.node.get_closest_marker("impact_medium"):
            impact_level = TestImpact.MEDIUM
        elif report.node.get_closest_marker("impact_low"):
            impact_level = TestImpact.LOW
        
        execution = TestExecution(
            test_id=test_id,
            test_name=test_name,
            file_path=file_path,
            status=report.outcome,
            execution_time_ms=report.duration * 1000,
            timestamp=datetime.now(timezone.utc),
            retry_count=0,
            flakiness_score=0.0,
            impact_level=impact_level
        )
        
        flakiness_detector.record_test_execution(execution)


def _get_changed_files() -> List[str]:
    """Get list of changed files from git."""
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1"],
            capture_output=True,
            text=True,
            cwd="."
        )
        
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.split('\n') if line.strip()]
        
        # Fallback: get changed files from current branch
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main"],
            capture_output=True,
            text=True,
            cwd="."
        )
        
        if result.returncode == 0:
            return [line.strip() for line in result.stdout.split('\n') if line.strip()]
    
    except Exception:
        pass
    
    return []


def _should_run_test(item, impacted_tests: List[str], impact_analysis: TestImpactAnalysis) -> bool:
    """Determine if test should be run based on impact analysis."""
    test_path = str(item.fspath)
    
    # Always run directly impacted tests
    if test_path in impacted_tests:
        return True
    
    # Run tests for affected services
    for service in impact_analysis.affected_services:
        if service in test_path:
            return True
    
    # Run critical path tests
    if impact_analysis.critical_path and _is_critical_test(test_path):
        return True
    
    return False


def _is_critical_test(test_path: str) -> bool:
    """Check if test is critical for system operation."""
    critical_patterns = [
        "test_api_gateway",
        "test_orchestrator",
        "test_router",
        "test_security",
        "test_e2e"
    ]
    
    return any(pattern in test_path for pattern in critical_patterns)
