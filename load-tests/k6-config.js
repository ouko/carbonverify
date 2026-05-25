/**
 * k6 load testing configuration for CarbonVerify.
 *
 * Usage:
 *   k6 run --env BASE_URL=https://api.carbonverify.io load-tests/auth-load.js
 *   k6 run --env BASE_URL=https://api.carbonverify.io load-tests/api-load.js
 *   k6 cloud load-tests/api-load.js  # Run on Grafana Cloud
 */

export const BASE_URL = __ENV.BASE_URL || 'http://localhost:8000';
export const FRONTEND_URL = __ENV.FRONTEND_URL || 'http://localhost:5173';

// Standard thresholds for production readiness
export const THRESHOLDS = {
  http_req_duration: ['p(95)<500', 'p(99)<1000'],  // 95% under 500ms, 99% under 1s
  http_req_failed: ['rate<0.01'],                   // <1% error rate
  http_reqs: ['rate>100'],                          // >100 RPS sustained
  iterations: ['rate>10'],                          // >10 iterations/sec per VU
};

// Load stages for stress test
export const STRESS_STAGES = [
  { duration: '2m', target: 50 },   // Ramp up to 50 VUs
  { duration: '5m', target: 50 },   // Sustain 50 VUs
  { duration: '2m', target: 100 },  // Ramp to 100 VUs
  { duration: '5m', target: 100 },  // Sustain 100 VUs
  { duration: '2m', target: 200 },  // Stress test: 200 VUs
  { duration: '2m', target: 0 },    // Ramp down
];

// Load stages for soak test (long-running stability)
export const SOAK_STAGES = [
  { duration: '5m', target: 50 },
  { duration: '30m', target: 50 },
  { duration: '5m', target: 0 },
];

// Load stages for spike test
export const SPIKE_STAGES = [
  { duration: '1m', target: 10 },
  { duration: '30s', target: 200 },
  { duration: '1m', target: 200 },
  { duration: '30s', target: 10 },
  { duration: '2m', target: 10 },
];

// Helper to set default headers
export function defaultHeaders(token) {
  const headers = {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

// Helper to check response
export function checkResponse(res, expectedStatus, checks) {
  const result = checks || {};
  result[`status is ${expectedStatus}`] = (r) => r.status === expectedStatus;
  result['response time < 500ms'] = (r) => r.timings.duration < 500;
  return result;
}
