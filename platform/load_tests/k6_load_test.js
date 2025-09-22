/**
 * K6 Load Test Script for Multi-AI-Agent Platform
 * Tests capacity levers and degrade switches under peak traffic
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('error_rate');
const responseTime = new Trend('response_time');
const requestCount = new Counter('request_count');

// Test configuration
export const options = {
  stages: [
    // Ramp up
    { duration: '2m', target: 100 },   // Ramp up to 100 users over 2 minutes
    { duration: '5m', target: 100 },   // Stay at 100 users for 5 minutes
    { duration: '2m', target: 200 },   // Ramp up to 200 users over 2 minutes
    { duration: '5m', target: 200 },   // Stay at 200 users for 5 minutes
    { duration: '2m', target: 500 },   // Ramp up to 500 users over 2 minutes
    { duration: '5m', target: 500 },   // Stay at 500 users for 5 minutes
    { duration: '2m', target: 1000 },  // Ramp up to 1000 users over 2 minutes
    { duration: '10m', target: 1000 }, // Stay at 1000 users for 10 minutes
    // Ramp down
    { duration: '2m', target: 0 },     // Ramp down to 0 users over 2 minutes
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests should be below 2s
    http_req_failed: ['rate<0.1'],     // Error rate should be below 10%
    error_rate: ['rate<0.05'],         // Custom error rate should be below 5%
  },
};

// Base URL configuration
const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
const TENANT_ID = __ENV.TENANT_ID || 'load-test-tenant';

// Test scenarios
const scenarios = {
  // Normal API calls
  api_calls: {
    weight: 40,
    endpoint: '/api/v1/chat/completions',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': TENANT_ID,
    },
    payload: {
      model: 'gpt-3.5-turbo',
      messages: [
        { role: 'user', content: 'Hello, how are you?' }
      ],
      max_tokens: 100,
      temperature: 0.7
    }
  },
  
  // Tool calls
  tool_calls: {
    weight: 30,
    endpoint: '/api/v1/tools/execute',
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': TENANT_ID,
    },
    payload: {
      tool_name: 'search',
      parameters: {
        query: 'artificial intelligence',
        limit: 10
      }
    }
  },
  
  // WebSocket connections
  websocket: {
    weight: 20,
    endpoint: '/ws',
    method: 'GET',
    headers: {
      'X-Tenant-ID': TENANT_ID,
    }
  },
  
  // File uploads
  file_upload: {
    weight: 10,
    endpoint: '/api/v1/upload',
    method: 'POST',
    headers: {
      'X-Tenant-ID': TENANT_ID,
    },
    payload: {
      file_type: 'document',
      content: 'Sample document content for load testing'
    }
  }
};

// Helper function to select scenario based on weight
function selectScenario() {
  const random = Math.random() * 100;
  let cumulative = 0;
  
  for (const [name, scenario] of Object.entries(scenarios)) {
    cumulative += scenario.weight;
    if (random <= cumulative) {
      return { name, ...scenario };
    }
  }
  
  // Fallback to API calls
  return { name: 'api_calls', ...scenarios.api_calls };
}

// Main test function
export default function() {
  const scenario = selectScenario();
  const url = `${BASE_URL}${scenario.endpoint}`;
  
  // Record request
  requestCount.add(1);
  
  let response;
  const startTime = Date.now();
  
  if (scenario.method === 'POST') {
    response = http.post(url, JSON.stringify(scenario.payload), {
      headers: scenario.headers,
      timeout: '30s'
    });
  } else if (scenario.method === 'GET') {
    response = http.get(url, {
      headers: scenario.headers,
      timeout: '30s'
    });
  }
  
  const endTime = Date.now();
  const duration = endTime - startTime;
  
  // Record metrics
  responseTime.add(duration);
  
  // Check response
  const success = check(response, {
    'status is 200 or 201': (r) => r.status === 200 || r.status === 201,
    'response time < 2s': (r) => r.timings.duration < 2000,
    'response has body': (r) => r.body && r.body.length > 0,
  });
  
  // Check for quota exceeded
  const quotaExceeded = response.status === 429;
  if (quotaExceeded) {
    console.log(`Quota exceeded for scenario: ${scenario.name}`);
  }
  
  // Check for degrade mode indicators
  const degradeMode = response.headers['X-Degrade-Mode'];
  if (degradeMode) {
    console.log(`Degrade mode active: ${degradeMode}`);
  }
  
  // Record error rate
  errorRate.add(!success || response.status >= 400);
  
  // Log performance issues
  if (duration > 5000) {
    console.log(`Slow response: ${scenario.name} took ${duration}ms`);
  }
  
  // Sleep between requests
  sleep(Math.random() * 2 + 0.5); // 0.5-2.5 seconds
}

// Setup function
export function setup() {
  console.log('Starting load test...');
  console.log(`Base URL: ${BASE_URL}`);
  console.log(`Tenant ID: ${TENANT_ID}`);
  
  // Test basic connectivity
  const healthCheck = http.get(`${BASE_URL}/health`);
  if (healthCheck.status !== 200) {
    throw new Error(`Health check failed: ${healthCheck.status}`);
  }
  
  console.log('Health check passed');
  return { startTime: Date.now() };
}

// Teardown function
export function teardown(data) {
  const duration = Date.now() - data.startTime;
  console.log(`Load test completed in ${duration}ms`);
}

// Handle summary
export function handleSummary(data) {
  return {
    'load_test_results.json': JSON.stringify(data, null, 2),
    'load_test_summary.html': generateHtmlReport(data),
  };
}

// Generate HTML report
function generateHtmlReport(data) {
  const { metrics } = data;
  
  return `
<!DOCTYPE html>
<html>
<head>
    <title>Load Test Results</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .metric { margin: 10px 0; padding: 10px; border: 1px solid #ddd; }
        .success { background-color: #d4edda; }
        .warning { background-color: #fff3cd; }
        .error { background-color: #f8d7da; }
        table { width: 100%; border-collapse: collapse; }
        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }
        th { background-color: #f2f2f2; }
    </style>
</head>
<body>
    <h1>Load Test Results</h1>
    
    <div class="metric ${metrics.http_req_failed.values.rate < 0.1 ? 'success' : 'error'}">
        <h3>Error Rate</h3>
        <p>HTTP Request Failed Rate: ${(metrics.http_req_failed.values.rate * 100).toFixed(2)}%</p>
        <p>Custom Error Rate: ${(metrics.error_rate.values.rate * 100).toFixed(2)}%</p>
    </div>
    
    <div class="metric ${metrics.http_req_duration.values.p95 < 2000 ? 'success' : 'warning'}">
        <h3>Response Time</h3>
        <p>Average: ${metrics.http_req_duration.values.avg.toFixed(2)}ms</p>
        <p>P95: ${metrics.http_req_duration.values.p95.toFixed(2)}ms</p>
        <p>P99: ${metrics.http_req_duration.values.p99.toFixed(2)}ms</p>
    </div>
    
    <div class="metric">
        <h3>Request Count</h3>
        <p>Total Requests: ${metrics.http_reqs.values.count}</p>
        <p>Requests per Second: ${metrics.http_reqs.values.rate.toFixed(2)}</p>
    </div>
    
    <h2>Thresholds</h2>
    <table>
        <tr>
            <th>Threshold</th>
            <th>Expected</th>
            <th>Actual</th>
            <th>Status</th>
        </tr>
        <tr>
            <td>HTTP Request Duration P95</td>
            <td>&lt; 2000ms</td>
            <td>${metrics.http_req_duration.values.p95.toFixed(2)}ms</td>
            <td>${metrics.http_req_duration.values.p95 < 2000 ? '✅ PASS' : '❌ FAIL'}</td>
        </tr>
        <tr>
            <td>HTTP Request Failed Rate</td>
            <td>&lt; 10%</td>
            <td>${(metrics.http_req_failed.values.rate * 100).toFixed(2)}%</td>
            <td>${metrics.http_req_failed.values.rate < 0.1 ? '✅ PASS' : '❌ FAIL'}</td>
        </tr>
        <tr>
            <td>Custom Error Rate</td>
            <td>&lt; 5%</td>
            <td>${(metrics.error_rate.values.rate * 100).toFixed(2)}%</td>
            <td>${metrics.error_rate.values.rate < 0.05 ? '✅ PASS' : '❌ FAIL'}</td>
        </tr>
    </table>
</body>
</html>
  `;
}
