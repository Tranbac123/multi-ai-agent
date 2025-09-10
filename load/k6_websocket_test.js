/**
 * K6 WebSocket Load Test for AIaaS Platform
 * 
 * This script tests WebSocket connections and real-time chat functionality
 * under various load conditions.
 */

import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { Rate, Trend, Counter } from 'k6/metrics';

// Custom metrics
const wsConnectionRate = new Rate('ws_connection_success_rate');
const wsMessageRate = new Rate('ws_message_success_rate');
const wsConnectionDuration = new Trend('ws_connection_duration');
const wsMessageLatency = new Trend('ws_message_latency');
const wsErrors = new Counter('ws_errors');

// Test configuration
export const options = {
  stages: [
    { duration: '2m', target: 10 },   // Ramp up to 10 users
    { duration: '5m', target: 10 },   // Stay at 10 users
    { duration: '2m', target: 50 },   // Ramp up to 50 users
    { duration: '5m', target: 50 },   // Stay at 50 users
    { duration: '2m', target: 100 },  // Ramp up to 100 users
    { duration: '5m', target: 100 },  // Stay at 100 users
    { duration: '2m', target: 0 },    // Ramp down to 0 users
  ],
  thresholds: {
    ws_connection_success_rate: ['rate>0.95'],
    ws_message_success_rate: ['rate>0.90'],
    ws_connection_duration: ['p(95)<1000'],
    ws_message_latency: ['p(95)<500'],
    ws_errors: ['count<100'],
  },
};

// Test data
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

const tenants = [
  'tenant_001',
  'tenant_002', 
  'tenant_003',
  'tenant_004',
  'tenant_005'
];

export default function () {
  const tenantId = tenants[Math.floor(Math.random() * tenants.length)];
  const userId = `user_${Math.floor(Math.random() * 10000)}`;
  const sessionId = `session_${Math.floor(Math.random() * 100000)}`;
  
  const url = `ws://localhost:8000/ws/chat?tenant_id=${tenantId}&user_id=${userId}&session_id=${sessionId}`;
  
  const startTime = Date.now();
  
  const res = ws.connect(url, {}, function (socket) {
    const connectionDuration = Date.now() - startTime;
    wsConnectionDuration.add(connectionDuration);
    wsConnectionRate.add(1);
    
    // Send initial message
    const initialMessage = {
      type: 'user_message',
      content: testMessages[Math.floor(Math.random() * testMessages.length)],
      timestamp: Date.now(),
      metadata: {
        tenant_id: tenantId,
        user_id: userId,
        session_id: sessionId
      }
    };
    
    socket.send(JSON.stringify(initialMessage));
    
    // Listen for responses
    socket.on('message', function (data) {
      try {
        const message = JSON.parse(data);
        const messageLatency = Date.now() - startTime;
        wsMessageLatency.add(messageLatency);
        wsMessageRate.add(1);
        
        check(message, {
          'message has type': (msg) => msg.type !== undefined,
          'message has content': (msg) => msg.content !== undefined,
          'message has timestamp': (msg) => msg.timestamp !== undefined,
        });
        
        // Send follow-up message
        if (message.type === 'agent_response') {
          sleep(1);
          const followUpMessage = {
            type: 'user_message',
            content: testMessages[Math.floor(Math.random() * testMessages.length)],
            timestamp: Date.now(),
            metadata: {
              tenant_id: tenantId,
              user_id: userId,
              session_id: sessionId
            }
          };
          socket.send(JSON.stringify(followUpMessage));
        }
        
      } catch (e) {
        wsErrors.add(1);
        console.error('Error parsing message:', e);
      }
    });
    
    socket.on('error', function (e) {
      wsErrors.add(1);
      console.error('WebSocket error:', e);
    });
    
    socket.on('close', function () {
      wsConnectionRate.add(0);
    });
    
    // Keep connection alive for 30 seconds
    sleep(30);
    
    socket.close();
  });
  
  check(res, {
    'WebSocket connection established': (r) => r && r.status === 101,
  });
  
  if (!res || res.status !== 101) {
    wsConnectionRate.add(0);
    wsErrors.add(1);
  }
}

export function handleSummary(data) {
  return {
    'load/websocket_test_results.json': JSON.stringify(data, null, 2),
  };
}
