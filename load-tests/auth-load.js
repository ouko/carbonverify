/**
 * k6 load test: Authentication endpoints
 * Tests login, refresh, and authenticated API access under load.
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Rate, Trend } from 'k6/metrics';
import { BASE_URL, THRESHOLDS, STRESS_STAGES, defaultHeaders, checkResponse } from './k6-config.js';

// Custom metrics
const loginErrorRate = new Rate('login_errors');
const refreshErrorRate = new Rate('refresh_errors');
const loginDuration = new Trend('login_duration');
const apiDuration = new Trend('authenticated_api_duration');

export const options = {
  stages: STRESS_STAGES,
  thresholds: THRESHOLDS,
};

// Test user credentials (create these in the test DB before running)
const TEST_USERS = [
  { email: 'loadtest1@carbonverify.io', password: 'LoadTest123!' },
  { email: 'loadtest2@carbonverify.io', password: 'LoadTest123!' },
  { email: 'loadtest3@carbonverify.io', password: 'LoadTest123!' },
];

export function setup() {
  // Verify API is reachable
  const res = http.get(`${BASE_URL}/health`);
  if (res.status !== 200) {
    throw new Error(`API not ready: ${res.status}`);
  }
  return { baseUrl: BASE_URL };
}

export default function (data) {
  const user = TEST_USERS[__VU % TEST_USERS.length];

  group('Login', () => {
    const loginRes = http.post(
      `${BASE_URL}/auth/login`,
      JSON.stringify({
        email: user.email,
        password: user.password,
      }),
      { headers: defaultHeaders() }
    );

    loginDuration.add(loginRes.timings.duration);
    const loginSuccess = check(loginRes, checkResponse(loginRes, 200, {
      'has access_token': (r) => r.json('access_token') !== undefined,
    }));
    loginErrorRate.add(!loginSuccess);

    if (loginSuccess) {
      const accessToken = loginRes.json('access_token');

      group('Authenticated API Calls', () => {
        // Dashboard data
        const dashboardRes = http.get(`${BASE_URL}/projects`, {
          headers: defaultHeaders(accessToken),
        });
        apiDuration.add(dashboardRes.timings.duration);
        check(dashboardRes, {
          'projects status 200': (r) => r.status === 200,
        });

        // Leads list
        const leadsRes = http.get(`${BASE_URL}/leads`, {
          headers: defaultHeaders(accessToken),
        });
        apiDuration.add(leadsRes.timings.duration);
        check(leadsRes, {
          'leads status 200': (r) => r.status === 200,
        });

        // Refresh token
        const refreshRes = http.post(
          `${BASE_URL}/auth/refresh`,
          null,
          { headers: defaultHeaders() }
        );
        const refreshSuccess = check(refreshRes, {
          'refresh status 200 or 401': (r) => r.status === 200 || r.status === 401,
        });
        refreshErrorRate.add(!refreshSuccess);
      });
    }
  });

  sleep(1);
}

export function teardown(data) {
  console.log('Load test complete');
}
