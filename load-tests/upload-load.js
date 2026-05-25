/**
 * k6 load test: File upload endpoint
 * Tests multipart upload with virus scanning under load.
 * WARNING: Use a small test file to avoid excessive bandwidth.
 */

import http from 'k6/http';
import { check, sleep, group } from 'k6';
import { Trend } from 'k6/metrics';
import { BASE_URL, THRESHOLDS, STRESS_STAGES } from './k6-config.js';

const uploadDuration = new Trend('upload_duration');

export const options = {
  stages: [
    { duration: '1m', target: 10 },
    { duration: '3m', target: 10 },
    { duration: '1m', target: 0 },
  ],
  thresholds: {
    http_req_duration: ['p(95)<2000'], // Uploads are slower
    http_req_failed: ['rate<0.05'],
  },
};

const TEST_TOKEN = __ENV.TEST_TOKEN || '';
const TEST_PROJECT_ID = __ENV.TEST_PROJECT_ID || '00000000-0000-0000-0000-000000000001';

// Small CSV test file (embedded as binary)
const TEST_FILE = open('./fixtures/test-upload.csv', 'b');

export default function () {
  if (!TEST_TOKEN) {
    console.log('SKIP: No TEST_TOKEN provided');
    sleep(1);
    return;
  }

  group('File Upload', () => {
    const data = {
      file: http.file(TEST_FILE, 'test-upload.csv', 'text/csv'),
      source_type: 'document',
    };

    const uploadRes = http.post(
      `${BASE_URL}/uploads/projects/${TEST_PROJECT_ID}/upload`,
      data,
      {
        headers: {
          Authorization: `Bearer ${TEST_TOKEN}`,
        },
      }
    );

    uploadDuration.add(uploadRes.timings.duration);
    check(uploadRes, {
      'upload status 200 or 201': (r) => r.status === 200 || r.status === 201,
      'upload response time < 2s': (r) => r.timings.duration < 2000,
    });
  });

  sleep(2);
}
