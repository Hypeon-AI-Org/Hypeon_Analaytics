#!/usr/bin/env bash
# Run Alembic migrations for product-engine DB.
set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"
export DATABASE_URL="${DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/hypeon}"
alembic -c infra/migrations/alembic.ini upgrade head
echo "Migrations complete."
