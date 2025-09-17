"""
Tests for quality analysis tools and detectors.

This module tests the quality analysis tools including duplication detection,
dead code detection, and complexity analysis.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest
import structlog

from scripts.quality_analysis_report import QualityAnalysisReporter


class TestQualityAnalysisReporter:
    """Test cases for QualityAnalysisReporter."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.reporter = QualityAnalysisReporter(self.temp_dir)
    
    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_parse_jscpd_output(self):
        """Test parsing jscpd output."""
        
        # Sample jscpd output
        jscpd_output = """
Found 5 duplicated lines in 2 files (0.1%)
Found 15 duplicated tokens in 3 files (2.5%)
Total: 1000 lines, 500 tokens
        """
        
        summary = self.reporter._parse_jscpd_output(jscpd_output)
        
        assert summary["duplicated_lines"] == 5
        assert summary["total_lines"] == 1000
        assert summary["duplication_percentage"] == 0.1
        assert summary["duplicated_tokens"] == 15
        assert summary["total_tokens"] == 500
    
    def test_parse_vulture_output(self):
        """Test parsing vulture output."""
        
        # Sample vulture output
        vulture_output = """
apps/api-gateway/main.py:45:1 unused import 'os' (90% confidence)
apps/orchestrator/core.py:120:5 unused variable 'temp_var' (85% confidence)
libs/utils/helper.py:30:1 unused function 'helper_func' (95% confidence)
        """
        
        summary = self.reporter._parse_vulture_output(vulture_output)
        
        assert summary["dead_code_items"] == 3
        assert summary["files_analyzed"] == 3
        assert summary["confidence_levels"]["high"] == 2  # 90% and 95%
        assert summary["confidence_levels"]["medium"] == 1  # 85%
        assert summary["confidence_levels"]["low"] == 0
    
    def test_parse_ts_prune_output(self):
        """Test parsing ts-prune output."""
        
        # Sample ts-prune output
        ts_prune_output = """
web/src/components/Button.tsx:15:5 unused export 'ButtonProps'
web/src/utils/helpers.ts:8:1 unused export 'formatDate'
web/src/hooks/useAuth.ts:25:3 unused export 'useAuthState'
        """
        
        summary = self.reporter._parse_ts_prune_output(ts_prune_output)
        
        assert summary["unused_exports"] == 3
        assert summary["files_analyzed"] == 3
    
    def test_parse_radon_output_json(self):
        """Test parsing radon JSON output."""
        
        # Sample radon JSON output
        radon_json = {
            "apps/api-gateway/main.py": [
                {"name": "health_check", "complexity": 2, "rank": "A"},
                {"name": "complex_function", "complexity": 12, "rank": "F"}
            ],
            "apps/orchestrator/core.py": [
                {"name": "simple_function", "complexity": 1, "rank": "A"}
            ]
        }
        
        summary = self.reporter._parse_radon_output(json.dumps(radon_json))
        
        assert summary["high_complexity"] == 1  # complexity >= 10
        assert summary["medium_complexity"] == 0  # complexity 6-9
        assert summary["low_complexity"] == 2  # complexity < 6
        assert summary["total_functions"] == 3
    
    def test_parse_radon_output_text(self):
        """Test parsing radon text output."""
        
        # Sample radon text output
        radon_text = """
apps/api-gateway/main.py:45:1 - health_check - A (2)
apps/api-gateway/main.py:120:1 - complex_function - F (12)
apps/orchestrator/core.py:30:1 - simple_function - A (1)
        """
        
        summary = self.reporter._parse_radon_output(radon_text)
        
        assert summary["high_complexity"] == 1  # complexity >= 10
        assert summary["medium_complexity"] == 0  # complexity 6-9
        assert summary["low_complexity"] == 2  # complexity < 6
        assert summary["total_functions"] == 3
    
    def test_generate_summary_report_pass(self):
        """Test generating summary report with passing metrics."""
        
        duplication_data = {
            "summary": {"duplication_percentage": 2.5}
        }
        
        dead_code_data = {
            "python": {"summary": {"dead_code_items": 5}},
            "typescript": {"summary": {"unused_exports": 3}}
        }
        
        complexity_data = {
            "summary": {
                "high_complexity": 3,
                "medium_complexity": 5,
                "total_functions": 50
            }
        }
        
        summary = self.reporter.generate_summary_report(
            duplication_data, dead_code_data, complexity_data
        )
        
        assert summary["overall_status"] == "pass"
        assert summary["duplication"]["status"] == "pass"
        assert summary["dead_code"]["status"] == "pass"
        assert summary["complexity"]["status"] == "pass"
        assert summary["dead_code"]["total_items"] == 8
        assert len(summary["recommendations"]) >= 1
    
    def test_generate_summary_report_fail(self):
        """Test generating summary report with failing metrics."""
        
        duplication_data = {
            "summary": {"duplication_percentage": 8.5}
        }
        
        dead_code_data = {
            "python": {"summary": {"dead_code_items": 25}},
            "typescript": {"summary": {"unused_exports": 15}}
        }
        
        complexity_data = {
            "summary": {
                "high_complexity": 20,
                "medium_complexity": 10,
                "total_functions": 50
            }
        }
        
        summary = self.reporter.generate_summary_report(
            duplication_data, dead_code_data, complexity_data
        )
        
        assert summary["overall_status"] == "fail"
        assert summary["duplication"]["status"] == "fail"
        assert summary["dead_code"]["status"] == "pass"  # Still pass, but total > 20
        assert summary["complexity"]["status"] == "warn"  # High complexity > 15
        assert summary["dead_code"]["total_items"] == 40
        assert len(summary["recommendations"]) >= 3
    
    @patch('subprocess.run')
    def test_run_duplication_analysis_success(self, mock_run):
        """Test successful duplication analysis."""
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Found 5 duplicated lines in 2 files (0.1%)"
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = self.reporter.run_duplication_analysis()
        
        assert result["exit_code"] == 0
        assert result["tool"] == "jscpd"
        assert "summary" in result
        assert result["summary"]["duplication_percentage"] == 0.1
    
    @patch('subprocess.run')
    def test_run_dead_code_analysis_success(self, mock_run):
        """Test successful dead code analysis."""
        
        # Mock vulture output
        vulture_result = MagicMock()
        vulture_result.returncode = 0
        vulture_result.stdout = "apps/test.py:1:1 unused import 'os' (90% confidence)"
        vulture_result.stderr = ""
        
        # Mock npm run dead-code output
        npm_result = MagicMock()
        npm_result.returncode = 0
        npm_result.stdout = "web/src/test.ts:5:1 unused export 'test'"
        npm_result.stderr = ""
        
        mock_run.side_effect = [vulture_result, npm_result]
        
        # Mock Path.exists for web directory
        with patch('pathlib.Path.exists', return_value=True):
            result = self.reporter.run_dead_code_analysis()
        
        assert "python" in result
        assert "typescript" in result
        assert result["python"]["exit_code"] == 0
        assert result["typescript"]["exit_code"] == 0
    
    @patch('subprocess.run')
    def test_run_complexity_analysis_success(self, mock_run):
        """Test successful complexity analysis."""
        
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps({
            "apps/test.py": [
                {"name": "test_func", "complexity": 5, "rank": "B"}
            ]
        })
        mock_result.stderr = ""
        mock_run.return_value = mock_result
        
        result = self.reporter.run_complexity_analysis()
        
        assert result["exit_code"] == 0
        assert result["tool"] == "radon"
        assert "summary" in result
    
    def test_generate_html_report(self):
        """Test HTML report generation."""
        
        summary = {
            "timestamp": "2024-01-01T00:00:00",
            "overall_status": "pass",
            "duplication": {"percentage": 2.5, "status": "pass"},
            "dead_code": {"total_items": 8, "status": "pass"},
            "complexity": {"high_complexity_functions": 3, "status": "pass"},
            "recommendations": ["Code quality is within acceptable limits."]
        }
        
        self.reporter._generate_html_report(summary)
        
        html_file = Path(self.temp_dir) / "quality_analysis_report.html"
        assert html_file.exists()
        
        html_content = html_file.read_text()
        assert "Quality Analysis Report" in html_content
        assert "pass" in html_content
        assert "2.5%" in html_content


