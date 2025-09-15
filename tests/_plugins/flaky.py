"""Flaky test management plugin."""

import pytest
import time
import random
from typing import Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class FlakyTestInfo:
    """Information about a flaky test."""
    test_name: str
    failure_count: int = 0
    success_count: int = 0
    last_failure: Optional[str] = None
    is_quarantined: bool = False
    quarantine_reason: Optional[str] = None
    auto_retry_count: int = 0
    max_retries: int = 2


class FlakyTestManager:
    """Manages flaky test detection and handling."""
    
    def __init__(self):
        self.flaky_tests: Dict[str, FlakyTestInfo] = {}
        self.quarantine_list: Dict[str, str] = {}  # test_name -> reason
        self.retry_count = 2  # Default retry count
    
    def mark_test_flaky(self, test_name: str, max_retries: int = 2, reason: str = "Unknown") -> None:
        """Mark a test as potentially flaky."""
        if test_name not in self.flaky_tests:
            self.flaky_tests[test_name] = FlakyTestInfo(test_name, max_retries=max_retries)
    
    def quarantine_test(self, test_name: str, reason: str) -> None:
        """Quarantine a test (skip it)."""
        self.quarantine_list[test_name] = reason
        if test_name in self.flaky_tests:
            self.flaky_tests[test_name].is_quarantined = True
            self.flaky_tests[test_name].quarantine_reason = reason
    
    def unquarantine_test(self, test_name: str) -> None:
        """Remove test from quarantine."""
        if test_name in self.quarantine_list:
            del self.quarantine_list[test_name]
        if test_name in self.flaky_tests:
            self.flaky_tests[test_name].is_quarantined = False
            self.flaky_tests[test_name].quarantine_reason = None
    
    def should_retry_test(self, test_name: str) -> bool:
        """Check if a test should be retried."""
        if test_name in self.quarantine_list:
            return False
        
        if test_name not in self.flaky_tests:
            return False
        
        test_info = self.flaky_tests[test_name]
        return test_info.auto_retry_count < test_info.max_retries
    
    def record_test_result(self, test_name: str, passed: bool, error_message: str = None) -> None:
        """Record the result of a test execution."""
        if test_name not in self.flaky_tests:
            self.flaky_tests[test_name] = FlakyTestInfo(test_name)
        
        test_info = self.flaky_tests[test_name]
        
        if passed:
            test_info.success_count += 1
        else:
            test_info.failure_count += 1
            test_info.last_failure = error_message or "Unknown error"
    
    def get_flakiness_score(self, test_name: str) -> float:
        """Calculate flakiness score (0.0 = never fails, 1.0 = always fails)."""
        if test_name not in self.flaky_tests:
            return 0.0
        
        test_info = self.flaky_tests[test_name]
        total_runs = test_info.success_count + test_info.failure_count
        
        if total_runs == 0:
            return 0.0
        
        return test_info.failure_count / total_runs
    
    def generate_flakiness_report(self) -> Dict[str, Any]:
        """Generate a report of flaky tests."""
        report = {
            "total_tests": len(self.flaky_tests),
            "quarantined_tests": len(self.quarantine_list),
            "high_flakiness_tests": [],
            "recent_failures": [],
            "quarantine_list": self.quarantine_list.copy()
        }
        
        for test_name, test_info in self.flaky_tests.items():
            flakiness_score = self.get_flakiness_score(test_name)
            
            if flakiness_score > 0.3:  # 30% failure rate
                report["high_flakiness_tests"].append({
                    "test_name": test_name,
                    "flakiness_score": flakiness_score,
                    "failure_count": test_info.failure_count,
                    "success_count": test_info.success_count,
                    "last_failure": test_info.last_failure
                })
            
            if test_info.last_failure and test_info.failure_count > 0:
                report["recent_failures"].append({
                    "test_name": test_name,
                    "last_failure": test_info.last_failure,
                    "failure_count": test_info.failure_count
                })
        
        # Sort by flakiness score
        report["high_flakiness_tests"].sort(key=lambda x: x["flakiness_score"], reverse=True)
        report["recent_failures"].sort(key=lambda x: x["failure_count"], reverse=True)
        
        return report


