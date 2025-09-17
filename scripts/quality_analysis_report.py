#!/usr/bin/env python3
"""
Quality Analysis Report Generator

Generates a comprehensive report combining duplication, dead code, and complexity analysis.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import structlog

logger = structlog.get_logger(__name__)


class QualityAnalysisReporter:
    """Generates comprehensive quality analysis reports."""
    
    def __init__(self, reports_dir: str = "reports"):
        self.reports_dir = Path(reports_dir)
        self.reports_dir.mkdir(exist_ok=True)
        
        # Ensure subdirectories exist
        (self.reports_dir / "duplication").mkdir(exist_ok=True)
        (self.reports_dir / "dead-code").mkdir(exist_ok=True)
        (self.reports_dir / "complexity").mkdir(exist_ok=True)
        
    def run_duplication_analysis(self) -> Dict[str, Any]:
        """Run duplication analysis using jscpd."""
        
        logger.info("Running duplication analysis...")
        
        try:
            # Run jscpd
            result = subprocess.run(
                ["jscpd", "--config", ".jscpd.json"],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            # Parse jscpd output
            duplication_data = {
                "timestamp": datetime.now().isoformat(),
                "tool": "jscpd",
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "summary": self._parse_jscpd_output(result.stdout)
            }
            
            # Save detailed report
            with open(self.reports_dir / "duplication" / "duplication_report.json", "w") as f:
                json.dump(duplication_data, f, indent=2)
            
            logger.info("Duplication analysis completed", 
                       exit_code=result.returncode,
                       duplication_percentage=duplication_data["summary"].get("percentage", 0))
            
            return duplication_data
            
        except subprocess.TimeoutExpired:
            logger.error("Duplication analysis timed out")
            return {"error": "Analysis timed out", "timestamp": datetime.now().isoformat()}
        except Exception as e:
            logger.error("Duplication analysis failed", error=str(e))
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
    
    def run_dead_code_analysis(self) -> Dict[str, Any]:
        """Run dead code analysis using vulture and ts-prune."""
        
        logger.info("Running dead code analysis...")
        
        dead_code_data = {
            "timestamp": datetime.now().isoformat(),
            "python": {},
            "typescript": {}
        }
        
        # Python dead code analysis
        try:
            result = subprocess.run(
                ["vulture", "apps/", "libs/", "control-plane/", "data-plane/", "services/",
                 "--min-confidence", "80", "--sort-by-size"],
                capture_output=True,
                text=True,
                timeout=180
            )
            
            dead_code_data["python"] = {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "summary": self._parse_vulture_output(result.stdout)
            }
            
            # Save Python dead code report
            with open(self.reports_dir / "dead-code" / "python-dead-code.txt", "w") as f:
                f.write(result.stdout)
            
        except Exception as e:
            dead_code_data["python"] = {"error": str(e)}
        
        # TypeScript dead code analysis
        try:
            # Change to web directory and run ts-prune
            web_dir = Path("web")
            if web_dir.exists():
                result = subprocess.run(
                    ["npm", "run", "dead-code"],
                    cwd=web_dir,
                    capture_output=True,
                    text=True,
                    timeout=120
                )
                
                dead_code_data["typescript"] = {
                    "exit_code": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "summary": self._parse_ts_prune_output(result.stdout)
                }
            else:
                dead_code_data["typescript"] = {"error": "Web directory not found"}
                
        except Exception as e:
            dead_code_data["typescript"] = {"error": str(e)}
        
        # Save dead code report
        with open(self.reports_dir / "dead-code" / "dead_code_report.json", "w") as f:
            json.dump(dead_code_data, f, indent=2)
        
        logger.info("Dead code analysis completed")
        return dead_code_data
    
    def run_complexity_analysis(self) -> Dict[str, Any]:
        """Run complexity analysis using radon."""
        
        logger.info("Running complexity analysis...")
        
        complexity_data = {
            "timestamp": datetime.now().isoformat(),
            "tool": "radon"
        }
        
        try:
            # Run radon complexity analysis
            result = subprocess.run(
                ["radon", "cc", "apps/", "libs/", "control-plane/", "data-plane/", "services/",
                 "-nc", "-j"],
                capture_output=True,
                text=True,
                timeout=180
            )
            
            complexity_data.update({
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "summary": self._parse_radon_output(result.stdout)
            })
            
            # Save complexity report
            with open(self.reports_dir / "complexity" / "complexity.json", "w") as f:
                json.dump(complexity_data, f, indent=2)
            
            # Also save human-readable version
            with open(self.reports_dir / "complexity" / "complexity.txt", "w") as f:
                f.write(result.stdout)
            
            logger.info("Complexity analysis completed", 
                       exit_code=result.returncode,
                       high_complexity_functions=complexity_data["summary"].get("high_complexity", 0))
            
            return complexity_data
            
        except Exception as e:
            logger.error("Complexity analysis failed", error=str(e))
            return {"error": str(e), "timestamp": datetime.now().isoformat()}
    
    def _parse_jscpd_output(self, output: str) -> Dict[str, Any]:
        """Parse jscpd output to extract summary information."""
        
        summary = {
            "duplication_percentage": 0.0,
            "duplicated_lines": 0,
            "total_lines": 0,
            "duplicated_tokens": 0,
            "total_tokens": 0,
            "duplicated_blocks": 0
        }
        
        try:
            lines = output.split('\n')
            for line in lines:
                if 'Found' in line and 'duplicated' in line:
                    # Parse lines like "Found 5 duplicated lines in 2 files (0.1%)"
                    parts = line.split()
                    for i, part in enumerate(parts):
                        if part == 'duplicated' and i > 0:
                            summary["duplicated_lines"] = int(parts[i-1])
                        elif part == 'lines' and i > 2:
                            summary["total_lines"] = int(parts[i-2])
                        elif '(' in part and '%' in part:
                            percentage_str = part.strip('()%')
                            summary["duplication_percentage"] = float(percentage_str)
                            
        except Exception as e:
            logger.warning("Failed to parse jscpd output", error=str(e))
        
        return summary
    
    def _parse_vulture_output(self, output: str) -> Dict[str, Any]:
        """Parse vulture output to extract summary information."""
        
        summary = {
            "dead_code_items": 0,
            "confidence_levels": {"high": 0, "medium": 0, "low": 0},
            "files_analyzed": 0
        }
        
        try:
            lines = output.split('\n')
            summary["dead_code_items"] = len([line for line in lines if ':' in line and 'unused' in line.lower()])
            
            # Count confidence levels
            for line in lines:
                if 'high confidence' in line.lower():
                    summary["confidence_levels"]["high"] += 1
                elif 'medium confidence' in line.lower():
                    summary["confidence_levels"]["medium"] += 1
                elif 'low confidence' in line.lower():
                    summary["confidence_levels"]["low"] += 1
            
            # Count unique files
            files = set()
            for line in lines:
                if ':' in line:
                    file_path = line.split(':')[0]
                    if file_path.strip():
                        files.add(file_path)
            summary["files_analyzed"] = len(files)
            
        except Exception as e:
            logger.warning("Failed to parse vulture output", error=str(e))
        
        return summary
    
    def _parse_ts_prune_output(self, output: str) -> Dict[str, Any]:
        """Parse ts-prune output to extract summary information."""
        
        summary = {
            "unused_exports": 0,
            "files_analyzed": 0
        }
        
        try:
            lines = output.split('\n')
            summary["unused_exports"] = len([line for line in lines if line.strip() and not line.startswith('npm')])
            
            # Count unique files
            files = set()
            for line in lines:
                if ':' in line:
                    file_path = line.split(':')[0]
                    if file_path.strip():
                        files.add(file_path)
            summary["files_analyzed"] = len(files)
            
        except Exception as e:
            logger.warning("Failed to parse ts-prune output", error=str(e))
        
        return summary
    
    def _parse_radon_output(self, output: str) -> Dict[str, Any]:
        """Parse radon output to extract summary information."""
        
        summary = {
            "high_complexity": 0,
            "medium_complexity": 0,
            "low_complexity": 0,
            "total_functions": 0,
            "average_complexity": 0.0,
            "complexity_distribution": {}
        }
        
        try:
            # Try to parse as JSON first
            if output.strip().startswith('{'):
                data = json.loads(output)
                if isinstance(data, dict):
                    summary.update(data)
                    return summary
        except json.JSONDecodeError:
            pass
        
        # Parse text output
        try:
            lines = output.split('\n')
            for line in lines:
                if ' - ' in line and '(' in line and ')' in line:
                    # Parse lines like "apps/api-gateway/main.py:45:1 - C - 8 (complexity)"
                    parts = line.split(' - ')
                    if len(parts) >= 3:
                        complexity_part = parts[2]
                        if '(' in complexity_part:
                            complexity_value = complexity_part.split('(')[0].strip()
                            try:
                                complexity = int(complexity_value)
                                summary["total_functions"] += 1
                                if complexity >= 10:
                                    summary["high_complexity"] += 1
                                elif complexity >= 6:
                                    summary["medium_complexity"] += 1
                                else:
                                    summary["low_complexity"] += 1
                            except ValueError:
                                pass
                                
        except Exception as e:
            logger.warning("Failed to parse radon output", error=str(e))
        
        return summary
    
    def generate_summary_report(self, duplication_data: Dict, dead_code_data: Dict, complexity_data: Dict) -> Dict[str, Any]:
        """Generate a comprehensive summary report."""
        
        summary = {
            "timestamp": datetime.now().isoformat(),
            "analysis_type": "comprehensive_quality_analysis",
            "duplication": {
                "percentage": duplication_data.get("summary", {}).get("duplication_percentage", 0),
                "status": "pass" if duplication_data.get("summary", {}).get("duplication_percentage", 0) < 5 else "fail",
                "threshold": 5.0
            },
            "dead_code": {
                "python_items": dead_code_data.get("python", {}).get("summary", {}).get("dead_code_items", 0),
                "typescript_items": dead_code_data.get("typescript", {}).get("summary", {}).get("unused_exports", 0),
                "total_items": 0,
                "status": "pass"
            },
            "complexity": {
                "high_complexity_functions": complexity_data.get("summary", {}).get("high_complexity", 0),
                "medium_complexity_functions": complexity_data.get("summary", {}).get("medium_complexity", 0),
                "total_functions": complexity_data.get("summary", {}).get("total_functions", 0),
                "status": "pass" if complexity_data.get("summary", {}).get("high_complexity", 0) < 10 else "warn"
            },
            "overall_status": "pass",
            "recommendations": []
        }
        
        # Calculate total dead code items
        summary["dead_code"]["total_items"] = (
            summary["dead_code"]["python_items"] + 
            summary["dead_code"]["typescript_items"]
        )
        
        # Determine overall status
        if (summary["duplication"]["status"] == "fail" or 
            summary["dead_code"]["total_items"] > 20 or
            summary["complexity"]["high_complexity_functions"] > 15):
            summary["overall_status"] = "fail"
        elif (summary["duplication"]["percentage"] > 3 or 
              summary["dead_code"]["total_items"] > 10 or
              summary["complexity"]["high_complexity_functions"] > 10):
            summary["overall_status"] = "warn"
        
        # Generate recommendations
        if summary["duplication"]["percentage"] > 3:
            summary["recommendations"].append(
                f"High code duplication detected ({summary['duplication']['percentage']:.1f}%). "
                "Consider refactoring common patterns into shared utilities."
            )
        
        if summary["dead_code"]["total_items"] > 10:
            summary["recommendations"].append(
                f"Dead code detected ({summary['dead_code']['total_items']} items). "
                "Remove unused functions, variables, and imports."
            )
        
        if summary["complexity"]["high_complexity_functions"] > 10:
            summary["recommendations"].append(
                f"High complexity functions detected ({summary['complexity']['high_complexity_functions']}). "
                "Consider breaking down complex functions into smaller, more manageable pieces."
            )
        
        if summary["overall_status"] == "pass":
            summary["recommendations"].append("Code quality is within acceptable limits.")
        
        return summary
    
    def run_comprehensive_analysis(self) -> Dict[str, Any]:
        """Run comprehensive quality analysis and generate reports."""
        
        logger.info("Starting comprehensive quality analysis...")
        
        # Run all analyses
        duplication_data = self.run_duplication_analysis()
        dead_code_data = self.run_dead_code_analysis()
        complexity_data = self.run_complexity_analysis()
        
        # Generate summary report
        summary = self.generate_summary_report(duplication_data, dead_code_data, complexity_data)
        
        # Save summary report
        with open(self.reports_dir / "quality_analysis_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        
        # Generate HTML report
        self._generate_html_report(summary)
        
        logger.info("Comprehensive quality analysis completed", 
                   overall_status=summary["overall_status"])
        
        return summary
    
    def _generate_html_report(self, summary: Dict[str, Any]):
        """Generate an HTML report for the quality analysis."""
        
        html_content = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Quality Analysis Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
        .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .header {{ text-align: center; margin-bottom: 30px; }}
        .status {{ padding: 10px 20px; border-radius: 5px; font-weight: bold; text-transform: uppercase; }}
        .status.pass {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
        .status.warn {{ background-color: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }}
        .status.fail {{ background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
        .section {{ margin: 20px 0; padding: 20px; border: 1px solid #ddd; border-radius: 5px; }}
        .metric {{ display: inline-block; margin: 10px 20px 10px 0; }}
        .metric-label {{ font-weight: bold; color: #666; }}
        .metric-value {{ font-size: 1.2em; color: #333; }}
        .recommendations {{ background-color: #e7f3ff; padding: 15px; border-radius: 5px; border-left: 4px solid #007bff; }}
        .recommendations ul {{ margin: 10px 0; }}
        .recommendations li {{ margin: 5px 0; }}
        .timestamp {{ color: #666; font-size: 0.9em; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Quality Analysis Report</h1>
            <p class="timestamp">Generated on {summary['timestamp']}</p>
        </div>
        
        <div class="section">
            <h2>📊 Overall Status</h2>
            <div class="status {summary['overall_status']}">
                {summary['overall_status'].upper()}
            </div>
        </div>
        
        <div class="section">
            <h2>🔄 Code Duplication</h2>
            <div class="metric">
                <div class="metric-label">Duplication Percentage</div>
                <div class="metric-value">{summary['duplication']['percentage']:.1f}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">Threshold</div>
                <div class="metric-value">{summary['duplication']['threshold']}%</div>
            </div>
            <div class="metric">
                <div class="metric-label">Status</div>
                <div class="metric-value">{summary['duplication']['status'].upper()}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>💀 Dead Code</h2>
            <div class="metric">
                <div class="metric-label">Python Items</div>
                <div class="metric-value">{summary['dead_code']['python_items']}</div>
            </div>
            <div class="metric">
                <div class="metric-label">TypeScript Items</div>
                <div class="metric-value">{summary['dead_code']['typescript_items']}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Total Items</div>
                <div class="metric-value">{summary['dead_code']['total_items']}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Status</div>
                <div class="metric-value">{summary['dead_code']['status'].upper()}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>📈 Code Complexity</h2>
            <div class="metric">
                <div class="metric-label">High Complexity</div>
                <div class="metric-value">{summary['complexity']['high_complexity_functions']}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Medium Complexity</div>
                <div class="metric-value">{summary['complexity']['medium_complexity_functions']}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Total Functions</div>
                <div class="metric-value">{summary['complexity']['total_functions']}</div>
            </div>
            <div class="metric">
                <div class="metric-label">Status</div>
                <div class="metric-value">{summary['complexity']['status'].upper()}</div>
            </div>
        </div>
        
        <div class="section">
            <h2>💡 Recommendations</h2>
            <div class="recommendations">
                <ul>
                    {''.join([f'<li>{rec}</li>' for rec in summary['recommendations']])}
                </ul>
            </div>
        </div>
        
        <div class="section">
            <h2>📁 Report Files</h2>
            <p>Detailed reports are available in the following locations:</p>
            <ul>
                <li><strong>Duplication:</strong> reports/duplication/duplication_report.json</li>
                <li><strong>Dead Code:</strong> reports/dead-code/dead_code_report.json</li>
                <li><strong>Complexity:</strong> reports/complexity/complexity.json</li>
                <li><strong>Summary:</strong> reports/quality_analysis_summary.json</li>
            </ul>
        </div>
    </div>
</body>
</html>
        """
        
        with open(self.reports_dir / "quality_analysis_report.html", "w") as f:
            f.write(html_content)


