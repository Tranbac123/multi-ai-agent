#!/usr/bin/env python3
"""
Platform Readiness Audit Script

Scans the codebase for production readiness criteria:
- Loop guards, progress(), oscillation detector
- Strict JSON validators at API/Orchestrator/Router/Tool boundaries
- Router metrics & expected_vs_actual tracking
- Tool adapter invariants (timeouts/retries/circuit/bulkhead/idempotency/write-ahead)
- WebSocket backpressure metrics
- RLS policy usage in DB layer
- OTEL attributes & Prometheus metrics names

Usage:
    python scripts/audit_readiness.py [--verbose] [--fix]
"""

import ast
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
import argparse
import json


class ReadinessAuditor:
    """Audits codebase for production readiness criteria."""
    
    def __init__(self, root_path: Path, verbose: bool = False, fix: bool = False):
        self.root_path = root_path
        self.verbose = verbose
        self.fix = fix
        self.issues: List[Dict] = []
        self.passes: List[str] = []
        
        # Define critical patterns and requirements
        self.loop_safety_patterns = [
            r'MAX_STEPS\s*=',
            r'MAX_WALL_MS\s*=',
            r'MAX_REPAIR_ATTEMPTS\s*=',
            r'progress\(',
            r'oscillation.*detector',
            r'loop_cut_total',
            r'no_progress_events_total'
        ]
        
        self.contract_patterns = [
            r'strict\s*=\s*True',
            r'forbid_extra\s*=\s*True',
            r'AgentSpec',
            r'MessageSpec',
            r'ToolSpec',
            r'ErrorSpec',
            r'RouterDecisionRequest',
            r'RouterDecisionResponse'
        ]
        
        self.router_patterns = [
            r'token_count',
            r'json_schema_strictness',
            r'domain_flags',
            r'novelty',
            r'historical_failure_rate',
            r'router_decision_latency_ms',
            r'router_misroute_rate',
            r'tier_distribution',
            r'expected_vs_actual'
        ]
        
        self.tool_adapter_patterns = [
            r'timeout',
            r'retry.*backoff',
            r'circuit.*breaker',
            r'bulkhead',
            r'idempotency',
            r'write.*ahead',
            r'compensate\(',
            r'retry_total',
            r'circuit_open_total'
        ]
        
        self.websocket_patterns = [
            r'ws_active_connections',
            r'ws_backpressure_drops',
            r'ws_send_errors',
            r'backpressure.*policy',
            r'drop.*intermediate'
        ]
        
        self.rls_patterns = [
            r'ROW\s+LEVEL\s+SECURITY',
            r'RLS',
            r'tenant_id.*policy',
            r'cross.*tenant.*zero'
        ]
        
        self.otel_patterns = [
            r'run_id',
            r'step_id',
            r'tenant_id',
            r'tool_id',
            r'tier',
            r'workflow',
            r'span\.set_attribute'
        ]
        
        self.prometheus_patterns = [
            r'agent_run_latency_ms',
            r'router_decision_latency_ms',
            r'router_misroute_rate',
            r'expected_vs_actual_cost',
            r'ws_backpressure_drops',
            r'tool_error_rate',
            r'retry_total',
            r'cost_usd_total',
            r'tokens_total'
        ]
    
    def log(self, message: str, level: str = "INFO"):
        """Log message with level."""
        if self.verbose or level in ["ERROR", "WARN"]:
            print(f"[{level}] {message}")
    
    def add_issue(self, category: str, file_path: str, line_num: int, 
                  message: str, severity: str = "ERROR"):
        """Add an issue to the audit results."""
        self.issues.append({
            "category": category,
            "file": file_path,
            "line": line_num,
            "message": message,
            "severity": severity
        })
        self.log(f"Issue in {file_path}:{line_num} - {message}", severity)
    
    def add_pass(self, category: str, file_path: str, message: str):
        """Add a passing check to the audit results."""
        self.passes.append(f"{category}: {file_path} - {message}")
        self.log(f"PASS: {category} - {file_path} - {message}")
    
    def scan_file(self, file_path: Path) -> Dict[str, List[str]]:
        """Scan a single file for patterns."""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            self.log(f"Error reading {file_path}: {e}", "ERROR")
            return {}
        
        patterns_found = {}
        
        # Check for Python patterns
        if file_path.suffix == '.py':
            try:
                tree = ast.parse(content)
                patterns_found.update(self._analyze_python_ast(tree, content, file_path))
            except SyntaxError as e:
                self.add_issue("SYNTAX", str(file_path), e.lineno, f"Syntax error: {e}")
        
        # Check for SQL patterns
        if file_path.suffix in ['.sql', '.py']:
            patterns_found.update(self._analyze_sql_patterns(content, file_path))
        
        # Check for YAML/JSON patterns
        if file_path.suffix in ['.yaml', '.yml', '.json']:
            patterns_found.update(self._analyze_config_patterns(content, file_path))
        
        return patterns_found
    
    def _analyze_python_ast(self, tree: ast.AST, content: str, file_path: Path) -> Dict[str, List[str]]:
        """Analyze Python AST for readiness patterns."""
        patterns_found = {}
        
        # Check for class definitions and their methods
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                class_name = node.name
                
                # Check for required methods in specific classes
                if 'Orchestrator' in class_name:
                    self._check_orchestrator_class(node, content, file_path)
                elif 'Router' in class_name:
                    self._check_router_class(node, content, file_path)
                elif 'Adapter' in class_name or 'Tool' in class_name:
                    self._check_tool_adapter_class(node, content, file_path)
                elif 'Realtime' in class_name or 'WebSocket' in class_name:
                    self._check_websocket_class(node, content, file_path)
            
            elif isinstance(node, ast.FunctionDef):
                self._check_function_patterns(node, content, file_path)
        
        return patterns_found
    
    def _check_orchestrator_class(self, node: ast.ClassDef, content: str, file_path: Path):
        """Check orchestrator class for loop safety patterns."""
        class_content = ast.get_source_segment(content, node)
        
        # Check for loop safety constants
        required_constants = ['MAX_STEPS', 'MAX_WALL_MS', 'MAX_REPAIR_ATTEMPTS']
        for constant in required_constants:
            if constant not in class_content:
                self.add_issue("LOOP_SAFETY", str(file_path), node.lineno, 
                             f"Missing {constant} in Orchestrator class")
            else:
                self.add_pass("LOOP_SAFETY", str(file_path), f"Found {constant}")
        
        # Check for progress method
        if 'progress(' not in class_content:
            self.add_issue("LOOP_SAFETY", str(file_path), node.lineno, 
                         "Missing progress() method in Orchestrator")
        else:
            self.add_pass("LOOP_SAFETY", str(file_path), "Found progress() method")
        
        # Check for oscillation detection
        if 'oscillation' not in class_content.lower():
            self.add_issue("LOOP_SAFETY", str(file_path), node.lineno, 
                         "Missing oscillation detection in Orchestrator")
        else:
            self.add_pass("LOOP_SAFETY", str(file_path), "Found oscillation detection")
    
    def _check_router_class(self, node: ast.ClassDef, content: str, file_path: Path):
        """Check router class for required patterns."""
        class_content = ast.get_source_segment(content, node)
        
        # Check for feature extractor patterns
        feature_patterns = ['token_count', 'json_schema_strictness', 'domain_flags', 
                           'novelty', 'historical_failure_rate']
        for pattern in feature_patterns:
            if pattern not in class_content:
                self.add_issue("ROUTER", str(file_path), node.lineno, 
                             f"Missing {pattern} in Router class")
            else:
                self.add_pass("ROUTER", str(file_path), f"Found {pattern}")
        
        # Check for metrics
        metric_patterns = ['router_decision_latency_ms', 'router_misroute_rate', 
                          'expected_vs_actual']
        for pattern in metric_patterns:
            if pattern not in class_content:
                self.add_issue("ROUTER", str(file_path), node.lineno, 
                             f"Missing {pattern} metric in Router")
            else:
                self.add_pass("ROUTER", str(file_path), f"Found {pattern} metric")
    
    def _check_tool_adapter_class(self, node: ast.ClassDef, content: str, file_path: Path):
        """Check tool adapter class for reliability patterns."""
        class_content = ast.get_source_segment(content, node)
        
        # Check for reliability patterns
        reliability_patterns = ['timeout', 'retry', 'circuit.*breaker', 'bulkhead', 
                               'idempotency', 'write.*ahead']
        for pattern in reliability_patterns:
            if not re.search(pattern, class_content, re.IGNORECASE):
                self.add_issue("TOOL_ADAPTER", str(file_path), node.lineno, 
                             f"Missing {pattern} in Tool Adapter")
            else:
                self.add_pass("TOOL_ADAPTER", str(file_path), f"Found {pattern}")
        
        # Check for compensate method
        if 'compensate(' not in class_content:
            self.add_issue("TOOL_ADAPTER", str(file_path), node.lineno, 
                         "Missing compensate() method in Tool Adapter")
        else:
            self.add_pass("TOOL_ADAPTER", str(file_path), "Found compensate() method")
    
    def _check_websocket_class(self, node: ast.ClassDef, content: str, file_path: Path):
        """Check websocket class for backpressure patterns."""
        class_content = ast.get_source_segment(content, node)
        
        # Check for backpressure patterns
        backpressure_patterns = ['ws_active_connections', 'ws_backpressure_drops', 
                                'ws_send_errors', 'backpressure.*policy']
        for pattern in backpressure_patterns:
            if not re.search(pattern, class_content, re.IGNORECASE):
                self.add_issue("WEBSOCKET", str(file_path), node.lineno, 
                             f"Missing {pattern} in WebSocket class")
            else:
                self.add_pass("WEBSOCKET", str(file_path), f"Found {pattern}")
    
    def _check_function_patterns(self, node: ast.FunctionDef, content: str, file_path: Path):
        """Check function for specific patterns."""
        func_content = ast.get_source_segment(content, node)
        
        # Check for Pydantic strict validation in API functions
        if 'api' in str(file_path).lower() or 'gateway' in str(file_path).lower():
            if 'strict=True' not in func_content and 'forbid_extra=True' not in func_content:
                if 'BaseModel' in func_content or 'Pydantic' in func_content:
                    self.add_issue("CONTRACTS", str(file_path), node.lineno, 
                                 f"Missing strict validation in {node.name}")
    
    def _analyze_sql_patterns(self, content: str, file_path: Path) -> Dict[str, List[str]]:
        """Analyze SQL content for RLS patterns."""
        patterns_found = {}
        
        # Check for RLS patterns
        rls_patterns = ['ROW LEVEL SECURITY', 'RLS', 'POLICY', 'tenant_id']
        for pattern in rls_patterns:
            if re.search(pattern, content, re.IGNORECASE):
                patterns_found.setdefault('RLS', []).append(pattern)
                self.add_pass("RLS", str(file_path), f"Found {pattern}")
        
        if 'RLS' not in patterns_found and 'migration' in str(file_path):
            self.add_issue("RLS", str(file_path), 0, "Missing RLS patterns in migration")
        
        return patterns_found
    
    def _analyze_config_patterns(self, content: str, file_path: Path) -> Dict[str, List[str]]:
        """Analyze config files for required patterns."""
        patterns_found = {}
        
        # Check for Prometheus metrics in config files
        if 'prometheus' in content.lower() or 'metrics' in content.lower():
            prom_patterns = ['agent_run_latency_ms', 'router_decision_latency_ms', 
                            'tool_error_rate', 'cost_usd_total']
            for pattern in prom_patterns:
                if pattern in content:
                    patterns_found.setdefault('PROMETHEUS', []).append(pattern)
                    self.add_pass("PROMETHEUS", str(file_path), f"Found {pattern}")
        
        return patterns_found
    
    def scan_directory(self, directory: Path) -> Dict[str, int]:
        """Scan directory for readiness patterns."""
        stats = {
            'files_scanned': 0,
            'issues_found': 0,
            'patterns_found': 0
        }
        
        # Define directories to scan
        scan_dirs = [
            'apps',
            'libs',
            'data-plane',
            'observability',
            'tests'
        ]
        
        for scan_dir in scan_dirs:
            dir_path = self.root_path / scan_dir
            if not dir_path.exists():
                continue
            
            for file_path in dir_path.rglob('*.py'):
                if self._should_scan_file(file_path):
                    stats['files_scanned'] += 1
                    patterns = self.scan_file(file_path)
                    stats['patterns_found'] += sum(len(v) for v in patterns.values())
        
        # Also scan specific important files
        important_files = [
            'Makefile',
            'pyproject.toml',
            'requirements.txt',
            'docker-compose.yml'
        ]
        
        for filename in important_files:
            file_path = self.root_path / filename
            if file_path.exists():
                stats['files_scanned'] += 1
                self.scan_file(file_path)
        
        stats['issues_found'] = len(self.issues)
        return stats
    
    def _should_scan_file(self, file_path: Path) -> bool:
        """Determine if file should be scanned."""
        # Skip test files for now (focus on production code)
        if 'test' in str(file_path).lower() and file_path.name.startswith('test_'):
            return False
        
        # Skip __pycache__ and other non-source files
        if '__pycache__' in str(file_path) or file_path.suffix in ['.pyc', '.pyo']:
            return False
        
        return True
    
    def generate_report(self) -> Dict:
        """Generate comprehensive audit report."""
        report = {
            'summary': {
                'total_issues': len(self.issues),
                'total_passes': len(self.passes),
                'status': 'PASS' if len(self.issues) == 0 else 'FAIL'
            },
            'issues_by_category': {},
            'issues': self.issues,
            'passes': self.passes
        }
        
        # Group issues by category
        for issue in self.issues:
            category = issue['category']
            if category not in report['issues_by_category']:
                report['issues_by_category'][category] = []
            report['issues_by_category'][category].append(issue)
        
        return report
    
    def print_summary(self):
        """Print audit summary."""
        print("\n" + "="*80)
        print("PLATFORM READINESS AUDIT SUMMARY")
        print("="*80)
        
        if not self.issues:
            print("✅ PASS - All readiness criteria met!")
        else:
            print(f"❌ FAIL - {len(self.issues)} issues found")
        
        print(f"📊 Total passes: {len(self.passes)}")
        print(f"📊 Total issues: {len(self.issues)}")
        
        if self.issues:
            print("\n🚨 ISSUES BY CATEGORY:")
            for category, issues in self.generate_report()['issues_by_category'].items():
                print(f"\n{category.upper()}: {len(issues)} issues")
                for issue in issues[:5]:  # Show first 5 issues
                    print(f"  • {issue['file']}:{issue['line']} - {issue['message']}")
                if len(issues) > 5:
                    print(f"  ... and {len(issues) - 5} more")
        
        print("\n" + "="*80)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description='Audit platform readiness')
    parser.add_argument('--verbose', '-v', action='store_true', 
                       help='Verbose output')
    parser.add_argument('--fix', action='store_true', 
                       help='Attempt to fix issues (not implemented)')
    parser.add_argument('--root', default='.', 
                       help='Root directory to scan (default: current)')
    
    args = parser.parse_args()
    
    root_path = Path(args.root).resolve()
    if not root_path.exists():
        print(f"Error: Root path {root_path} does not exist")
        sys.exit(1)
    
    auditor = ReadinessAuditor(root_path, args.verbose, args.fix)
    
    print("🔍 Scanning codebase for production readiness...")
    stats = auditor.scan_directory(root_path)
    
    print(f"📁 Files scanned: {stats['files_scanned']}")
    print(f"🔍 Patterns found: {stats['patterns_found']}")
    
    auditor.print_summary()
    
    # Exit with error code if issues found
    if auditor.issues:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == '__main__':
    main()
