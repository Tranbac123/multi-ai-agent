"""Test impact analysis plugin for selective test execution."""

import os
import json
import ast
import git
from pathlib import Path
from typing import Dict, Set, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class TestImpactRule:
    """Rule for determining which tests to run based on changes."""
    pattern: str  # File pattern to match
    test_paths: List[str]  # Test paths to run when pattern matches
    priority: int = 1  # Higher priority rules run first
    description: str = ""


@dataclass
class ChangeInfo:
    """Information about a file change."""
    file_path: str
    change_type: str  # 'added', 'modified', 'deleted'
    lines_changed: Optional[List[int]] = None


class TestImpactAnalyzer:
    """Analyzes code changes to determine which tests to run."""
    
    def __init__(self, repo_root: str = "."):
        self.repo_root = Path(repo_root)
        self.rules: List[TestImpactRule] = []
        self.change_cache: Dict[str, List[ChangeInfo]] = {}
        self._load_default_rules()
    
    def _load_default_rules(self):
        """Load default test impact rules."""
        default_rules = [
            # Core platform changes
            TestImpactRule(
                pattern="apps/api-gateway/**",
                test_paths=["tests/integration/api_gateway/", "tests/contract/", "tests/e2e/"],
                priority=10,
                description="API Gateway changes require integration and E2E tests"
            ),
            TestImpactRule(
                pattern="apps/orchestrator/**",
                test_paths=["tests/integration/orchestrator/", "tests/e2e/", "tests/chaos/"],
                priority=10,
                description="Orchestrator changes require integration, E2E, and chaos tests"
            ),
            TestImpactRule(
                pattern="apps/router-service/**",
                test_paths=["tests/integration/router/", "tests/eval/", "tests/performance/"],
                priority=10,
                description="Router changes require integration, evaluation, and performance tests"
            ),
            TestImpactRule(
                pattern="apps/realtime/**",
                test_paths=["tests/integration/realtime/", "tests/performance/"],
                priority=9,
                description="Realtime changes require integration and performance tests"
            ),
            TestImpactRule(
                pattern="apps/billing-service/**",
                test_paths=["tests/integration/billing/", "tests/e2e/"],
                priority=9,
                description="Billing changes require integration and E2E tests"
            ),
            TestImpactRule(
                pattern="apps/analytics-service/**",
                test_paths=["tests/integration/analytics/", "tests/observability/"],
                priority=8,
                description="Analytics changes require integration and observability tests"
            ),
            
            # Contract and schema changes
            TestImpactRule(
                pattern="libs/contracts/**",
                test_paths=["tests/contract/", "tests/integration/", "tests/e2e/"],
                priority=10,
                description="Contract changes require all integration tests"
            ),
            TestImpactRule(
                pattern="libs/adapters/**",
                test_paths=["tests/integration/orchestrator/", "tests/chaos/"],
                priority=9,
                description="Adapter changes require orchestrator and chaos tests"
            ),
            
            # Infrastructure changes
            TestImpactRule(
                pattern="infra/**",
                test_paths=["tests/integration/k8s/", "tests/chaos/"],
                priority=8,
                description="Infrastructure changes require K8s and chaos tests"
            ),
            TestImpactRule(
                pattern=".github/workflows/**",
                test_paths=["tests/_plugins/", "tests/performance/"],
                priority=7,
                description="CI/CD changes require plugin and performance tests"
            ),
            
            # Test infrastructure changes
            TestImpactRule(
                pattern="tests/_fixtures/**",
                test_paths=["tests/unit/", "tests/integration/"],
                priority=6,
                description="Test fixture changes require unit and integration tests"
            ),
            TestImpactRule(
                pattern="tests/_helpers/**",
                test_paths=["tests/unit/", "tests/integration/"],
                priority=6,
                description="Test helper changes require unit and integration tests"
            ),
            TestImpactRule(
                pattern="tests/_plugins/**",
                test_paths=["tests/unit/", "tests/integration/", "tests/e2e/"],
                priority=7,
                description="Test plugin changes require comprehensive testing"
            ),
            
            # Configuration changes
            TestImpactRule(
                pattern="pytest.ini",
                test_paths=["tests/unit/", "tests/integration/"],
                priority=5,
                description="Pytest configuration changes require basic tests"
            ),
            TestImpactRule(
                pattern="requirements*.txt",
                test_paths=["tests/unit/", "tests/integration/"],
                priority=5,
                description="Dependency changes require basic tests"
            ),
            
            # Documentation changes (low priority)
            TestImpactRule(
                pattern="docs/**",
                test_paths=["tests/unit/"],  # Minimal testing for docs
                priority=1,
                description="Documentation changes require minimal testing"
            ),
            TestImpactRule(
                pattern="README.md",
                test_paths=["tests/unit/"],
                priority=1,
                description="README changes require minimal testing"
            )
        ]
        
        self.rules = sorted(default_rules, key=lambda x: x.priority, reverse=True)
    
    def get_changes(self, base_ref: str = "origin/main", head_ref: str = "HEAD") -> List[ChangeInfo]:
        """Get list of changed files between two git references."""
        cache_key = f"{base_ref}..{head_ref}"
        
        if cache_key in self.change_cache:
            return self.change_cache[cache_key]
        
        try:
            repo = git.Repo(self.repo_root)
            
            # Get diff between base and head
            diff = repo.git.diff("--name-status", f"{base_ref}..{head_ref}")
            
            changes = []
            for line in diff.strip().split('\n'):
                if not line:
                    continue
                
                parts = line.split('\t')
                if len(parts) >= 2:
                    change_type_map = {
                        'A': 'added',
                        'M': 'modified',
                        'D': 'deleted',
                        'R': 'renamed',
                        'C': 'copied'
                    }
                    
                    change_type = change_type_map.get(parts[0], 'modified')
                    file_path = parts[1]
                    
                    changes.append(ChangeInfo(
                        file_path=file_path,
                        change_type=change_type
                    ))
            
            self.change_cache[cache_key] = changes
            return changes
            
        except Exception as e:
            print(f"Warning: Could not get git changes: {e}")
            return []
    
    def analyze_impact(self, changes: List[ChangeInfo]) -> Dict[str, List[str]]:
        """Analyze which tests should be run based on changes."""
        test_impact = {
            "high_priority": set(),
            "medium_priority": set(),
            "low_priority": set(),
            "all_tests": set()
        }
        
        for change in changes:
            file_path = change.file_path
            
            # Check against rules
            for rule in self.rules:
                if self._matches_pattern(file_path, rule.pattern):
                    for test_path in rule.test_paths:
                        # Categorize by priority
                        if rule.priority >= 9:
                            test_impact["high_priority"].add(test_path)
                        elif rule.priority >= 6:
                            test_impact["medium_priority"].add(test_path)
                        else:
                            test_impact["low_priority"].add(test_path)
                        
                        test_impact["all_tests"].add(test_path)
        
        # Convert sets to lists and sort
        for priority in test_impact:
            test_impact[priority] = sorted(list(test_impact[priority]))
        
        return test_impact
    
    def _matches_pattern(self, file_path: str, pattern: str) -> bool:
        """Check if file path matches the pattern."""
        import fnmatch
        
        # Handle glob patterns
        if '*' in pattern or '?' in pattern or '[' in pattern:
            return fnmatch.fnmatch(file_path, pattern)
        
        # Handle directory patterns
        if pattern.endswith('/**'):
            prefix = pattern[:-3]
            return file_path.startswith(prefix)
        
        # Exact match
        return file_path == pattern
    
    def get_test_commands(self, changes: List[ChangeInfo], max_tests: int = None) -> List[str]:
        """Get pytest commands to run based on changes."""
        impact = self.analyze_impact(changes)
        
        commands = []
        
        # High priority tests (always run)
        if impact["high_priority"]:
            for test_path in impact["high_priority"][:max_tests]:
                commands.append(f"pytest {test_path} -v")
        
        # Medium priority tests (run if time permits)
        if impact["medium_priority"] and (not max_tests or len(commands) < max_tests):
            remaining = max_tests - len(commands) if max_tests else len(impact["medium_priority"])
            for test_path in impact["medium_priority"][:remaining]:
                commands.append(f"pytest {test_path} -v")
        
        # Low priority tests (run if still time)
        if impact["low_priority"] and (not max_tests or len(commands) < max_tests):
            remaining = max_tests - len(commands) if max_tests else len(impact["low_priority"])
            for test_path in impact["low_priority"][:remaining]:
                commands.append(f"pytest {test_path} -v")
        
        return commands
    
    def should_run_full_suite(self, changes: List[ChangeInfo]) -> bool:
        """Determine if full test suite should be run."""
        # Run full suite for critical changes
        critical_patterns = [
            "pytest.ini",
            "requirements*.txt",
            "tests/_plugins/**",
            "tests/_fixtures/**",
            "tests/_helpers/**",
            "libs/contracts/**"
        ]
        
        for change in changes:
            for pattern in critical_patterns:
                if self._matches_pattern(change.file_path, pattern):
                    return True
        
        # Run full suite if too many files changed
        if len(changes) > 50:
            return True
        
        # Run full suite if core services changed
        core_services = ["apps/api-gateway/**", "apps/orchestrator/**", "apps/router-service/**"]
        core_changes = 0
        
        for change in changes:
            for pattern in core_services:
                if self._matches_pattern(change.file_path, pattern):
                    core_changes += 1
                    break
        
        if core_changes >= 2:  # Multiple core services changed
            return True
        
        return False


