/**
 * k6 load test: Core API endpoints (read-heavy)
 * Tests project listing, lead scraping, calculations under sustained load.
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Trend } from 'k6/metrics';
import { BASE_URL, THRESHOLDS, SOAK_STAGES, defaultHeaders } from './k6-config.js';

const projectListDuration = new Trend('project_list_duration');
const leadListDuration = new Trend('lead_list_duration');
const calculationDuration = new Trend('calculation_duration');

export const options = {
  stages: SOAK_STAGES,
  thresholds: THRESHOLDS,
};

// Static token for read-only endpoints (create a long-lived test token)
const TEST_TOKEN = __ENV.TEST_TOKEN || '';

export default function () {
  const headers = defaultHeaders(TEST_TOKEN);

  group('Public/Read Endpoints', () => {
    // Health check
    const healthRes = http.get(`${BASE_URL}/health`);
    check(healthRes, {
      'health status 200': (r) => r.status === 200,
    });

    // Metrics endpoint (Prometheus)
    const metricsRes = http.get(`${BASE_URL}/metrics`);
    check(metricsRes, {
      'metrics status 200': (r) => r.status === 200,
    });
  });

  if (TEST_TOKEN) {
    group('Authenticated Read Endpoints', () => {
      // Projects list
      const projectsRes = http.get(`${BASE_URL}/projects`, { headers });
      projectListDuration.add(projectsRes.timings.duration);
      check(projectsRes, {
        'projects status 200': (r) => r.status === 200,
        'projects response time < 300ms': (r) => r.timings.duration < 300,
      });

      // Leads list
      const leadsRes = http.get(`${BASE_URL}/leads`, { headers });
      leadListDuration.add(leadsRes.timings.duration);
      check(leadsRes, {
        'leads status 200': (r) => r.status === 200,
        'leads response time < 500ms': (r) => r.timings.duration < 500,
      });

      // Scraper health
      const scraperHealthRes = http.get(`${BASE_URL}/leads/scraper-health`, { headers });
      check(scraperHealthRes, {
        'scraper health status 200': (r) => r.status === 200,
      });
    });
  }

  sleep(Math.random() * 2 + 0.5); // 0.5-2.5s think time
}
