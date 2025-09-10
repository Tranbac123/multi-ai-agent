/**
 * K6 API Load Test for AIaaS Platform
 * 
 * This script tests REST API endpoints under various load conditions.
 */

import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const apiSuccessRate = new Rate('api_success_rate');
const apiResponseTime = new Trend('api_response_time');
const apiErrors = new Counter('api_errors');
const apiRequests = new Counter('api_requests');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 20 },   // Ramp up to 20 users
    { duration: '5m', target: 20 },   // Stay at 20 users
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 200 },  // Ramp up to 200 users
    { duration: '5m', target: 200 },  // Stay at 200 users
    { duration: '2m', target: 0 },    // Ramp down to 0 users
  ],
  thresholds: {
    api_success_rate: ['rate>0.95'],
    api_response_time: ['p(95)<1000'],
    api_errors: ['count<50'],
  },
};

// Test data
const tenants = [
  'tenant_001',
  'tenant_002', 
  'tenant_003',
  'tenant_004',
  'tenant_005'
];

const testMessages = [
  "Hello, I need help with my order",
  "What are your business hours?",
  "I want to return a product",
  "Can you help me track my shipment?",
  "I have a technical issue",
  "What payment methods do you accept?",
  "I need to update my account information",
  "Can you help me with billing?",
  "I want to cancel my subscription",
  "How do I contact customer support?"
];

// Base URL
const BASE_URL = 'http://localhost:8000';

export default function () {
  const tenantId = tenants[Math.floor(Math.random() * tenants.length)];
  const userId = `user_${Math.floor(Math.random() * 10000)}`;
  
  // Test different API endpoints
  const endpoint = Math.random();
  
  if (endpoint < 0.3) {
    testChatEndpoint(tenantId, userId);
  } else if (endpoint < 0.5) {
    testHealthEndpoint();
  } else if (endpoint < 0.7) {
    testAnalyticsEndpoint(tenantId);
  } else if (endpoint < 0.9) {
    testBillingEndpoint(tenantId);
  } else {
    testAuthEndpoint();
  }
  
  sleep(1);
}

function testChatEndpoint(tenantId, userId) {
  const url = `${BASE_URL}/chat/messages`;
  const payload = {
    message: testMessages[Math.floor(Math.random() * testMessages.length)],
    tenant_id: tenantId,
    user_id: userId,
    session_id: `session_${Math.floor(Math.random() * 100000)}`,
    metadata: {
      source: 'k6_test',
      timestamp: Date.now()
    }
  };
  
  const params = {
    headers: {
      'Content-Type': 'application/json',
      'X-Tenant-ID': tenantId,
      'X-User-ID': userId,
    },
  };
  
  const response = http.post(url, JSON.stringify(payload), params);
  
  apiRequests.add(1);
  apiResponseTime.add(response.timings.duration);
  
  const success = check(response, {
    'chat endpoint status is 200': (r) => r.status === 200,
    'chat endpoint has response body': (r) => r.body && r.body.length > 0,
    'chat endpoint response time < 2s': (r) => r.timings.duration < 2000,
  });
  
  apiSuccessRate.add(success);
  if (!success) {
    apiErrors.add(1);
  }
}

function testHealthEndpoint() {
  const url = `${BASE_URL}/healthz`;
  
  const response = http.get(url);
  
  apiRequests.add(1);
  apiResponseTime.add(response.timings.duration);
  
  const success = check(response, {
    'health endpoint status is 200': (r) => r.status === 200,
    'health endpoint response time < 100ms': (r) => r.timings.duration < 100,
  });
  
  apiSuccessRate.add(success);
  if (!success) {
    apiErrors.add(1);
  }
}

function testAnalyticsEndpoint(tenantId) {
  const url = `${BASE_URL}/analytics/kpi`;
  const params = {
    headers: {
      'X-Tenant-ID': tenantId,
    },
  };
  
  const response = http.get(url, params);
  
  apiRequests.add(1);
  apiResponseTime.add(response.timings.duration);
  
  const success = check(response, {
    'analytics endpoint status is 200': (r) => r.status === 200,
    'analytics endpoint response time < 1s': (r) => r.timings.duration < 1000,
  });
  
  apiSuccessRate.add(success);
  if (!success) {
    apiErrors.add(1);
  }
}

function testBillingEndpoint(tenantId) {
  const url = `${BASE_URL}/billing/usage`;
  const params = {
    headers: {
      'X-Tenant-ID': tenantId,
    },
  };
  
  const response = http.get(url, params);
  
  apiRequests.add(1);
  apiResponseTime.add(response.timings.duration);
  
  const success = check(response, {
    'billing endpoint status is 200': (r) => r.status === 200,
    'billing endpoint response time < 1s': (r) => r.timings.duration < 1000,
  });
  
  apiSuccessRate.add(success);
  if (!success) {
    apiErrors.add(1);
  }
}

function testAuthEndpoint() {
  const url = `${BASE_URL}/auth/status`;
  
  const response = http.get(url);
  
  apiRequests.add(1);
  apiResponseTime.add(response.timings.duration);
  
  const success = check(response, {
    'auth endpoint status is 200 or 401': (r) => r.status === 200 || r.status === 401,
    'auth endpoint response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  apiSuccessRate.add(success);
  if (!success) {
    apiErrors.add(1);
  }
}

export function handleSummary(data) {
  return {
    'load/api_test_results.json': JSON.stringify(data, null, 2),
  };
}
