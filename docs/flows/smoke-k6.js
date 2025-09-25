import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate } from 'k6/metrics';

// Custom metrics
const errorRate = new Rate('errors');

// Configuration
export const options = {
  stages: [
    { duration: '30s', target: 5 }, // Ramp up to 5 users
    { duration: '1m', target: 5 },  // Stay at 5 users
    { duration: '30s', target: 0 }, // Ramp down to 0 users
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // 95% of requests must complete below 2s
    http_req_failed: ['rate<0.1'],     // Error rate must be below 10%
    errors: ['rate<0.1'],              // Custom error rate must be below 10%
  },
};

// Base URLs
const BASE_URL = 'http://localhost';
const API_GATEWAY_URL = `${BASE_URL}:8000`;
const MODEL_GATEWAY_URL = `${BASE_URL}:8080`;
const TOOLS_SERVICE_URL = `${BASE_URL}:8082`;
const RETRIEVAL_SERVICE_URL = `${BASE_URL}:8081`;
const ROUTER_SERVICE_URL = `${BASE_URL}:8083`;

// Test data
const testQueries = [
  'What is the weather like today?',
  'Tell me about artificial intelligence',
  'How does machine learning work?',
  'What are the latest technology trends?',
  'Explain quantum computing in simple terms',
];

const testUrls = [
  'https://example.com',
  'https://news.ycombinator.com',
  'https://github.com',
];

// Helper function to get random item from array
function getRandomItem(array) {
  return array[Math.floor(Math.random() * array.length)];
}