class TestQualityAnalysisIntegration:
    """Integration tests for quality analysis tools."""
    
    def test_duplication_detection_config(self):
        """Test that jscpd configuration is valid."""
        
        config_file = Path(".jscpd.json")
        assert config_file.exists()
        
        with open(config_file) as f:
            config = json.load(f)
        
        assert config["threshold"] == 30
        assert "reporters" in config
        assert "html" in config["reporters"]
        assert "json" in config["reporters"]
        assert "output" in config
        assert config["output"] == "./reports/duplication"
    
    def test_ruff_config_duplication_rules(self):
        """Test that ruff configuration includes duplication detection rules."""
        
        config_file = Path(".ruff.toml")
        assert config_file.exists()
        
        with open(config_file) as f:
            config_content = f.read()
        
        # Check for specific rules that help detect duplication
        assert "F401" in config_content  # unused imports
        assert "F841" in config_content  # unused variables
        assert "ERA" in config_content   # eradicate (remove commented code)
        assert "SIM" in config_content   # flake8-simplify
        assert "PLR" in config_content   # pylint refactor
        assert "TRY" in config_content   # tryceratops
        assert "UP" in config_content    # pyupgrade
        assert "PERF" in config_content  # perflint
    
    def test_mypy_strict_config(self):
        """Test that mypy configuration is in strict mode."""
        
        config_file = Path("mypy.ini")
        assert config_file.exists()
        
        with open(config_file) as f:
            config_content = f.read()
        
        assert "strict = True" in config_content
        assert "disallow_untyped_defs = True" in config_content
        assert "warn_return_any = True" in config_content
    
    def test_eslint_config_duplication_rules(self):
        """Test that ESLint configuration includes duplication detection rules."""
        
        config_file = Path("web/.eslintrc.cjs")
        assert config_file.exists()
        
        with open(config_file) as f:
            config_content = f.read()
        
        # Check for rules that help detect duplication
        assert "no-duplicate-imports" in config_content
        assert "import/no-duplicates" in config_content
        assert "import/order" in config_content
        assert "no-unused-vars" in config_content
    
    def test_package_json_scripts(self):
        """Test that package.json includes dead code detection scripts."""
        
        package_file = Path("web/package.json")
        assert package_file.exists()
        
        with open(package_file) as f:
            package_data = json.load(f)
        
        scripts = package_data.get("scripts", {})
        assert "ts-unused-exports" in scripts
        assert "ts-unused-exports-report" in scripts
        assert "dead-code" in scripts
        
        # Check that ts-prune is in devDependencies
        dev_deps = package_data.get("devDependencies", {})
        assert "ts-prune" in dev_deps
    
    def test_requirements_dev_tools(self):
        """Test that requirements-dev.txt includes quality analysis tools."""
        
        requirements_file = Path("requirements-dev.txt")
        assert requirements_file.exists()
        
        with open(requirements_file) as f:
            requirements_content = f.read()
        
        # Check for quality analysis tools
        assert "jscpd" in requirements_content
        assert "vulture" in requirements_content
        assert "radon" in requirements_content
        assert "ruff" in requirements_content
        assert "mypy" in requirements_content
    
    def test_makefile_targets(self):
        """Test that Makefile includes quality analysis targets."""
        
        makefile = Path("Makefile")
        assert makefile.exists()
        
        with open(makefile) as f:
            makefile_content = f.read()
        
        # Check for quality analysis targets
        assert "dup:" in makefile_content
        assert "dead:" in makefile_content
        assert "comp:" in makefile_content
        assert "qa:" in makefile_content
        assert "qa-comprehensive:" in makefile_content
        assert "jscpd" in makefile_content
        assert "vulture" in makefile_content
        assert "radon" in makefile_content


