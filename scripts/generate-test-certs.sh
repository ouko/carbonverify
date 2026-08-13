#!/usr/bin/env bash
# Generate self-signed certificates for test-server deployments.
# Production should use real Let's Encrypt certs instead.
set -euo pipefail

SERVER_NAME="${SERVER_NAME:-carbonverify.space}"
SERVER_IP="${1:-}"
CERT_DIR="/etc/letsencrypt/live/$SERVER_NAME"
mkdir -p "$CERT_DIR"

if [[ -f "$CERT_DIR/fullchain.pem" && -f "$CERT_DIR/privkey.pem" ]]; then
  echo "Certificates already exist at $CERT_DIR"
  exit 0
fi

SAN="DNS:$SERVER_NAME"
if [[ -n "$SERVER_IP" ]]; then
  SAN="${SAN},IP:${SERVER_IP}"
fi

echo "Generating self-signed certificate for $SERVER_NAME (SAN: $SAN)..."
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout "$CERT_DIR/privkey.pem" \
  -out "$CERT_DIR/fullchain.pem" \
  -subj "/CN=$SERVER_NAME" \
  -addext "subjectAltName=$SAN"

echo "Done. Certificates written to $CERT_DIR"
