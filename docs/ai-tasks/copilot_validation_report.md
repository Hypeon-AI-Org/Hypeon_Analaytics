# Copilot vs BigQuery validation

Source: `copilot_answers.md`

## Extracted Copilot metrics (sample)

- **Q1**: {'total_revenue': 22754.37}
- **Q3**: {'sessions': '8439', 'add_to_cart_rate_pct': '3.58', 'total_revenue_usd': '10250.23'}

## Comparison results

- **Q6** (campaign_count): expected `58`, actual `108` — ✗ mismatch
  - Meta=67 Pinterest=41
- **Q1 (Pinterest order value)** (total_revenue_pinterest): expected `22754.37`, actual `3741571.16` — ✗ mismatch
  - Pinterest Total_order_value_Checkout sum

Summary: 0/2 checks matched.