class TestImpactPlugin:
    """Pytest plugin for test impact analysis."""
    
    def __init__(self):
        self.analyzer = TestImpactAnalyzer()
        self.selected_tests: Set[str] = set()
    
    def pytest_configure(self, config):
        """Configure the plugin."""
        # Get changes from environment or git
        base_ref = os.getenv("CI_BASE_REF", "origin/main")
        head_ref = os.getenv("CI_HEAD_REF", "HEAD")
        
        changes = self.analyzer.get_changes(base_ref, head_ref)
        
        if changes:
            impact = self.analyzer.analyze_impact(changes)
            
            # Set selected tests
            for test_path in impact["all_tests"]:
                self.selected_tests.add(test_path)
            
            print(f"\nTest Impact Analysis:")
            print(f"  Changes detected: {len(changes)}")
            print(f"  High priority tests: {len(impact['high_priority'])}")
            print(f"  Medium priority tests: {len(impact['medium_priority'])}")
            print(f"  Low priority tests: {len(impact['low_priority'])}")
            
            if impact["high_priority"]:
                print(f"  High priority paths: {impact['high_priority'][:3]}...")
    
    def pytest_collection_modifyitems(self, config, items):
        """Modify test collection based on impact analysis."""
        if not self.selected_tests:
            return
        
        selected_items = []
        for item in items:
            # Check if test should be included
            test_path = str(item.fspath)
            should_include = False
            
            for selected_path in self.selected_tests:
                if selected_path in test_path or test_path.startswith(selected_path):
                    should_include = True
                    break
            
            if should_include:
                selected_items.append(item)
            else:
                # Skip test
                skip_marker = pytest.mark.skip(reason="Not selected by test impact analysis")
                item.add_marker(skip_marker)
        
        # Update items list
        items[:] = selected_items


def pytest_configure(config):
    """Configure pytest to use test impact plugin."""
    if os.getenv("ENABLE_TEST_IMPACT", "false").lower() == "true":
        config.pluginmanager.register(TestImpactPlugin(), "test-impact-plugin")
