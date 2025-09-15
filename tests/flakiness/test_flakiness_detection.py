"""
Tests for flakiness detection and quarantine system.

This module tests:
- Flakiness rate calculation
- Test quarantine logic
- Retry mechanisms for flaky tests
- Flakiness reporting and analytics
- Integration with CI/CD pipeline
"""

import pytest
import time
import random
import json
import asyncio
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, asdict
from enum import Enum
from unittest.mock import Mock, patch
from pathlib import Path


class TestStatus(Enum):
    """Test execution status."""
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    ERROR = "error"
    FLAKY = "flaky"


@dataclass
class TestExecution:
    """Individual test execution record."""
    test_id: str
    status: TestStatus
    duration_ms: float
    timestamp: float
    retry_count: int = 0
    failure_reason: Optional[str] = None
    environment: str = "ci"
    branch: str = "main"


@dataclass
class FlakinessReport:
    """Flakiness analysis report."""
    test_id: str
    total_executions: int
    passed_count: int
    failed_count: int
    flakiness_rate: float
    last_30_days: bool
    quarantine_recommended: bool
    retry_recommended: bool
    confidence_score: float


class FlakinessDetector:
    """Detects flaky tests based on execution history."""
    
    def __init__(self, flakiness_threshold: float = 0.1):
        self.flakiness_threshold = flakiness_threshold
        self.test_history: Dict[str, List[TestExecution]] = {}
        self.quarantine_list: set = set()
    
    def record_execution(self, execution: TestExecution):
        """Record a test execution."""
        if execution.test_id not in self.test_history:
            self.test_history[execution.test_id] = []
        
        self.test_history[execution.test_id].append(execution)
        
        # Keep only last 100 executions per test
        if len(self.test_history[execution.test_id]) > 100:
            self.test_history[execution.test_id] = self.test_history[execution.test_id][-100:]
    
    def calculate_flakiness_rate(self, test_id: str, window_days: int = 30) -> float:
        """Calculate flakiness rate for a test."""
        if test_id not in self.test_history:
            return 0.0
        
        executions = self.test_history[test_id]
        cutoff_time = time.time() - (window_days * 24 * 60 * 60)
        
        # Filter to recent executions
        recent_executions = [
            ex for ex in executions 
            if ex.timestamp >= cutoff_time
        ]
        
        if len(recent_executions) < 5:  # Need at least 5 executions for reliable calculation
            return 0.0
        
        # Count status changes (flakiness indicator)
        status_changes = 0
        last_status = None
        
        for execution in recent_executions:
            if last_status is not None and execution.status != last_status:
                status_changes += 1
            last_status = execution.status
        
        # Flakiness rate is the ratio of status changes to total executions
        flakiness_rate = status_changes / len(recent_executions)
        return flakiness_rate
    
    def is_flaky(self, test_id: str) -> bool:
        """Determine if a test is flaky."""
        flakiness_rate = self.calculate_flakiness_rate(test_id)
        return flakiness_rate >= self.flakiness_threshold
    
    def generate_flakiness_report(self, test_id: str) -> FlakinessReport:
        """Generate a detailed flakiness report for a test."""
        if test_id not in self.test_history:
            return FlakinessReport(
                test_id=test_id,
                total_executions=0,
                passed_count=0,
                failed_count=0,
                flakiness_rate=0.0,
                last_30_days=False,
                quarantine_recommended=False,
                retry_recommended=False,
                confidence_score=0.0
            )
        
        executions = self.test_history[test_id]
        cutoff_time = time.time() - (30 * 24 * 60 * 60)
        recent_executions = [ex for ex in executions if ex.timestamp >= cutoff_time]
        
        passed_count = sum(1 for ex in recent_executions if ex.status == TestStatus.PASSED)
        failed_count = sum(1 for ex in recent_executions if ex.status == TestStatus.FAILED)
        total_executions = len(recent_executions)
        
        flakiness_rate = self.calculate_flakiness_rate(test_id)
        quarantine_recommended = flakiness_rate >= self.flakiness_threshold
        retry_recommended = flakiness_rate >= 0.05  # Lower threshold for retry recommendation
        
        # Confidence score based on number of executions
        confidence_score = min(1.0, total_executions / 50.0)
        
        return FlakinessReport(
            test_id=test_id,
            total_executions=total_executions,
            passed_count=passed_count,
            failed_count=failed_count,
            flakiness_rate=flakiness_rate,
            last_30_days=len(recent_executions) > 0,
            quarantine_recommended=quarantine_recommended,
            retry_recommended=retry_recommended,
            confidence_score=confidence_score
        )
    
    def quarantine_test(self, test_id: str):
        """Add a test to quarantine list."""
        self.quarantine_list.add(test_id)
    
    def unquarantine_test(self, test_id: str):
        """Remove a test from quarantine list."""
        self.quarantine_list.discard(test_id)
    
    def is_quarantined(self, test_id: str) -> bool:
        """Check if a test is quarantined."""
        return test_id in self.quarantine_list