def main():
    """Main function to run quality analysis."""
    
    parser = argparse.ArgumentParser(description="Quality Analysis Report Generator")
    parser.add_argument("--reports-dir", default="reports", help="Reports directory")
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    parser.add_argument("--html", action="store_true", help="Generate HTML report")
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = "DEBUG" if args.verbose else "INFO"
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
    
    try:
        reporter = QualityAnalysisReporter(args.reports_dir)
        summary = reporter.run_comprehensive_analysis()
        
        # Print summary
        print(f"\n{'='*60}")
        print(f"Quality Analysis Report")
        print(f"{'='*60}")
        print(f"Overall Status: {summary['overall_status'].upper()}")
        print(f"Duplication: {summary['duplication']['percentage']:.1f}% ({summary['duplication']['status']})")
        print(f"Dead Code: {summary['dead_code']['total_items']} items ({summary['dead_code']['status']})")
        print(f"High Complexity: {summary['complexity']['high_complexity_functions']} functions ({summary['complexity']['status']})")
        
        if summary['recommendations']:
            print(f"\nRecommendations:")
            for rec in summary['recommendations']:
                print(f"  - {rec}")
        
        print(f"\nDetailed reports saved to: {args.reports_dir}/")
        print(f"{'='*60}")
        
        # Exit with appropriate code
        if summary['overall_status'] == 'fail':
            sys.exit(2)
        elif summary['overall_status'] == 'warn':
            sys.exit(1)
        else:
            sys.exit(0)
            
    except Exception as e:
        logger.error("Quality analysis failed", error=str(e))
        print(f"Quality analysis failed: {e}")
        sys.exit(3)


if __name__ == "__main__":
    main()
