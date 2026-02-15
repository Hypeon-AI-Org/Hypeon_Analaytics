# Changelog

## Unreleased

- **Schema:** Add raw_shopify_transactions, extend raw_shopify_orders (name, financial_status, net_revenue, etc.), add ingest_audit. Order reconciliation from transactions (sale − refund); net_revenue and audit rows.
- Monorepo skeleton and tooling.
- Shared package: DB session, enums, schemas, SQL models, Alembic migration.
- Minimal API: health, decisions, POST /run stub.
- CSV ingest into raw tables.
- Attribution package and attribution_events.
- MMM package and mmm_results.
- Metrics package and unified_daily_metrics.
- Rules engine and decision_store.
- API: full pipeline and endpoints.
- Scripts, Docker, integration test, CI, docs.
