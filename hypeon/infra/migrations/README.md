# Alembic migrations (product-engine)

## Running migrations

From repo root (e.g. `hypeon/`):

```bash
export DATABASE_URL=postgresql://user:pass@host:5432/dbname
alembic -c infra/migrations/alembic.ini upgrade head
```

## Revision 003 — Shopify transactions, order columns, ingest_audit

- **raw_shopify_orders**: adds `name`, `closed_at`, `cancelled_at`, `financial_status`, `fulfillment_status`, `total_price`, `subtotal_price`, `total_tax`, `currency`, `source_name`, `line_items_json`, `customer_id`, `is_test`, `net_revenue`. All nullable for backward compatibility.
- **raw_shopify_transactions**: new table; `order_id` FK to `raw_shopify_orders.id`. Used to compute `net_revenue` (sale − refund) per order.
- **ingest_audit**: new table; one row per order after reconciliation (`order_id`, `computed_net_revenue`, `diff`, `note`).

### Rollback

`alembic downgrade 002` will drop `ingest_audit`, `raw_shopify_transactions`, and the new columns on `raw_shopify_orders`. Any application logic depending on `net_revenue` or transactions will break until re-migrated. Back up data before rolling back.
