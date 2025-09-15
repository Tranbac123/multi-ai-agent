"""Run all tests for the AIaaS platform."""

import asyncio
import subprocess
import sys
from pathlib import Path
import structlog

# Configure logging
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
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


def run_command(command: str, description: str) -> bool:
    """Run a command and return success status."""
    logger.info(f"Running {description}")

    try:
        result = subprocess.run(
            command.split(), capture_output=True, text=True, check=True
        )

        logger.info(f"{description} completed successfully")
        if result.stdout:
            print(result.stdout)

        return True

    except subprocess.CalledProcessError as e:
        logger.error(f"{description} failed", error=str(e), stderr=e.stderr)
        if e.stdout:
            print("STDOUT:", e.stdout)
        if e.stderr:
            print("STDERR:", e.stderr)
        return False


def run_unit_tests() -> bool:
    """Run unit tests."""
    return run_command(
        "python -m pytest tests/unit/ -v --cov=libs --cov=apps --cov-report=html --cov-report=term",
        "Unit tests",
    )


def run_integration_tests() -> bool:
    """Run integration tests."""
    return run_command("python -m pytest tests/integration/ -v", "Integration tests")


def run_e2e_tests() -> bool:
    """Run end-to-end tests."""
    return run_command("python -m pytest tests/e2e/ -v", "End-to-end tests")


def run_contract_tests() -> bool:
    """Run contract tests."""
    return run_command("python -m pytest tests/contract/ -v", "Contract tests")


def run_evaluation_tests() -> bool:
    """Run evaluation tests."""
    return run_command("python eval/run_evaluation.py --type all", "Evaluation tests")


def run_linting() -> bool:
    """Run linting."""
    return run_command("ruff check .", "Ruff linting")


def run_formatting() -> bool:
    """Run formatting check."""
    return run_command("black --check .", "Black formatting check")


def run_type_checking() -> bool:
    """Run type checking."""
    return run_command("mypy libs/ apps/", "MyPy type checking")


def run_security_scan() -> bool:
    """Run security scan."""
    return run_command("safety check", "Safety security scan")


def run_all_quality_checks() -> bool:
    """Run all quality checks."""
    logger.info("Running all quality checks")

    checks = [
        ("Linting", run_linting),
        ("Formatting", run_formatting),
        ("Type Checking", run_type_checking),
        ("Security Scan", run_security_scan),
    ]

    all_passed = True
    for name, check_func in checks:
        if not check_func():
            all_passed = False
            logger.error(f"{name} failed")
        else:
            logger.info(f"{name} passed")

    return all_passed


def run_all_tests() -> bool:
    """Run all tests."""
    logger.info("Running all tests")

    test_suites = [
        ("Unit Tests", run_unit_tests),
        ("Integration Tests", run_integration_tests),
        ("End-to-End Tests", run_e2e_tests),
        ("Contract Tests", run_contract_tests),
        ("Evaluation Tests", run_evaluation_tests),
    ]

    all_passed = True
    for name, test_func in test_suites:
        if not test_func():
            all_passed = False
            logger.error(f"{name} failed")
        else:
            logger.info(f"{name} passed")

    return all_passed


def run_specific_test_type(test_type: str) -> bool:
    """Run specific test type."""
    test_functions = {
        "unit": run_unit_tests,
        "integration": run_integration_tests,
        "e2e": run_e2e_tests,
        "contract": run_contract_tests,
        "evaluation": run_evaluation_tests,
        "quality": run_all_quality_checks,
    }

    if test_type not in test_functions:
        logger.error(f"Unknown test type: {test_type}")
        return False

    return test_functions[test_type]()


def main():
    """Main function."""
    import argparse

    parser = argparse.ArgumentParser(description="Run AIaaS platform tests")
    parser.add_argument(
        "--type",
        choices=[
            "unit",
            "integration",
            "e2e",
            "contract",
            "evaluation",
            "quality",
            "all",
        ],
        default="all",
        help="Type of tests to run",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    if args.verbose:
        logger.info("Running tests in verbose mode")

    if args.type == "all":
        success = run_all_tests()
    else:
        success = run_specific_test_type(args.type)

    if success:
        logger.info("All tests passed successfully")
        sys.exit(0)
    else:
        logger.error("Some tests failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
