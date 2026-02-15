#!/usr/bin/env bash
# Run product-engine pipeline: ingest -> attribution -> mmm -> metrics -> rules.
# Usage: ./scripts/run_product_engine.sh [--seed N]
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/hypeon}"
export DATA_RAW_DIR="${DATA_RAW_DIR:-$REPO_ROOT/data/raw}"
SEED=""
for arg in "$@"; do
  if [ "$arg" = "--seed" ]; then
    NEXT_IS_SEED=1
  elif [ -n "$NEXT_IS_SEED" ]; then
    SEED="$arg"
    NEXT_IS_SEED=""
  fi
done
export PYTHONPATH="$REPO_ROOT"
python -c "
from pathlib import Path
from datetime import date, timedelta
from packages.shared.src.db import get_session
from packages.shared.src.ingest import run_ingest
from packages.attribution.src.runner import run_attribution
from packages.mmm.src.runner import run_mmm
from packages.metrics.src.aggregator import run_metrics
from packages.rules_engine.src.rules import run_rules
import os
if '$SEED':
    import random
    random.seed(int('$SEED'))
run_id = 'run-' + ('$SEED' if '$SEED' else 'default')
data_dir = Path(os.environ.get('DATA_RAW_DIR', 'data/raw'))
with get_session() as session:
    run_ingest(session, data_dir=data_dir)
    start = date.today() - timedelta(days=90)
    end = date.today()
    run_attribution(session, run_id=run_id, start_date=start, end_date=end)
    run_mmm(session, run_id=run_id, start_date=start, end_date=end)
    run_metrics(session, start_date=start, end_date=end, attribution_run_id=run_id)
    run_rules(session, start_date=start, end_date=end, mmm_run_id=run_id)
print('Pipeline completed. run_id=', run_id)
"
