#!/usr/bin/env bash
#
# Seed (or re-seed) demo data into the local database.
#
# This truncates all data tables and re-runs the seed script.
# Use with caution — this destroys existing data.
#
# Usage:
#   ./scripts/seed-local.sh
#   ./scripts/seed-local.sh --yes   # Skip confirmation prompt
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

RESET='\033[0m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'

log_info()  { echo -e "${BLUE}[INFO]${RESET}  $*"; }
log_ok()    { echo -e "${GREEN}[OK]${RESET}    $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${RESET}  $*"; }
log_error() { echo -e "${RED}[ERROR]${RESET} $*"; }

AUTO_YES=false
for arg in "$@"; do
  case "$arg" in
    --yes|-y) AUTO_YES=true ;;
  esac
done

cd "$PROJECT_ROOT/backend"
source .venv/bin/activate

set -a
source "$PROJECT_ROOT/.env.local"
set +a

echo ""
if [[ "$AUTO_YES" != true ]]; then
  log_warn "This will DELETE all existing data and re-seed with demo data."
  read -p "Are you sure? [y/N] " -n 1 -r
  echo ""

  if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    log_info "Aborted."
    exit 0
  fi
fi

log_info "Truncating data tables..."
python -c "
import asyncio
from sqlalchemy import text
from app.database import engine

async def clean():
    tables = [
        'human_escalations', 'validation_runs', 'validation_workflows',
        'commissions', 'escrows', 'buyer_profiles', 'brokerage_transactions',
        'brokerage_listings', 'token_retirements', 'token_listings',
        'carbon_credit_tokens', 'portfolio_holdings', 'corporate_portfolios',
        'data_subject_requests', 'consent_records', 'conflicts_of_interest',
        'breach_notifications', 'leads', 'enumerators', 'survey_responses',
        'support_tickets', 'whatsapp_conversations', 'audit_logs',
        'orchestrator_events', 'agent_runs', 'human_review_queue', 'reports',
        'calculation_runs', 'data_sources', 'file_uploads', 'projects',
        'developers', 'users', 'refresh_tokens', 'user_invites',
        'methodology_versions'
    ]
    for t in tables:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(f'TRUNCATE TABLE {t} CASCADE'))
            print(f'  Truncated {t}')
        except Exception as e:
            if 'does not exist' in str(e):
                pass
            else:
                print(f'  Error on {t}: {str(e)[:80]}')

asyncio.run(clean())
"

log_info "Seeding demo data..."
python -m scripts.seed_demo_data

log_ok "Done. Demo accounts (password: DemoPass123!):"
echo "  admin@carbonverify.demo      (Admin)"
echo "  operator@carbonverify.demo   (Operator)"
echo "  developer@carbonverify.demo  (Developer)"
echo "  viewer@carbonverify.demo     (Viewer)"
echo ""
