# Integration Tests

This directory contains Postman/Newman collections for API integration testing.

## Setup

1. Export your Postman collection as `carbonverify-api.json`
2. Create environment files:
   - `staging-env.json` - Staging environment variables
   - `production-env.json` - Production environment variables

## Running Locally

```bash
npm install -g newman
newman run carbonverify-api.json -e staging-env.json
```

## CI/CD

Integration tests run automatically after staging deployment in the GitHub Actions pipeline.
