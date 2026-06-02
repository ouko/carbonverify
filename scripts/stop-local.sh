#!/usr/bin/env bash
#
# Stop all CarbonVerify local development services.
#
# Usage:
#   ./scripts/stop-local.sh           # Stop everything (app + infra)
#   ./scripts/stop-local.sh --app     # Stop only backend/frontend/celery
#   ./scripts/stop-local.sh --infra   # Stop only Docker infra
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
PIDFILE="$PROJECT_ROOT/.local-dev.pids"

# Colors
RESET='\033[0m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'

log_info()  { echo -e "${GREEN}[INFO]${RESET}  $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*"; }

cd "$PROJECT_ROOT"

STOP_INFRA=true
STOP_APP=true

for arg in "$@"; do
  case "$arg" in
    --infra) STOP_APP=false ;;
    --app)   STOP_INFRA=false ;;
    --help|-h)
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --app     Stop only backend/frontend/celery"
      echo "  --infra   Stop only Docker infrastructure (db + redis)"
      echo "  --help    Show this help"
      exit 0
      ;;
    *)
      log_error "Unknown argument: $arg"
      exit 1
      ;;
  esac
done

# ------------------------------------------------------------------
# Stop application services
# ------------------------------------------------------------------
if [[ "$STOP_APP" == true ]]; then
  if [[ -f "$PIDFILE" ]]; then
    log_info "Stopping application services..."
    while IFS=: read -r name pid; do
      if kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        # Give it a moment to shut down gracefully
        sleep 1
        if kill -0 "$pid" 2>/dev/null; then
          kill -9 "$pid" 2>/dev/null || true
        fi
        log_info "Stopped $name (PID $pid)"
      else
        log_warn "$name (PID $pid) was not running"
      fi
    done < "$PIDFILE"
    rm -f "$PIDFILE"
    log_info "Application services stopped"
  else
    log_warn "No PID file found — application services may not be running"
    # Attempt to find and kill by pattern as fallback
    log_info "Trying fallback process cleanup..."
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    pkill -f "vite" 2>/dev/null || true
    pkill -f "celery -A app.tasks.celery_app" 2>/dev/null || true
  fi
fi

# ------------------------------------------------------------------
# Stop Docker infrastructure
# ------------------------------------------------------------------
if [[ "$STOP_INFRA" == true ]]; then
  log_info "Stopping Docker infrastructure..."
  docker-compose -f docker-compose.yml -f docker-compose.local.yml down --volumes=false 2>/dev/null || true
  log_info "Infrastructure stopped"
fi

echo ""
log_info "All done."
