#!/usr/bin/env python3
"""
CI Integration script for flakiness detection and management.

This script:
- Runs tests with flakiness detection
- Identifies flaky tests
- Quarantines problematic tests
- Generates flakiness reports
- Integrates with CI pipeline
"""

import sys
import json
import subprocess
import argparse
from pathlib import Path
from typing import Dict, List, Any
import time


class FlakinessCI:
    """CI integration for flakiness management."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.reports_dir = self.project_root / "reports" / "flakiness"
        self.reports_dir.mkdir(parents=True, exist_ok=True)
        
    def run_tests_with_flakiness_detection(self, test_path: str = "tests/", 
                                         max_retries: int = 3,
                                         quarantine_flaky: bool = True) -> Dict[str, Any]:
        """Run tests with flakiness detection."""
        print(f"Running tests with flakiness detection in {test_path}")
        
        # Run tests multiple times to detect flakiness
        results = []
        for run in range(max_retries):
            print(f"Test run {run + 1}/{max_retries}")
            
            # Run pytest with flakiness detection
            cmd = [
                "python3", "-m", "pytest", 
                test_path,
                "-v",
                "--tb=short",
                "--flakiness-detection",
                f"--flakiness-report={self.reports_dir}/run_{run}.json"
            ]
            
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.project_root)
                results.append({
                    "run": run + 1,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "timestamp": time.time()
                })
            except Exception as e:
                results.append({
                    "run": run + 1,
                    "error": str(e),
                    "timestamp": time.time()
                })
        
        return {
            "test_runs": results,
            "total_runs": max_retries,
            "timestamp": time.time()
        }
    
    def analyze_flakiness(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze test results for flakiness."""
        print("Analyzing test results for flakiness...")
        
        # Simple flakiness analysis based on return codes
        flaky_tests = []
        stable_tests = []
        
        # For now, we'll do a simple analysis
        # In a real implementation, this would parse pytest output
        success_count = sum(1 for run in test_results["test_runs"] 
                          if run.get("returncode", 1) == 0)
        
        flakiness_rate = 1.0 - (success_count / test_results["total_runs"])
        
        return {
            "flakiness_rate": flakiness_rate,
            "success_rate": success_count / test_results["total_runs"],
            "flaky_tests": flaky_tests,
            "stable_tests": stable_tests,
            "analysis_timestamp": time.time()
        }
    
    def generate_flakiness_report(self, analysis: Dict[str, Any]) -> str:
        """Generate a comprehensive flakiness report."""
        report_file = self.reports_dir / f"flakiness_report_{int(time.time())}.json"
        
        report = {
            "summary": {
                "overall_flakiness_rate": analysis["flakiness_rate"],
                "success_rate": analysis["success_rate"],
                "total_tests_analyzed": len(analysis.get("flaky_tests", [])) + 
                                       len(analysis.get("stable_tests", [])),
                "quarantine_recommended": analysis["flakiness_rate"] > 0.1
            },
            "detailed_analysis": analysis,
            "recommendations": self._generate_recommendations(analysis),
            "generated_at": time.time(),
            "generated_by": "flakiness_ci_integration.py"
        }
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print(f"Flakiness report generated: {report_file}")
        return str(report_file)
    
    def _generate_recommendations(self, analysis: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on flakiness analysis."""
        recommendations = []
        
        flakiness_rate = analysis["flakiness_rate"]
        
        if flakiness_rate > 0.2:
            recommendations.append("CRITICAL: High flakiness rate detected. Immediate attention required.")
            recommendations.append("Consider quarantining all flaky tests.")
        elif flakiness_rate > 0.1:
            recommendations.append("WARNING: Moderate flakiness rate detected.")
            recommendations.append("Review and fix flaky tests before next release.")
        elif flakiness_rate > 0.05:
            recommendations.append("INFO: Low flakiness rate detected.")
            recommendations.append("Monitor flaky tests and fix when convenient.")
        else:
            recommendations.append("SUCCESS: Low flakiness rate. Tests are stable.")
        
        if analysis.get("flaky_tests"):
            recommendations.append(f"Focus on fixing {len(analysis['flaky_tests'])} identified flaky tests.")
        
        return recommendations
    
    def quarantine_flaky_tests(self, analysis: Dict[str, Any]) -> List[str]:
        """Quarantine identified flaky tests."""
        print("Quarantining flaky tests...")
        
        quarantined_tests = []
        flaky_tests = analysis.get("flaky_tests", [])
        
        for test in flaky_tests:
            # In a real implementation, this would modify test files or config
            # For now, we'll just log the quarantine action
            print(f"Quarantining test: {test}")
            quarantined_tests.append(test)
        
        # Save quarantine list
        quarantine_file = self.reports_dir / "quarantine_list.json"
        with open(quarantine_file, 'w') as f:
            json.dump({
                "quarantined_tests": quarantined_tests,
                "quarantine_timestamp": time.time(),
                "reason": "Automated flakiness detection"
            }, f, indent=2)
        
        return quarantined_tests
    
    def run_quarantine_job(self) -> Dict[str, Any]:
        """Run a separate job for quarantined tests."""
        print("Running quarantined tests job...")
        
        # This would run only quarantined tests in a separate CI job
        # For now, we'll simulate this
        return {
            "quarantine_job_status": "simulated",
            "tests_run": 0,
            "timestamp": time.time()
        }


def main():
    """Main entry point for CI integration."""
    parser = argparse.ArgumentParser(description="CI Integration for Flakiness Management")
    parser.add_argument("--test-path", default="tests/", 
                       help="Path to test directory")
    parser.add_argument("--max-retries", type=int, default=3,
                       help="Maximum number of test runs for flakiness detection")
    parser.add_argument("--quarantine", action="store_true",
                       help="Automatically quarantine flaky tests")
    parser.add_argument("--report-only", action="store_true",
                       help="Generate report without quarantining")
    
    args = parser.parse_args()
    
    # Initialize CI integration
    ci = FlakinessCI(".")
    
    try:
        # Run tests with flakiness detection
        test_results = ci.run_tests_with_flakiness_detection(
            args.test_path, 
            args.max_retries
        )
        
        # Analyze results
        analysis = ci.analyze_flakiness(test_results)
        
        # Generate report
        report_file = ci.generate_flakiness_report(analysis)
        
        # Quarantine flaky tests if requested
        if args.quarantine and not args.report_only:
            quarantined = ci.quarantine_flaky_tests(analysis)
            print(f"Quarantined {len(quarantined)} flaky tests")
        
        # Print summary
        print("\n" + "="*50)
        print("FLAKINESS ANALYSIS SUMMARY")
        print("="*50)
        print(f"Overall Flakiness Rate: {analysis['flakiness_rate']:.2%}")
        print(f"Success Rate: {analysis['success_rate']:.2%}")
        print(f"Report Generated: {report_file}")
        
        # Exit with appropriate code
        if analysis["flakiness_rate"] > 0.1:
            print("WARNING: High flakiness rate detected!")
            sys.exit(1)
        else:
            print("SUCCESS: Acceptable flakiness rate")
            sys.exit(0)
            
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