class TestRetryManager:
    """Manages retry logic for flaky tests."""
    
    def __init__(self, max_retries: int = 3, retry_delay_ms: int = 100):
        self.max_retries = max_retries
        self.retry_delay_ms = retry_delay_ms
        self.retry_counts: Dict[str, int] = {}
    
    def should_retry(self, test_id: str, status: TestStatus) -> bool:
        """Determine if a test should be retried."""
        if status == TestStatus.PASSED:
            return False
        
        current_retries = self.retry_counts.get(test_id, 0)
        return current_retries < self.max_retries
    
    def record_retry(self, test_id: str):
        """Record a retry attempt."""
        self.retry_counts[test_id] = self.retry_counts.get(test_id, 0) + 1
    
    def get_retry_count(self, test_id: str) -> int:
        """Get current retry count for a test."""
        return self.retry_counts.get(test_id, 0)
    
    async def execute_with_retry(self, test_id: str, test_func, *args, **kwargs):
        """Execute a test function with retry logic."""
        last_exception = None
        
        for attempt in range(self.max_retries + 1):
            try:
                result = await test_func(*args, **kwargs) if asyncio.iscoroutinefunction(test_func) else test_func(*args, **kwargs)
                if attempt > 0:
                    self.retry_counts[test_id] = attempt
                return result
            except Exception as e:
                last_exception = e
                if attempt < self.max_retries:
                    await asyncio.sleep(self.retry_delay_ms / 1000.0)
                else:
                    break
        
        raise last_exception


class FlakinessReporter:
    """Generates flakiness reports and analytics."""
    
    def __init__(self, detector: FlakinessDetector):
        self.detector = detector
    
    def generate_summary_report(self) -> Dict[str, Any]:
        """Generate a summary report of all tests."""
        total_tests = len(self.detector.test_history)
        flaky_tests = []
        quarantined_tests = list(self.detector.quarantine_list)
        
        for test_id in self.detector.test_history:
            if self.detector.is_flaky(test_id):
                flaky_tests.append(test_id)
        
        flakiness_rate = len(flaky_tests) / total_tests if total_tests > 0 else 0.0
        
        return {
            "total_tests": total_tests,
            "flaky_tests_count": len(flaky_tests),
            "quarantined_tests_count": len(quarantined_tests),
            "overall_flakiness_rate": flakiness_rate,
            "flaky_tests": flaky_tests,
            "quarantined_tests": quarantined_tests,
            "recommendations": self._generate_recommendations(flaky_tests, quarantined_tests)
        }
    
    def _generate_recommendations(self, flaky_tests: List[str], quarantined_tests: List[str]) -> List[str]:
        """Generate recommendations based on flakiness analysis."""
        recommendations = []
        
        if len(flaky_tests) > 0:
            recommendations.append(f"Review {len(flaky_tests)} flaky tests for potential fixes")
        
        if len(quarantined_tests) > 0:
            recommendations.append(f"Investigate {len(quarantined_tests)} quarantined tests")
        
        if len(flaky_tests) > len(quarantined_tests) * 2:
            recommendations.append("Consider increasing retry counts for stable tests")
        
        return recommendations
    
    def export_report(self, filepath: str):
        """Export flakiness report to JSON file."""
        report = self.generate_summary_report()
        
        # Add detailed reports for each flaky test
        detailed_reports = {}
        for test_id in self.detector.test_history:
            detailed_reports[test_id] = asdict(self.detector.generate_flakiness_report(test_id))
        
        report["detailed_reports"] = detailed_reports
        
        with open(filepath, 'w') as f:
            json.dump(report, f, indent=2, default=str)


# Pytest plugin for flakiness detection
class FlakinessPlugin:
    """Pytest plugin for automatic flakiness detection."""
    
    def __init__(self):
        self.detector = FlakinessDetector()
        self.retry_manager = TestRetryManager()
    
    def pytest_runtest_setup(self, item):
        """Called before each test setup."""
        test_id = f"{item.nodeid}"
        
        # Skip quarantined tests
        if self.detector.is_quarantined(test_id):
            pytest.skip(f"Test {test_id} is quarantined due to flakiness")
    
    def pytest_runtest_teardown(self, item, nextitem):
        """Called after each test teardown."""
        pass
    
    def pytest_runtest_logreport(self, report):
        """Called for each test report."""
        test_id = f"{report.nodeid}"
        
        # Record execution
        status = TestStatus.PASSED if report.outcome == "passed" else TestStatus.FAILED
        execution = TestExecution(
            test_id=test_id,
            status=status,
            duration_ms=report.duration * 1000,
            timestamp=time.time(),
            retry_count=self.retry_manager.get_retry_count(test_id),
            failure_reason=str(report.longrepr) if report.longrepr else None
        )
        
        self.detector.record_execution(execution)
        
        # Check if test should be quarantined
        if self.detector.is_flaky(test_id):
            self.detector.quarantine_test(test_id)


