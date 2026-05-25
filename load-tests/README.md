# Load Testing with k6

## Prerequisites

```bash
# Install k6
brew install k6          # macOS
# or
sudo apt-get install k6  # Ubuntu/Debian
```

## Quick Start

### 1. Create test users

Before running auth tests, create test users in the database:

```sql
INSERT INTO users (email, name, role, hashed_password, mfa_enabled)
VALUES
  ('loadtest1@carbonverify.io', 'Load Test 1', 'viewer', '$2b$12$...hash...', false),
  ('loadtest2@carbonverify.io', 'Load Test 2', 'viewer', '$2b$12$...hash...', false),
  ('loadtest3@carbonverify.io', 'Load Test 3', 'viewer', '$2b$12$...hash...', false);
```

Generate a test JWT token for read-only tests:
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"loadtest1@carbonverify.io","password":"LoadTest123!"}'
```

### 2. Run tests

```bash
# Auth endpoint stress test (login + API calls)
k6 run --env BASE_URL=http://localhost:8000 load-tests/auth-load.js

# Read API soak test (sustained load)
k6 run --env BASE_URL=http://localhost:8000 --env TEST_TOKEN=eyJhbG... load-tests/api-load.js

# File upload test
k6 run --env BASE_URL=http://localhost:8000 --env TEST_TOKEN=eyJhbG... load-tests/upload-load.js
```

### 3. Run on Grafana Cloud (optional)

```bash
k6 cloud load-tests/api-load.js
```

## Test Scenarios

| File | Purpose | Duration | Max VUs |
|------|---------|----------|---------|
| `auth-load.js` | Login + authenticated API stress | ~16 min | 200 |
| `api-load.js` | Read endpoint soak test | ~40 min | 50 |
| `upload-load.js` | Multipart upload test | ~5 min | 10 |

## Interpreting Results

**Pass criteria for production readiness:**
- p95 response time < 500ms for reads, < 2000ms for uploads
- Error rate < 1%
- No memory leaks over soak test duration
- Database connection pool not exhausted

## CI Integration

Add to GitHub Actions for nightly load tests:

```yaml
- name: Run k6 load tests
  uses: grafana/k6-action@v0.3.1
  with:
    filename: load-tests/api-load.js
    flags: --env BASE_URL=https://staging.carbonverify.io
```
