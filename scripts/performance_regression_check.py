#!/usr/bin/env python3
"""Performance regression check script for CI/CD integration."""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

def run_locust_test(host: str, output_file: str, users: int = 50, run_time: str = "60s"):
    """Run Locust performance test."""
    cmd = [
        "locust", "-f", "tests/performance/locustfile.py",
        "--host", host, "--users", str(users), "--spawn-rate", "5",
        "--run-time", run_time, "--headless", "--only-summary", "--json", output_file
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        return result.returncode == 0
    except:
        return False

def extract_metrics(locust_results: dict) -> dict:
    """Extract performance metrics from Locust results."""
    metrics = {}
    if "requests" in locust_results:
        for req in locust_results["requests"]:
            name = req.get("name", "unknown")
            metrics[name] = {
                "avg_latency_ms": req.get("avg_response_time", 0),
                "max_latency_ms": req.get("max_response_time", 0),
                "error_rate_percent": (req.get("num_failures", 0) / max(req.get("num_requests", 1), 1)) * 100,
                "throughput_rps": req.get("current_rps", 0)
            }
    return metrics

def detect_regression(baseline: dict, current: dict, threshold: float = 10.0) -> bool:
    """Detect performance regression."""
    for endpoint in baseline:
        if endpoint not in current:
            continue
        
        baseline_metrics = baseline[endpoint]
        current_metrics = current[endpoint]
        
        # Check latency regression
        latency_increase = ((current_metrics.get("avg_latency_ms", 0) - baseline_metrics.get("avg_latency_ms", 0)) / 
                           max(baseline_metrics.get("avg_latency_ms", 1), 1)) * 100
        
        if latency_increase > threshold:
            return True
    
    return False

def main():
    """Main performance regression check."""
    parser = argparse.ArgumentParser(description="Performance regression check")
    parser.add_argument("--host", default="http://localhost:8000", help="API host URL")
    parser.add_argument("--baseline-file", default="performance_baselines.json", help="Baseline file")
    parser.add_argument("--threshold", type=float, default=10.0, help="Regression threshold %")
    parser.add_argument("--update-baseline", action="store_true", help="Update baseline")
    
    args = parser.parse_args()
    
    if args.update_baseline:
        print("Updating baseline...")
        if run_locust_test(args.host, "baseline_results.json"):
            with open("baseline_results.json", 'r') as f:
                results = json.load(f)
            metrics = extract_metrics(results)
            with open(args.baseline_file, 'w') as f:
                json.dump(metrics, f, indent=2)
            print(f"Baseline saved to {args.baseline_file}")
        else:
            print("Failed to collect baseline")
            sys.exit(1)
    else:
        print("Checking regression...")
        try:
            with open(args.baseline_file, 'r') as f:
                baseline = json.load(f)
        except FileNotFoundError:
            print("No baseline found. Run with --update-baseline first.")
            sys.exit(1)
        
        if run_locust_test(args.host, "regression_results.json"):
            with open("regression_results.json", 'r') as f:
                results = json.load(f)
            current = extract_metrics(results)
            
            if detect_regression(baseline, current, args.threshold):
                print("❌ Performance regression detected")
                sys.exit(1)
            else:
                print("✅ No regression detected")
                sys.exit(0)
        else:
            print("Failed to run regression test")
            sys.exit(1)

if __name__ == "__main__":
    main()