@pytest.fixture
def flakiness_detector():
    """Fixture for flakiness detector."""
    return FlakinessDetector()


@pytest.fixture
def retry_manager():
    """Fixture for test retry manager."""
    return TestRetryManager()


@pytest.fixture
def flakiness_reporter(flakiness_detector):
    """Fixture for flakiness reporter."""
    return FlakinessReporter(flakiness_detector)


class TestFlakinessDetection:
    """Test flakiness detection functionality."""
    
    def test_flakiness_calculation_stable_test(self, flakiness_detector):
        """Test flakiness calculation for a stable test."""
        test_id = "test_stable_function"
        
        # Record 10 passing executions
        for i in range(10):
            execution = TestExecution(
                test_id=test_id,
                status=TestStatus.PASSED,
                duration_ms=100.0,
                timestamp=time.time() - i * 3600  # 1 hour apart
            )
            flakiness_detector.record_execution(execution)
        
        flakiness_rate = flakiness_detector.calculate_flakiness_rate(test_id)
        assert flakiness_rate == 0.0
        assert not flakiness_detector.is_flaky(test_id)
    
    def test_flakiness_calculation_flaky_test(self, flakiness_detector):
        """Test flakiness calculation for a flaky test."""
        test_id = "test_flaky_function"
        
        # Record alternating pass/fail pattern
        for i in range(10):
            status = TestStatus.PASSED if i % 2 == 0 else TestStatus.FAILED
            execution = TestExecution(
                test_id=test_id,
                status=status,
                duration_ms=100.0,
                timestamp=time.time() - i * 3600
            )
            flakiness_detector.record_execution(execution)
        
        flakiness_rate = flakiness_detector.calculate_flakiness_rate(test_id)
        assert flakiness_rate > 0.0
        assert flakiness_detector.is_flaky(test_id)
    
    def test_flakiness_report_generation(self, flakiness_detector):
        """Test flakiness report generation."""
        test_id = "test_report_generation"
        
        # Record mixed results
        for i in range(20):
            status = TestStatus.PASSED if i % 3 == 0 else TestStatus.FAILED
            execution = TestExecution(
                test_id=test_id,
                status=status,
                duration_ms=100.0,
                timestamp=time.time() - i * 3600
            )
            flakiness_detector.record_execution(execution)
        
        report = flakiness_detector.generate_flakiness_report(test_id)
        
        assert report.test_id == test_id
        assert report.total_executions == 20
        assert report.passed_count > 0
        assert report.failed_count > 0
        assert report.flakiness_rate > 0.0
        assert report.quarantine_recommended
    
    def test_quarantine_functionality(self, flakiness_detector):
        """Test quarantine functionality."""
        test_id = "test_quarantine"
        
        # Mark test as flaky
        flakiness_detector.quarantine_test(test_id)
        assert flakiness_detector.is_quarantined(test_id)
        
        # Unquarantine test
        flakiness_detector.unquarantine_test(test_id)
        assert not flakiness_detector.is_quarantined(test_id)


class TestRetryManagerFunctionality:
    """Test retry manager functionality."""
    
    def test_retry_logic(self, retry_manager):
        """Test retry logic."""
        test_id = "test_retry_logic"
        
        # First failure should trigger retry
        assert retry_manager.should_retry(test_id, TestStatus.FAILED)
        assert retry_manager.get_retry_count(test_id) == 0
        
        # Record retry
        retry_manager.record_retry(test_id)
        assert retry_manager.get_retry_count(test_id) == 1
        
        # Should still retry
        assert retry_manager.should_retry(test_id, TestStatus.FAILED)
        
        # Record more retries
        for _ in range(2):
            retry_manager.record_retry(test_id)
        
        # Should not retry anymore
        assert not retry_manager.should_retry(test_id, TestStatus.FAILED)
    
    def test_success_no_retry(self, retry_manager):
        """Test that successful tests don't trigger retries."""
        test_id = "test_success"
        
        assert not retry_manager.should_retry(test_id, TestStatus.PASSED)


