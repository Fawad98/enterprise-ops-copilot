"""Generate synthetic retail sales data with planted patterns for the Analytics agent.

Planted, objectively-checkable patterns (use these to write eval questions with known answers):
  1. SKU-0007 revenue collapses after 2026-05-01 (biggest single-SKU drop in May 2026).
  2. The 'West' region grows sharply starting 2026-04-01 (Q2 surge).
  3. 'Electronics' is the highest-revenue category overall.
Run:  python data/generate_data.py
Output: data/sales.csv
"""
import numpy as np
import pandas as pd

rng = np.random.default_rng(42)

products = [f"SKU-{i:04d}" for i in range(1, 51)]
# Deterministic category assignment so Electronics is well represented and SKU-0007 is Electronics.
categories_pool = ["Electronics", "Home", "Apparel", "Toys", "Grocery"]
cat_by_product = {}
for idx, p in enumerate(products):
    cat_by_product[p] = categories_pool[idx % len(categories_pool)]
cat_by_product["SKU-0007"] = "Electronics"  # ensure the collapsing SKU is Electronics

regions = ["North", "South", "East", "West"]

rows = []
for date in pd.date_range("2025-07-01", "2026-06-30", freq="D"):
    n_orders = int(rng.integers(80, 140))
    for _ in range(n_orders):
        product = products[int(rng.integers(0, 50))]
        category = cat_by_product[product]

        # PATTERN 1: SKU-0007 revenue collapses after 2026-05-01 (drop ~80% of its sales)
        if product == "SKU-0007" and date > pd.Timestamp("2026-05-01") and rng.random() < 0.8:
            continue

        # Electronics priced higher on average -> highest total revenue category (PATTERN 3)
        if category == "Electronics":
            price = float(rng.uniform(80, 500))
        elif category == "Grocery":
            price = float(rng.uniform(3, 40))
        else:
            price = float(rng.uniform(10, 200))

        qty = int(rng.integers(1, 5))

        # PATTERN 2: 'West' over-represented from 2026-04-01 (Q2 surge)
        if date >= pd.Timestamp("2026-04-01"):
            region = rng.choice(regions, p=[0.2, 0.2, 0.2, 0.4])
        else:
            region = rng.choice(regions, p=[0.25, 0.25, 0.25, 0.25])

        rows.append({
            "date": date.date(),
            "product": product,
            "category": category,
            "region": region,
            "unit_price": round(price, 2),
            "quantity": qty,
            "revenue": round(price * qty, 2),
        })

df = pd.DataFrame(rows)
df.to_csv("data/sales.csv", index=False)
print(f"Wrote data/sales.csv with {len(df):,} rows "
      f"({df['date'].min()} to {df['date'].max()})")

# --- Verify the planted patterns so you KNOW the ground truth for evals ---
d = df.copy()
d["date"] = pd.to_datetime(d["date"])
may = d[(d["date"] >= "2026-05-01") & (d["date"] <= "2026-05-31")]
apr = d[(d["date"] >= "2026-04-01") & (d["date"] <= "2026-04-30")]
print("\n--- GROUND TRUTH (for your eval dataset) ---")
print("Top category by total revenue:",
      d.groupby("category")["revenue"].sum().idxmax())
sku_apr = apr.groupby("product")["revenue"].sum()
sku_may = may.groupby("product")["revenue"].sum()
drop = (sku_apr - sku_may).sort_values(ascending=False)
print("Biggest revenue drop Apr->May (top 3):")
print(drop.head(3).round(0).to_string())
print("West region share before Apr 2026:",
      round((d[d['date'] < '2026-04-01']['region'].value_counts(normalize=True)['West']) * 100, 1), "%")
print("West region share from Apr 2026:",
      round((d[d['date'] >= '2026-04-01']['region'].value_counts(normalize=True)['West']) * 100, 1), "%")