// Helper function to generate session ID
function generateSessionId() {
  return `sess_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
}

export default function () {
  const sessionId = generateSessionId();
  const tenantId = 'tenant_123';
  
  // Test 1: API Gateway Health Check
  const healthCheck = http.get(`${API_GATEWAY_URL}/healthz`);
  const healthCheckPassed = check(healthCheck, {
    'API Gateway health check status is 200': (r) => r.status === 200,
    'API Gateway health check response time < 500ms': (r) => r.timings.duration < 500,
    'API Gateway health check contains status': (r) => r.json('status') === 'healthy',
  });
  errorRate.add(!healthCheckPassed);
  
  if (!healthCheckPassed) {
    console.error('API Gateway health check failed:', healthCheck.status, healthCheck.body);
  }
  
  sleep(0.1);
  
  // Test 2: API Gateway Root Endpoint
  const rootCheck = http.get(`${API_GATEWAY_URL}/`);
  const rootCheckPassed = check(rootCheck, {
    'API Gateway root status is 200': (r) => r.status === 200,
    'API Gateway root contains message': (r) => r.json('message') === 'API Gateway',
  });
  errorRate.add(!rootCheckPassed);
  
  sleep(0.1);
  
  // Test 3: Ask Question (Main Chat Flow)
  const query = getRandomItem(testQueries);
  const askPayload = JSON.stringify({
    query: query,
    session_id: sessionId,
  });
  
  const askHeaders = {
    'Content-Type': 'application/json',
    'X-Tenant-Id': tenantId,
    'X-Request-Id': `req_${Date.now()}`,
  };
  
  const askResponse = http.post(`${API_GATEWAY_URL}/ask`, askPayload, { headers: askHeaders });
  const askPassed = check(askResponse, {
    'Ask endpoint status is 200': (r) => r.status === 200,
    'Ask endpoint response time < 10s': (r) => r.timings.duration < 10000,
    'Ask endpoint contains answer': (r) => r.json('answer') && r.json('answer').length > 0,
    'Ask endpoint contains citations': (r) => Array.isArray(r.json('citations')),
    'Ask endpoint contains trace': (r) => Array.isArray(r.json('trace')),
  });
  errorRate.add(!askPassed);
  
  if (!askPassed) {
    console.error('Ask endpoint failed:', askResponse.status, askResponse.body);
  }
  
  sleep(0.5);
  
  // Test 4: Model Gateway Health Check
  const modelHealthCheck = http.get(`${MODEL_GATEWAY_URL}/healthz`);
  const modelHealthPassed = check(modelHealthCheck, {
    'Model Gateway health check status is 200': (r) => r.status === 200,
    'Model Gateway health check response time < 500ms': (r) => r.timings.duration < 500,
  });
  errorRate.add(!modelHealthPassed);
  
  sleep(0.1);
  
  // Test 5: Tools Service Health Check
  const toolsHealthCheck = http.get(`${TOOLS_SERVICE_URL}/healthz`);
  const toolsHealthPassed = check(toolsHealthCheck, {
    'Tools Service health check status is 200': (r) => r.status === 200,
    'Tools Service health check response time < 500ms': (r) => r.timings.duration < 500,
  });
  errorRate.add(!toolsHealthPassed);
  
  sleep(0.1);
  
  // Test 6: Tools Service - List Tools
  const listToolsResponse = http.get(`${TOOLS_SERVICE_URL}/v1/tools`);
  const listToolsPassed = check(listToolsResponse, {
    'List tools status is 200': (r) => r.status === 200,
    'List tools contains tools array': (r) => Array.isArray(r.json('tools')),
    'List tools contains web_search tool': (r) => {
      const tools = r.json('tools');
      return tools.some(tool => tool.name === 'web_search');
    },
  });
  errorRate.add(!listToolsPassed);
  
  sleep(0.1);
  
  // Test 7: Tools Service - Execute Web Search
  const webSearchPayload = JSON.stringify({
    name: 'web_search',
    args: {
      query: 'latest AI news 2024',
    },
  });
  
  const webSearchResponse = http.post(`${TOOLS_SERVICE_URL}/v1/tools/exec`, webSearchPayload, {
    headers: { 'Content-Type': 'application/json' },
  });
  const webSearchPassed = check(webSearchResponse, {
    'Web search status is 200': (r) => r.status === 200,
    'Web search response time < 15s': (r) => r.timings.duration < 15000,
    'Web search success is true': (r) => r.json('success') === true,
    'Web search contains output': (r) => r.json('output') && r.json('output').length > 0,
  });
  errorRate.add(!webSearchPassed);
  
  if (!webSearchPassed) {
    console.error('Web search failed:', webSearchResponse.status, webSearchResponse.body);
  }
  
  sleep(0.5);
  
  // Test 8: Tools Service - Execute Echo Tool
  const echoPayload = JSON.stringify({
    name: 'echo',
    args: {
      text: 'Hello from k6 smoke test!',
    },
  });
  
  const echoResponse = http.post(`${TOOLS_SERVICE_URL}/v1/tools/exec`, echoPayload, {
    headers: { 'Content-Type': 'application/json' },
  });
  const echoPassed = check(echoResponse, {
    'Echo tool status is 200': (r) => r.status === 200,
    'Echo tool response time < 1s': (r) => r.timings.duration < 1000,
    'Echo tool success is true': (r) => r.json('success') === true,
    'Echo tool output matches input': (r) => r.json('output') === 'Hello from k6 smoke test!',
  });
  errorRate.add(!echoPassed);
  
  sleep(0.1);
  
  // Test 9: Retrieval Service Health Check
  const retrievalHealthCheck = http.get(`${RETRIEVAL_SERVICE_URL}/healthz`);
  const retrievalHealthPassed = check(retrievalHealthCheck, {
    'Retrieval Service health check status is 200': (r) => r.status === 200,
    'Retrieval Service health check response time < 500ms': (r) => r.timings.duration < 500,
  });
  errorRate.add(!retrievalHealthPassed);
  
  sleep(0.1);
  
  // Test 10: Router Service Health Check
  const routerHealthCheck = http.get(`${ROUTER_SERVICE_URL}/healthz`);
  const routerHealthPassed = check(routerHealthCheck, {
    'Router Service health check status is 200': (r) => r.status === 200,
    'Router Service health check response time < 500ms': (r) => r.timings.duration < 500,
  });
  errorRate.add(!routerHealthPassed);
  
  sleep(0.1);
  
  // Test 11: Router Service - Route Request
  const routePayload = JSON.stringify({
    query: 'Find all documents about Q4 financial performance and summarize the key metrics',
    context: {
      user_id: 'user_123',
      session_id: sessionId,
    },
  });
  
  const routeHeaders = {
    'Content-Type': 'application/json',
    'X-Tenant-Id': tenantId,
  };
  
  const routeResponse = http.post(`${ROUTER_SERVICE_URL}/route`, routePayload, { headers: routeHeaders });
  const routePassed = check(routeResponse, {
    'Router route status is 200': (r) => r.status === 200,
    'Router route response time < 2s': (r) => r.timings.duration < 2000,
    'Router route contains tier': (r) => r.json('tier') && r.json('tier').length > 0,
    'Router route contains confidence': (r) => typeof r.json('confidence') === 'number',
  });
  errorRate.add(!routePassed);
  
  sleep(0.2);
  
  // Test 12: Chat Completion API
  const chatPayload = JSON.stringify({
    messages: [
      {
        role: 'system',
        content: 'You are a helpful AI assistant.',
      },
      {
        role: 'user',
        content: 'Hello, how are you?',
      },
    ],
    model: 'gpt-4o-mini',
    temperature: 0.7,
    max_tokens: 100,
  });
  
  const chatResponse = http.post(`${API_GATEWAY_URL}/v1/chat`, chatPayload, {
    headers: { 'Content-Type': 'application/json' },
  });
  const chatPassed = check(chatResponse, {
    'Chat completion status is 200': (r) => r.status === 200,
    'Chat completion response time < 10s': (r) => r.timings.duration < 10000,
    'Chat completion contains content': (r) => r.json('content') && r.json('content').length > 0,
  });
  errorRate.add(!chatPassed);
  
  if (!chatPassed) {
    console.error('Chat completion failed:', chatResponse.status, chatResponse.body);
  }
  
  sleep(0.5);
}

export function handleSummary(data) {
  return {
    'smoke-test-summary.json': JSON.stringify({
      timestamp: new Date().toISOString(),
      test_duration: data.state.testRunDurationMs,
      total_requests: data.metrics.http_reqs.values.count,
      failed_requests: data.metrics.http_req_failed.values.count,
      avg_response_time: data.metrics.http_req_duration.values.avg,
      p95_response_time: data.metrics.http_req_duration.values['p(95)'],
      error_rate: data.metrics.errors.values.rate,
      thresholds: {
        'http_req_duration_p95': data.thresholds['http_req_duration']['p(95)<2000'] ? 'PASS' : 'FAIL',
        'http_req_failed_rate': data.thresholds['http_req_failed']['rate<0.1'] ? 'PASS' : 'FAIL',
        'errors_rate': data.thresholds['errors']['rate<0.1'] ? 'PASS' : 'FAIL',
      },
      services_tested: [
        'API Gateway',
        'Model Gateway', 
        'Tools Service',
        'Retrieval Service',
        'Router Service'
      ],
      test_scenarios: [
        'Health checks',
        'Main chat flow',
        'Web search integration',
        'Tool execution',
        'Request routing',
        'Chat completion'
      ]
    }, null, 2),
  };
}
