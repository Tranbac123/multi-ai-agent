#!/usr/bin/env bash
set -euo pipefail

echo "🤖 Running complete test suite..."

# Create test results directory
mkdir -p test-results
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEST_LOG="test-results/test_$TIMESTAMP.log"
SUMMARY_FILE="test-results/summary_$TIMESTAMP.txt"

# Initialize summary file
echo "AI Chatbot Test Suite Results - $(date)" > "$SUMMARY_FILE"
echo "===========================================" >> "$SUMMARY_FILE"
echo "" >> "$SUMMARY_FILE"

# Function to run test and log results
run_test() {
  local test_name=$1
  local test_script=$2
  
  echo "Running $test_name..."
  echo "Test: $test_name" >> "$TEST_LOG"
  echo "Started: $(date)" >> "$TEST_LOG"
  echo "----------------------------------------" >> "$TEST_LOG"
  
  if bash "$test_script" >> "$TEST_LOG" 2>&1; then
    echo "✅ $test_name PASSED"
    echo "PASS: $test_name" >> "$SUMMARY_FILE"
    return 0
  else
    echo "❌ $test_name FAILED"
    echo "FAIL: $test_name" >> "$SUMMARY_FILE"
    return 1
  fi
}

# Counter for passed/failed tests
PASSED=0
FAILED=0

# Run all tests
echo "Starting test suite at $(date)"
echo "Test log: $TEST_LOG"
echo ""

# Basic tests
if run_test "Health Checks" "scripts/test-health.sh"; then
  ((PASSED++))
else
  ((FAILED++))
fi

if run_test "API Tests" "scripts/test-api.sh"; then
  ((PASSED++))
else
  ((FAILED++))
fi

if run_test "Frontend Tests" "scripts/test-frontend.sh"; then
  ((PASSED++))
else
  ((FAILED++))
fi

if run_test "End-to-End Flow" "scripts/test-e2e.sh"; then
  ((PASSED++))
else
  ((FAILED++))
fi

# Performance tests
if run_test "Performance Tests" "scripts/test-performance.sh"; then
  ((PASSED++))
else
  ((FAILED++))
fi

# Database tests
if run_test "Database Tests" "scripts/test-database.sh"; then
  ((PASSED++))
else
  ((FAILED++))
fi

# Security tests
if run_test "Security Tests" "scripts/test-security.sh"; then
  ((PASSED++))
else
  ((FAILED++))
fi

# Load tests
if run_test "Load Tests" "scripts/test-load.sh"; then
  ((PASSED++))
else
  ((FAILED++))
fi

# Add summary to log file
echo "" >> "$TEST_LOG"
echo "===========================================" >> "$TEST_LOG"
echo "Test Suite Summary" >> "$TEST_LOG"
echo "===========================================" >> "$TEST_LOG"
echo "Total tests: $((PASSED + FAILED))" >> "$TEST_LOG"
echo "Passed: $PASSED" >> "$TEST_LOG"
echo "Failed: $FAILED" >> "$TEST_LOG"
echo "Success rate: $(( (PASSED * 100) / (PASSED + FAILED) ))%" >> "$TEST_LOG"
echo "Completed: $(date)" >> "$TEST_LOG"

# Generate final summary
echo ""
echo "📊 Test Suite Summary"
echo "===================="
echo "Total tests: $((PASSED + FAILED))"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Success rate: $(( (PASSED * 100) / (PASSED + FAILED) ))%"
echo ""

# Show detailed results
echo "📋 Detailed Results:"
echo "==================="
cat "$SUMMARY_FILE"

# Show service status
echo ""
echo "📊 Current Service Status:"
echo "=========================="
docker-compose -f docker-compose.local.yml ps 2>/dev/null || echo "Docker Compose not available"

# Show system resources
echo ""
echo "💻 System Resources:"
echo "==================="
if command -v docker &> /dev/null; then
  echo "Docker containers:"
  docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || echo "Docker stats not available"
fi

# Show disk usage
echo ""
echo "💾 Disk Usage:"
echo "============="
df -h | head -1
df -h | grep -E "(/$|/home|/Users)" || echo "Disk usage info not available"

# Generate HTML report
echo ""
echo "📄 Generating HTML report..."
cat > "test-results/report_$TIMESTAMP.html" << EOF
<!DOCTYPE html>
<html>
<head>
    <title>AI Chatbot Test Report - $TIMESTAMP</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }
        .header { background-color: #f8f9fa; padding: 20px; border-radius: 5px; margin-bottom: 20px; }
        .pass { color: #28a745; font-weight: bold; }
        .fail { color: #dc3545; font-weight: bold; }
        .summary { background-color: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; }
        .logs { background-color: #f8f9fa; padding: 15px; border-radius: 5px; font-family: monospace; white-space: pre-wrap; overflow-x: auto; }
        .status { background-color: #fff3cd; padding: 15px; border-radius: 5px; margin: 20px 0; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
        .success-rate { font-size: 1.2em; font-weight: bold; }
    </style>
</head>
<body>
    <div class="header">
        <h1>🤖 AI Chatbot Test Report</h1>
        <p><strong>Generated:</strong> $(date)</p>
        <p><strong>Test Suite:</strong> Complete Local Testing</p>
    </div>
    
    <div class="summary">
        <h2>📊 Test Summary</h2>
        <p><strong>Total Tests:</strong> $((PASSED + FAILED))</p>
        <p><strong>Passed:</strong> <span class="pass">$PASSED</span></p>
        <p><strong>Failed:</strong> <span class="fail">$FAILED</span></p>
        <p><strong>Success Rate:</strong> <span class="success-rate">$(( (PASSED * 100) / (PASSED + FAILED) ))%</span></p>
    </div>
    
    <h2>📋 Test Results</h2>
    <div class="logs">$(cat "$SUMMARY_FILE")</div>
    
    <h2>📊 Service Status</h2>
    <div class="status">
        <pre>$(docker-compose -f docker-compose.local.yml ps 2>/dev/null || echo "Docker Compose not available")</pre>
    </div>
    
    <h2>💻 System Resources</h2>
    <div class="status">
        <pre>$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" 2>/dev/null || echo "Docker stats not available")</pre>
    </div>
    
    <h2>📝 Detailed Logs</h2>
    <div class="logs">$(tail -100 "$TEST_LOG")</div>
    
    <div style="margin-top: 40px; padding: 20px; background-color: #f8f9fa; border-radius: 5px;">
        <h3>🔧 Troubleshooting Tips</h3>
        <ul>
            <li>Check service logs: <code>docker-compose -f docker-compose.local.yml logs -f</code></li>
            <li>Restart services: <code>docker-compose -f docker-compose.local.yml restart</code></li>
            <li>Check health: <code>./scripts/test-health.sh</code></li>
            <li>View full logs: <code>cat $TEST_LOG</code></li>
        </ul>
    </div>
</body>
</html>
EOF

echo "📄 HTML report generated: test-results/report_$TIMESTAMP.html"

# Final status
echo ""
if [ $FAILED -eq 0 ]; then
  echo "🎉 All tests passed! Your AI chatbot is working perfectly!"
  exit 0
else
  echo "⚠️  Some tests failed. Please check the logs and fix the issues."
  echo "📄 View detailed logs: $TEST_LOG"
  echo "📄 View HTML report: test-results/report_$TIMESTAMP.html"
  exit 1
fi
