#!/usr/bin/env bash
# Deploy the consolidated CarbonVerify stack to the test server.
# Run from /opt/carbonverify on the test server as a user with docker and sudo access.
set -euo pipefail

REPO_DIR="${REPO_DIR:-/opt/carbonverify}"
BRANCH="${BRANCH:-feature/validation-workflow-builder}"
SERVER_IP="${SERVER_IP:-}"

cd "$REPO_DIR"

echo "==> Pulling latest $BRANCH"
git fetch origin
git checkout "$BRANCH"
git pull origin "$BRANCH"

echo "==> Ensuring SSL certificates exist"
if [[ -f /etc/letsencrypt/live/carbonverify.space/fullchain.pem && -f /etc/letsencrypt/live/carbonverify.space/privkey.pem ]]; then
  echo "    Real Let's Encrypt certs found."
else
  if [[ -z "$SERVER_IP" ]]; then
    echo "WARNING: No real certs and SERVER_IP not set. Generating cert without IP SAN."
  fi
  sudo bash scripts/generate-test-certs.sh "$SERVER_IP"
fi

echo "==> Stopping old containers (including orphans)"
docker compose -f docker-compose.yml -f docker-compose.production.yml down --remove-orphans

echo "==> Building and starting the full stack"
docker compose -f docker-compose.yml -f docker-compose.production.yml up --build -d

echo "==> Waiting for services to start"
sleep 10

echo "==> Health checks"
docker compose -f docker-compose.yml -f docker-compose.production.yml ps

echo "--- Backend health (HTTP) ---"
curl -fsS http://localhost:8000/health/ || echo "BACKEND HEALTH FAILED"

echo "--- Frontend via reverse proxy (HTTPS, self-signed cert OK) ---"
curl -fsSk https://localhost/health/ || echo "PROXY HEALTH FAILED"

echo "--- Frontend container direct (HTTP) ---"
curl -fsS http://localhost:8080/index.html || echo "FRONTEND DIRECT HEALTH FAILED"

echo "==> Done"