# Global flaky test manager
flaky_manager = FlakyTestManager()


def flaky(max_retries: int = 2, reason: str = "Potentially flaky test"):
    """Decorator to mark a test as potentially flaky with auto-retry."""
    def decorator(func):
        test_name = f"{func.__module__}::{func.__name__}"
        flaky_manager.mark_test_flaky(test_name, max_retries, reason)
        
        def wrapper(*args, **kwargs):
            # Check if test is quarantined
            if test_name in flaky_manager.quarantine_list:
                pytest.skip(f"Test quarantined: {flaky_manager.quarantine_list[test_name]}")
            
            # Execute test with retries
            last_error = None
            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)
                    flaky_manager.record_test_result(test_name, True)
                    return result
                except Exception as e:
                    last_error = e
                    flaky_manager.record_test_result(test_name, False, str(e))
                    
                    if attempt < max_retries:
                        # Wait before retry with exponential backoff
                        wait_time = (2 ** attempt) + random.uniform(0, 1)
                        time.sleep(wait_time)
                        continue
                    else:
                        # Final attempt failed
                        raise e
            
            return None
        
        # Copy function metadata
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__module__ = func.__module__
        
        return wrapper
    
    return decorator


def quarantine(reason: str = "Test quarantined"):
    """Decorator to quarantine a test (skip it)."""
    def decorator(func):
        test_name = f"{func.__module__}::{func.__name__}"
        flaky_manager.quarantine_test(test_name, reason)
        
        def wrapper(*args, **kwargs):
            pytest.skip(f"Test quarantined: {reason}")
        
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__
        wrapper.__module__ = func.__module__
        
        return wrapper
    
    return decorator


class FlakyTestPlugin:
    """Pytest plugin for flaky test management."""
    
    def __init__(self):
        self.manager = flaky_manager
    
    def pytest_runtest_setup(self, item):
        """Called before each test runs."""
        test_name = f"{item.module.__name__}::{item.name}"
        
        # Check if test should be skipped due to quarantine
        if test_name in self.manager.quarantine_list:
            pytest.skip(f"Test quarantined: {self.manager.quarantine_list[test_name]}")
    
    def pytest_runtest_logreport(self, report):
        """Called when a test report is ready."""
        if report.when == "call":  # Only on actual test execution
            test_name = f"{report.nodeid}"
            passed = report.outcome == "passed"
            error_message = str(report.longrepr) if report.longrepr else None
            
            self.manager.record_test_result(test_name, passed, error_message)
    
    def pytest_sessionfinish(self, session, exitstatus):
        """Called after test session finishes."""
        # Generate and print flakiness report
        report = self.manager.generate_flakiness_report()
        
        print("\n" + "="*60)
        print("FLAKY TEST REPORT")
        print("="*60)
        print(f"Total tracked tests: {report['total_tests']}")
        print(f"Quarantined tests: {report['quarantined_tests']}")
        print(f"High flakiness tests: {len(report['high_flakiness_tests'])}")
        
        if report["high_flakiness_tests"]:
            print("\nHigh Flakiness Tests:")
            for test in report["high_flakiness_tests"][:5]:  # Top 5
                print(f"  - {test['test_name']}: {test['flakiness_score']:.2%} failure rate")
        
        if report["quarantine_list"]:
            print(f"\nQuarantined Tests ({len(report['quarantine_list'])}):")
            for test_name, reason in list(report["quarantine_list"].items())[:5]:
                print(f"  - {test_name}: {reason}")
        
        print("="*60)


def pytest_configure(config):
    """Configure pytest to use the flaky test plugin."""
    config.pluginmanager.register(FlakyTestPlugin(), "flaky-test-plugin")
