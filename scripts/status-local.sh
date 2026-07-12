#!/usr/bin/env bash
#
# Check the status of all CarbonVerify local development services.
#
# Usage:
#   ./scripts/status-local.sh
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PIDFILE="$PROJECT_ROOT/.local-dev.pids"
LOG_DIR="$PROJECT_ROOT/.local-logs"

# Colors
RESET='\033[0m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'

log_ok()    { echo -e "${GREEN}●${RESET} $*"; }
log_warn()  { echo -e "${YELLOW}●${RESET} $*"; }
log_error() { echo -e "${RED}●${RESET} $*"; }

cd "$PROJECT_ROOT"

echo ""
echo -e "${BLUE}Docker Infrastructure${RESET}"
echo "─────────────────────"

if docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" 2>/dev/null | grep -q "cv-"; then
  docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}" | grep "cv-" | while read line; do
    echo "  $line"
  done
else
  log_error "No cv-* containers running"
fi

echo ""
echo -e "${BLUE}Application Services${RESET}"
echo "────────────────────"

if [[ -f "$PIDFILE" ]]; then
  while IFS=: read -r name pid; do
    if kill -0 "$pid" 2>/dev/null; then
      log_ok "$name is running (PID $pid)"
    else
      log_error "$name is NOT running (PID $pid stale)"
    fi
  done < "$PIDFILE"
else
  log_warn "No PID file found"
fi

echo ""
echo -e "${BLUE}Ports${RESET}"
echo "─────"

for port in 5432 6380 8001 5173; do
  if lsof -Pi ":$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
    service=""
    case $port in
      5432) service="PostgreSQL" ;;
      6380) service="Redis" ;;
      8001) service="FastAPI" ;;
      5173) service="Vite Frontend" ;;
    esac
    log_ok "Port $port — $service"
  else
    log_error "Port $port — nothing listening"
  fi
done

echo ""
echo -e "${BLUE}Health Checks${RESET}"
echo "─────────────"

if curl -s http://localhost:8001/health/ >/dev/null 2>&1; then
  HEALTH=$(curl -s http://localhost:8001/health/ 2>/dev/null)
  log_ok "Backend health: $HEALTH"
else
  log_error "Backend health check failed"
fi

echo ""
echo -e "${BLUE}Recent Logs${RESET}"
echo "───────────"
if [[ -d "$LOG_DIR" ]]; then
  for log in backend frontend celery-worker celery-beat; do
    f="$LOG_DIR/$log.log"
    if [[ -f "$f" ]]; then
      size=$(du -h "$f" 2>/dev/null | cut -f1)
      last_line=$(tail -1 "$f" 2>/dev/null | cut -c1-80)
      echo "  $log.log ($size): $last_line"
    fi
  done
else
  echo "  No logs directory found"
fi

echo ""