@pytest.mark.asyncio
async def test_quality_analysis_workflow():
    """Test the complete quality analysis workflow."""
    
    with tempfile.TemporaryDirectory() as temp_dir:
        reporter = QualityAnalysisReporter(temp_dir)
        
        # Mock the subprocess calls to simulate successful analysis
        with patch('subprocess.run') as mock_run:
            # Mock jscpd
            jscpd_result = MagicMock()
            jscpd_result.returncode = 0
            jscpd_result.stdout = "Found 5 duplicated lines in 2 files (0.1%)"
            jscpd_result.stderr = ""
            
            # Mock vulture
            vulture_result = MagicMock()
            vulture_result.returncode = 0
            vulture_result.stdout = "apps/test.py:1:1 unused import 'os' (90% confidence)"
            vulture_result.stderr = ""
            
            # Mock npm
            npm_result = MagicMock()
            npm_result.returncode = 0
            npm_result.stdout = "web/src/test.ts:5:1 unused export 'test'"
            npm_result.stderr = ""
            
            # Mock radon
            radon_result = MagicMock()
            radon_result.returncode = 0
            radon_result.stdout = json.dumps({
                "apps/test.py": [
                    {"name": "test_func", "complexity": 5, "rank": "B"}
                ]
            })
            radon_result.stderr = ""
            
            mock_run.side_effect = [jscpd_result, vulture_result, npm_result, radon_result]
            
            # Mock Path.exists for web directory
            with patch('pathlib.Path.exists', return_value=True):
                summary = reporter.run_comprehensive_analysis()
            
            # Verify the workflow completed successfully
            assert "overall_status" in summary
            assert "duplication" in summary
            assert "dead_code" in summary
            assert "complexity" in summary
            assert "recommendations" in summary
            
            # Verify files were created
            reports_dir = Path(temp_dir)
            assert (reports_dir / "quality_analysis_summary.json").exists()
            assert (reports_dir / "quality_analysis_report.html").exists()
            assert (reports_dir / "duplication" / "duplication_report.json").exists()
            assert (reports_dir / "dead-code" / "dead_code_report.json").exists()
            assert (reports_dir / "complexity" / "complexity.json").exists()
