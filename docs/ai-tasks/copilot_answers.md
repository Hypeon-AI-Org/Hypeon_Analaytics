# Copilot answers

Org: org_test | API: http://localhost:8001

---

## Q1: Top 10 product IDs driving 50% of revenue — pareto/cumulative revenue ranking


I couldn't find relevant data for that question. Queries tried: WITH revenue_by_product AS (
  SELECT
    item_id,
    SUM(item_revenue_in_usd) AS total_revenue
  FROM (
    SELECT item_id, item_revenue_in_usd
    FROM `braided-verve-459208-i6.analytics_444259275.events_20260224`
    WHERE item_revenue_in_usd > 0
    UNION ALL
    SELECT item_id, item_revenue_in_usd
    FROM `braided-verve-459208-i6.analytics_444259275.events_20260225`
    WHERE item_revenue_in_usd > 0
    UNION ALL
    SELECT item_id, item_revenue_in_usd
    FROM `braided-verve-459208-i6.an.... Try rephrasing or ask about a different metric (e.g. revenue by product, top channels, ROAS).


---


## Q2: High volume vs high profit products — units sold vs revenue per order, two-axis sort


## Summary

**High-volume products** are dominated by William Morris wallpapers, with the top item selling 14 units and generating $1,494 in revenue. **High-profit products** show strong revenue per order ($1,494–$618), but many are single-order sales. The dataset contains 117 products; top performers below.

---

## Top Products by Volume (Units Sold)

| Item Name | Brand | Units Sold | Total Orders | Revenue per Order | Revenue per Unit |
|-----------|-------|------------|--------------|-------------------|------------------|
| Fruit Bayleaf/Russet - 217087 | William Morris | 14 | 1 | $1,493.78 | $106.70 |
| Scroll Thyme/Pear - 210365 | William Morris | 10 | 1 | $954.55 | $95.46 |
| Willow Boughs Thyme/Wedgwood - 217556 | Morris & Co | 7 | 1 | $866.08 | $123.73 |
| Savannah - 6939 | Boråstapeter | 6 | 2 | $175.18 | $58.39 |
| Rose Garden - 6928 | Boråstapeter | 5 | 1 | $291.97 | $58.39 |

---

## Key Insights

- **Volume leaders** are premium wallpapers with high unit prices ($95–$154 per unit)
- **Profit concentration**: Top 5 products account for 46 units sold and $3,956 in revenue
- **Order frequency**: Most high-volume items come from single large orders; only Savannah (6939) has repeat orders (2 orders, 6 units)
- **Price range**: Revenue per unit spans $4.32 (samples) to $154.55 (premium wallpaper)


*Data: 117 rows*


---


## Q3: New product launch performance — sessions, add-to-cart rate, revenue vs existing catalogue


## Summary

The new product launch generated **8,438 sessions** over the past 30 days with a **2.7% add-to-cart rate** and **$10,250.23 in revenue**.

## Key Metrics

| Metric | Value |
|--------|-------|
| Sessions | 8,438 |
| Add-to-Cart Rate | 2.7% |
| Total Revenue | $10,250.23 |

---

**Note:** This result shows new product performance only. To compare against your existing catalogue, please run a similar query filtered for existing products or request a side-by-side comparison query.


*Data: 1 rows*


---


## Q4: Products that spiked in last 14 days vs 14 days before — period-over-period delta

**Error:** ("Connection broken: ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host', None, 10054, None)", ConnectionResetError(10054, 'An existing connection was forcibly closed by the remote host', None, 10054, None))


---


## Q5: Which two products are most often bought together? — basket analysis, co-purchase pairs

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q6: True last-click ROAS vs what Google/Meta claim — the double-counting reality check

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q7: Which channels actually bring new customers vs recycled buyers — is_new_customer by channel

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q8: Most common channel path before first purchase — multi-touch journey mapping

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q9: Days from first visit to first purchase by channel — time lag analysis

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q10: Which Google campaigns to scale vs pause right now — campaign-level ROAS with threshold flags

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q11: Which channel acquires customers with the highest 90-day LTV — not first order, total 90-day spend

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q12: Repeat purchase rate + what did they first buy — cohort repurchase analysis

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q13: Customers who used to buy every 3–4 weeks but went quiet 45–90 days ago — churn risk list

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q14: Profile of the top 10% spenders — channel, first product, purchase frequency

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q15: Top 5 cities by revenue vs cities with traffic but no conversions — geo funnel gap

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q16: Countries adding to cart but abandoning checkout — signals friction or shipping/pricing issues

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q17: Mobile vs desktop conversion rate gap — confirm the suspicion most founders have

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q18: Which landing pages generate revenue, not just traffic — entry page → order attribution

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---


## Q19: Where exactly do people drop off in checkout — paid vs organic — funnel step comparison

**Error:** HTTPConnectionPool(host='localhost', port=8001): Max retries exceeded with url: /api/v1/copilot/chat/stream (Caused by NewConnectionError("HTTPConnection(host='localhost', port=8001): Failed to establish a new connection: [WinError 10061] No connection could be made because the target machine actively refused it"))


---

