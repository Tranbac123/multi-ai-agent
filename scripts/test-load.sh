#!/usr/bin/env bash
set -euo pipefail

echo "⚡ Running load test..."

# Check if k6 is available
if ! command -v k6 &> /dev/null; then
  echo "⚠️  k6 not installed. Installing k6 for load testing..."
  
  if [[ "$OSTYPE" == "darwin"* ]]; then
    if command -v brew &> /dev/null; then
      brew install k6
    else
      echo "❌ Homebrew not found. Please install k6 manually: https://k6.io/docs/getting-started/installation/"
      exit 1
    fi
  else
    # Linux installation
    sudo gpg -k
    sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69
    echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list
    sudo apt-get update
    sudo apt-get install k6
  fi
fi

# Create k6 test script
echo "Creating k6 load test script..."
cat > /tmp/load-test.js << 'EOF'
import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '30s', target: 10 },
    { duration: '1m', target: 10 },
    { duration: '30s', target: 20 },
    { duration: '1m', target: 20 },
    { duration: '30s', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<5000'],
    http_req_failed: ['rate<0.1'],
  },
};

export default function() {
  let response = http.post('http://localhost:8000/ask', 
    JSON.stringify({query: 'Load test question'}),
    { headers: { 'Content-Type': 'application/json' } }
  );
  
  check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 5000ms': (r) => r.timings.duration < 5000,
    'response has answer': (r) => {
      try {
        let body = JSON.parse(r.body);
        return body.answer !== undefined;
      } catch (e) {
        return false;
      }
    },
  });
  
  sleep(1);
}
EOF

# Run load test
echo "Starting load test..."
echo "Test will run for 3 minutes with up to 20 concurrent users"
echo ""

k6 run /tmp/load-test.js

# Cleanup
rm /tmp/load-test.js

echo ""
echo "🎉 Load test completed!"
echo ""
echo "📊 Load Test Summary:"
echo "  - Duration: 3 minutes"
echo "  - Max concurrent users: 20"
echo "  - Target: /ask endpoint"
echo "  - Thresholds: 95% of requests < 5s, < 10% failure rate"
echo ""
echo "💡 Performance Tips:"
echo "  - Monitor CPU and memory usage during load tests"
echo "  - Check database connection pools"
echo "  - Consider horizontal scaling for high traffic"
echo "  - Implement caching for frequently asked questions"
