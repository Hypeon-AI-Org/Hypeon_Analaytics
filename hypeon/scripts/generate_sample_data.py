"""
Generate 90 days of realistic sample data for a brand: Meta/Google ads + Shopify orders.
Run from repo root: python scripts/generate_sample_data.py
Writes to data/raw/*.csv
"""
import csv
import random
from datetime import date, timedelta

random.seed(42)

START = date(2025, 1, 1)
DAYS = 90
END = START + timedelta(days=DAYS - 1)

# ---- Meta: 3 campaigns ----
META_CAMPAIGNS = [
    ("meta_br", "Brand Awareness"),
    ("meta_conv", "Conversion - Purchase"),
    ("meta_ret", "Retargeting - Cart"),
]
# Base daily spend per campaign (then add noise + weekly + trend)
META_BASE = {"meta_br": 80, "meta_conv": 200, "meta_ret": 120}


def meta_spend(d: date, cid: str, cname: str) -> tuple:
    base = META_BASE.get(cid, 100)
    day_idx = (d - START).days
    trend = 1.0 + 0.001 * day_idx  # slight upward trend
    weekly = 1.2 if d.weekday() < 5 else 0.85  # weekday vs weekend
    noise = random.gauss(1.0, 0.15)
    spend = max(10, round(base * trend * weekly * noise, 2))
    imp = int(spend * random.gauss(12, 2))
    clk = max(0, int(imp * random.gauss(0.02, 0.005)))
    return (d, cid, cname, spend, imp, clk)


# ---- Google: 2 campaigns ----
GOOGLE_CAMPAIGNS = [
    ("goog_search", "Search - Brand"),
    ("goog_pmax", "Performance Max"),
]
GOOGLE_BASE = {"goog_search": 90, "goog_pmax": 180}


def google_spend(d: date, cid: str, cname: str) -> tuple:
    base = GOOGLE_BASE.get(cid, 100)
    day_idx = (d - START).days
    trend = 1.0 + 0.0008 * day_idx
    weekly = 1.15 if d.weekday() < 5 else 0.9
    noise = random.gauss(1.0, 0.12)
    spend = max(10, round(base * trend * weekly * noise, 2))
    imp = int(spend * random.gauss(25, 4))
    clk = max(0, int(imp * random.gauss(0.015, 0.004)))
    return (d, cid, cname, spend, imp, clk)


# ---- Orders: revenue with lag vs spend ----
def gen_orders():
    # Precompute daily total spend (meta + google) for rough revenue correlation
    daily_spend = {}
    for d in (START + timedelta(days=i) for i in range(DAYS)):
        total = sum(META_BASE.values()) + sum(GOOGLE_BASE.values())
        daily_spend[d] = total * random.gauss(1.0, 0.1)
    orders = []
    order_id = 1
    for d in (START + timedelta(days=i) for i in range(DAYS)):
        # 5–25 orders per day, more when "spend" is higher
        base_orders = 8 + int(daily_spend[d] / 50)
        n_orders = max(2, min(30, int(random.gauss(base_orders, 4))))
        for _ in range(n_orders):
            # Revenue per order: mix of small and larger baskets
            if random.random() < 0.6:
                rev = round(random.gauss(45, 20), 2)
            else:
                rev = round(random.gauss(120, 50), 2)
            rev = max(10, rev)
            is_new = random.random() < 0.4
            name = f"#{1000 + order_id}"
            orders.append((f"ord_{order_id}", name, d, rev, is_new))
            order_id += 1
    return orders


def main():
    from pathlib import Path
    repo_root = Path(__file__).resolve().parent.parent
    out_dir = repo_root / "data" / "raw"
    out_dir.mkdir(parents=True, exist_ok=True)

    # Meta
    with open(out_dir / "meta_ads.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "campaign_id", "campaign_name", "spend", "impressions", "clicks"])
        for d in (START + timedelta(days=i) for i in range(DAYS)):
            for cid, cname in META_CAMPAIGNS:
                w.writerow(meta_spend(d, cid, cname))

    # Google
    with open(out_dir / "google_ads.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "campaign_id", "campaign_name", "spend", "impressions", "clicks"])
        for d in (START + timedelta(days=i) for i in range(DAYS)):
            for cid, cname in GOOGLE_CAMPAIGNS:
                w.writerow(google_spend(d, cid, cname))

    # Orders
    orders = gen_orders()
    with open(out_dir / "shopify_orders.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["order_id", "name", "order_date", "revenue", "is_new_customer"])
        for row in orders:
            w.writerow(row)

    print(f"Wrote meta_ads.csv, google_ads.csv, shopify_orders.csv to {out_dir!s}")
    print(f"Date range: {START} to {END}, {len(orders)} orders, Meta campaigns: {len(META_CAMPAIGNS)}, Google: {len(GOOGLE_CAMPAIGNS)}")


if __name__ == "__main__":
    main()