class TestFlakinessReporter:
    """Test flakiness reporter functionality."""
    
    def test_summary_report(self, flakiness_reporter, flakiness_detector):
        """Test summary report generation."""
        # Add some test data
        for i in range(3):
            test_id = f"test_{i}"
            for j in range(10):
                status = TestStatus.PASSED if j % 2 == 0 else TestStatus.FAILED
                execution = TestExecution(
                    test_id=test_id,
                    status=status,
                    duration_ms=100.0,
                    timestamp=time.time() - j * 3600
                )
                flakiness_detector.record_execution(execution)
        
        # Quarantine one test
        flakiness_detector.quarantine_test("test_1")
        
        report = flakiness_reporter.generate_summary_report()
        
        assert report["total_tests"] == 3
        assert report["flaky_tests_count"] == 3  # All tests are flaky due to alternating pattern
        assert report["quarantined_tests_count"] == 1
        assert report["overall_flakiness_rate"] == 1.0
        assert len(report["recommendations"]) > 0
    
    def test_report_export(self, flakiness_reporter, flakiness_detector, tmp_path):
        """Test report export functionality."""
        # Add some test data
        test_id = "test_export"
        for i in range(5):
            execution = TestExecution(
                test_id=test_id,
                status=TestStatus.PASSED,
                duration_ms=100.0,
                timestamp=time.time() - i * 3600
            )
            flakiness_detector.record_execution(execution)
        
        # Export report
        report_file = tmp_path / "flakiness_report.json"
        flakiness_reporter.export_report(str(report_file))
        
        # Verify file was created and contains data
        assert report_file.exists()
        
        with open(report_file, 'r') as f:
            report_data = json.load(f)
        
        assert "total_tests" in report_data
        assert "detailed_reports" in report_data
        assert test_id in report_data["detailed_reports"]


class TestFlakyTestSimulation:
    """Test simulation of flaky tests for demonstration."""
    
    def test_stable_test_simulation(self):
        """Simulate a stable test."""
        # This test should always pass
        assert True
    
    @pytest.mark.flaky
    def test_flaky_test_simulation(self):
        """Simulate a flaky test."""
        # This test has a 30% chance of failing
        if random.random() < 0.3:
            pytest.fail("Simulated flaky test failure")
        assert True
    
    @pytest.mark.flaky
    def test_intermittent_failure_simulation(self):
        """Simulate an intermittent failure."""
        # This test fails every 4th execution
        current_time = int(time.time())
        if current_time % 4 == 0:
            pytest.fail("Simulated intermittent failure")
        assert True
    
    def test_time_dependent_flaky_test(self):
        """Test that depends on timing (potentially flaky)."""
        # Simulate timing-dependent behavior
        start_time = time.time()
        time.sleep(0.001)  # Small delay
        end_time = time.time()
        
        # This could be flaky depending on system load
        assert end_time > start_time
    
    def test_resource_dependent_flaky_test(self):
        """Test that depends on external resources (potentially flaky)."""
        # Simulate resource dependency
        random_value = random.randint(1, 100)
        
        # This could be flaky if the resource is not always available
        assert random_value > 0


class TestQuarantineIntegration:
    """Test integration of quarantine system with pytest."""
    
    def test_quarantine_plugin_setup(self):
        """Test that quarantine plugin can be set up."""
        plugin = FlakinessPlugin()
        assert plugin.detector is not None
        assert plugin.retry_manager is not None
    
    def test_quarantine_list_management(self):
        """Test quarantine list management."""
        detector = FlakinessDetector()
        
        # Initially empty
        assert len(detector.quarantine_list) == 0
        
        # Add tests to quarantine
        detector.quarantine_test("test1")
        detector.quarantine_test("test2")
        
        assert len(detector.quarantine_list) == 2
        assert "test1" in detector.quarantine_list
        assert "test2" in detector.quarantine_list
        
        # Remove one test
        detector.unquarantine_test("test1")
        assert len(detector.quarantine_list) == 1
        assert "test1" not in detector.quarantine_list
        assert "test2" in detector.quarantine_list


class TestFlakinessThresholds:
    """Test different flakiness thresholds and their effects."""
    
    def test_low_flakiness_threshold(self):
        """Test with low flakiness threshold."""
        detector = FlakinessDetector(flakiness_threshold=0.05)
        
        test_id = "test_low_threshold"
        # Record slightly flaky test (10% flakiness)
        for i in range(20):
            status = TestStatus.FAILED if i == 0 else TestStatus.PASSED
            execution = TestExecution(
                test_id=test_id,
                status=status,
                duration_ms=100.0,
                timestamp=time.time() - i * 3600
            )
            detector.record_execution(execution)
        
        assert detector.is_flaky(test_id)
    
    def test_high_flakiness_threshold(self):
        """Test with high flakiness threshold."""
        detector = FlakinessDetector(flakiness_threshold=0.5)
        
        test_id = "test_high_threshold"
        # Record moderately flaky test (20% flakiness)
        for i in range(20):
            status = TestStatus.FAILED if i % 5 == 0 else TestStatus.PASSED
            execution = TestExecution(
                test_id=test_id,
                status=status,
                duration_ms=100.0,
                timestamp=time.time() - i * 3600
            )
            detector.record_execution(execution)
        
        assert not detector.is_flaky(test_id)  # Not flaky enough for high threshold
